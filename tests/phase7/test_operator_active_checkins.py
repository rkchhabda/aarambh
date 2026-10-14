"""Automated test battery for governed operator acceptance active-operation accounting.

Covers 10 required governance properties:
1. Overnight active interval does not count as operator activity.
2. Wall-clock duration is distinct from accepted active duration.
3. Explicit check-ins create qualifying intervals.
4. Gaps above 300 seconds are excluded.
5. Generated or manually edited check-ins are rejected.
6. A session cannot PASS with 1,800 wall-clock seconds but insufficient active seconds.
7. A session may PASS with at least 1,800 verified active seconds.
8. Aborted sessions contribute zero accepted seconds.
9. Check-ins do not mutate preserved evidence.
10. Check-ins issue zero network requests.
"""

from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import socket
import tempfile
from typing import Any, Dict

import pytest

from phase7.operator.constants import (
    AcceptanceExitCode,
    AcceptanceWorkflow,
    InterfaceMode,
    OperatorRole,
    ApplicationState,
)
from phase7.operator.acceptance_runner import (
    AcceptanceStatus,
    OperatorAcceptanceEvaluator,
    OperatorAcceptanceHarness,
    SessionRecordType,
    compute_active_operating_seconds,
    compute_record_checksum,
    REJECTION_CHECK_IN_OUT_OF_ORDER,
    REJECTION_FUTURE_TIMESTAMP,
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


def test_overnight_active_interval_does_not_count_as_operator_activity(temp_acceptance_dir):
    """Property 1: Overnight active interval without check-ins contributes 0 active seconds."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)
    harness.start_session("REAL-S01", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")

    active_file = temp_acceptance_dir / "in_progress" / "REAL-S01.active.json"
    in_prog = json.loads(active_file.read_text(encoding="utf-8"))

    # Simulate 75,000s elapsed overnight without any check-ins
    overnight_start = datetime.now(timezone.utc) - timedelta(seconds=75000)
    in_prog["start_timestamp_utc"] = overnight_start.isoformat()
    in_prog["check_ins"][0]["timestamp_utc"] = overnight_start.isoformat()
    in_prog["checksum_sha256"] = compute_record_checksum(in_prog)
    active_file.write_text(json.dumps(in_prog, indent=2), encoding="utf-8")

    code, status_dict, msg = harness.get_status("REAL-S01")
    assert code == AcceptanceExitCode.SUCCESS
    assert status_dict["wall_clock_elapsed_seconds"] >= 75000.0
    assert status_dict["active_operating_seconds"] == 0.0
    assert status_dict["check_in_overdue"] is True
    assert status_dict["finalization_eligible"] is False
    assert "CHECK_IN_OVERDUE" in msg
    assert "MINIMUM_REAL_DURATION_NOT_YET_MET" in msg


def test_wall_clock_duration_distinct_from_accepted_active_duration(temp_acceptance_dir):
    """Property 2: Wall-clock duration and active operating duration are kept strictly distinct."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)
    harness.start_session("REAL-S01", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")

    active_file = temp_acceptance_dir / "in_progress" / "REAL-S01.active.json"
    in_prog = json.loads(active_file.read_text(encoding="utf-8"))

    # 2 hours total wall-clock (7200s), but only 2 check-ins spaced by 200s (400 active seconds)
    t0 = datetime.now(timezone.utc) - timedelta(seconds=7200)
    t1 = t0 + timedelta(seconds=200)
    t2 = t1 + timedelta(seconds=200)

    in_prog["start_timestamp_utc"] = t0.isoformat()
    in_prog["check_ins"] = [
        {"check_in_index": 0, "timestamp_utc": t0.isoformat(), "gap_seconds": 0.0, "qualifying": True, "type": "SESSION_START"},
        {"check_in_index": 1, "timestamp_utc": t1.isoformat(), "gap_seconds": 200.0, "qualifying": True, "type": "OPERATOR_CHECK_IN"},
        {"check_in_index": 2, "timestamp_utc": t2.isoformat(), "gap_seconds": 200.0, "qualifying": True, "type": "OPERATOR_CHECK_IN"},
    ]
    in_prog["active_operating_seconds"] = 400.0
    in_prog["check_in_count"] = 2
    in_prog["checksum_sha256"] = compute_record_checksum(in_prog)
    active_file.write_text(json.dumps(in_prog, indent=2), encoding="utf-8")

    code, status_dict, _ = harness.get_status("REAL-S01")
    assert code == AcceptanceExitCode.SUCCESS
    assert status_dict["wall_clock_elapsed_seconds"] >= 7200.0
    assert status_dict["active_operating_seconds"] == 400.0
    assert status_dict["wall_clock_elapsed_seconds"] != status_dict["active_operating_seconds"]


def test_explicit_check_ins_create_qualifying_intervals(temp_acceptance_dir):
    """Property 3: Explicit check-in CLI commands append qualifying checkpoints and log to audit."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)
    harness.start_session("REAL-S01", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")

    # Record first explicit check-in
    code, entry, msg = harness.check_in("REAL-S01")
    assert code == AcceptanceExitCode.SUCCESS
    assert entry["check_in_index"] == 1
    assert entry["qualifying"] is True
    assert "CHECK_IN_RECORDED" in msg

    # Audit log check
    audit_file = temp_acceptance_dir / "audit" / "session_lifecycle.jsonl"
    lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    event = json.loads(lines[1])
    assert event["event"] == "OPERATOR_CHECK_IN"
    assert event["session_id"] == "REAL-S01"
    assert event["check_in_index"] == 1


def test_gaps_above_300_seconds_excluded(temp_acceptance_dir):
    """Property 4: Gaps above 300 seconds contribute 0 seconds to active operating time."""
    t0 = datetime(2026, 10, 13, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=250)   # 250s <= 300s -> qualifying (+250s)
    t2 = t1 + timedelta(seconds=500)   # 500s > 300s -> EXCLUDED (+0s)
    t3 = t2 + timedelta(seconds=200)   # 200s <= 300s -> qualifying (+200s)

    check_ins = [
        {"timestamp_utc": t0.isoformat(), "type": "SESSION_START"},
        {"timestamp_utc": t1.isoformat(), "type": "OPERATOR_CHECK_IN"},
        {"timestamp_utc": t2.isoformat(), "type": "OPERATOR_CHECK_IN"},
        {"timestamp_utc": t3.isoformat(), "type": "OPERATOR_CHECK_IN"},
    ]

    active_sec = compute_active_operating_seconds(check_ins)
    assert active_sec == 450.0  # 250 + 0 + 200 = 450s


def test_generated_or_manually_edited_check_ins_rejected(temp_acceptance_dir):
    """Property 5: Tampered or out-of-order check-ins are strictly rejected by checksum and validation."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)
    harness.start_session("REAL-S01", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")

    active_file = temp_acceptance_dir / "in_progress" / "REAL-S01.active.json"
    in_prog = json.loads(active_file.read_text(encoding="utf-8"))

    # 1. Tampering without recomputing checksum -> Checksum mismatch
    in_prog["active_operating_seconds"] = 9999.0
    active_file.write_text(json.dumps(in_prog, indent=2), encoding="utf-8")
    code, _, msg = harness.check_in("REAL-S01")
    assert code == AcceptanceExitCode.INTEGRITY_FAILURE
    assert "Checksum mismatch" in msg

    # 2. Recomputed checksum with out-of-order check-in timestamp
    t_now = datetime.now(timezone.utc)
    t_past = t_now - timedelta(seconds=100)
    in_prog["check_ins"] = [
        {"timestamp_utc": t_now.isoformat()},
        {"timestamp_utc": t_past.isoformat()},  # precedes previous!
    ]
    in_prog["checksum_sha256"] = compute_record_checksum(in_prog)
    active_file.write_text(json.dumps(in_prog, indent=2), encoding="utf-8")

    errors = OperatorAcceptanceEvaluator.validate_session_record(
        {
            "session_id": "REAL-S01",
            "session_record_type": SessionRecordType.REAL_OPERATOR_SESSION.value,
            "start_timestamp_utc": t_past.isoformat(),
            "end_timestamp_utc": t_now.isoformat(),
            "check_ins": in_prog["check_ins"],
        }
    )
    assert REJECTION_CHECK_IN_OUT_OF_ORDER in errors


def test_session_cannot_pass_with_1800_wallclock_seconds_but_insufficient_active_seconds(temp_acceptance_dir):
    """Property 6: 1,800 wall-clock seconds without qualifying active check-ins cannot finalize with PASS."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)
    harness.start_session("REAL-S01", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")

    active_file = temp_acceptance_dir / "in_progress" / "REAL-S01.active.json"
    in_prog = json.loads(active_file.read_text(encoding="utf-8"))

    # 1,850 wall-clock seconds elapsed, but NO check-ins
    t0 = datetime.now(timezone.utc) - timedelta(seconds=1850)
    in_prog["start_timestamp_utc"] = t0.isoformat()
    in_prog["monotonic_start_seconds"] = in_prog["monotonic_start_seconds"] - 1850.0
    in_prog["check_ins"] = [{"check_in_index": 0, "timestamp_utc": t0.isoformat(), "type": "SESSION_START"}]
    in_prog["checksum_sha256"] = compute_record_checksum(in_prog)
    active_file.write_text(json.dumps(in_prog, indent=2), encoding="utf-8")

    code, _, msg = harness.finalize_session("REAL-S01", session_outcome="PASS")
    assert code == AcceptanceExitCode.DURATION_NOT_MET
    assert "MINIMUM_ACTIVE_DURATION_NOT_MET" in msg
    assert active_file.exists()


def test_session_may_pass_with_at_least_1800_verified_active_seconds(temp_acceptance_dir):
    """Property 7: A session with at least 1,800 verified active seconds passes finalization cleanly."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)
    harness.start_session("REAL-S01", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")

    active_file = temp_acceptance_dir / "in_progress" / "REAL-S01.active.json"
    in_prog = json.loads(active_file.read_text(encoding="utf-8"))

    t0 = datetime.now(timezone.utc) - timedelta(seconds=1805)
    in_prog["start_timestamp_utc"] = t0.isoformat()
    in_prog["monotonic_start_seconds"] = in_prog["monotonic_start_seconds"] - 1805.0

    # 6 check-ins every 300s -> 1,800 active seconds
    check_ins = [{"check_in_index": 0, "timestamp_utc": t0.isoformat(), "type": "SESSION_START"}]
    for i in range(1, 7):
        chk_t = t0 + timedelta(seconds=i * 300)
        check_ins.append({"check_in_index": i, "timestamp_utc": chk_t.isoformat(), "type": "OPERATOR_CHECK_IN"})
    in_prog["check_ins"] = check_ins
    in_prog["active_operating_seconds"] = 1800.0
    in_prog["check_in_count"] = 6
    in_prog["checksum_sha256"] = compute_record_checksum(in_prog)
    active_file.write_text(json.dumps(in_prog, indent=2), encoding="utf-8")

    code, final_rec, msg = harness.finalize_session("REAL-S01", session_outcome="PASS")
    assert code == AcceptanceExitCode.SUCCESS
    assert final_rec["status"] == "PASS"
    assert final_rec["active_operating_seconds"] >= 1800.0
    assert final_rec["wall_clock_duration_seconds"] >= 1800.0
    assert not active_file.exists()
    assert (temp_acceptance_dir / "real_sessions" / "REAL-S01.final.json").exists()


def test_aborted_sessions_contribute_zero_accepted_seconds(temp_acceptance_dir):
    """Property 8: Aborted sessions contribute zero accepted operating seconds to the master summary."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)
    harness.start_session("REAL-S01", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")

    code, aborted_rec, msg = harness.abort_session("REAL-S01", reason_code="STALE_UNATTENDED_SESSION")
    assert code == AcceptanceExitCode.SUCCESS
    assert aborted_rec["status"] == "ABORTED"
    assert aborted_rec["active_operating_seconds"] == 0.0

    code_sum, summary, _ = harness.summarize()
    assert code_sum == AcceptanceExitCode.SUCCESS
    assert summary["real_operator_sessions_count"] == 1
    assert summary["passed_real_sessions_count"] == 0
    assert summary["total_real_operating_seconds"] == 0.0


def test_check_ins_do_not_mutate_preserved_evidence(temp_acceptance_dir):
    """Property 9: Operator check-in operations do not touch preserved staging evidence or test files."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)
    harness.start_session("REAL-S01", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")

    # Place a sentinel mock preserved file
    sessions_dir = temp_acceptance_dir / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    sentinel = sessions_dir / "preserved_s01.json"
    sentinel.write_text("IMMUTABLE_PRESERVED_CONTENT", encoding="utf-8")
    before_mtime = sentinel.stat().st_mtime_ns

    # Perform check-in
    code, _, _ = harness.check_in("REAL-S01")
    assert code == AcceptanceExitCode.SUCCESS

    # Verify sentinel untouched
    assert sentinel.read_text(encoding="utf-8") == "IMMUTABLE_PRESERVED_CONTENT"
    assert sentinel.stat().st_mtime_ns == before_mtime


def test_check_ins_issue_zero_network_requests(temp_acceptance_dir, monkeypatch):
    """Property 10: Check-ins are strictly offline and make 0 network connections."""
    def forbidden_connect(*args, **kwargs):
        raise RuntimeError("NETWORK_CONNECTION_PROHIBITED")

    monkeypatch.setattr(socket.socket, "connect", forbidden_connect)

    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)
    harness.start_session("REAL-S01", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")
    code, _, msg = harness.check_in("REAL-S01")

    assert code == AcceptanceExitCode.SUCCESS
    assert "CHECK_IN_RECORDED" in msg
