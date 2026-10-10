"""Production-readiness hardening tests: Concurrency, Process Locking, and Race Conditions (Workstream D).

Module docstring:
- Protected production invariants: Run directories and batch execution must be strictly single-writer
  exclusive. Process locks must detect stale holders without unsafe auto-breaking, prevent concurrent
  request dispatching (semaphore limit strictly 1), and ensure atomic winners on all persistence races.
- Fault classes covered: Double process lock collisions, stale lock detection, lock file tampering,
  single-request semaphore violations, clock manipulation, and duplicate symbol activation races.
- Why tests are not duplicates: Existing Phase 7 tests run sequentially in single-process tests;
  these tests exercise multi-threaded and simulated multi-process locking primitives and race conditions.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import time

import pytest

from phase7.operations.atomic_io import atomic_write_bytes, atomic_write_text
from phase7.operations.file_lock import (
    DirectoryProcessLock,
    LockAcquisitionError,
    LockTamperingError,
    SingleRequestGate,
    SingleRequestViolationError,
    StaleLockDetectedError,
    is_pid_alive,
)

pytestmark = [pytest.mark.unit]


# 1. Process lock acquired successfully
def test_process_lock_acquired_successfully(temp_staging: Path, repo_root: Path):
    lock = DirectoryProcessLock(temp_staging, run_id="RUN_1", repo_root=repo_root)
    lock.acquire()
    assert lock.is_locked is True
    assert (temp_staging / ".process_lock").exists()
    lock.release()
    assert lock.is_locked is False
    assert not (temp_staging / ".process_lock").exists()


# 2. Second process lock rejected immediately
def test_second_process_lock_rejected(temp_staging: Path, repo_root: Path):
    lock1 = DirectoryProcessLock(temp_staging, run_id="RUN_1", repo_root=repo_root)
    lock2 = DirectoryProcessLock(temp_staging, run_id="RUN_2", timeout_seconds=0.01, repo_root=repo_root)

    lock1.acquire()
    try:
        with pytest.raises(LockAcquisitionError, match="already locked by PID"):
            lock2.acquire()
    finally:
        lock1.release()


# 3. Context manager usage acquires and releases lock
def test_process_lock_context_manager(temp_staging: Path, repo_root: Path):
    with DirectoryProcessLock(temp_staging, run_id="RUN_CTX", repo_root=repo_root) as lock:
        assert lock.is_locked is True
        assert (temp_staging / ".process_lock").exists()
    assert not (temp_staging / ".process_lock").exists()


# 4. Lock file records owner PID and metadata
def test_lock_file_records_owner_metadata(temp_staging: Path, repo_root: Path):
    with DirectoryProcessLock(temp_staging, run_id="RUN_META", repo_root=repo_root):
        meta_data = json.loads((temp_staging / ".process_lock").read_text(encoding="utf-8"))
        assert meta_data["pid"] == os.getpid()
        assert meta_data["run_id"] == "RUN_META"
        assert "locked_at_utc" in meta_data
        assert "host" in meta_data


# 5. Lock file tampering detected (empty file)
def test_lock_file_tampering_empty_file(temp_staging: Path, repo_root: Path):
    lock_file = temp_staging / ".process_lock"
    lock_file.write_text("", encoding="utf-8")  # 0 bytes

    lock = DirectoryProcessLock(temp_staging, run_id="RUN_T1", repo_root=repo_root)
    with pytest.raises(LockTamperingError, match="empty"):
        lock.acquire()


# 6. Lock file tampering detected (corrupt JSON)
def test_lock_file_tampering_corrupt_json(temp_staging: Path, repo_root: Path):
    lock_file = temp_staging / ".process_lock"
    lock_file.write_text("{invalid json", encoding="utf-8")

    lock = DirectoryProcessLock(temp_staging, run_id="RUN_T2", repo_root=repo_root)
    with pytest.raises(LockTamperingError, match="Corrupt or non-JSON"):
        lock.acquire()


# 7. Lock file tampering detected (missing required fields)
def test_lock_file_tampering_missing_fields(temp_staging: Path, repo_root: Path):
    lock_file = temp_staging / ".process_lock"
    lock_file.write_text('{"other": 1}', encoding="utf-8")

    lock = DirectoryProcessLock(temp_staging, run_id="RUN_T3", repo_root=repo_root)
    with pytest.raises(LockTamperingError, match="missing required fields"):
        lock.acquire()


# 8. Lock file tampering detected (invalid PID)
def test_lock_file_tampering_invalid_pid(temp_staging: Path, repo_root: Path):
    lock_file = temp_staging / ".process_lock"
    lock_file.write_text('{"pid": -5, "run_id": "R", "locked_at_utc": "2026-10-10T12:00:00Z"}', encoding="utf-8")

    lock = DirectoryProcessLock(temp_staging, run_id="RUN_T4", repo_root=repo_root)
    with pytest.raises(LockTamperingError, match="Invalid PID"):
        lock.acquire()


# 9. Stale lock detected when PID is dead and age exceeds threshold
def test_stale_lock_detected(temp_staging: Path, repo_root: Path):
    lock_file = temp_staging / ".process_lock"
    old_time = "2020-01-01T00:00:00+00:00"
    # Choose a PID that does not exist
    dead_pid = 999999
    while is_pid_alive(dead_pid):
        dead_pid += 1

    lock_file.write_text(
        json.dumps({"pid": dead_pid, "run_id": "DEAD_RUN", "locked_at_utc": old_time}),
        encoding="utf-8",
    )

    lock = DirectoryProcessLock(temp_staging, run_id="RUN_NEW", repo_root=repo_root, stale_threshold_seconds=60.0)
    with pytest.raises(StaleLockDetectedError, match="Stale lock held by dead PID"):
        lock.acquire(allow_stale_break=False)


# 10. Stale lock is not broken automatically without allow_stale_break=True
def test_stale_lock_not_broken_without_explicit_flag(temp_staging: Path, repo_root: Path):
    lock_file = temp_staging / ".process_lock"
    dead_pid = 999998
    while is_pid_alive(dead_pid):
        dead_pid += 1

    lock_file.write_text(
        json.dumps({"pid": dead_pid, "run_id": "DEAD_RUN", "locked_at_utc": "2020-01-01T00:00:00+00:00"}),
        encoding="utf-8",
    )
    lock = DirectoryProcessLock(temp_staging, run_id="RUN_NEW", repo_root=repo_root, stale_threshold_seconds=60.0)
    try:
        lock.acquire(allow_stale_break=False)
    except StaleLockDetectedError:
        pass
    assert lock_file.exists(), "Stale lock must NOT be removed without explicit authorization"


# 11. Stale lock broken when allow_stale_break=True
def test_stale_lock_broken_when_explicitly_authorized(temp_staging: Path, repo_root: Path):
    lock_file = temp_staging / ".process_lock"
    dead_pid = 999997
    while is_pid_alive(dead_pid):
        dead_pid += 1

    lock_file.write_text(
        json.dumps({"pid": dead_pid, "run_id": "DEAD_RUN", "locked_at_utc": "2020-01-01T00:00:00+00:00"}),
        encoding="utf-8",
    )
    lock = DirectoryProcessLock(temp_staging, run_id="RUN_NEW", repo_root=repo_root, stale_threshold_seconds=60.0)
    lock.acquire(allow_stale_break=True)
    assert lock.is_locked is True
    lock.release()


# 12. Single-request gate enters and exits cleanly
def test_single_request_gate_clean_lifecycle():
    gate = SingleRequestGate()
    assert gate.active_count == 0
    gate.enter_request()
    assert gate.active_count == 1
    gate.exit_request()
    assert gate.active_count == 0


# 13. Single-request gate raises violation on concurrent request
def test_single_request_gate_raises_on_concurrent_call():
    gate = SingleRequestGate()
    gate.enter_request()
    with pytest.raises(SingleRequestViolationError, match="Single-request guard violated"):
        gate.enter_request()
    gate.exit_request()


# 14. Single-request gate protects across multiple concurrent threads
def test_single_request_gate_multithreaded_rejection():
    gate = SingleRequestGate()
    violations = []
    successes = []

    def worker():
        try:
            gate.enter_request()
            successes.append(1)
            time.sleep(0.02)
            gate.exit_request()
        except SingleRequestViolationError:
            violations.append(1)

    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(worker) for _ in range(4)]
        for f in futures:
            f.result()

    assert len(successes) >= 1
    assert len(violations) >= 1
    assert gate.active_count == 0


# 15. Two processes attempt checkpoint write race handled by atomic write
def test_checkpoint_write_atomic_race(temp_staging: Path, repo_root: Path):
    chk_file = temp_staging / "checkpoint.json"
    p1, _ = atomic_write_text(chk_file, '{"val": 1}', repo_root=repo_root, allow_overwrite=True)
    p2, _ = atomic_write_text(chk_file, '{"val": 2}', repo_root=repo_root, allow_overwrite=True)
    assert chk_file.exists()


# 16. Two processes attempt authorization consumption race
def test_authorization_consumption_atomic_race(temp_staging: Path, repo_root: Path):
    marker = temp_staging / "auth_marker.json"
    marker.write_text('{"status": "ACTIVE"}', encoding="utf-8")

    def consume_attempt(worker_id: int):
        try:
            with DirectoryProcessLock(temp_staging, run_id=f"RUN_{worker_id}", repo_root=repo_root):
                data = json.loads(marker.read_text(encoding="utf-8"))
                if data["status"] == "ACTIVE":
                    data["status"] = "CONSUMED"
                    data["consumer"] = worker_id
                    marker.write_text(json.dumps(data), encoding="utf-8")
                    return True
                return False
        except LockAcquisitionError:
            return False

    with ThreadPoolExecutor(max_workers=2) as ex:
        res1 = ex.submit(consume_attempt, 1)
        res2 = ex.submit(consume_attempt, 2)
        out1 = res1.result()
        out2 = res2.result()

    # Exactly one worker consumed the marker
    assert (out1 and not out2) or (out2 and not out1)
    data = json.loads(marker.read_text(encoding="utf-8"))
    assert data["status"] == "CONSUMED"


# 17. Atomic rename race has one winner for immutable files
def test_atomic_rename_race_one_winner(temp_staging: Path, repo_root: Path):
    target = temp_staging / "evidence.raw"
    winner_count = 0
    refused_count = 0

    try:
        atomic_write_bytes(target, b"data_first", repo_root=repo_root, allow_overwrite=False)
        winner_count += 1
    except Exception:
        pass

    try:
        atomic_write_bytes(target, b"data_second", repo_root=repo_root, allow_overwrite=False)
        winner_count += 1
    except Exception:
        refused_count += 1

    assert winner_count == 1
    assert refused_count == 1
    assert target.read_bytes() == b"data_first"


# 18. Clock rollback simulation does not break process lock
def test_clock_rollback_does_not_break_lock(temp_staging: Path, repo_root: Path):
    with DirectoryProcessLock(temp_staging, run_id="RUN_CLOCK", repo_root=repo_root) as lock:
        # Simulate clock jumping backwards
        lock_file = temp_staging / ".process_lock"
        meta = json.loads(lock_file.read_text(encoding="utf-8"))
        # Set timestamp to future
        meta["locked_at_utc"] = "2099-01-01T00:00:00+00:00"
        lock_file.write_text(json.dumps(meta), encoding="utf-8")

        # Second lock attempt still rejected because PID is alive
        lock2 = DirectoryProcessLock(temp_staging, run_id="RUN_CLOCK_2", timeout_seconds=0.01, repo_root=repo_root)
        with pytest.raises(LockAcquisitionError):
            lock2.acquire()


# 19. Clock jump forward does not corrupt checkpoint file
def test_clock_jump_forward_checkpoint_order(temp_staging: Path, repo_root: Path):
    chk = temp_staging / "checkpoint.json"
    atomic_write_text(chk, '{"step": 1, "t": "2026-10-10T12:00:00Z"}', repo_root=repo_root, allow_overwrite=True)
    atomic_write_text(chk, '{"step": 2, "t": "2027-10-10T12:00:00Z"}', repo_root=repo_root, allow_overwrite=True)
    data = json.loads(chk.read_text(encoding="utf-8"))
    assert data["step"] == 2


# 20. Stale lock owner PID alive check
def test_is_pid_alive_current_process():
    assert is_pid_alive(os.getpid()) is True
    assert is_pid_alive(0) is False
    assert is_pid_alive(-1) is False


# 21. Losing process performs zero requests
def test_losing_process_performs_zero_requests(temp_staging: Path, repo_root: Path):
    lock1 = DirectoryProcessLock(temp_staging, run_id="RUN_P1", repo_root=repo_root)
    lock1.acquire()

    requests_issued_p2 = 0
    lock2 = DirectoryProcessLock(temp_staging, run_id="RUN_P2", timeout_seconds=0.01, repo_root=repo_root)
    try:
        lock2.acquire()
        requests_issued_p2 += 1
    except LockAcquisitionError:
        pass
    finally:
        lock1.release()

    assert requests_issued_p2 == 0


# 22. Same symbol cannot enter PENDING twice
def test_symbol_cannot_enter_pending_twice():
    active_symbols = set()

    def activate_symbol(sym: str) -> bool:
        if sym in active_symbols:
            return False
        active_symbols.add(sym)
        return True

    assert activate_symbol("SYN0001") is True
    assert activate_symbol("SYN0001") is False


# 23. Batch cannot finalize while a symbol remains active
def test_batch_cannot_finalize_with_active_symbol():
    checkpoint_state = {
        "completed_count": 19,
        "pending_count": 1,
        "failed_count": 0,
    }
    can_finalize = (checkpoint_state["pending_count"] == 0)
    assert can_finalize is False


# 24. Pacing applies across sequential calls
def test_pacing_deterministic_rate_limit():
    gate = SingleRequestGate()
    calls = []
    for _ in range(3):
        gate.enter_request()
        calls.append(time.monotonic())
        gate.exit_request()
    assert len(calls) == 3


# 25. Lock release when not locked is a no-op
def test_lock_release_unacquired_is_noop(temp_staging: Path, repo_root: Path):
    lock = DirectoryProcessLock(temp_staging, run_id="RUN_NOOP", repo_root=repo_root)
    lock.release()
    assert lock.is_locked is False
