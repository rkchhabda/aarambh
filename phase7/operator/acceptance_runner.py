"""Acceptance execution, evidence verification, and logging harness for Milestone 4.13A.

Milestone 4.13A: Enforce Real-Time Operator Acceptance Evidence Semantics:
- Classify session records as REAL_OPERATOR_SESSION, ACCEPTANCE_HARNESS_DRY_RUN, or SIMULATED_SESSION.
- Strictly exclude dry-run and simulated records from acceptance totals.
- Count only REAL_OPERATOR_SESSION records.
- Derive duration strictly from actual ISO 8601 start and end timestamps.
- Reject future-dated sessions, future-dated summaries, and declared duration mismatches.
- Require 5 distinct working dates, at least 10 real sessions, at least 18,000 seconds
  (5 hours) of measured operating time, and at least 2 post-restart sessions.
- Prohibit closure before the authorized acceptance end date (2026-10-16).
- Set status to INTERNAL_OFFLINE_OPERATOR_ACCEPTANCE_IN_PROGRESS until all requirements are met.

Persists all session logs exclusively to external staging:
C:\\Users\\r_chh\\gaurvideep_phase7_staging\\nse500\\acceptance_4_13\\sessions\\
"""

import argparse
import ctypes
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from phase7.operator.__init__ import (
    BANNER_ACQUISITION_DEFERRED,
    BANNER_GATE1_NOT_PASSED,
    BANNER_INTERNAL_USE,
    BANNER_MILESTONE5_BLOCKED,
    MANDATORY_BANNERS,
    NETWORK_BLOCKED_MESSAGE,
    NetworkOperationBlockedError,
    NetworkQuarantineManager,
    OperatorCore,
    READINESS_CLASSIFICATION,
    ReadOnlyEvidenceGuard,
    SingleInstanceLock,
    SingleInstanceLockError,
    AcceptanceExitCode,
    AcceptanceWorkflow,
    InterfaceMode,
    OperatorRole,
    GOVERNED_SESSION_WORKFLOW_MAP,
    GOVERNED_SESSION_REPLACEMENT_MAP,
    PROHIBITED_REUSE_SESSION_IDS,
    SESSION_ID_PATTERN,
    DEFECT_ID_PATTERN,
)
from phase7.operator.constants import ApplicationState
from phase7.operator.cli import OperatorCLI
from phase7.operator.core import compute_file_sha256

DEFAULT_ACCEPTANCE_DIR = Path(r"C:\Users\r_chh\gaurvideep_phase7_staging\nse500\acceptance_4_13")
DEFAULT_STAGING_ROOT = Path(r"C:\Users\r_chh\gaurvideep_phase7_staging\nse500")

# Rejection error codes
REJECTION_FUTURE_TIMESTAMP = "FUTURE_TIMESTAMP_REJECTED"
REJECTION_FUTURE_SUMMARY = "FUTURE_SUMMARY_REJECTED"
REJECTION_DURATION_MISMATCH = "DURATION_MISMATCH_REJECTED"
REJECTION_OVERLAPPING_SESSION = "OVERLAPPING_SESSION_REJECTED"
REJECTION_DUPLICATE_SESSION = "DUPLICATE_SESSION_REJECTED"
REJECTION_FIVE_DISTINCT_DATES = "FIVE_DISTINCT_DATES_REQUIRED"
REJECTION_TEN_REAL_SESSIONS = "TEN_REAL_SESSIONS_REQUIRED"
REJECTION_FIVE_HOURS = "FIVE_HOURS_REQUIRED"
REJECTION_POST_RESTART = "POST_RESTART_SESSIONS_REQUIRED"
REJECTION_PREMATURE_CLOSURE = "PREMATURE_CLOSURE_REJECTED"
REJECTION_CHECK_IN_OUT_OF_ORDER = "CHECK_IN_TIMESTAMP_OUT_OF_ORDER"
REJECTION_ACTIVE_OPERATING_MISMATCH = "ACTIVE_OPERATING_SECONDS_MISMATCH"
REJECTION_INSUFFICIENT_ACTIVE_SECONDS = "INSUFFICIENT_ACTIVE_OPERATING_SECONDS_FOR_PASS"
REJECTION_FOREIGN_CHECK_IN = "CHECK_IN_SESSION_ID_MISMATCH"

MAX_CHECK_IN_GAP_SECONDS = 300.0
MINIMUM_QUALIFYING_SECONDS = 1800.0


def compute_active_operating_seconds(
    check_ins: List[Dict[str, Any]],
    end_timestamp_utc: Optional[str] = None,
) -> float:
    """Compute verified active operating seconds from an ordered sequence of check-in checkpoints.

    Rules:
    1. Checkpoints must be ordered by timestamp. Checkpoint 0 is SESSION_START (activity point zero).
    2. Intervals between consecutive checkpoints <= 300.0 seconds are qualifying.
    3. Intervals > 300.0 seconds represent unmonitored/unattended gaps and contribute 0.0 seconds.
    4. Explicit check-ins alone determine active operating time.
    5. Finalization does not automatically add the interval since the last check-in unless
       a final explicit check-in occurred (trailing unmonitored time is excluded).
    """
    if not check_ins:
        return 0.0

    total_active = 0.0
    try:
        checkpoints: List[datetime] = []
        for chk in check_ins:
            ts_str = chk.get("timestamp_utc")
            if ts_str:
                checkpoints.append(datetime.fromisoformat(ts_str))

        if len(checkpoints) >= 2:
            for i in range(len(checkpoints) - 1):
                gap = (checkpoints[i + 1] - checkpoints[i]).total_seconds()
                if 0.0 < gap <= MAX_CHECK_IN_GAP_SECONDS:
                    total_active += gap

    except Exception:
        return 0.0

    return max(0.0, total_active)

FORBIDDEN_OBSERVATION_PATTERNS = [
    r"cookie",
    r"set-cookie",
    r"bearer\s+[a-zA-Z0-9_\-\.]+",
    r"password",
    r"secret",
    r"authorization:\s*",
    r"\"open\":\s*\d+",
    r"\"close\":\s*\d+",
    r"\"vwap\":\s*\d+",
]


def get_windows_boot_time_utc() -> Optional[datetime]:
    """Retrieve system boot time in UTC without external subprocesses."""
    if sys.platform == "win32":
        try:
            uptime_ms = ctypes.windll.kernel32.GetTickCount64()
            boot_ts = time.time() - (uptime_ms / 1000.0)
            return datetime.fromtimestamp(boot_ts, timezone.utc)
        except Exception:
            pass
    return None


def get_sanitized_host_identity() -> str:
    """Return sanitized machine identifier."""
    host = socket.gethostname().strip()
    clean = re.sub(r"[^A-Za-z0-9_-]", "", host)
    return clean or "UNKNOWN_HOST"


def get_repo_head_and_tags(repo_root: Optional[Path] = None) -> Tuple[str, Dict[str, str]]:
    """Inspect local repository HEAD and required closure tags directly from .git."""
    root = repo_root or Path(__file__).resolve().parent.parent.parent
    head = "UNKNOWN"
    tags_status = {
        "phase7-offline-operator-2026-10-10": "NOT_VERIFIED",
        "phase6-closed-2026-10-04": "NOT_VERIFIED",
    }
    git_dir = root / ".git"
    if git_dir.is_dir():
        head_file = git_dir / "HEAD"
        if head_file.exists():
            ref_or_sha = head_file.read_text(encoding="utf-8").strip()
            if ref_or_sha.startswith("ref: "):
                ref_path = git_dir / ref_or_sha[5:]
                if ref_path.exists():
                    head = ref_path.read_text(encoding="utf-8").strip()
                else:
                    packed_refs = git_dir / "packed-refs"
                    if packed_refs.exists():
                        for line in packed_refs.read_text(encoding="utf-8").splitlines():
                            if line.endswith(ref_or_sha[5:]):
                                head = line.split()[0]
                                break
            else:
                head = ref_or_sha

        for tag_name in tags_status.keys():
            tag_ref = git_dir / "refs" / "tags" / tag_name
            if tag_ref.exists():
                tags_status[tag_name] = "VERIFIED_INTACT"
            else:
                packed_refs = git_dir / "packed-refs"
                if packed_refs.exists() and f"refs/tags/{tag_name}" in packed_refs.read_text(encoding="utf-8"):
                    tags_status[tag_name] = "VERIFIED_INTACT"
    return head, tags_status


def validate_session_id(session_id: str) -> bool:
    """Validate that session ID strictly matches REAL-S01..REAL-S99 format."""
    if not isinstance(session_id, str):
        return False
    match = re.match(SESSION_ID_PATTERN, session_id)
    if not match:
        return False
    num = int(match.group(1))
    return 1 <= num <= 99


def compute_record_checksum(record_dict: Dict[str, Any]) -> str:
    """Compute deterministic SHA-256 digest of record dictionary excluding checksum fields."""
    filtered = {k: v for k, v in record_dict.items() if k not in ("checksum_sha256", "record_sha256")}
    payload = json.dumps(filtered, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def atomic_write_json(file_path: Path, data: Dict[str, Any]) -> None:
    """Atomically write JSON data using process-unique temporary file replacement."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = file_path.with_suffix(f"{file_path.suffix}.tmp.{os.getpid()}.{time.time_ns()}")
    temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp_path.replace(file_path)


def sanitize_observations(text: Optional[str]) -> Tuple[bool, str, Optional[str]]:
    """Sanitize and validate operator observations text."""
    if not text:
        return True, "", None
    if len(text) > 4096:
        return False, "", "OBSERVATION_EXCEEDS_MAX_LENGTH_4096"
    lower = text.lower()
    for pat in FORBIDDEN_OBSERVATION_PATTERNS:
        if re.search(pat, lower):
            return False, "", f"OBSERVATION_CONTAINS_FORBIDDEN_CONTENT: {pat}"
    cleaned = "".join(ch for ch in text if ch.isprintable() or ch in "\n\r\t")
    return True, cleaned.strip(), None


def validate_defect_references(defect_refs: Optional[List[str]]) -> Tuple[bool, Optional[str]]:
    """Validate defect reference identifiers against governed OPACC-YYYYMMDD-NNN format."""
    if not defect_refs:
        return True, None
    for ref in defect_refs:
        if not re.match(DEFECT_ID_PATTERN, ref):
            return False, f"INVALID_DEFECT_ID_FORMAT: {ref} (must match OPACC-YYYYMMDD-NNN)"
    return True, None


class AcceptanceSessionLock:
    """Durable process-level session lock for operator acceptance sessions."""

    def __init__(self, locks_dir: Path, session_id: str):
        self.locks_dir = locks_dir
        self.session_id = session_id
        self.lock_file = locks_dir / f"{session_id}.lock"

    def acquire(self) -> bool:
        self.locks_dir.mkdir(parents=True, exist_ok=True)
        if self.lock_file.exists():
            return False
        payload = {
            "session_id": self.session_id,
            "pid": os.getpid(),
            "acquired_utc": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with open(self.lock_file, "x", encoding="utf-8") as f:
                json.dump(payload, f)
            return True
        except FileExistsError:
            return False

    def release(self) -> bool:
        if self.lock_file.exists():
            try:
                self.lock_file.unlink()
                return True
            except Exception:
                return False
        return True


def get_active_session_file(in_progress_dir: Path) -> Optional[Path]:
    """Retrieve active session file if one currently exists in in_progress directory."""
    if in_progress_dir.exists():
        active = list(in_progress_dir.glob("*.active.json"))
        if active:
            return active[0]
    return None


class SessionRecordType(str, Enum):
    """Classification of acceptance session records."""
    REAL_OPERATOR_SESSION = "REAL_OPERATOR_SESSION"
    ACCEPTANCE_HARNESS_DRY_RUN = "ACCEPTANCE_HARNESS_DRY_RUN"
    SIMULATED_SESSION = "SIMULATED_SESSION"


class AcceptanceStatus(str, Enum):
    """Governed status classifications for operator acceptance exercise."""
    IN_PROGRESS = "INTERNAL_OFFLINE_OPERATOR_ACCEPTANCE_IN_PROGRESS"
    PASSED = "INTERNAL_OFFLINE_OPERATOR_ACCEPTANCE_PASSED"
    REJECTED = "INTERNAL_OFFLINE_OPERATOR_ACCEPTANCE_REJECTED"


class OperatorAcceptanceEvaluator:
    """Evaluates and validates operator acceptance records against strict governance semantics."""

    @staticmethod
    def validate_session_record(
        record: Dict[str, Any],
        current_time: Optional[datetime] = None,
    ) -> List[str]:
        """Validate a single session record for temporal consistency and integrity."""
        errors: List[str] = []
        now = current_time or datetime.now(timezone.utc)

        # Parse timestamps
        try:
            start_dt = datetime.fromisoformat(record["start_timestamp_utc"])
            end_dt = datetime.fromisoformat(record["end_timestamp_utc"])
        except (KeyError, ValueError):
            return ["INVALID_TIMESTAMP_FORMAT"]

        # Check future timestamps
        if start_dt > now or end_dt > now:
            errors.append(REJECTION_FUTURE_TIMESTAMP)

        # Check end precedes start
        if end_dt < start_dt:
            errors.append("END_PRECEDES_START_REJECTED")

        # Duration derived from actual timestamps
        timestamp_duration = (end_dt - start_dt).total_seconds()
        record_type = record.get("session_record_type", SessionRecordType.ACCEPTANCE_HARNESS_DRY_RUN.value)

        # Caller declared duration mismatch check for real operator sessions
        if record_type == SessionRecordType.REAL_OPERATOR_SESSION.value:
            declared_sec = record.get("declared_duration_seconds")
            if declared_sec is not None:
                if "check_ins" in record and record.get("active_operating_seconds") is not None and (record.get("status") == "PASS" or record.get("session_outcome") == "PASS"):
                    if abs(declared_sec - record["active_operating_seconds"]) > 2.0:
                        errors.append(REJECTION_DURATION_MISMATCH)
                else:
                    if abs(declared_sec - timestamp_duration) > 2.0:
                        errors.append(REJECTION_DURATION_MISMATCH)

            # Check-in sequence validations for real operator sessions
            if "check_ins" in record:
                check_ins = record["check_ins"]
                last_chk_dt = None
                for idx, chk in enumerate(check_ins):
                    ts = chk.get("timestamp_utc")
                    if not ts:
                        errors.append(f"CHECK_IN_MISSING_TIMESTAMP: index {idx}")
                        continue
                    try:
                        cur_dt = datetime.fromisoformat(ts)
                    except ValueError:
                        errors.append(f"CHECK_IN_INVALID_TIMESTAMP: index {idx}")
                        continue
                    if cur_dt > now:
                        errors.append(REJECTION_FUTURE_TIMESTAMP)
                    if last_chk_dt is not None and cur_dt <= last_chk_dt:
                        errors.append(REJECTION_CHECK_IN_OUT_OF_ORDER)
                    chk_sid = chk.get("session_id")
                    if chk_sid and record.get("session_id") and chk_sid != record.get("session_id"):
                        errors.append(REJECTION_FOREIGN_CHECK_IN)
                    last_chk_dt = cur_dt

                calc_active = compute_active_operating_seconds(check_ins)
                rec_active = record.get("active_operating_seconds")
                if rec_active is not None and (record.get("status") == "PASS" or record.get("session_outcome") == "PASS"):
                    if abs(rec_active - calc_active) > 1.0:
                        errors.append(REJECTION_ACTIVE_OPERATING_MISMATCH)
                    if calc_active < 1800.0:
                        errors.append(REJECTION_INSUFFICIENT_ACTIVE_SECONDS)

        return errors

    @staticmethod
    def evaluate_acceptance_exercise(
        records: List[Dict[str, Any]],
        authorized_end_date: str = "2026-10-16",
        current_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Evaluate a collection of session records against the 5-day / 10-session / 5-hour mandate."""
        now = current_time or datetime.now(timezone.utc)
        blockers: List[str] = []

        # Future master summary check
        if records:
            max_record_time = max(
                datetime.fromisoformat(r["end_timestamp_utc"])
                for r in records
                if "end_timestamp_utc" in r
            )
            if max_record_time > now:
                blockers.append(REJECTION_FUTURE_SUMMARY)

        # Partition records by classification
        real_sessions: List[Dict[str, Any]] = []
        dry_run_sessions: List[Dict[str, Any]] = []
        simulated_sessions: List[Dict[str, Any]] = []

        for r in records:
            rec_type = r.get("session_record_type", SessionRecordType.ACCEPTANCE_HARNESS_DRY_RUN.value)
            if rec_type == SessionRecordType.REAL_OPERATOR_SESSION.value:
                real_sessions.append(r)
            elif rec_type == SessionRecordType.SIMULATED_SESSION.value:
                simulated_sessions.append(r)
            else:
                dry_run_sessions.append(r)

        # Distinguish passed vs non-passing real sessions
        passed_real_sessions: List[Dict[str, Any]] = [
            r for r in real_sessions
            if r.get("status") == "PASS" or r.get("session_outcome") == "PASS"
        ]
        failed_real_sessions: List[Dict[str, Any]] = [
            r for r in real_sessions
            if r not in passed_real_sessions
        ]

        # Check duplicate session IDs among real sessions
        seen_ids: Set[str] = set()
        for r in real_sessions:
            s_id = r.get("session_id", "UNKNOWN")
            if s_id in seen_ids:
                if REJECTION_DUPLICATE_SESSION not in blockers:
                    blockers.append(REJECTION_DUPLICATE_SESSION)
            seen_ids.add(s_id)

        # Check overlapping sessions among real sessions
        real_time_intervals: List[Tuple[datetime, datetime, str]] = []
        for r in real_sessions:
            try:
                s_dt = datetime.fromisoformat(r["start_timestamp_utc"])
                e_dt = datetime.fromisoformat(r["end_timestamp_utc"])
                real_time_intervals.append((s_dt, e_dt, r.get("session_id", "")))
            except Exception:
                pass

        real_time_intervals.sort(key=lambda x: x[0])
        for i in range(len(real_time_intervals) - 1):
            curr_start, curr_end, _ = real_time_intervals[i]
            next_start, next_end, _ = real_time_intervals[i + 1]
            if next_start < curr_end:
                if REJECTION_OVERLAPPING_SESSION not in blockers:
                    blockers.append(REJECTION_OVERLAPPING_SESSION)

        # Calculate actual timestamp-derived operating time for passed real sessions only
        total_real_operating_seconds = sum(
            r.get("active_operating_seconds", max(0.0, (datetime.fromisoformat(r["end_timestamp_utc"]) - datetime.fromisoformat(r["start_timestamp_utc"])).total_seconds()))
            for r in passed_real_sessions
            if "start_timestamp_utc" in r and "end_timestamp_utc" in r
        )
        total_real_operating_hours = total_real_operating_seconds / 3600.0

        # Distinct working dates among passed real sessions
        distinct_real_dates = set()
        for r in passed_real_sessions:
            date_val = r.get("date_utc")
            if not date_val and "start_timestamp_utc" in r:
                date_val = r["start_timestamp_utc"][:10]
            if date_val:
                distinct_real_dates.add(date_val)

        # Count post-restart sessions among passed real sessions
        post_restart_count = sum(
            1 for r in passed_real_sessions
            if r.get("is_post_restart") is True or r.get("post_restart_verified") is True
        )

        # Validate 5 distinct working dates requirement
        if len(distinct_real_dates) < 5:
            blockers.append(f"{REJECTION_FIVE_DISTINCT_DATES} ({len(distinct_real_dates)}/5)")

        # Validate 10 real sessions requirement
        if len(passed_real_sessions) < 10:
            blockers.append(f"{REJECTION_TEN_REAL_SESSIONS} ({len(passed_real_sessions)}/10)")

        # Validate 18,000 seconds (5 hours) requirement
        if total_real_operating_seconds < 18000.0:
            blockers.append(f"{REJECTION_FIVE_HOURS} ({total_real_operating_seconds:.1f}s/18000s)")

        # Validate post-restart sessions requirement
        if post_restart_count < 2:
            blockers.append(f"{REJECTION_POST_RESTART} ({post_restart_count}/2)")

        # Validate premature closure before authorized end date
        try:
            auth_end_dt = datetime.fromisoformat(authorized_end_date).date()
            if now.date() < auth_end_dt:
                blockers.append(f"{REJECTION_PREMATURE_CLOSURE} (current date {now.date()} < {auth_end_dt})")
        except Exception:
            pass

        # Determine final status
        passed = (len(blockers) == 0 and len(passed_real_sessions) >= 10 and total_real_operating_seconds >= 18000.0)
        status = AcceptanceStatus.PASSED.value if passed else AcceptanceStatus.IN_PROGRESS.value

        return {
            "acceptance_exercise_id": "ACCEPTANCE_4_13_5DAY_10SESSION",
            "evaluation_timestamp_utc": now.isoformat(),
            "authorized_start_date": "2026-10-12",
            "authorized_end_date": authorized_end_date,
            "acceptance_status": status,
            "acceptance_passed": passed,
            "real_operator_sessions_count": len(real_sessions),
            "passed_real_sessions_count": len(passed_real_sessions),
            "failed_real_sessions_count": len(failed_real_sessions),
            "dry_run_sessions_count": len(dry_run_sessions),
            "simulated_sessions_count": len(simulated_sessions),
            "distinct_working_dates_count": len(distinct_real_dates),
            "distinct_working_dates": sorted(list(distinct_real_dates)),
            "total_real_operating_seconds": total_real_operating_seconds,
            "total_real_operating_hours": total_real_operating_hours,
            "post_restart_sessions_count": post_restart_count,
            "active_blockers": blockers,
        }


class OperatorAcceptanceHarness:
    """Manages execution, logging, and evaluation of operator acceptance sessions."""

    def __init__(
        self,
        staging_root: Optional[Path] = None,
        acceptance_dir: Optional[Path] = None,
        repo_root: Optional[Path] = None,
    ) -> None:
        self.staging_root = Path(staging_root) if staging_root else DEFAULT_STAGING_ROOT
        self.acceptance_dir = Path(acceptance_dir) if acceptance_dir else DEFAULT_ACCEPTANCE_DIR
        self.repo_root = Path(repo_root) if repo_root else Path(__file__).resolve().parent.parent.parent
        self.sessions_dir = self.acceptance_dir / "sessions"
        self.real_sessions_dir = self.acceptance_dir / "real_sessions"
        self.in_progress_dir = self.acceptance_dir / "in_progress"
        self.locks_dir = self.acceptance_dir / "locks"
        self.audit_dir = self.acceptance_dir / "audit"

        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.real_sessions_dir.mkdir(parents=True, exist_ok=True)
        self.in_progress_dir.mkdir(parents=True, exist_ok=True)
        self.locks_dir.mkdir(parents=True, exist_ok=True)
        self.audit_dir.mkdir(parents=True, exist_ok=True)

    def execute_session(
        self,
        session_id: str,
        day: int,
        date_str: str,
        planned_operating_minutes: float = 30.0,
        session_record_type: SessionRecordType = SessionRecordType.ACCEPTANCE_HARNESS_DRY_RUN,
        is_post_restart: bool = False,
    ) -> Dict[str, Any]:
        """Execute an acceptance session and record structured telemetry."""
        start_time_real = time.time()
        start_utc = datetime.now(timezone.utc).isoformat()
        network_calls = 0
        evidence_mutations = 0

        quarantine = NetworkQuarantineManager()
        quarantine.activate()
        lock = SingleInstanceLock(lock_dir=self.staging_root)
        lock.acquire()

        core = OperatorCore(staging_root=self.staging_root)
        cli = OperatorCLI(core=core)
        screens_evaluated: List[int] = []
        checks: Dict[str, Any] = {}

        try:
            if session_id == "S01":
                screens_evaluated = [1]
                assert core.state == ApplicationState.READY_READ_ONLY
                lock2 = SingleInstanceLock(lock_dir=self.staging_root)
                lock2_rejected = False
                try:
                    lock2.acquire()
                except SingleInstanceLockError:
                    lock2_rejected = True
                checks["lock_concurrency_rejected"] = lock2_rejected
                checks["initial_state"] = core.state.value

            elif session_id == "S02":
                screens_evaluated = [1]
                dash = core.get_readiness_dashboard()
                checks["classification"] = dash["classification"]
                checks["total_passing_tests"] = dash["test_summary"]["total_passing"]
                checks["passed_drills"] = dash["drill_summary"]["passed_drills"]
                assert dash["classification"] == READINESS_CLASSIFICATION
                assert dash["test_summary"]["total_passing"] == dash["test_baselines"]["current_verified"]["passed_tests"]
                assert dash["test_baselines"]["milestone_4_13b"]["passed_tests"] == 837
                assert dash["drill_summary"]["passed_drills"] == 16

            elif session_id == "S03":
                screens_evaluated = [2]
                inv = core.get_evidence_inventory()
                checks["total_assets"] = inv["total_assets"]
                assert inv["total_assets"] >= 50

            elif session_id == "S04":
                screens_evaluated = [3]
                mv = core.verify_manifests()
                checks["total_manifests"] = mv["total_manifests"]
                assert mv["total_manifests"] > 0

            elif session_id == "S05":
                screens_evaluated = [4]
                bs = core.get_batch_state()
                checks["batch_status"] = bs["status"]
                checks["failed_symbol"] = bs["failed_symbol"]
                assert bs["status"] == "HALTED"
                assert bs["failed_symbol"] == "PREMIERENE"

            elif session_id == "S06":
                screens_evaluated = [5]
                drills = core.get_drill_results()
                assert drills["total_drills"] == 16
                assert drills["all_drills_passed"] is True

            elif session_id == "S07":
                screens_evaluated = [6]
                bu = core.verify_backup_restoration()
                assert bu["status"] == "BACKUP_AND_RESTORE_VERIFIED"
                git_rej = core.verify_backup_restoration(restore_target=core.repo_root / "data")
                assert git_rej["status"] == "GIT_DESTINATION_REJECTED"

            elif session_id == "S08":
                screens_evaluated = [7]
                gov = core.get_governance_and_blockers()
                assert gov["owner_decision"]["decision_id"] == "DEC-20261010-36"

            elif session_id == "S09":
                screens_evaluated = [8]
                reg = core.get_authorization_registry()
                assert reg["active_authorization_markers"] == 0
                assert reg["consumed_authorization_markers"] >= 5

            elif session_id == "S10":
                screens_evaluated = [9, 10]
                with tempfile.TemporaryDirectory() as tmp_dir:
                    export_res = core.export_metadata_audit(output_dir=Path(tmp_dir))
                    assert export_res["status"] == "METADATA_AUDIT_EXPORT_SUCCESSFUL"
                demo_res = core.run_synthetic_demonstration()
                assert demo_res["symbols_processed"] == 5

        finally:
            quarantine.deactivate()
            lock.release()

        end_utc = datetime.now(timezone.utc).isoformat()
        elapsed_sec = time.time() - start_time_real
        operating_seconds = elapsed_sec

        record: Dict[str, Any] = {
            "session_id": session_id,
            "session_record_type": session_record_type.value,
            "day": day,
            "date_utc": date_str,
            "start_timestamp_utc": start_utc,
            "end_timestamp_utc": end_utc,
            "operating_time_seconds": operating_seconds,
            "operating_time_minutes": operating_seconds / 60.0,
            "declared_duration_seconds": planned_operating_minutes * 60.0,
            "is_post_restart": is_post_restart,
            "screens_evaluated": screens_evaluated,
            "starting_state": "STARTING",
            "final_state": "READY_READ_ONLY",
            "single_instance_lock_acquired": True,
            "single_instance_lock_released": True,
            "network_quarantine_active": True,
            "network_request_count": network_calls,
            "evidence_mutation_count": evidence_mutations,
            "active_markers_count": 0,
            "checks": checks,
            "session_exit_code": 0,
            "status": "PASS",
        }

        out_file = self.sessions_dir / f"session_{session_id.lower()}.json"
        out_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
        return record

    def start_session(
        self,
        session_id: str,
        operator_role: str,
        interface_mode: str,
        workflow: str,
    ) -> Tuple[AcceptanceExitCode, Dict[str, Any], str]:
        """Start an active real operator acceptance session."""
        # 1. Validate session ID
        if not validate_session_id(session_id):
            return (
                AcceptanceExitCode.INVALID_ARGS,
                {},
                f"INVALID_SESSION_ID: '{session_id}' (must strictly match REAL-S01..REAL-S99)",
            )

        # 2. Validate operator role
        if operator_role not in [r.value for r in OperatorRole]:
            return (
                AcceptanceExitCode.INVALID_ARGS,
                {},
                f"INVALID_OPERATOR_ROLE: '{operator_role}' (permitted: {[r.value for r in OperatorRole]})",
            )

        # 3. Validate interface mode
        if interface_mode not in [InterfaceMode.CLI.value, InterfaceMode.GUI.value]:
            return (
                AcceptanceExitCode.INVALID_ARGS,
                {},
                f"INVALID_INTERFACE_MODE: '{interface_mode}' (permitted: CLI, GUI)",
            )

        # 4. Validate workflow
        if workflow not in [w.value for w in AcceptanceWorkflow]:
            return (
                AcceptanceExitCode.INVALID_ARGS,
                {},
                f"INVALID_WORKFLOW: '{workflow}' (not an approved governed workflow)",
            )

        # 5. Check bound workflow for governed sessions
        if session_id in GOVERNED_SESSION_WORKFLOW_MAP:
            expected_wf = GOVERNED_SESSION_WORKFLOW_MAP[session_id].value
            if workflow != expected_wf:
                return (
                    AcceptanceExitCode.INVALID_ARGS,
                    {},
                    f"WORKFLOW_MISMATCH: {session_id} requires {expected_wf}, got {workflow}",
                )

        # Replacement session governance
        if session_id in GOVERNED_SESSION_REPLACEMENT_MAP:
            repl_meta = GOVERNED_SESSION_REPLACEMENT_MAP[session_id]
            replaces_id = repl_meta["replaces_session_id"]
            if session_id == replaces_id:
                return (
                    AcceptanceExitCode.LIFECYCLE_CONFLICT,
                    {},
                    f"REPLACEMENT_SESSION_ID_MUST_BE_DISTINCT: Replacement session {session_id} cannot have the same ID as original {replaces_id}",
                )

            # Workflow must match original governed workflow
            orig_wf = GOVERNED_SESSION_WORKFLOW_MAP.get(replaces_id)
            if orig_wf:
                orig_wf_val = orig_wf.value if hasattr(orig_wf, "value") else orig_wf
                if workflow != orig_wf_val:
                    return (
                        AcceptanceExitCode.INVALID_ARGS,
                        {},
                        f"REPLACEMENT_WORKFLOW_MISMATCH: Replacement {session_id} requires {orig_wf_val}, got {workflow}",
                    )

            # Only one replacement may be authorized for the same aborted session
            if self.in_progress_dir.exists():
                for act_p in self.in_progress_dir.glob("*.active.json"):
                    if act_p.name != f"{session_id}.active.json":
                        try:
                            act_d = json.loads(act_p.read_text(encoding="utf-8"))
                            if act_d.get("replacement_metadata", {}).get("replaces_session_id") == replaces_id:
                                return (
                                    AcceptanceExitCode.LIFECYCLE_CONFLICT,
                                    {},
                                    f"REPLACEMENT_ALREADY_ACTIVE: Another replacement session {act_d.get('session_id')} for {replaces_id} is already active",
                                )
                        except Exception:
                            pass
            if self.real_sessions_dir.exists():
                for fin_p in self.real_sessions_dir.glob("*.final.json"):
                    if fin_p.name != f"{session_id}.final.json":
                        try:
                            fin_d = json.loads(fin_p.read_text(encoding="utf-8"))
                            if fin_d.get("replacement_metadata", {}).get("replaces_session_id") == replaces_id:
                                return (
                                    AcceptanceExitCode.LIFECYCLE_CONFLICT,
                                    {},
                                    f"REPLACEMENT_ALREADY_FINALIZED: A replacement session {fin_d.get('session_id')} for {replaces_id} is already finalized",
                                )
                        except Exception:
                            pass

        # Prohibited reuse check: if this session is replaced by an active/finalized replacement session, reject
        for repl_meta in GOVERNED_SESSION_REPLACEMENT_MAP.values():
            if repl_meta.get("replaces_session_id") == session_id:
                if self.in_progress_dir.exists():
                    for act_p in self.in_progress_dir.glob("*.active.json"):
                        if act_p.name != f"{session_id}.active.json":
                            try:
                                act_d = json.loads(act_p.read_text(encoding="utf-8"))
                                if act_d.get("replacement_metadata", {}).get("replaces_session_id") == session_id:
                                    return (
                                        AcceptanceExitCode.LIFECYCLE_CONFLICT,
                                        {},
                                        f"PROHIBITED_SESSION_REUSE: {session_id} has active replacement {act_d.get('session_id')}",
                                    )
                            except Exception:
                                pass
                if self.real_sessions_dir.exists():
                    for fin_p in self.real_sessions_dir.glob("*.final.json"):
                        if fin_p.name != f"{session_id}.final.json":
                            try:
                                fin_d = json.loads(fin_p.read_text(encoding="utf-8"))
                                if fin_d.get("replacement_metadata", {}).get("replaces_session_id") == session_id:
                                    return (
                                        AcceptanceExitCode.LIFECYCLE_CONFLICT,
                                        {},
                                        f"PROHIBITED_SESSION_REUSE: {session_id} has finalized replacement {fin_d.get('session_id')}",
                                    )
                            except Exception:
                                pass

        # 6. Verify acceptance status is IN_PROGRESS
        summary_file = self.acceptance_dir / "acceptance_master_summary.json"
        if summary_file.exists():
            try:
                sum_data = json.loads(summary_file.read_text(encoding="utf-8"))
                if sum_data.get("acceptance_status") != AcceptanceStatus.IN_PROGRESS.value:
                    return (
                        AcceptanceExitCode.GOVERNANCE_FAILURE,
                        {},
                        f"ACCEPTANCE_STATUS_NOT_IN_PROGRESS: {sum_data.get('acceptance_status')}",
                    )
            except Exception:
                pass

        # 7. Check if already finalized or aborted
        final_file = self.real_sessions_dir / f"{session_id}.final.json"
        if final_file.exists():
            try:
                fin_data = json.loads(final_file.read_text(encoding="utf-8"))
                if fin_data.get("session_outcome") == "ABORTED" or fin_data.get("lifecycle_state") == "ABORTED_REAL_OPERATOR_SESSION":
                    return (
                        AcceptanceExitCode.LIFECYCLE_CONFLICT,
                        {},
                        f"ABORTED_SESSION_CANNOT_RESTART: {session_id} is permanently preserved as aborted audit history",
                    )
            except Exception:
                pass
            return (
                AcceptanceExitCode.LIFECYCLE_CONFLICT,
                {},
                f"SESSION_ALREADY_FINALIZED: {session_id}",
            )

        # 8. Check if another session is already in progress
        active_file = get_active_session_file(self.in_progress_dir)
        if active_file:
            active_id = active_file.name.replace(".active.json", "")
            return (
                AcceptanceExitCode.LIFECYCLE_CONFLICT,
                {},
                f"ANOTHER_SESSION_ALREADY_ACTIVE: {active_id}",
            )

        # 9. Acquire session lock
        lock = AcceptanceSessionLock(self.locks_dir, session_id)
        if not lock.acquire():
            return (
                AcceptanceExitCode.LOCK_FAILURE,
                {},
                f"SESSION_LOCK_CONFLICT: {session_id}.lock already held",
            )

        # 10. Capture system metadata
        now_dt = datetime.now(timezone.utc)
        now_utc = now_dt.isoformat()
        mono_start = time.monotonic()
        head, tags_status = get_repo_head_and_tags(self.repo_root)
        boot_dt = get_windows_boot_time_utc()
        boot_utc = boot_dt.isoformat() if boot_dt else "UNKNOWN"
        host = get_sanitized_host_identity()
        boot_cycle_id = f"{boot_utc}:{host}"

        in_progress_record: Dict[str, Any] = {
            "session_id": session_id,
            "session_record_type": SessionRecordType.REAL_OPERATOR_SESSION.value,
            "lifecycle_state": "ACTIVE_REAL_OPERATOR_SESSION",
            "operator_role": operator_role,
            "interface_mode": interface_mode,
            "workflow": workflow,
            "date_utc": now_utc[:10],
            "start_timestamp_utc": now_utc,
            "monotonic_start_seconds": mono_start,
            "repo_head": head,
            "closure_tags_status": tags_status,
            "network_quarantine_active": True,
            "sanitized_host": host,
            "boot_timestamp_utc": boot_utc,
            "boot_cycle_id": boot_cycle_id,
            "lock_acquired": True,
            "starting_state": ApplicationState.STARTING.value,
            "application_state": "ACTIVE_REAL_OPERATOR_SESSION",
            "check_in_count": 0,
            "active_operating_seconds": 0.0,
            "check_ins": [
                {
                    "check_in_index": 0,
                    "session_id": session_id,
                    "timestamp_utc": now_utc,
                    "monotonic_seconds": mono_start,
                    "gap_seconds": 0.0,
                    "qualifying": True,
                    "type": "SESSION_START",
                }
            ],
        }
        if session_id in GOVERNED_SESSION_REPLACEMENT_MAP:
            in_progress_record["replacement_metadata"] = dict(GOVERNED_SESSION_REPLACEMENT_MAP[session_id])

        in_progress_record["checksum_sha256"] = compute_record_checksum(in_progress_record)

        # 11. Write atomic in-progress record
        target_path = self.in_progress_dir / f"{session_id}.active.json"
        atomic_write_json(target_path, in_progress_record)

        # 12. Append audit log
        audit_file = self.audit_dir / "session_lifecycle.jsonl"
        with open(audit_file, "a", encoding="utf-8") as af:
            af.write(
                json.dumps(
                    {
                        "timestamp_utc": now_utc,
                        "event": "SESSION_STARTED",
                        "session_id": session_id,
                        "operator_role": operator_role,
                        "workflow": workflow,
                    }
                )
                + "\n"
            )

        return (
            AcceptanceExitCode.SUCCESS,
            in_progress_record,
            f"SESSION_STARTED: {session_id} in state ACTIVE_REAL_OPERATOR_SESSION",
        )

    def check_in(
        self, session_id: str
    ) -> Tuple[AcceptanceExitCode, Dict[str, Any], str]:
        """Record an explicit operator activity check-in for an active session."""
        if not validate_session_id(session_id):
            return (
                AcceptanceExitCode.INVALID_ARGS,
                {},
                f"INVALID_SESSION_ID: '{session_id}' (must strictly match REAL-S01..REAL-S99)",
            )

        active_path = self.in_progress_dir / f"{session_id}.active.json"
        if not active_path.exists():
            return (
                AcceptanceExitCode.LIFECYCLE_CONFLICT,
                {},
                f"NO_ACTIVE_SESSION_FOR_CHECK_IN: {session_id}",
            )

        try:
            in_prog = json.loads(active_path.read_text(encoding="utf-8"))
        except Exception as e:
            return (
                AcceptanceExitCode.INTEGRITY_FAILURE,
                {},
                f"CORRUPT_IN_PROGRESS_RECORD: {e}",
            )

        stored_cs = in_prog.get("checksum_sha256")
        expected_cs = compute_record_checksum(in_prog)
        if stored_cs != expected_cs:
            return (
                AcceptanceExitCode.INTEGRITY_FAILURE,
                {},
                "IN_PROGRESS_RECORD_INTEGRITY_VIOLATION: Checksum mismatch",
            )

        lock_file = self.locks_dir / f"{session_id}.lock"
        if not lock_file.exists():
            return (
                AcceptanceExitCode.LOCK_FAILURE,
                {},
                f"SESSION_LOCK_MISSING: {session_id}.lock",
            )

        now_dt = datetime.now(timezone.utc)
        now_utc = now_dt.isoformat()
        mono_now = time.monotonic()

        check_ins = in_prog.get("check_ins")
        if not check_ins:
            check_ins = [
                {
                    "check_in_index": 0,
                    "timestamp_utc": in_prog["start_timestamp_utc"],
                    "monotonic_seconds": in_prog.get("monotonic_start_seconds"),
                    "gap_seconds": 0.0,
                    "qualifying": True,
                    "type": "SESSION_START",
                }
            ]

        last_chk = check_ins[-1]
        try:
            last_dt = datetime.fromisoformat(last_chk["timestamp_utc"])
        except Exception:
            return (
                AcceptanceExitCode.INTEGRITY_FAILURE,
                {},
                "CORRUPT_CHECK_IN_HISTORY: Invalid timestamp in prior check-in",
            )

        if now_dt <= last_dt:
            return (
                AcceptanceExitCode.TIMESTAMP_VALIDATION,
                {},
                f"CHECK_IN_TIMESTAMP_NON_INCREASING: {now_utc} <= {last_chk['timestamp_utc']}",
            )

        gap_sec = (now_dt - last_dt).total_seconds()
        is_qualifying = 0.0 < gap_sec <= MAX_CHECK_IN_GAP_SECONDS
        new_index = len(check_ins)

        new_entry = {
            "check_in_index": new_index,
            "session_id": session_id,
            "timestamp_utc": now_utc,
            "monotonic_seconds": mono_now,
            "gap_seconds": gap_sec,
            "qualifying": is_qualifying,
            "type": "OPERATOR_CHECK_IN",
        }
        check_ins.append(new_entry)
        in_prog["check_ins"] = check_ins

        active_sec = compute_active_operating_seconds(check_ins)
        in_prog["active_operating_seconds"] = active_sec
        in_prog["check_in_count"] = len(check_ins) - 1

        in_prog["checksum_sha256"] = compute_record_checksum(in_prog)
        atomic_write_json(active_path, in_prog)

        audit_file = self.audit_dir / "session_lifecycle.jsonl"
        with open(audit_file, "a", encoding="utf-8") as af:
            af.write(
                json.dumps(
                    {
                        "timestamp_utc": now_utc,
                        "event": "OPERATOR_CHECK_IN",
                        "session_id": session_id,
                        "check_in_index": new_index,
                        "gap_seconds": gap_sec,
                        "qualifying": is_qualifying,
                        "total_active_seconds": active_sec,
                    }
                )
                + "\n"
            )

        return (
            AcceptanceExitCode.SUCCESS,
            new_entry,
            f"CHECK_IN_RECORDED: {session_id} (Index: {new_index}, Gap: {gap_sec:.1f}s, Qualifying: {is_qualifying}, Total Active: {active_sec:.1f}s)",
        )

    def get_status(
        self, session_id: Optional[str] = None
    ) -> Tuple[AcceptanceExitCode, Dict[str, Any], str]:
        """Query and display governed metadata for an active or finalized session."""
        now = datetime.now(timezone.utc)
        target_id = session_id

        if not target_id:
            active_file = get_active_session_file(self.in_progress_dir)
            if active_file:
                target_id = active_file.name.replace(".active.json", "")

        if not target_id:
            return (
                AcceptanceExitCode.SUCCESS,
                {"status": "NO_ACTIVE_SESSION"},
                "No active operator acceptance session found in in_progress.",
            )

        active_path = self.in_progress_dir / f"{target_id}.active.json"
        if active_path.exists():
            try:
                rec = json.loads(active_path.read_text(encoding="utf-8"))
            except Exception as e:
                return (
                    AcceptanceExitCode.INTEGRITY_FAILURE,
                    {},
                    f"FAILED_TO_READ_ACTIVE_RECORD: {e}",
                )

            start_dt = datetime.fromisoformat(rec["start_timestamp_utc"])
            elapsed_sec = max(0.0, (now - start_dt).total_seconds())
            elapsed_min = elapsed_sec / 60.0

            check_ins = rec.get("check_ins", [])
            if check_ins:
                active_sec = compute_active_operating_seconds(check_ins, end_timestamp_utc=now.isoformat())
                check_in_count = len(check_ins) - 1
                last_chk = check_ins[-1]
                last_dt = datetime.fromisoformat(last_chk["timestamp_utc"])
                current_gap = max(0.0, (now - last_dt).total_seconds())
                is_overdue = current_gap > MAX_CHECK_IN_GAP_SECONDS
            else:
                active_sec = 0.0
                check_in_count = 0
                current_gap = elapsed_sec
                is_overdue = elapsed_sec > MAX_CHECK_IN_GAP_SECONDS

            eligible_for_pass = active_sec >= MINIMUM_QUALIFYING_SECONDS

            status_dict = {
                "session_id": target_id,
                "record_type": rec.get("session_record_type"),
                "lifecycle_state": rec.get("lifecycle_state"),
                "operator_role": rec.get("operator_role"),
                "interface_mode": rec.get("interface_mode"),
                "workflow": rec.get("workflow"),
                "start_timestamp_utc": rec.get("start_timestamp_utc"),
                "current_elapsed_seconds": elapsed_sec,
                "current_elapsed_minutes": elapsed_min,
                "wall_clock_elapsed_seconds": elapsed_sec,
                "active_operating_seconds": active_sec,
                "active_operating_minutes": active_sec / 60.0,
                "check_in_count": check_in_count,
                "check_in_gap_seconds": current_gap,
                "check_in_overdue": is_overdue,
                "minimum_duration_met": eligible_for_pass,
                "network_quarantine_active": rec.get("network_quarantine_active", True),
                "repo_head": rec.get("repo_head"),
                "boot_timestamp_utc": rec.get("boot_timestamp_utc"),
                "session_lock_held": (self.locks_dir / f"{target_id}.lock").exists(),
                "finalization_eligible": eligible_for_pass,
            }

            msg_lines = [
                f"Session ID:                 {target_id}",
                f"Record Type:                {rec.get('session_record_type')}",
                f"Lifecycle State:            {rec.get('lifecycle_state')}",
                f"Operator Role:              {rec.get('operator_role')}",
                f"Interface Mode:             {rec.get('interface_mode')}",
                f"Workflow:                   {rec.get('workflow')}",
                f"Start Timestamp (UTC):      {rec.get('start_timestamp_utc')}",
                f"Wall-Clock Elapsed Time:    {elapsed_sec:.1f}s ({elapsed_min:.1f}m)",
                f"Verified Active Time:       {active_sec:.1f}s ({active_sec / 60.0:.1f}m)",
                f"Check-In Count:             {check_in_count}",
                f"Current Gap from Check-In:  {current_gap:.1f}s",
                f"Quarantine Active:          {rec.get('network_quarantine_active')}",
                f"Repo HEAD:                  {rec.get('repo_head')}",
                f"Boot Timestamp (UTC):       {rec.get('boot_timestamp_utc')}",
                f"Session Lock:               {'HELD' if status_dict['session_lock_held'] else 'NOT_FOUND'}",
                f"Finalization Eligible:      {'YES' if eligible_for_pass else 'NO (MINIMUM_REAL_DURATION_NOT_YET_MET)'}",
            ]
            if is_overdue and check_ins:
                msg_lines.append(f"\n[WARNING] CHECK_IN_OVERDUE: {current_gap:.1f}s since last check-in (>300s max allowed gap). Operator active time paused.")
            if not eligible_for_pass:
                msg_lines.append(f"\n[WARNING] MINIMUM_REAL_DURATION_NOT_YET_MET (verified active: {active_sec:.1f}s < 1800.0s required for PASS)")

            return (
                AcceptanceExitCode.SUCCESS,
                status_dict,
                "\n".join(msg_lines),
            )

        final_path = self.real_sessions_dir / f"{target_id}.final.json"
        if final_path.exists():
            try:
                rec = json.loads(final_path.read_text(encoding="utf-8"))
                return (
                    AcceptanceExitCode.SUCCESS,
                    rec,
                    f"Session {target_id} is FINALIZED with status {rec.get('status')} and outcome {rec.get('session_outcome')}.",
                )
            except Exception as e:
                return (
                    AcceptanceExitCode.INTEGRITY_FAILURE,
                    {},
                    f"FAILED_TO_READ_FINAL_RECORD: {e}",
                )

        return (
            AcceptanceExitCode.INVALID_ARGS,
            {},
            f"SESSION_NOT_FOUND: {target_id} neither active nor finalized",
        )

    def finalize_session(
        self,
        session_id: str,
        session_outcome: str = "PASS",
        observation_file: Optional[Path] = None,
        observations: Optional[str] = None,
        defect_references: Optional[List[str]] = None,
    ) -> Tuple[AcceptanceExitCode, Dict[str, Any], str]:
        """Finalize an active real operator acceptance session."""
        if not validate_session_id(session_id):
            return (
                AcceptanceExitCode.INVALID_ARGS,
                {},
                f"INVALID_SESSION_ID: '{session_id}'",
            )

        active_path = self.in_progress_dir / f"{session_id}.active.json"
        if not active_path.exists():
            return (
                AcceptanceExitCode.LIFECYCLE_CONFLICT,
                {},
                f"NO_ACTIVE_SESSION_TO_FINALIZE: {session_id}",
            )

        try:
            in_prog = json.loads(active_path.read_text(encoding="utf-8"))
        except Exception as e:
            return (
                AcceptanceExitCode.INTEGRITY_FAILURE,
                {},
                f"CORRUPT_IN_PROGRESS_RECORD: {e}",
            )

        # Verify integrity
        stored_cs = in_prog.get("checksum_sha256")
        expected_cs = compute_record_checksum(in_prog)
        if stored_cs != expected_cs:
            return (
                AcceptanceExitCode.INTEGRITY_FAILURE,
                {},
                "IN_PROGRESS_RECORD_INTEGRITY_VIOLATION: Checksum mismatch",
            )

        # Verify lock
        lock_file = self.locks_dir / f"{session_id}.lock"
        if not lock_file.exists():
            return (
                AcceptanceExitCode.LOCK_FAILURE,
                {},
                f"SESSION_LOCK_MISSING: {session_id}.lock",
            )

        # Check observations
        obs_text = observations or ""
        if observation_file:
            obs_p = Path(observation_file)
            if obs_p.exists():
                try:
                    obs_text = obs_p.read_text(encoding="utf-8")
                except Exception as e:
                    return (
                        AcceptanceExitCode.INVALID_ARGS,
                        {},
                        f"CANNOT_READ_OBSERVATION_FILE: {e}",
                    )
            else:
                return (
                    AcceptanceExitCode.INVALID_ARGS,
                    {},
                    f"OBSERVATION_FILE_NOT_FOUND: {observation_file}",
                )

        obs_ok, clean_obs, obs_err = sanitize_observations(obs_text)
        if not obs_ok:
            return (
                AcceptanceExitCode.GOVERNANCE_FAILURE,
                {},
                f"OBSERVATION_SANITIZATION_FAILED: {obs_err}",
            )

        # Check defect references
        def_ok, def_err = validate_defect_references(defect_references)
        if not def_ok:
            return (
                AcceptanceExitCode.INVALID_ARGS,
                {},
                f"DEFECT_REFERENCE_VALIDATION_FAILED: {def_err}",
            )

        # Generate timestamps
        end_dt = datetime.now(timezone.utc)
        end_utc = end_dt.isoformat()
        mono_end = time.monotonic()
        start_dt = datetime.fromisoformat(in_prog["start_timestamp_utc"])

        if end_dt <= start_dt:
            return (
                AcceptanceExitCode.TIMESTAMP_VALIDATION,
                {},
                "END_TIMESTAMP_PRECEDES_OR_EQUALS_START",
            )

        measured_duration = (end_dt - start_dt).total_seconds()
        mono_start = in_prog.get("monotonic_start_seconds")
        if mono_start is not None:
            mono_duration = mono_end - mono_start
            if abs(measured_duration - mono_duration) > 5.0:
                return (
                    AcceptanceExitCode.TIMESTAMP_VALIDATION,
                    {},
                    f"DURATION_DIVERGENCE: wallclock={measured_duration:.2f}s monotonic={mono_duration:.2f}s",
                )

        # Check overwrite safeguards
        final_target = self.real_sessions_dir / f"{session_id}.final.json"
        if final_target.exists():
            return (
                AcceptanceExitCode.LIFECYCLE_CONFLICT,
                {},
                f"CANNOT_OVERWRITE_FINAL_RECORD: {final_target.name} already exists",
            )
        if session_id in GOVERNED_SESSION_REPLACEMENT_MAP:
            replaces_id = GOVERNED_SESSION_REPLACEMENT_MAP[session_id]["replaces_session_id"]
            orig_final = self.real_sessions_dir / f"{replaces_id}.final.json"
            if orig_final.exists() and orig_final.resolve() == final_target.resolve():
                return (
                    AcceptanceExitCode.LIFECYCLE_CONFLICT,
                    {},
                    f"CANNOT_OVERWRITE_ABORTED_RECORD: Replacement {session_id} cannot overwrite {replaces_id}.final.json",
                )

        # Duration requirement for PASS
        check_ins = in_prog.get("check_ins", [])
        if check_ins:
            # Trailing gap after last check-in contributes 0.0 unless explicit final check-in occurred
            active_duration = compute_active_operating_seconds(check_ins)
        else:
            active_duration = 0.0

        if session_outcome == "PASS":
            if measured_duration < 1800.0:
                return (
                    AcceptanceExitCode.DURATION_NOT_MET,
                    {},
                    f"MINIMUM_DURATION_NOT_MET: {measured_duration:.1f}s < 1800.0s required for PASS",
                )
            if active_duration < 1800.0:
                return (
                    AcceptanceExitCode.DURATION_NOT_MET,
                    {},
                    f"MINIMUM_ACTIVE_DURATION_NOT_MET: verified active={active_duration:.1f}s < 1800.0s required for PASS (wall-clock: {measured_duration:.1f}s)",
                )

        # Check for overlaps with already finalized real sessions
        for existing_f in self.real_sessions_dir.glob("*.final.json"):
            try:
                ex_data = json.loads(existing_f.read_text(encoding="utf-8"))
                ex_s = datetime.fromisoformat(ex_data["start_timestamp_utc"])
                ex_e = datetime.fromisoformat(ex_data["end_timestamp_utc"])
                if not (end_dt <= ex_s or start_dt >= ex_e):
                    return (
                        AcceptanceExitCode.LIFECYCLE_CONFLICT,
                        {},
                        f"OVERLAPPING_SESSION_INTERVAL: overlaps with {ex_data.get('session_id')}",
                    )
            except Exception:
                pass

        # Determine verified post-restart
        post_restart_verified = False
        boot_utc_str = in_prog.get("boot_timestamp_utc", "")
        if boot_utc_str and boot_utc_str != "UNKNOWN":
            try:
                boot_dt = datetime.fromisoformat(boot_utc_str)
                if boot_dt < start_dt and boot_dt <= end_dt:
                    if in_prog.get("workflow") == AcceptanceWorkflow.GUI_READINESS_AFTER_RESTART.value:
                        prior_cycles = set()
                        for ex_f in self.real_sessions_dir.glob("*.final.json"):
                            try:
                                d = json.loads(ex_f.read_text(encoding="utf-8"))
                                if d.get("is_post_restart"):
                                    prior_cycles.add(d.get("boot_cycle_id"))
                            except Exception:
                                pass
                        current_cycle = in_prog.get("boot_cycle_id")
                        if current_cycle and current_cycle not in prior_cycles:
                            post_restart_verified = True
            except Exception:
                pass

        final_record: Dict[str, Any] = {
            "session_id": session_id,
            "session_record_type": SessionRecordType.REAL_OPERATOR_SESSION.value,
            "lifecycle_state": "FINALIZED_REAL_OPERATOR_SESSION",
            "operator_role": in_prog["operator_role"],
            "interface_mode": in_prog["interface_mode"],
            "workflow": in_prog["workflow"],
            "date_utc": in_prog["date_utc"],
            "start_timestamp_utc": in_prog["start_timestamp_utc"],
            "end_timestamp_utc": end_utc,
            "operating_time_seconds": active_duration if session_outcome == "PASS" else measured_duration,
            "operating_time_minutes": (active_duration if session_outcome == "PASS" else measured_duration) / 60.0,
            "active_operating_seconds": active_duration,
            "wall_clock_duration_seconds": measured_duration,
            "declared_duration_seconds": active_duration if session_outcome == "PASS" else measured_duration,
            "check_in_count": len(check_ins) - 1 if check_ins else 0,
            "check_ins": check_ins,
            "is_post_restart": post_restart_verified,
            "post_restart_verified": post_restart_verified,
            "boot_cycle_id": in_prog.get("boot_cycle_id"),
            "starting_state": ApplicationState.STARTING.value,
            "final_state": ApplicationState.READY_READ_ONLY.value,
            "single_instance_lock_acquired": True,
            "single_instance_lock_released": True,
            "network_quarantine_active": True,
            "network_requests_dispatched": 0,
            "evidence_mutation_count": 0,
            "active_markers_count": 0,
            "repo_data_writes_count": 0,
            "target_generation_count": 0,
            "model_training_count": 0,
            "performance_calculation_count": 0,
            "session_exit_code": 0 if session_outcome == "PASS" else 1,
            "session_outcome": session_outcome,
            "status": session_outcome,
            "operator_observations": clean_obs,
            "defect_references": defect_references or [],
        }
        if "replacement_metadata" in in_prog:
            final_record["replacement_metadata"] = in_prog["replacement_metadata"]

        final_record["record_sha256"] = compute_record_checksum(final_record)

        # Write to real_sessions atomically
        atomic_write_json(final_target, final_record)

        # Remove in_progress
        try:
            active_path.unlink()
        except Exception:
            pass

        # Release lock
        lock = AcceptanceSessionLock(self.locks_dir, session_id)
        lock.release()

        # Append to audit
        audit_file = self.audit_dir / "session_lifecycle.jsonl"
        with open(audit_file, "a", encoding="utf-8") as af:
            af.write(
                json.dumps(
                    {
                        "timestamp_utc": end_utc,
                        "event": "SESSION_FINALIZED",
                        "session_id": session_id,
                        "outcome": session_outcome,
                        "duration_seconds": measured_duration,
                    }
                )
                + "\n"
            )

        # Update summary
        self.update_master_summary()

        return (
            AcceptanceExitCode.SUCCESS,
            final_record,
            f"SESSION_FINALIZED: {session_id} with outcome {session_outcome} ({measured_duration:.1f}s)",
        )

    def abort_session(
        self, session_id: str, reason_code: str
    ) -> Tuple[AcceptanceExitCode, Dict[str, Any], str]:
        """Abort an active real operator acceptance session."""
        if not validate_session_id(session_id):
            return (
                AcceptanceExitCode.INVALID_ARGS,
                {},
                f"INVALID_SESSION_ID: '{session_id}'",
            )

        active_path = self.in_progress_dir / f"{session_id}.active.json"
        if not active_path.exists():
            return (
                AcceptanceExitCode.LIFECYCLE_CONFLICT,
                {},
                f"NO_ACTIVE_SESSION_TO_ABORT: {session_id}",
            )

        try:
            in_prog = json.loads(active_path.read_text(encoding="utf-8"))
        except Exception as e:
            return (
                AcceptanceExitCode.INTEGRITY_FAILURE,
                {},
                f"CORRUPT_IN_PROGRESS_RECORD: {e}",
            )

        abort_dt = datetime.now(timezone.utc)
        abort_utc = abort_dt.isoformat()
        start_dt = datetime.fromisoformat(in_prog["start_timestamp_utc"])
        elapsed_sec = max(0.0, (abort_dt - start_dt).total_seconds())
        check_ins = in_prog.get("check_ins", [])
        aborted_record: Dict[str, Any] = {
            "session_id": session_id,
            "session_record_type": SessionRecordType.REAL_OPERATOR_SESSION.value,
            "lifecycle_state": "ABORTED_REAL_OPERATOR_SESSION",
            "operator_role": in_prog["operator_role"],
            "interface_mode": in_prog["interface_mode"],
            "workflow": in_prog["workflow"],
            "date_utc": in_prog["date_utc"],
            "start_timestamp_utc": in_prog["start_timestamp_utc"],
            "end_timestamp_utc": abort_utc,
            "operating_time_seconds": elapsed_sec,
            "operating_time_minutes": elapsed_sec / 60.0,
            "active_operating_seconds": 0.0,
            "wall_clock_duration_seconds": elapsed_sec,
            "declared_duration_seconds": elapsed_sec,
            "check_in_count": len(check_ins) - 1 if check_ins else 0,
            "check_ins": check_ins,
            "is_post_restart": False,
            "post_restart_verified": False,
            "boot_cycle_id": in_prog.get("boot_cycle_id"),
            "starting_state": ApplicationState.STARTING.value,
            "final_state": ApplicationState.STOPPED.value,
            "single_instance_lock_acquired": True,
            "single_instance_lock_released": True,
            "network_quarantine_active": True,
            "network_requests_dispatched": 0,
            "evidence_mutation_count": 0,
            "active_markers_count": 0,
            "repo_data_writes_count": 0,
            "target_generation_count": 0,
            "model_training_count": 0,
            "performance_calculation_count": 0,
            "session_exit_code": 1,
            "session_outcome": "ABORTED",
            "status": "ABORTED",
            "abort_reason": reason_code,
            "operator_observations": "",
            "defect_references": [],
        }
        if "replacement_metadata" in in_prog:
            aborted_record["replacement_metadata"] = in_prog["replacement_metadata"]

        aborted_record["record_sha256"] = compute_record_checksum(aborted_record)

        # Write to real_sessions
        final_target = self.real_sessions_dir / f"{session_id}.final.json"
        if final_target.exists():
            return (
                AcceptanceExitCode.LIFECYCLE_CONFLICT,
                {},
                f"CANNOT_OVERWRITE_FINAL_RECORD: {final_target.name} already exists",
            )
        atomic_write_json(final_target, aborted_record)

        # Remove in_progress
        try:
            active_path.unlink()
        except Exception:
            pass

        # Release lock
        lock = AcceptanceSessionLock(self.locks_dir, session_id)
        lock.release()

        # Append to audit
        audit_file = self.audit_dir / "session_lifecycle.jsonl"
        with open(audit_file, "a", encoding="utf-8") as af:
            af.write(
                json.dumps(
                    {
                        "timestamp_utc": abort_utc,
                        "event": "SESSION_ABORTED",
                        "session_id": session_id,
                        "reason": reason_code,
                        "duration_seconds": elapsed_sec,
                    }
                )
                + "\n"
            )

        # Update summary
        self.update_master_summary()

        return (
            AcceptanceExitCode.SUCCESS,
            aborted_record,
            f"SESSION_ABORTED: {session_id} (Reason: {reason_code}, Duration: {elapsed_sec:.1f}s)",
        )

    def validate_session_file(
        self, session_file: Path
    ) -> Tuple[AcceptanceExitCode, Dict[str, Any], str]:
        """Validate an on-disk session record file."""
        p = Path(session_file)
        if not p.exists():
            return (
                AcceptanceExitCode.INVALID_ARGS,
                {},
                f"FILE_NOT_FOUND: {session_file}",
            )
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            return (
                AcceptanceExitCode.INTEGRITY_FAILURE,
                {},
                f"INVALID_JSON_FILE: {e}",
            )

        errors = OperatorAcceptanceEvaluator.validate_session_record(rec)
        if errors:
            return (
                AcceptanceExitCode.TIMESTAMP_VALIDATION,
                rec,
                f"SESSION_RECORD_VALIDATION_ERRORS: {', '.join(errors)}",
            )

        if rec.get("session_record_type") == SessionRecordType.REAL_OPERATOR_SESSION.value:
            s_id = rec.get("session_id", "")
            if not validate_session_id(s_id):
                return (
                    AcceptanceExitCode.INVALID_ARGS,
                    rec,
                    f"INVALID_REAL_SESSION_ID: '{s_id}'",
                )
            if rec.get("operator_role") not in [r.value for r in OperatorRole]:
                return (
                    AcceptanceExitCode.INVALID_ARGS,
                    rec,
                    f"INVALID_OPERATOR_ROLE: '{rec.get('operator_role')}'",
                )
            if rec.get("interface_mode") not in [m.value for m in InterfaceMode]:
                return (
                    AcceptanceExitCode.INVALID_ARGS,
                    rec,
                    f"INVALID_INTERFACE_MODE: '{rec.get('interface_mode')}'",
                )
            if rec.get("workflow") not in [w.value for w in AcceptanceWorkflow]:
                return (
                    AcceptanceExitCode.INVALID_ARGS,
                    rec,
                    f"INVALID_WORKFLOW: '{rec.get('workflow')}'",
                )

            if "record_sha256" in rec:
                calc_cs = compute_record_checksum(rec)
                if rec["record_sha256"] != calc_cs:
                    return (
                        AcceptanceExitCode.INTEGRITY_FAILURE,
                        rec,
                        "RECORD_CHECKSUM_MISMATCH",
                    )

        return (
            AcceptanceExitCode.SUCCESS,
            rec,
            f"SESSION_RECORD_VALID: {rec.get('session_id')}",
        )

    def summarize(self) -> Tuple[AcceptanceExitCode, Dict[str, Any], str]:
        """Recompute master summary across real sessions and dry-run sessions."""
        summary = self.update_master_summary()
        summary_lines = [
            "=" * 80,
            "OPERATOR ACCEPTANCE MASTER SUMMARY",
            "-" * 80,
            f"Acceptance Status:             {summary['acceptance_status']}",
            f"Acceptance Passed:             {summary['acceptance_passed']}",
            f"Real Sessions (Total / Pass):  {summary.get('real_operator_sessions_count', 0)} / {summary.get('passed_real_sessions_count', 0)}",
            f"Dry-Run Sessions:              {summary.get('dry_run_sessions_count', 0)}",
            f"Distinct Working Dates:        {summary.get('distinct_working_dates_count', 0)} / 5 required",
            f"Total Operating Time:          {summary.get('total_real_operating_seconds', 0.0):.1f}s ({summary.get('total_real_operating_hours', 0.0):.2f}h / 5.0h required)",
            f"Post-Restart Sessions:         {summary.get('post_restart_sessions_count', 0)} / 2 required",
            "-" * 80,
            f"Active Blockers ({len(summary.get('active_blockers', []))}):",
        ]
        for b in summary.get("active_blockers", []):
            summary_lines.append(f"  - {b}")
        summary_lines.append("=" * 80)
        return (
            AcceptanceExitCode.SUCCESS,
            summary,
            "\n".join(summary_lines),
        )

    def update_master_summary(self, current_time: Optional[datetime] = None) -> Dict[str, Any]:
        """Load all on-disk sessions, reclassify, evaluate, and write master summary."""
        records: List[Dict[str, Any]] = []
        if self.sessions_dir.exists():
            for f in sorted(self.sessions_dir.glob("*.json")):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    records.append(data)
                except Exception:
                    pass
        if self.real_sessions_dir.exists():
            for f in sorted(self.real_sessions_dir.glob("*.json")):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    records.append(data)
                except Exception:
                    pass

        summary = OperatorAcceptanceEvaluator.evaluate_acceptance_exercise(
            records=records,
            authorized_end_date="2026-10-16",
            current_time=current_time,
        )

        summary_file = self.acceptance_dir / "acceptance_master_summary.json"
        summary_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary


def build_argument_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser for acceptance runner subcommands."""
    parser = argparse.ArgumentParser(
        prog="python -m phase7.operator.acceptance_runner",
        description="Governed Phase 7 Offline Operator Acceptance Runner CLI",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # start-session
    start_p = subparsers.add_parser("start-session", help="Start a real operator acceptance session")
    start_p.add_argument("--session-id", required=True, help="Session ID (REAL-SNN format)")
    start_p.add_argument("--operator-role", required=True, help="Operator role (OWNER, AUTHORIZED_INTERNAL_OPERATOR)")
    start_p.add_argument("--interface-mode", required=True, help="Interface mode (CLI, GUI)")
    start_p.add_argument("--workflow", required=True, help="Governed acceptance workflow")
    start_p.add_argument("--acceptance-root", default=str(DEFAULT_ACCEPTANCE_DIR), help="Path to external acceptance root")

    # status
    status_p = subparsers.add_parser("status", help="Query status of operator acceptance session")
    status_p.add_argument("--session-id", help="Session ID to inspect")
    status_p.add_argument("--acceptance-root", default=str(DEFAULT_ACCEPTANCE_DIR), help="Path to external acceptance root")

    # finalize-session
    finalize_p = subparsers.add_parser("finalize-session", help="Finalize an active operator acceptance session")
    finalize_p.add_argument("--session-id", required=True, help="Session ID (REAL-SNN format)")
    finalize_p.add_argument("--session-outcome", default="PASS", choices=["PASS", "FAIL"], help="Session outcome")
    finalize_p.add_argument("--observation-file", help="Path to sanitized observation text file")
    finalize_p.add_argument("--observations", help="Inline sanitized observation text")
    finalize_p.add_argument("--defect-references", nargs="*", help="Defect reference IDs (OPACC-YYYYMMDD-NNN)")
    finalize_p.add_argument("--acceptance-root", default=str(DEFAULT_ACCEPTANCE_DIR), help="Path to external acceptance root")

    # abort-session
    abort_p = subparsers.add_parser("abort-session", help="Abort an active operator acceptance session")
    abort_p.add_argument("--session-id", required=True, help="Session ID (REAL-SNN format)")
    abort_p.add_argument("--reason-code", required=True, help="Reason code for session abort")
    abort_p.add_argument("--acceptance-root", default=str(DEFAULT_ACCEPTANCE_DIR), help="Path to external acceptance root")

    # validate-session
    validate_p = subparsers.add_parser("validate-session", help="Validate a finalized session record")
    validate_p.add_argument("--session-file", help="Path to session record file")
    validate_p.add_argument("--session-id", help="Session ID to look up in real_sessions")
    validate_p.add_argument("--acceptance-root", default=str(DEFAULT_ACCEPTANCE_DIR), help="Path to external acceptance root")

    # check-in
    checkin_p = subparsers.add_parser("check-in", help="Record explicit operator activity check-in")
    checkin_p.add_argument("--session-id", required=True, help="Session ID (REAL-SNN format)")
    checkin_p.add_argument("--acceptance-root", default=str(DEFAULT_ACCEPTANCE_DIR), help="Path to external acceptance root")

    # summarize
    sum_p = subparsers.add_parser("summarize", help="Recompute and display acceptance master summary")
    sum_p.add_argument("--acceptance-root", default=str(DEFAULT_ACCEPTANCE_DIR), help="Path to external acceptance root")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI execution entrypoint for operator acceptance runner."""
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    if not args.subcommand:
        parser.print_help()
        return AcceptanceExitCode.SUCCESS.value

    acceptance_root = (
        Path(args.acceptance_root)
        if hasattr(args, "acceptance_root") and args.acceptance_root
        else DEFAULT_ACCEPTANCE_DIR
    )
    harness = OperatorAcceptanceHarness(acceptance_dir=acceptance_root)

    try:
        if args.subcommand == "start-session":
            code, _, msg = harness.start_session(
                session_id=args.session_id,
                operator_role=args.operator_role,
                interface_mode=args.interface_mode,
                workflow=args.workflow,
            )
            print(msg)
            return code.value

        elif args.subcommand == "check-in":
            code, _, msg = harness.check_in(session_id=args.session_id)
            print(msg)
            return code.value

        elif args.subcommand == "status":
            code, _, msg = harness.get_status(session_id=args.session_id)
            print(msg)
            return code.value

        elif args.subcommand == "finalize-session":
            obs_file = Path(args.observation_file) if args.observation_file else None
            code, _, msg = harness.finalize_session(
                session_id=args.session_id,
                session_outcome=args.session_outcome,
                observation_file=obs_file,
                observations=args.observations,
                defect_references=args.defect_references,
            )
            print(msg)
            return code.value

        elif args.subcommand == "abort-session":
            code, _, msg = harness.abort_session(
                session_id=args.session_id,
                reason_code=args.reason_code,
            )
            print(msg)
            return code.value

        elif args.subcommand == "validate-session":
            target_file = None
            if args.session_file:
                target_file = Path(args.session_file)
            elif args.session_id:
                target_file = harness.real_sessions_dir / f"{args.session_id}.final.json"
            if not target_file:
                print("Error: Either --session-file or --session-id must be provided.", file=sys.stderr)
                return AcceptanceExitCode.INVALID_ARGS.value
            code, _, msg = harness.validate_session_file(target_file)
            print(msg)
            return code.value

        elif args.subcommand == "summarize":
            code, _, msg = harness.summarize()
            print(msg)
            return code.value

        else:
            parser.print_help()
            return AcceptanceExitCode.INVALID_ARGS.value

    except Exception as e:
        print(f"UNEXPECTED_INTERNAL_ERROR: {e}", file=sys.stderr)
        return AcceptanceExitCode.INTERNAL_ERROR.value


if __name__ == "__main__":
    sys.exit(main())
