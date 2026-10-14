"""Automated test suite for governed replacement sessions and check-in integrity reconciliation.

Milestone 4.13C:
1. Aborted session ID cannot restart.
2. Replacement session has a different ID.
3. Replacement session inherits zero time.
4. Replacement session does not inherit check-ins.
5. Replacement authorization links to the aborted record.
6. Replacement plus nine other passed workflows gives ten passed sessions.
7. Aborted session is excluded from accepted totals.
8. Replacement cannot overwrite the aborted record.
9. Only one replacement may be authorized for the same aborted session.
10. Replacement workflow must match the original governed workflow.
11. Finalization does not credit trailing time without final check-in.
12. Duplicate check-in timestamps are rejected.
13. Foreign check-ins from another session are rejected.
"""

from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import tempfile
from typing import Any, Dict, List

import pytest

from phase7.operator.constants import (
    AcceptanceExitCode,
    AcceptanceWorkflow,
    GOVERNED_SESSION_REPLACEMENT_MAP,
)
from phase7.operator.acceptance_runner import (
    AcceptanceStatus,
    OperatorAcceptanceEvaluator,
    OperatorAcceptanceHarness,
    SessionRecordType,
    compute_active_operating_seconds,
    compute_record_checksum,
    REJECTION_TEN_REAL_SESSIONS,
    REJECTION_FOREIGN_CHECK_IN,
    REJECTION_CHECK_IN_OUT_OF_ORDER,
)

pytestmark = [pytest.mark.unit]


@pytest.fixture
def temp_acceptance_dir():
    """Create an isolated temporary acceptance directory tree."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir) / "acceptance_4_13"
        root.mkdir(parents=True, exist_ok=True)
        summary_file = root / "acceptance_master_summary.json"
        summary_file.write_text(
            json.dumps(
                {
                    "acceptance_exercise_id": "ACCEPTANCE_4_13_5DAY_10SESSION",
                    "acceptance_status": AcceptanceStatus.IN_PROGRESS.value,
                    "acceptance_passed": False,
                    "real_operator_sessions_count": 0,
                    "dry_run_sessions_count": 0,
                    "active_blockers": ["INCOMPLETE"],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        yield root


# =============================================================================
# 1. Aborted session ID cannot restart
# =============================================================================
def test_aborted_session_id_cannot_restart(temp_acceptance_dir):
    """Test 1: An aborted session record permanently locks the session ID from restarting."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)
    code1, _, _ = harness.start_session("REAL-S01", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")
    assert code1 == AcceptanceExitCode.SUCCESS

    code2, _, _ = harness.abort_session("REAL-S01", reason_code="STALE_UNATTENDED_SESSION")
    assert code2 == AcceptanceExitCode.SUCCESS

    # Attempt to restart REAL-S01
    code3, _, msg = harness.start_session("REAL-S01", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")
    assert code3 == AcceptanceExitCode.LIFECYCLE_CONFLICT
    assert "ABORTED_SESSION_CANNOT_RESTART" in msg or "SESSION_ALREADY_FINALIZED" in msg


# =============================================================================
# 2. Replacement session has a different ID
# =============================================================================
def test_replacement_session_has_different_id():
    """Test 2: Governed replacement session ID must be distinct from original aborted session ID."""
    assert "REAL-S11" in GOVERNED_SESSION_REPLACEMENT_MAP
    repl = GOVERNED_SESSION_REPLACEMENT_MAP["REAL-S11"]
    assert repl["replaces_session_id"] == "REAL-S01"
    assert repl["replaces_session_id"] != "REAL-S11"


# =============================================================================
# 3. Replacement session inherits zero time
# =============================================================================
def test_replacement_session_inherits_zero_time(temp_acceptance_dir):
    """Test 3: Replacement session REAL-S11 starts with 0.0 operating time and 0.0 active seconds."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)
    code, active_rec, msg = harness.start_session("REAL-S11", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")
    assert code == AcceptanceExitCode.SUCCESS
    assert active_rec["session_id"] == "REAL-S11"
    assert active_rec["active_operating_seconds"] == 0.0

    code_st, status_dict, _ = harness.get_status("REAL-S11")
    assert code_st == AcceptanceExitCode.SUCCESS
    assert status_dict["active_operating_seconds"] == 0.0


# =============================================================================
# 4. Replacement session does not inherit check-ins
# =============================================================================
def test_replacement_session_does_not_inherit_checkins(temp_acceptance_dir):
    """Test 4: Replacement session REAL-S11 starts with only its own SESSION_START checkpoint."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)
    code, active_rec, _ = harness.start_session("REAL-S11", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")
    assert code == AcceptanceExitCode.SUCCESS
    assert active_rec["check_in_count"] == 0
    assert len(active_rec["check_ins"]) == 1
    assert active_rec["check_ins"][0]["check_in_index"] == 0
    assert active_rec["check_ins"][0]["session_id"] == "REAL-S11"
    assert active_rec["check_ins"][0]["type"] == "SESSION_START"


# =============================================================================
# 5. Replacement authorization links to the aborted record
# =============================================================================
def test_replacement_authorization_links_to_aborted_record(temp_acceptance_dir):
    """Test 5: Replacement session records contain explicit replacement_metadata linking to REAL-S01."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)
    code, active_rec, _ = harness.start_session("REAL-S11", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")
    assert code == AcceptanceExitCode.SUCCESS
    assert "replacement_metadata" in active_rec

    meta = active_rec["replacement_metadata"]
    assert meta["replaces_session_id"] == "REAL-S01"
    assert meta["replacement_reason"] == "STALE_UNATTENDED_SESSION"
    assert meta["original_outcome"] == "ABORTED"
    assert meta["original_accepted_seconds"] == 0
    assert meta["replacement_authorized_by"] == "OWNER"
    assert meta["replacement_reuse_prohibited"] is True


# =============================================================================
# 6. Replacement plus nine other passed workflows gives ten passed sessions
# =============================================================================
def test_replacement_plus_nine_other_passed_workflows_gives_ten_passed_sessions():
    """Test 6: Aborted REAL-S01 + replacement REAL-S11 + REAL-S02..REAL-S10 satisfies the 10 real sessions requirement."""
    records: List[Dict[str, Any]] = []
    base_dt = datetime(2026, 10, 13, 0, 0, 0, tzinfo=timezone.utc)

    # 1. Aborted REAL-S01 (contributes 0 to passed count, 0 to operating seconds)
    records.append({
        "session_id": "REAL-S01",
        "session_record_type": SessionRecordType.REAL_OPERATOR_SESSION.value,
        "lifecycle_state": "ABORTED_REAL_OPERATOR_SESSION",
        "workflow": "READINESS_DASHBOARD_AND_LIFECYCLE",
        "status": "ABORTED",
        "session_outcome": "ABORTED",
        "start_timestamp_utc": base_dt.isoformat(),
        "end_timestamp_utc": (base_dt + timedelta(seconds=75000)).isoformat(),
        "active_operating_seconds": 0.0,
        "date_utc": "2026-10-13",
    })

    # Workflows for REAL-S11 and REAL-S02..REAL-S10 non-overlapping across 5 distinct dates
    session_plan = [
        ("REAL-S11", AcceptanceWorkflow.READINESS_DASHBOARD_AND_LIFECYCLE.value, "2026-10-14", "10:00:00", False),
        ("REAL-S02", AcceptanceWorkflow.EVIDENCE_INVENTORY_AND_FILE_HEALTH.value, "2026-10-14", "11:00:00", False),
        ("REAL-S03", AcceptanceWorkflow.GUI_READINESS_AFTER_RESTART.value, "2026-10-15", "10:00:00", True),
        ("REAL-S04", AcceptanceWorkflow.MANIFEST_AND_CHECKSUM_VERIFICATION.value, "2026-10-15", "11:00:00", False),
        ("REAL-S05", AcceptanceWorkflow.HALTED_BATCH_INSPECTION.value, "2026-10-16", "10:00:00", False),
        ("REAL-S06", AcceptanceWorkflow.OPERATIONAL_DRILL_REVIEW.value, "2026-10-16", "11:00:00", False),
        ("REAL-S07", AcceptanceWorkflow.BACKUP_AND_RESTORE_VERIFICATION.value, "2026-10-17", "10:00:00", False),
        ("REAL-S08", AcceptanceWorkflow.GOVERNANCE_BLOCKERS_AND_AUTHORIZATION.value, "2026-10-17", "11:00:00", False),
        ("REAL-S09", AcceptanceWorkflow.METADATA_ONLY_AUDIT_EXPORT.value, "2026-10-18", "10:00:00", False),
        ("REAL-S10", AcceptanceWorkflow.FULL_APPLICATION_QUARANTINE_AND_SHUTDOWN.value, "2026-10-18", "11:00:00", True),
    ]

    for s_id, wf, d_str, t_str, post_rst in session_plan:
        s_time = datetime.fromisoformat(f"{d_str}T{t_str}+00:00")
        e_time = s_time + timedelta(seconds=1800)
        rec = {
            "session_id": s_id,
            "session_record_type": SessionRecordType.REAL_OPERATOR_SESSION.value,
            "lifecycle_state": "FINALIZED_REAL_OPERATOR_SESSION",
            "workflow": wf,
            "status": "PASS",
            "session_outcome": "PASS",
            "start_timestamp_utc": s_time.isoformat(),
            "end_timestamp_utc": e_time.isoformat(),
            "active_operating_seconds": 1800.0,
            "date_utc": d_str,
            "is_post_restart": post_rst,
            "post_restart_verified": post_rst,
        }
        if s_id == "REAL-S11":
            rec["replacement_metadata"] = GOVERNED_SESSION_REPLACEMENT_MAP["REAL-S11"]
        records.append(rec)

    eval_time = datetime(2026, 10, 19, 0, 0, 0, tzinfo=timezone.utc)
    summary = OperatorAcceptanceEvaluator.evaluate_acceptance_exercise(
        records=records,
        authorized_end_date="2026-10-18",
        current_time=eval_time,
    )

    assert summary["real_operator_sessions_count"] == 11
    assert summary["passed_real_sessions_count"] == 10
    assert summary["failed_real_sessions_count"] == 1  # REAL-S01 counted as failed/aborted
    assert summary["total_real_operating_seconds"] == 18000.0
    assert summary["distinct_working_dates_count"] == 5
    assert summary["post_restart_sessions_count"] == 2
    assert REJECTION_TEN_REAL_SESSIONS not in summary["active_blockers"]
    assert summary["acceptance_passed"] is True
    assert summary["acceptance_status"] == AcceptanceStatus.PASSED.value


# =============================================================================
# 7. Aborted session is excluded from accepted totals
# =============================================================================
def test_aborted_session_is_excluded_from_accepted_totals():
    """Test 7: Aborted session contributes 0 to passed sessions, accepted time, and dates."""
    base_dt = datetime(2026, 10, 13, 10, 0, 0, tzinfo=timezone.utc)
    aborted_rec = {
        "session_id": "REAL-S01",
        "session_record_type": SessionRecordType.REAL_OPERATOR_SESSION.value,
        "lifecycle_state": "ABORTED_REAL_OPERATOR_SESSION",
        "workflow": "READINESS_DASHBOARD_AND_LIFECYCLE",
        "status": "ABORTED",
        "session_outcome": "ABORTED",
        "start_timestamp_utc": base_dt.isoformat(),
        "end_timestamp_utc": (base_dt + timedelta(seconds=75000)).isoformat(),
        "active_operating_seconds": 0.0,
        "date_utc": "2026-10-13",
    }
    summary = OperatorAcceptanceEvaluator.evaluate_acceptance_exercise(
        records=[aborted_rec],
        authorized_end_date="2026-10-16",
        current_time=base_dt + timedelta(seconds=76000),
    )
    assert summary["real_operator_sessions_count"] == 1
    assert summary["passed_real_sessions_count"] == 0
    assert summary["total_real_operating_seconds"] == 0.0
    assert summary["distinct_working_dates_count"] == 0
    assert summary["post_restart_sessions_count"] == 0


# =============================================================================
# 8. Replacement cannot overwrite the aborted record
# =============================================================================
def test_replacement_cannot_overwrite_aborted_record(temp_acceptance_dir):
    """Test 8: Finalizing REAL-S11 writes to REAL-S11.final.json without touching REAL-S01.final.json."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)
    # 1. Place pre-existing aborted REAL-S01 session in the past
    s01_start = datetime.now(timezone.utc) - timedelta(seconds=7200)
    s01_end = s01_start + timedelta(seconds=3600)
    s01_final_rec = {
        "session_id": "REAL-S01",
        "session_record_type": SessionRecordType.REAL_OPERATOR_SESSION.value,
        "lifecycle_state": "ABORTED_REAL_OPERATOR_SESSION",
        "workflow": "READINESS_DASHBOARD_AND_LIFECYCLE",
        "status": "ABORTED",
        "session_outcome": "ABORTED",
        "start_timestamp_utc": s01_start.isoformat(),
        "end_timestamp_utc": s01_end.isoformat(),
        "active_operating_seconds": 0.0,
        "wall_clock_duration_seconds": 3600.0,
        "operating_time_seconds": 3600.0,
        "operator_role": "OWNER",
        "interface_mode": "CLI",
        "date_utc": s01_start.isoformat()[:10],
    }
    s01_final_rec["record_sha256"] = compute_record_checksum(s01_final_rec)
    s01_final = temp_acceptance_dir / "real_sessions" / "REAL-S01.final.json"
    s01_final.write_text(json.dumps(s01_final_rec, indent=2), encoding="utf-8")
    s01_sha_before = s01_final_rec["record_sha256"]

    # 2. Start and finalize REAL-S11
    code_start, _, _ = harness.start_session("REAL-S11", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")
    assert code_start == AcceptanceExitCode.SUCCESS

    # Simulate 1800s with check-ins
    active_file = temp_acceptance_dir / "in_progress" / "REAL-S11.active.json"
    in_prog = json.loads(active_file.read_text(encoding="utf-8"))
    t0 = datetime.now(timezone.utc) - timedelta(seconds=1805)
    in_prog["start_timestamp_utc"] = t0.isoformat()
    in_prog["monotonic_start_seconds"] = in_prog["monotonic_start_seconds"] - 1805.0

    check_ins = [{"check_in_index": 0, "session_id": "REAL-S11", "timestamp_utc": t0.isoformat(), "type": "SESSION_START"}]
    for i in range(1, 7):
        chk_t = t0 + timedelta(seconds=i * 300)
        check_ins.append({"check_in_index": i, "session_id": "REAL-S11", "timestamp_utc": chk_t.isoformat(), "type": "OPERATOR_CHECK_IN"})
    in_prog["check_ins"] = check_ins
    in_prog["active_operating_seconds"] = 1800.0
    in_prog["check_in_count"] = 6
    in_prog["checksum_sha256"] = compute_record_checksum(in_prog)
    active_file.write_text(json.dumps(in_prog, indent=2), encoding="utf-8")

    code_fin, fin_rec, _ = harness.finalize_session("REAL-S11", session_outcome="PASS")
    assert code_fin == AcceptanceExitCode.SUCCESS

    s11_final = temp_acceptance_dir / "real_sessions" / "REAL-S11.final.json"
    assert s11_final.exists()
    assert fin_rec["session_id"] == "REAL-S11"
    assert fin_rec["replacement_metadata"]["replaces_session_id"] == "REAL-S01"

    # Verify REAL-S01 was completely unchanged
    s01_sha_after = compute_record_checksum(json.loads(s01_final.read_text(encoding="utf-8")))
    assert s01_sha_after == s01_sha_before


# =============================================================================
# 9. Only one replacement may be authorized for the same aborted session
# =============================================================================
def test_only_one_replacement_may_be_authorized_for_same_aborted_session(temp_acceptance_dir, monkeypatch):
    """Test 9: Attempting to start a second replacement session for REAL-S01 is rejected."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)
    # Start REAL-S11
    code1, _, _ = harness.start_session("REAL-S11", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")
    assert code1 == AcceptanceExitCode.SUCCESS

    # Simulate attempt to authorize and start another session REAL-S99 replacing REAL-S01
    mock_repl_map = dict(GOVERNED_SESSION_REPLACEMENT_MAP)
    mock_repl_map["REAL-S99"] = {
        "replaces_session_id": "REAL-S01",
        "replacement_reason": "STALE_UNATTENDED_SESSION",
        "original_outcome": "ABORTED",
        "original_accepted_seconds": 0,
        "replacement_authorized_by": "OWNER",
        "replacement_authorization_date": "2026-10-14",
        "replacement_reuse_prohibited": True,
    }
    monkeypatch.setattr("phase7.operator.acceptance_runner.GOVERNED_SESSION_REPLACEMENT_MAP", mock_repl_map)

    # Release lock so lock doesn't conflict first
    lock = harness.locks_dir / "REAL-S11.lock"
    if lock.exists():
        lock.unlink()

    code2, _, msg2 = harness.start_session("REAL-S99", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")
    assert code2 == AcceptanceExitCode.LIFECYCLE_CONFLICT
    assert "REPLACEMENT_ALREADY_ACTIVE" in msg2 or "ANOTHER_SESSION_ALREADY_ACTIVE" in msg2


# =============================================================================
# 10. Replacement workflow must match the original governed workflow
# =============================================================================
def test_replacement_workflow_must_match_original_governed_workflow(temp_acceptance_dir):
    """Test 10: REAL-S11 is bound strictly to READINESS_DASHBOARD_AND_LIFECYCLE; other workflows fail."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)
    code, _, msg = harness.start_session("REAL-S11", "OWNER", "CLI", "EVIDENCE_INVENTORY_AND_FILE_HEALTH")
    assert code == AcceptanceExitCode.INVALID_ARGS
    assert "WORKFLOW_MISMATCH" in msg or "REPLACEMENT_WORKFLOW_MISMATCH" in msg


# =============================================================================
# 11. Finalization does not automatically credit trailing time without final check-in
# =============================================================================
def test_finalization_without_final_checkin_does_not_credit_trailing_time():
    """Test 11: Trailing time between last check-in and finalization is excluded unless explicit check-in occurred."""
    t0 = datetime(2026, 10, 13, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=240)   # Check-in 1: 240s active
    t2 = t1 + timedelta(seconds=240)   # Check-in 2: +240s = 480s active

    check_ins = [
        {"timestamp_utc": t0.isoformat(), "type": "SESSION_START"},
        {"timestamp_utc": t1.isoformat(), "type": "OPERATOR_CHECK_IN"},
        {"timestamp_utc": t2.isoformat(), "type": "OPERATOR_CHECK_IN"},
    ]

    # Session finalized 200s after t2 without an explicit check-in
    end_utc = (t2 + timedelta(seconds=200)).isoformat()
    active_sec = compute_active_operating_seconds(check_ins, end_timestamp_utc=end_utc)
    assert active_sec == 480.0  # Trailing 200s contributes 0.0


# =============================================================================
# 12. Duplicate and non-increasing check-ins are rejected
# =============================================================================
def test_duplicate_and_non_increasing_checkins_rejected():
    """Test 12: Duplicate check-in timestamps are rejected as out of order."""
    t0 = datetime(2026, 10, 13, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=100)

    # Duplicate timestamp
    record_duplicate = {
        "session_id": "REAL-S01",
        "session_record_type": SessionRecordType.REAL_OPERATOR_SESSION.value,
        "start_timestamp_utc": t0.isoformat(),
        "end_timestamp_utc": (t1 + timedelta(seconds=100)).isoformat(),
        "status": "PASS",
        "session_outcome": "PASS",
        "active_operating_seconds": 1800.0,
        "check_ins": [
            {"timestamp_utc": t0.isoformat(), "type": "SESSION_START"},
            {"timestamp_utc": t1.isoformat(), "type": "OPERATOR_CHECK_IN"},
            {"timestamp_utc": t1.isoformat(), "type": "OPERATOR_CHECK_IN"},  # duplicate
        ],
    }
    errors = OperatorAcceptanceEvaluator.validate_session_record(record_duplicate)
    assert REJECTION_CHECK_IN_OUT_OF_ORDER in errors


# =============================================================================
# 13. Foreign check-ins from another session are rejected
# =============================================================================
def test_foreign_checkin_injection_rejected():
    """Test 13: Check-in records carrying another session ID are detected and rejected."""
    t0 = datetime(2026, 10, 13, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=100)
    record = {
        "session_id": "REAL-S02",
        "session_record_type": SessionRecordType.REAL_OPERATOR_SESSION.value,
        "start_timestamp_utc": t0.isoformat(),
        "end_timestamp_utc": (t1 + timedelta(seconds=100)).isoformat(),
        "status": "PASS",
        "session_outcome": "PASS",
        "active_operating_seconds": 1800.0,
        "check_ins": [
            {"session_id": "REAL-S02", "timestamp_utc": t0.isoformat(), "type": "SESSION_START"},
            {"session_id": "REAL-S01", "timestamp_utc": t1.isoformat(), "type": "OPERATOR_CHECK_IN"},  # Foreign!
        ],
    }
    errors = OperatorAcceptanceEvaluator.validate_session_record(record)
    assert REJECTION_FOREIGN_CHECK_IN in errors
