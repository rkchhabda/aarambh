"""Single-instance application lock for Phase 7 Offline Operator Application.

Milestone 4.12: Ensures that only a single instance of the operator application
can run concurrently, preventing race conditions or concurrent access.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from phase7.operations.file_lock import (
    DirectoryProcessLock,
    is_pid_alive,
    LockAcquisitionError,
    LockError,
)

DEFAULT_OPERATOR_LOCK_DIR = Path(r"C:\Users\r_chh\gaurvideep_phase7_staging\nse500")


class SingleInstanceLockError(RuntimeError):
    """Raised when another instance of the operator application is already running."""
    pass


class SingleInstanceLock:
    """Manages an exclusive application-level single-instance lock."""

    def __init__(
        self,
        lock_dir: Optional[Path] = None,
        allow_stale_break: bool = False,
    ) -> None:
        self.lock_dir = Path(lock_dir) if lock_dir else DEFAULT_OPERATOR_LOCK_DIR
        self.allow_stale_break = allow_stale_break
        self._lock_held: bool = False
        self._internal_lock: Optional[DirectoryProcessLock] = None

    @property
    def is_locked(self) -> bool:
        return self._lock_held

    def acquire(self) -> None:
        """Acquire the single-instance lock or raise SingleInstanceLockError."""
        if self._lock_held:
            return

        self.lock_dir.mkdir(parents=True, exist_ok=True)

        try:
            self._internal_lock = DirectoryProcessLock(
                lock_dir=self.lock_dir,
                run_id="OPERATOR_APP_SINGLE_INSTANCE",
                timeout_seconds=0.1,
            )
            self._internal_lock.acquire(allow_stale_break=self.allow_stale_break)
            self._lock_held = True
        except LockAcquisitionError as e:
            raise SingleInstanceLockError(
                f"Cannot acquire single-instance lock: {e}"
            ) from e
        except Exception as e:
            raise SingleInstanceLockError(
                f"Unexpected failure acquiring single-instance lock: {e}"
            ) from e

    def release(self) -> None:
        """Release the single-instance lock."""
        if not self._lock_held:
            return

        try:
            if self._internal_lock:
                self._internal_lock.release()
        except Exception:
            pass
        finally:
            self._lock_held = False
            self._internal_lock = None

    def __enter__(self) -> "SingleInstanceLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
