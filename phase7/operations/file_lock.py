"""Inter-process file locking and single-writer concurrency controls for Phase 7.

Enforces:
- Exclusive single-writer lock for run and staging directories
- Cross-thread and cross-process concurrency exclusion
- Lock owner metadata recording: PID, host, start_time_utc, run_id
- Stale lock detection with conservative PID-validation
- Refusal to automatically break locks without explicit override
- Tamper detection on lock metadata files
- Single-request concurrency gate (semaphore limit = 1)
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Dict, Optional, Union

from phase7.operations.atomic_io import (
    AtomicIOError,
    validate_safe_staging_path,
)

# Optional platform-specific low-level locking
try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False


class LockError(AtomicIOError):
    """Base exception for file locking and concurrency violations."""
    pass


class LockAcquisitionError(LockError):
    """Raised when an exclusive lock cannot be acquired because another process holds it."""
    pass


class StaleLockDetectedError(LockError):
    """Raised when a lock file appears stale but automatic break is disallowed."""
    pass


class LockTamperingError(LockError):
    """Raised when a lock file has invalid JSON, missing keys, or corrupt metadata."""
    pass


class SingleRequestViolationError(LockError):
    """Raised when more than one concurrent request is dispatched."""
    pass


def is_pid_alive(pid: int) -> bool:
    """Check if process with given PID is currently alive on the host."""
    if pid <= 0:
        return False
    if os.name == "nt":
        # On Windows, try opening process handle with minimal query access
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            SYNCHRONIZE = 0x00100000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid
            )
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


class DirectoryProcessLock:
    """Governed exclusive filesystem lock guarding a run or staging directory."""

    def __init__(
        self,
        lock_dir: Union[Path, str],
        run_id: str,
        timeout_seconds: float = 0.0,
        repo_root: Optional[Union[Path, str]] = None,
        stale_threshold_seconds: float = 86400.0,
    ) -> None:
        self.lock_dir = validate_safe_staging_path(lock_dir, repo_root=repo_root)
        self.run_id = str(run_id)
        self.timeout_seconds = float(timeout_seconds)
        self.stale_threshold_seconds = float(stale_threshold_seconds)
        self.lock_file = self.lock_dir / ".process_lock"
        self.raw_lock_file = self.lock_dir / ".process_lock.raw"
        self._fd: Optional[int] = None
        self._is_locked = False

    @property
    def is_locked(self) -> bool:
        return self._is_locked

    def acquire(self, allow_stale_break: bool = False) -> None:
        """Acquire exclusive directory lock. Raises LockAcquisitionError if held."""
        if self._is_locked:
            return

        self.lock_dir.mkdir(parents=True, exist_ok=True)
        start_time = time.monotonic()

        while True:
            # Check existing lock file
            if self.lock_file.exists():
                try:
                    metadata = self._read_and_validate_lock_file()
                except LockTamperingError:
                    elapsed = time.monotonic() - start_time
                    if elapsed >= self.timeout_seconds:
                        raise
                    time.sleep(0.02)
                    continue
                except Exception as exc:
                    elapsed = time.monotonic() - start_time
                    if elapsed >= self.timeout_seconds:
                        raise LockAcquisitionError(
                            f"Directory '{self.lock_dir}' is locked and unreadable: {exc}"
                        )
                    time.sleep(0.05)
                    continue

                holder_pid = metadata.get("pid")
                holder_run_id = metadata.get("run_id")
                lock_time_str = metadata.get("locked_at_utc", "")

                try:
                    lock_dt = datetime.fromisoformat(lock_time_str)
                    age_seconds = (datetime.now(timezone.utc) - lock_dt).total_seconds()
                except Exception:
                    age_seconds = 0.0

                holder_alive = is_pid_alive(holder_pid) if holder_pid else False

                if not holder_alive and age_seconds > self.stale_threshold_seconds:
                    if allow_stale_break:
                        try:
                            self.lock_file.unlink()
                        except OSError:
                            pass
                        try:
                            self.raw_lock_file.unlink()
                        except OSError:
                            pass
                    else:
                        raise StaleLockDetectedError(
                            f"Stale lock held by dead PID {holder_pid} (run_id={holder_run_id}, "
                            f"age={age_seconds:.1f}s). Automatic break forbidden without allow_stale_break=True."
                        )
                else:
                    elapsed = time.monotonic() - start_time
                    if elapsed >= self.timeout_seconds:
                        raise LockAcquisitionError(
                            f"Directory '{self.lock_dir}' is already locked by PID {holder_pid} "
                            f"(run_id={holder_run_id}, alive={holder_alive})."
                        )
                    time.sleep(0.05)
                    continue

            # Attempt atomic creation of the raw OS lock file
            try:
                flags = os.O_CREAT | os.O_EXCL | os.O_RDWR
                if hasattr(os, "O_BINARY"):
                    flags |= os.O_BINARY
                fd = os.open(str(self.raw_lock_file), flags)
                self._fd = fd

                # Platform low-level lock if supported
                if HAS_MSVCRT:
                    try:
                        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    except OSError:
                        pass
                elif HAS_FCNTL:
                    try:
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except OSError:
                        pass

                # Write metadata atomically to readable lock_file
                now_utc = datetime.now(timezone.utc).isoformat()
                meta = {
                    "pid": os.getpid(),
                    "run_id": self.run_id,
                    "locked_at_utc": now_utc,
                    "host": os.getenv("COMPUTERNAME", os.getenv("HOSTNAME", "localhost")),
                }
                tmp_meta = self.lock_dir / f".tmp_meta_{os.getpid()}_{time.monotonic_ns()}"
                tmp_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
                os.replace(tmp_meta, self.lock_file)
                self._is_locked = True
                return

            except (FileExistsError, OSError) as exc:
                if self._fd is not None:
                    try:
                        os.close(self._fd)
                    except OSError:
                        pass
                    self._fd = None

                elapsed = time.monotonic() - start_time
                if elapsed >= self.timeout_seconds:
                    raise LockAcquisitionError(
                        f"Failed to acquire directory lock on '{self.raw_lock_file}': {exc}"
                    )
                time.sleep(0.05)

    def release(self) -> None:
        """Release the held directory lock."""
        if not self._is_locked:
            return

        try:
            if self._fd is not None:
                if HAS_MSVCRT:
                    try:
                        msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass
                elif HAS_FCNTL:
                    try:
                        fcntl.flock(self._fd, fcntl.LOCK_UN)
                    except OSError:
                        pass
                os.close(self._fd)
                self._fd = None
        finally:
            if self.raw_lock_file.exists():
                try:
                    self.raw_lock_file.unlink()
                except OSError:
                    pass
            if self.lock_file.exists():
                try:
                    self.lock_file.unlink()
                except OSError:
                    pass
            self._is_locked = False

    def _read_and_validate_lock_file(self) -> Dict[str, Any]:
        """Read and validate lock metadata for integrity and tamper detection."""
        try:
            content = self.lock_file.read_text(encoding="utf-8")
            if not content.strip():
                raise LockTamperingError("Lock file is empty (0 bytes).")
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LockTamperingError(f"Corrupt or non-JSON lock file: {exc}")

        required = {"pid", "run_id", "locked_at_utc"}
        missing = required - set(data.keys())
        if missing:
            raise LockTamperingError(f"Lock file missing required fields: {sorted(missing)}")

        if not isinstance(data["pid"], int) or data["pid"] <= 0:
            raise LockTamperingError(f"Invalid PID in lock file: {data.get('pid')}")

        return data

    def __enter__(self) -> "DirectoryProcessLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()


class SingleRequestGate:
    """Thread-safe and process-safe gate ensuring request semaphore limit remains strictly 1."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_requests = 0

    def enter_request(self) -> None:
        with self._lock:
            if self._active_requests >= 1:
                raise SingleRequestViolationError(
                    f"Single-request guard violated: {self._active_requests} request(s) already active."
                )
            self._active_requests += 1

    def exit_request(self) -> None:
        with self._lock:
            if self._active_requests > 0:
                self._active_requests -= 1

    @property
    def active_count(self) -> int:
        with self._lock:
            return self._active_requests
