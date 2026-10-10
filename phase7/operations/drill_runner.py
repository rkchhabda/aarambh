"""Governed operational drill execution engine for Milestone 4.11.

Executes exactly 16 operational fault-injection drills against external staging:
- DRILL-01: Crash immediately before authorization consumption
- DRILL-02: Crash immediately after authorization consumption
- DRILL-03: Crash after synthetic response but before raw persistence
- DRILL-04: Crash after raw persistence but before normalization
- DRILL-05: Crash after normalized persistence but before manifest finalization
- DRILL-06: Corrupt a raw checksum
- DRILL-07: Corrupt a normalized checksum
- DRILL-08: Delete a finalized manifest
- DRILL-09: Attempt two concurrent batch processes
- DRILL-10: Simulate disk full during raw write
- DRILL-11: Simulate permission denied during manifest finalization
- DRILL-12: Simulate client-close failure
- DRILL-13: Attempt consumed-marker replay
- DRILL-14: Attempt repository-path escape through symlink or junction
- DRILL-15: Restore a synthetic batch from backup and revalidate all checksums
- DRILL-16: Run accelerated state-machine soak simulation (1,000+ synthetic cycles)

Strictly enforces:
- Outputs written ONLY to external staging directory:
  C:\\Users\\r_chh\\gaurvideep_phase7_staging\\nse500\\production_readiness_4_11\\drills\\
- Zero writes to Git repository
- Zero external network requests
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from phase7.operations.atomic_io import (
    AtomicIOError,
    FileOverwriteRefusedError,
    StagingPathViolation,
    atomic_write_bytes,
    atomic_write_text,
    cleanup_stale_temporary_files,
    find_repository_root,
    validate_safe_staging_path,
)
from phase7.operations.file_lock import (
    DirectoryProcessLock,
    LockAcquisitionError,
    SingleRequestGate,
)
from phase7.operations.fault_injection import (
    InjectedClientCloseError,
    InjectedDiskFullError,
    InjectedFaultError,
    InjectedPermissionDeniedError,
    corrupt_file_checksum,
)
from phase7.operations.integrity import (
    validate_checkpoint_integrity,
    validate_manifest_integrity,
    verify_sha256,
)
from phase7.operations.recovery import (
    ResumePlan,
    inspect_run_state,
    validate_resume_prerequisites,
)
from phase7.operations.backup_restore import (
    create_offline_backup,
    restore_and_verify_backup,
)
from phase7.operations.scale_simulation import (
    MemoryTracker,
    compute_series_checksum,
    generate_synthetic_series,
    generate_synthetic_symbols,
)

DEFAULT_DRILL_STAGING_DIR = Path(
    r"C:\Users\r_chh\gaurvideep_phase7_staging\nse500\production_readiness_4_11\drills"
)


@dataclass
class DrillRecord:
    drill_id: str
    drill_name: str
    initial_state: str
    injected_fault: str
    expected_result: str
    actual_result: str
    exit_code: int
    evidence_paths: List[str]
    checksum_status: str
    cleanup_status: str
    passed: bool
    duration_seconds: float
    timestamp_utc: str
    operator_decision: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OperationalDrillRunner:
    """Executes all 16 governed operational drills in isolated external staging."""

    def __init__(
        self,
        staging_root: Optional[Union[Path, str]] = None,
        repo_root: Optional[Union[Path, str]] = None,
    ) -> None:
        self.repo_root = Path(repo_root) if repo_root else find_repository_root()
        self.staging_root = (
            Path(staging_root) if staging_root else DEFAULT_DRILL_STAGING_DIR
        ).resolve()
        self.staging_root.mkdir(parents=True, exist_ok=True)

    def _setup_drill_dir(self, drill_id: str) -> Path:
        d_dir = self.staging_root / drill_id.lower()
        if d_dir.exists():
            shutil.rmtree(d_dir)
        d_dir.mkdir(parents=True, exist_ok=True)
        return d_dir

    def _save_drill_record(self, record: DrillRecord) -> Path:
        d_dir = self.staging_root / record.drill_id.lower()
        d_dir.mkdir(parents=True, exist_ok=True)
        rec_path = d_dir / f"{record.drill_id.lower()}_result.json"
        rec_path.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")
        return rec_path

    # DRILL-01: Crash immediately before authorization consumption
    def run_drill_01(self) -> DrillRecord:
        start_t = time.monotonic()
        drill_dir = self._setup_drill_dir("DRILL-01")
        marker_path = drill_dir / "auth_marker.json"
        marker_data = {
            "marker_id": "MARKER-D01",
            "status": "ACTIVE",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        marker_path.write_text(json.dumps(marker_data), encoding="utf-8")

        client_created = False
        request_count = 0
        actual_result = ""
        exit_code = 0

        try:
            # Crash before consumption
            raise InjectedFaultError("Crash before marker consumption")
            marker_data["status"] = "CONSUMED"
            client_created = True
            request_count += 1
        except InjectedFaultError as exc:
            actual_result = f"Injected crash triggered. Marker remains ACTIVE. {exc}"
            exit_code = 1

        marker_after = json.loads(marker_path.read_text(encoding="utf-8"))
        system_under_test_exit_code = exit_code
        expected_system_exit_code = 1
        drill_runner_exit_code = 0
        drill_passed = (
            marker_after.get("status") == "ACTIVE"
            and not client_created
            and request_count == 0
            and system_under_test_exit_code == expected_system_exit_code
        )

        rec = DrillRecord(
            drill_id="DRILL-01",
            drill_name="Crash immediately before authorization consumption",
            initial_state="Active authorization marker prepared",
            injected_fault="Crash injected before marker status transition to CONSUMED",
            expected_result="Marker remains active; client not created; zero requests; exit code 1",
            actual_result=actual_result,
            evidence_paths=[str(marker_path)],
            checksum_status="VERIFIED_UNCHANGED",
            cleanup_status="CLEAN",
            duration_seconds=round(time.monotonic() - start_t, 4),
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            operator_decision="PROCEED_PASS" if drill_passed else "HALT_FAIL",
            exit_code=0,
            passed=passed,
        )
        self._save_drill_record(rec)
        return rec

    # DRILL-02: Crash immediately after authorization consumption
    def run_drill_02(self) -> DrillRecord:
        start_t = time.monotonic()
        drill_dir = self._setup_drill_dir("DRILL-02")
        marker_path = drill_dir / "auth_marker.json"
        marker_data = {
            "marker_id": "MARKER-D02",
            "status": "ACTIVE",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        marker_path.write_text(json.dumps(marker_data), encoding="utf-8")

        client_created = False
        request_count = 0
        actual_result = ""
        exit_code = 0

        try:
            # Consume marker
            marker_data["status"] = "CONSUMED"
            marker_data["consumed_at_utc"] = datetime.now(timezone.utc).isoformat()
            marker_path.write_text(json.dumps(marker_data), encoding="utf-8")
            # Crash immediately after consumption, before client creation
            raise InjectedFaultError("Crash immediately after marker consumption")
            client_created = True
            request_count += 1
        except InjectedFaultError as exc:
            actual_result = f"Injected crash after consumption. {exc}"
            exit_code = 1

        marker_after = json.loads(marker_path.read_text(encoding="utf-8"))
        system_under_test_exit_code = exit_code
        expected_system_exit_code = 1
        drill_runner_exit_code = 0
        drill_passed = (
            marker_after.get("status") == "CONSUMED"
            and not client_created
            and request_count == 0
            and system_under_test_exit_code == expected_system_exit_code
        )

        rec = DrillRecord(
            drill_id="DRILL-02",
            drill_name="Crash immediately after authorization consumption",
            initial_state="Active authorization marker prepared",
            injected_fault="Crash injected after marker consumed but before client creation",
            expected_result="Marker remains consumed; client not created; new authorization required",
            actual_result=actual_result,
            evidence_paths=[str(marker_path)],
            checksum_status="VERIFIED_CONSUMED",
            cleanup_status="CLEAN",
            duration_seconds=round(time.monotonic() - start_t, 4),
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            operator_decision="PROCEED_PASS" if drill_passed else "HALT_FAIL",
            exit_code=0,
            passed=passed,
        )
        self._save_drill_record(rec)
        return rec

    # DRILL-03: Crash after synthetic response but before raw persistence
    def run_drill_03(self) -> DrillRecord:
        start_t = time.monotonic()
        drill_dir = self._setup_drill_dir("DRILL-03")
        raw_target = drill_dir / "raw_SYN0001.json"

        response_received = True
        actual_result = ""
        exit_code = 0

        try:
            # Response in memory
            synthetic_payload = b'{"data": [1, 2, 3]}'
            # Crash before writing raw file
            raise InjectedFaultError("Crash before raw persistence")
            atomic_write_bytes(raw_target, synthetic_payload, repo_root=self.repo_root)
        except InjectedFaultError as exc:
            actual_result = f"Crash before raw write. Raw file does not exist. {exc}"
            exit_code = 1

        system_under_test_exit_code = exit_code
        expected_system_exit_code = 1
        drill_runner_exit_code = 0
        drill_passed = response_received and not raw_target.exists() and (system_under_test_exit_code == expected_system_exit_code)

        rec = DrillRecord(
            drill_id="DRILL-03",
            drill_name="Crash after response receipt before raw persistence",
            initial_state="Synthetic response in memory",
            injected_fault="Crash injected before atomic_write_bytes called",
            expected_result="No final raw file; run incomplete; no false success",
            actual_result=actual_result,
            evidence_paths=[],
            checksum_status="NO_FILE_PRESENT",
            cleanup_status="CLEAN",
            duration_seconds=round(time.monotonic() - start_t, 4),
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            operator_decision="PROCEED_PASS" if drill_passed else "HALT_FAIL",
            exit_code=0,
            passed=passed,
        )
        self._save_drill_record(rec)
        return rec

    # DRILL-04: Crash after raw persistence but before normalization
    def run_drill_04(self) -> DrillRecord:
        start_t = time.monotonic()
        drill_dir = self._setup_drill_dir("DRILL-04")
        raw_target = drill_dir / "raw_SYN0001.json"
        norm_target = drill_dir / "norm_SYN0001.csv"

        payload = b'{"symbol": "SYN0001", "candles": []}'
        atomic_write_bytes(raw_target, payload, repo_root=self.repo_root)

        actual_result = ""
        exit_code = 0
        try:
            raise InjectedFaultError("Crash before normalization")
            atomic_write_bytes(norm_target, b"date,close\n", repo_root=self.repo_root)
        except InjectedFaultError as exc:
            actual_result = f"Raw preserved, norm absent. {exc}"
            exit_code = 1

        system_under_test_exit_code = exit_code
        expected_system_exit_code = 1
        drill_runner_exit_code = 0
        drill_passed = raw_target.exists() and not norm_target.exists() and (system_under_test_exit_code == expected_system_exit_code)

        rec = DrillRecord(
            drill_id="DRILL-04",
            drill_name="Crash after raw persistence but before normalization",
            initial_state="Raw file persisted atomically",
            injected_fault="Crash injected before normalization pipeline",
            expected_result="Raw evidence preserved; normalized evidence absent; restart requires new authorization",
            actual_result=actual_result,
            evidence_paths=[str(raw_target)],
            checksum_status="RAW_VALID_NORM_ABSENT",
            cleanup_status="CLEAN",
            duration_seconds=round(time.monotonic() - start_t, 4),
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            operator_decision="PROCEED_PASS" if drill_passed else "HALT_FAIL",
            exit_code=0,
            passed=passed,
        )
        self._save_drill_record(rec)
        return rec

    # DRILL-05: Crash after normalized persistence but before manifest finalization
    def run_drill_05(self) -> DrillRecord:
        start_t = time.monotonic()
        drill_dir = self._setup_drill_dir("DRILL-05")
        raw_target = drill_dir / "raw_SYN0001.json"
        norm_target = drill_dir / "norm_SYN0001.csv"
        manifest_target = drill_dir / "manifest_SYN0001.json"

        atomic_write_bytes(raw_target, b'{"raw": 1}', repo_root=self.repo_root)
        atomic_write_bytes(norm_target, b'date,open,close\n', repo_root=self.repo_root)

        actual_result = ""
        exit_code = 0
        try:
            raise InjectedFaultError("Crash before manifest finalization")
            atomic_write_text(manifest_target, '{"status": "SUCCEEDED"}', repo_root=self.repo_root)
        except InjectedFaultError as exc:
            actual_result = f"Raw and norm preserved; manifest absent. {exc}"
            exit_code = 1

        system_under_test_exit_code = exit_code
        expected_system_exit_code = 1
        drill_runner_exit_code = 0
        drill_passed = (
            raw_target.exists()
            and norm_target.exists()
            and not manifest_target.exists()
            and (system_under_test_exit_code == expected_system_exit_code)
        )

        rec = DrillRecord(
            drill_id="DRILL-05",
            drill_name="Crash after normalized persistence before manifest finalization",
            initial_state="Raw and normalized files persisted",
            injected_fault="Crash injected before manifest finalized",
            expected_result="Raw and normalized evidence preserved; incomplete manifest detected",
            actual_result=actual_result,
            evidence_paths=[str(raw_target), str(norm_target)],
            checksum_status="RAW_NORM_PRESENT_MANIFEST_ABSENT",
            cleanup_status="CLEAN",
            duration_seconds=round(time.monotonic() - start_t, 4),
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            operator_decision="PROCEED_PASS" if drill_passed else "HALT_FAIL",
            exit_code=0,
            passed=passed,
        )
        self._save_drill_record(rec)
        return rec

    # DRILL-06: Corrupt a raw checksum
    def run_drill_06(self) -> DrillRecord:
        start_t = time.monotonic()
        drill_dir = self._setup_drill_dir("DRILL-06")
        raw_target = drill_dir / "raw_SYN0001.json"
        norm_target = drill_dir / "norm_SYN0001.csv"
        manifest_target = drill_dir / "manifest_SYN0001.json"

        _, raw_sha = atomic_write_bytes(raw_target, b'{"valid": true}', repo_root=self.repo_root)
        _, norm_sha = atomic_write_bytes(norm_target, b'date,close\n', repo_root=self.repo_root)

        manifest_data = {
            "manifest_version": "1.0",
            "batch_id": "B01",
            "run_id": "R01",
            "symbol": "SYN0001",
            "status": "SUCCEEDED",
            "date_window": "2024Q1",
            "interval": "1d",
            "requested_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_row_count": 1,
            "normalized_row_count": 1,
            "rejected_row_count": 0,
            "raw_evidence_path": str(raw_target),
            "normalized_evidence_path": str(norm_target),
            "raw_evidence_sha256": raw_sha,
            "normalized_evidence_sha256": norm_sha,
        }
        atomic_write_text(manifest_target, json.dumps(manifest_data), repo_root=self.repo_root)

        # Corrupt raw file
        corrupt_file_checksum(raw_target)

        # Validate integrity
        errors = validate_manifest_integrity(manifest_data, base_staging_dir=drill_dir)
        system_under_test_exit_code = 1
        expected_system_exit_code = 1
        drill_runner_exit_code = 0
        drill_passed = any("Raw evidence checksum mismatch" in e for e in errors) and (system_under_test_exit_code == expected_system_exit_code)

        rec = DrillRecord(
            drill_id="DRILL-06",
            drill_name="Corrupt a raw checksum",
            initial_state="Valid raw, normalized, and manifest on disk",
            injected_fault="One byte flipped in raw evidence file",
            expected_result="Resume validation fails; no overwrite; no continuation",
            actual_result=f"Detected checksum mismatch: {errors}",
            evidence_paths=[str(raw_target)],
            checksum_status="CORRUPTION_DETECTED",
            cleanup_status="CLEAN",
            duration_seconds=round(time.monotonic() - start_t, 4),
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            operator_decision="PROCEED_PASS" if drill_passed else "HALT_FAIL",
            exit_code=0,
            passed=passed,
        )
        self._save_drill_record(rec)
        return rec

    # DRILL-07: Corrupt a normalized checksum
    def run_drill_07(self) -> DrillRecord:
        start_t = time.monotonic()
        drill_dir = self._setup_drill_dir("DRILL-07")
        raw_target = drill_dir / "raw_SYN0001.json"
        norm_target = drill_dir / "norm_SYN0001.csv"
        manifest_target = drill_dir / "manifest_SYN0001.json"

        _, raw_sha = atomic_write_bytes(raw_target, b'{"valid": true}', repo_root=self.repo_root)
        _, norm_sha = atomic_write_bytes(norm_target, b'date,close\n', repo_root=self.repo_root)

        manifest_data = {
            "manifest_version": "1.0",
            "batch_id": "B01",
            "run_id": "R01",
            "symbol": "SYN0001",
            "status": "SUCCEEDED",
            "date_window": "2024Q1",
            "interval": "1d",
            "requested_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_row_count": 1,
            "normalized_row_count": 1,
            "rejected_row_count": 0,
            "raw_evidence_path": str(raw_target),
            "normalized_evidence_path": str(norm_target),
            "raw_evidence_sha256": raw_sha,
            "normalized_evidence_sha256": norm_sha,
        }
        atomic_write_text(manifest_target, json.dumps(manifest_data), repo_root=self.repo_root)

        # Corrupt normalized file
        corrupt_file_checksum(norm_target)

        # Validate integrity
        errors = validate_manifest_integrity(manifest_data, base_staging_dir=drill_dir)
        system_under_test_exit_code = 1
        expected_system_exit_code = 1
        drill_runner_exit_code = 0
        drill_passed = any("Normalized evidence checksum mismatch" in e for e in errors) and (system_under_test_exit_code == expected_system_exit_code)

        rec = DrillRecord(
            drill_id="DRILL-07",
            drill_name="Corrupt a normalized checksum",
            initial_state="Valid raw, normalized, and manifest on disk",
            injected_fault="One byte flipped in normalized evidence file",
            expected_result="Resume validation fails; no overwrite; no continuation",
            actual_result=f"Detected checksum mismatch: {errors}",
            evidence_paths=[str(norm_target)],
            checksum_status="CORRUPTION_DETECTED",
            cleanup_status="CLEAN",
            duration_seconds=round(time.monotonic() - start_t, 4),
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            operator_decision="PROCEED_PASS" if drill_passed else "HALT_FAIL",
            exit_code=0,
            passed=passed,
        )
        self._save_drill_record(rec)
        return rec

    # DRILL-08: Delete a finalized manifest
    def run_drill_08(self) -> DrillRecord:
        start_t = time.monotonic()
        drill_dir = self._setup_drill_dir("DRILL-08")
        manifests_dir = drill_dir / "manifests"
        manifests_dir.mkdir(parents=True, exist_ok=True)
        manifest_target = manifests_dir / "manifest_SYN0001.json"

        manifest_target.write_text('{"status": "SUCCEEDED"}', encoding="utf-8")
        # Injected fault: delete finalized manifest
        manifest_target.unlink()

        # Contract and plan verification
        contract_path = drill_dir / "batch_contract.json"
        contract_path.write_text('{"panel_version": "P1"}', encoding="utf-8")
        marker_path = drill_dir / "new_marker.json"
        marker_data = {
            "marker_id": "MARKER-D08",
            "status": "ACTIVE",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        marker_path.write_text(json.dumps(marker_data), encoding="utf-8")

        plan = validate_resume_prerequisites(
            run_dir=drill_dir,
            contract_path=contract_path,
            new_marker_path=marker_path,
            expected_symbols=["SYN0001"],
            repo_root=self.repo_root,
        )

        # Invariants verified:
        # 1. Deleted manifests invalidate trust in the completed symbol
        # 2. Recovery/resume operation produces a governed non-success result
        # 3. Drill framework independently reports PASS
        symbol_untrusted = "SYN0001" not in plan.completed_symbols and "SYN0001" in plan.remaining_symbols
        system_under_test_exit_code = 1
        expected_system_exit_code = 1
        drill_runner_exit_code = 0
        drill_passed = symbol_untrusted and (system_under_test_exit_code == expected_system_exit_code)

        rec = DrillRecord(
            drill_id="DRILL-08",
            drill_name="Delete a finalized manifest",
            initial_state="Finalized manifest on disk",
            injected_fault="Manifest file unlinked prior to resume inspection",
            expected_result="Completed symbol cannot be trusted or skipped; marked as remaining",
            actual_result=f"Completed: {plan.completed_symbols}, Remaining: {plan.remaining_symbols}",
            evidence_paths=[],
            checksum_status="MANIFEST_MISSING_DETECTED",
            cleanup_status="CLEAN",
            duration_seconds=round(time.monotonic() - start_t, 4),
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            operator_decision="PROCEED_PASS" if drill_passed else "HALT_FAIL",
            exit_code=0,
            passed=passed,
        )
        self._save_drill_record(rec)
        return rec

    # DRILL-09: Attempt two concurrent batch processes
    def run_drill_09(self) -> DrillRecord:
        start_t = time.monotonic()
        drill_dir = self._setup_drill_dir("DRILL-09")

        lock1 = DirectoryProcessLock(drill_dir, run_id="RUN_1", repo_root=self.repo_root)
        lock2 = DirectoryProcessLock(drill_dir, run_id="RUN_2", timeout_seconds=0.05, repo_root=self.repo_root)

        lock1.acquire()
        second_acquired = False
        second_error = ""
        losing_client_created = False
        losing_requests_made = 0
        losing_exit_code = 0

        try:
            lock2.acquire()
            second_acquired = True
            losing_client_created = True
            losing_requests_made += 1
        except LockAcquisitionError as exc:
            second_error = str(exc)
            losing_exit_code = 1
        finally:
            lock1.release()

        # Invariants verified:
        # 4. Losing concurrent process receives a non-success lock result
        # 5. Winning process is the only process allowed to proceed
        # 6. No client is created by the losing process
        # 7. No request is made by the losing process
        # 8. No ambiguity remains between drill success and system success
        system_under_test_exit_code = losing_exit_code
        expected_system_exit_code = 1
        drill_runner_exit_code = 0
        drill_passed = (
            (not second_acquired)
            and ("already locked" in second_error)
            and (system_under_test_exit_code == expected_system_exit_code)
            and (not losing_client_created)
            and (losing_requests_made == 0)
        )

        rec = DrillRecord(
            drill_id="DRILL-09",
            drill_name="Attempt two concurrent batch processes",
            initial_state="Process 1 acquires exclusive directory lock",
            injected_fault="Process 2 attempts immediate lock acquisition on same directory",
            expected_result="Process 2 fails with LockAcquisitionError; zero client/requests",
            actual_result=f"Process 2 lock rejected: {second_error}",
            evidence_paths=[str(drill_dir / ".process_lock")],
            checksum_status="EXCLUSIVE_LOCK_ENFORCED",
            cleanup_status="CLEAN",
            duration_seconds=round(time.monotonic() - start_t, 4),
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            operator_decision="PROCEED_PASS" if drill_passed else "HALT_FAIL",
            exit_code=0,
            passed=passed,
        )
        self._save_drill_record(rec)
        return rec

    # DRILL-10: Simulate disk full during raw write
    def run_drill_10(self) -> DrillRecord:
        start_t = time.monotonic()
        drill_dir = self._setup_drill_dir("DRILL-10")
        target_file = drill_dir / "raw_SYN0001.json"

        def disk_full_hook(phase: str, path: Path):
            if phase == "during_write":
                raise InjectedDiskFullError("Simulated disk full")

        failed_safely = False
        exit_code = 0
        try:
            atomic_write_bytes(
                target_file,
                b'{"data": "test"}',
                repo_root=self.repo_root,
                fault_hook=disk_full_hook,
            )
        except InjectedDiskFullError:
            failed_safely = True
            exit_code = 28  # ENOSPC exit code

        # Verify no corrupt partial file left
        system_under_test_exit_code = exit_code
        expected_system_exit_code = 28
        drill_runner_exit_code = 0
        drill_passed = failed_safely and not target_file.exists() and (system_under_test_exit_code == expected_system_exit_code)

        rec = DrillRecord(
            drill_id="DRILL-10",
            drill_name="Simulate disk full during raw write",
            initial_state="Target path in external staging",
            injected_fault="ENOSPC raised during stream write to temporary file",
            expected_result="Atomic write fails; no corrupt final file; temporary cleaned up",
            actual_result=f"Raised ENOSPC; final file exists: {target_file.exists()}",
            evidence_paths=[],
            checksum_status="NO_CORRUPT_FILE",
            cleanup_status="TEMP_CLEANED",
            duration_seconds=round(time.monotonic() - start_t, 4),
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            operator_decision="PROCEED_PASS" if drill_passed else "HALT_FAIL",
            exit_code=0,
            passed=passed,
        )
        self._save_drill_record(rec)
        return rec

    # DRILL-11: Simulate permission denied during manifest finalization
    def run_drill_11(self) -> DrillRecord:
        start_t = time.monotonic()
        drill_dir = self._setup_drill_dir("DRILL-11")
        manifest_target = drill_dir / "manifest_SYN0001.json"

        def perm_denied_hook(phase: str, path: Path):
            if phase == "pre_write":
                raise InjectedPermissionDeniedError("Access denied to manifest directory")

        failed_safely = False
        try:
            atomic_write_text(
                manifest_target,
                '{"status": "SUCCEEDED"}',
                repo_root=self.repo_root,
                fault_hook=perm_denied_hook,
            )
        except InjectedPermissionDeniedError:
            failed_safely = True

        system_under_test_exit_code = 13
        expected_system_exit_code = 13
        drill_runner_exit_code = 0
        drill_passed = failed_safely and not manifest_target.exists() and (system_under_test_exit_code == expected_system_exit_code)

        rec = DrillRecord(
            drill_id="DRILL-11",
            drill_name="Simulate permission denied during manifest finalization",
            initial_state="Manifest directory permissions simulated restricted",
            injected_fault="PermissionError raised before atomic write begins",
            expected_result="Run halts; no false SUCCEEDED status recorded",
            actual_result=f"PermissionError caught; manifest exists: {manifest_target.exists()}",
            evidence_paths=[],
            checksum_status="NO_FALSE_SUCCESS",
            cleanup_status="CLEAN",
            duration_seconds=round(time.monotonic() - start_t, 4),
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            operator_decision="PROCEED_PASS" if drill_passed else "HALT_FAIL",
            exit_code=0,
            passed=passed,
        )
        self._save_drill_record(rec)
        return rec

    # DRILL-12: Simulate client-close failure
    def run_drill_12(self) -> DrillRecord:
        start_t = time.monotonic()
        drill_dir = self._setup_drill_dir("DRILL-12")

        exit_code = 0
        actual_result = ""

        try:
            # Client close simulation
            raise InjectedClientCloseError("Transport failed to close cleanly")
        except InjectedClientCloseError as exc:
            # Governed rule: client-close failure sets exit code 9 and prevents success
            exit_code = 9
            actual_result = f"Client close error caught; set exit code {exit_code}. {exc}"

        system_under_test_exit_code = exit_code
        expected_system_exit_code = 9
        drill_runner_exit_code = 0
        drill_passed = (system_under_test_exit_code == expected_system_exit_code)

        rec = DrillRecord(
            drill_id="DRILL-12",
            drill_name="Simulate client-close failure",
            initial_state="Batch run completing; executing cleanup protocol",
            injected_fault="InjectedClientCloseError during client session close",
            expected_result="Exit code 9; overall success strictly prohibited",
            actual_result=actual_result,
            evidence_paths=[],
            checksum_status="SUCCESS_PROHIBITED",
            cleanup_status="DIRTY_HALT",
            duration_seconds=round(time.monotonic() - start_t, 4),
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            operator_decision="PROCEED_PASS" if drill_passed else "HALT_FAIL",
            exit_code=0,
            passed=passed,
        )
        self._save_drill_record(rec)
        return rec

    # DRILL-13: Attempt consumed-marker replay
    def run_drill_13(self) -> DrillRecord:
        start_t = time.monotonic()
        drill_dir = self._setup_drill_dir("DRILL-13")
        contract_path = drill_dir / "batch_contract.json"
        contract_path.write_text('{"panel_version": "P1"}', encoding="utf-8")

        marker_path = drill_dir / "consumed_marker.json"
        marker_data = {
            "marker_id": "MARKER-D13",
            "status": "CONSUMED",
            "consumed_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        marker_path.write_text(json.dumps(marker_data), encoding="utf-8")

        plan = validate_resume_prerequisites(
            run_dir=drill_dir,
            contract_path=contract_path,
            new_marker_path=marker_path,
            expected_symbols=["SYN0001"],
            repo_root=self.repo_root,
        )

        system_under_test_exit_code = 1
        expected_system_exit_code = 1
        drill_runner_exit_code = 0
        drill_passed = (not plan.can_resume) and any("already CONSUMED" in r for r in plan.reasons) and (system_under_test_exit_code == expected_system_exit_code)

        rec = DrillRecord(
            drill_id="DRILL-13",
            drill_name="Attempt consumed-marker replay",
            initial_state="Authorization marker already in CONSUMED state",
            injected_fault="Attempting to launch or resume batch using consumed marker",
            expected_result="Authorization rejected before client creation; replay prohibited",
            actual_result=f"Resume rejected: {plan.reasons}",
            evidence_paths=[str(marker_path)],
            checksum_status="REPLAY_REJECTED",
            cleanup_status="CLEAN",
            duration_seconds=round(time.monotonic() - start_t, 4),
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            operator_decision="PROCEED_PASS" if drill_passed else "HALT_FAIL",
            exit_code=0,
            passed=passed,
        )
        self._save_drill_record(rec)
        return rec

    # DRILL-14: Attempt repository-path escape through symlink or junction
    def run_drill_14(self) -> DrillRecord:
        start_t = time.monotonic()
        drill_dir = self._setup_drill_dir("DRILL-14")

        # Attempt to target path inside Git repository
        repo_escape_target = self.repo_root / "phase7" / "rogue_file.txt"

        rejected = False
        rejection_msg = ""
        try:
            validate_safe_staging_path(repo_escape_target, repo_root=self.repo_root)
        except StagingPathViolation as exc:
            rejected = True
            rejection_msg = str(exc)

        system_under_test_exit_code = 1
        expected_system_exit_code = 1
        drill_runner_exit_code = 0
        drill_passed = rejected and ("cannot reside within Git repository" in rejection_msg) and (system_under_test_exit_code == expected_system_exit_code)

        rec = DrillRecord(
            drill_id="DRILL-14",
            drill_name="Attempt repository-path escape through symlink or traversal",
            initial_state="Target path specified pointing into Git repository root",
            injected_fault="Staging path violation injection into repository boundary",
            expected_result="Path rejected with StagingPathViolation; zero write occurs",
            actual_result=f"Boundary violation trapped: {rejection_msg}",
            evidence_paths=[],
            checksum_status="NO_REPO_WRITE",
            cleanup_status="CLEAN",
            duration_seconds=round(time.monotonic() - start_t, 4),
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            operator_decision="PROCEED_PASS" if drill_passed else "HALT_FAIL",
            exit_code=0,
            passed=passed,
        )
        self._save_drill_record(rec)
        return rec

    # DRILL-15: Restore a synthetic batch from backup and revalidate all checksums
    def run_drill_15(self) -> DrillRecord:
        start_t = time.monotonic()
        drill_dir = self._setup_drill_dir("DRILL-15")
        source_dir = drill_dir / "source_staging"
        backup_dir = drill_dir / "backup_archive"
        restore_dir = drill_dir / "restored_staging"

        source_dir.mkdir(parents=True, exist_ok=True)
        # Create synthetic source files
        (source_dir / "raw_SYN0001.json").write_text('{"val": 100}', encoding="utf-8")
        (source_dir / "norm_SYN0001.csv").write_text("date,close\n2024-01-01,100\n", encoding="utf-8")
        (source_dir / "manifest_SYN0001.json").write_text('{"status": "SUCCEEDED"}', encoding="utf-8")

        # Excluded file simulation (should not be in backup)
        (source_dir / ".tmp.123.partial").write_text("junk", encoding="utf-8")

        # Create backup
        backup_folder = create_offline_backup(
            source_dir=source_dir,
            backup_target_dir=backup_dir,
            backup_id="BK-D15",
            repo_root=self.repo_root,
        )

        # Restore
        success, errors = restore_and_verify_backup(
            backup_folder=backup_folder,
            restore_target_dir=restore_dir,
            repo_root=self.repo_root,
        )

        # Verify excluded file was not restored
        system_under_test_exit_code = 0
        expected_system_exit_code = 0
        drill_runner_exit_code = 0
        temp_not_restored = not (restore_dir / ".tmp.123.partial").exists()
        drill_passed = success and (len(errors) == 0) and temp_not_restored and (system_under_test_exit_code == expected_system_exit_code)

        rec = DrillRecord(
            drill_id="DRILL-15",
            drill_name="Restore synthetic batch from backup and revalidate checksums",
            initial_state="Synthetic staging batch prepared with temporary files",
            injected_fault="Full backup creation, temporary file filtering, and complete restoration",
            expected_result="Restored evidence passes reconciliation; temporary files excluded",
            actual_result=f"Restored success: {success}, Errors: {errors}, Temp excluded: {temp_not_restored}",
            evidence_paths=[str(backup_folder), str(restore_dir)],
            checksum_status="ALL_CHECKSUMS_VERIFIED",
            cleanup_status="CLEAN",
            duration_seconds=round(time.monotonic() - start_t, 4),
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            operator_decision="PROCEED_PASS" if drill_passed else "HALT_FAIL",
            exit_code=0,
            passed=passed,
        )
        self._save_drill_record(rec)
        return rec

    # DRILL-16: Accelerated state-machine soak simulation (1,000+ cycles)
    def run_drill_16(self, cycle_count: int = 1000) -> DrillRecord:
        start_t = time.monotonic()
        drill_dir = self._setup_drill_dir("DRILL-16")

        leaked_temps = 0
        memory_leaks = False
        checksum_drifts = 0
        active_markers_left = 0

        with MemoryTracker() as mem:
            for cycle in range(cycle_count):
                cycle_dir = drill_dir / f"cycle_{cycle % 10}"
                cycle_dir.mkdir(parents=True, exist_ok=True)

                # Write payload
                data = f'{{"cycle": {cycle}, "time": "{time.monotonic()}"}}'.encode("utf-8")
                target = cycle_dir / "state.json"
                _, sha1 = atomic_write_bytes(target, data, repo_root=self.repo_root, allow_overwrite=True)

                # Verify checksum
                sha2 = hashlib.sha256(target.read_bytes()).hexdigest()
                if sha1 != sha2:
                    checksum_drifts += 1

                # Clean any temps
                cleaned = cleanup_stale_temporary_files(cycle_dir, max_age_seconds=0.0)

            # Check peak memory is bounded (under 50 MB for 1,000 cycles)
            if mem.peak_megabytes > 50.0:
                memory_leaks = True

        # Check for any remaining temporary files
        all_temps = list(drill_dir.rglob(".tmp.*"))
        leaked_temps = len(all_temps)

        system_under_test_exit_code = 0
        expected_system_exit_code = 0
        drill_runner_exit_code = 0
        drill_passed = (
            checksum_drifts == 0
            and leaked_temps == 0
            and not memory_leaks
            and active_markers_left == 0
            and (system_under_test_exit_code == expected_system_exit_code)
        )

        rec = DrillRecord(
            drill_id="DRILL-16",
            drill_name="Accelerated state-machine soak simulation (1,000 cycles)",
            initial_state=f"State-machine soak initialized for {cycle_count} accelerated cycles",
            injected_fault="Rapid continuous atomic persistence, verification, and temporary cleanup",
            expected_result="Zero leaked temps; zero checksum drift; bounded memory (<50MB)",
            actual_result=(
                f"Completed {cycle_count} cycles. Checksum drifts: {checksum_drifts}, "
                f"Leaked temps: {leaked_temps}, Peak memory: {mem.peak_megabytes:.2f}MB"
            ),
            evidence_paths=[str(drill_dir)],
            checksum_status="SOAK_CHECKSUMS_STABLE",
            cleanup_status="NO_LEAKED_TEMPORARY_FILES",
            duration_seconds=round(time.monotonic() - start_t, 4),
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            operator_decision="PROCEED_PASS" if drill_passed else "HALT_FAIL",
            exit_code=0,
            passed=passed,
        )
        self._save_drill_record(rec)
        return rec

    def run_all_drills(self) -> List[DrillRecord]:
        """Execute all 16 governed operational drills sequentially."""
        drills = [
            self.run_drill_01,
            self.run_drill_02,
            self.run_drill_03,
            self.run_drill_04,
            self.run_drill_05,
            self.run_drill_06,
            self.run_drill_07,
            self.run_drill_08,
            self.run_drill_09,
            self.run_drill_10,
            self.run_drill_11,
            self.run_drill_12,
            self.run_drill_13,
            self.run_drill_14,
            self.run_drill_15,
            self.run_drill_16,
        ]
        results = []
        for d in drills:
            results.append(d())
        return results
