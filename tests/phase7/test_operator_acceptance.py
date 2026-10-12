"""Automated test suite for Phase 7 Milestone 4.13A Operator Acceptance Evidence Semantics.

Milestone 4.13A: Validates strict real-time evidence semantics for operator acceptance:
1. Future-dated session rejection
2. Future-dated master-summary rejection
3. Dry-run exclusion from acceptance totals
4. Simulated-session exclusion from acceptance totals
5. Timestamp-derived duration calculation
6. Duration mismatch rejection
7. Overlapping-session rejection
8. Duplicate-session rejection
9. Five-distinct-day requirement
10. Ten-real-session requirement
11. Five-hour (18,000s) operating time requirement
12. Post-restart sessions requirement
13. Premature-closure rejection
14. Correct acceptance status when all requirements are genuinely met
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List
import pytest

from phase7.operator.acceptance_runner import (
    AcceptanceStatus,
    OperatorAcceptanceEvaluator,
    SessionRecordType,
    REJECTION_FUTURE_TIMESTAMP,
    REJECTION_FUTURE_SUMMARY,
    REJECTION_DURATION_MISMATCH,
    REJECTION_OVERLAPPING_SESSION,
    REJECTION_DUPLICATE_SESSION,
    REJECTION_FIVE_DISTINCT_DATES,
    REJECTION_TEN_REAL_SESSIONS,
    REJECTION_FIVE_HOURS,
    REJECTION_POST_RESTART,
    REJECTION_PREMATURE_CLOSURE,
)

pytestmark = [pytest.mark.unit]


# Helper to build mock session records
def _make_session(
    session_id: str,
    date_str: str,
    start_time_str: str,
    end_time_str: str,
    record_type: SessionRecordType = SessionRecordType.REAL_OPERATOR_SESSION,
    is_post_restart: bool = False,
    declared_duration: float = None,
) -> Dict[str, Any]:
    start_iso = f"{date_str}T{start_time_str}Z"
    end_iso = f"{date_str}T{end_time_str}Z"
    s_dt = datetime.fromisoformat(start_iso)
    e_dt = datetime.fromisoformat(end_iso)
    actual_seconds = (e_dt - s_dt).total_seconds()

    return {
        "session_id": session_id,
        "session_record_type": record_type.value,
        "date_utc": date_str,
        "start_timestamp_utc": start_iso,
        "end_timestamp_utc": end_iso,
        "operating_time_seconds": actual_seconds,
        "operating_time_minutes": actual_seconds / 60.0,
        "declared_duration_seconds": declared_duration if declared_duration is not None else actual_seconds,
        "is_post_restart": is_post_restart,
        "status": "PASS",
    }


# =============================================================================
# 1. Future-Dated Session Rejection
# =============================================================================
def test_future_dated_session_rejection():
    """Verify that sessions with timestamps postdating current time are rejected."""
    current_time = datetime(2026, 10, 12, 10, 0, 0, tzinfo=timezone.utc)
    future_session = _make_session("S03", "2026-10-13", "09:00:00", "09:30:00")

    errors = OperatorAcceptanceEvaluator.validate_session_record(future_session, current_time=current_time)
    assert REJECTION_FUTURE_TIMESTAMP in errors


# =============================================================================
# 2. Future-Dated Master Summary Rejection
# =============================================================================
def test_future_dated_master_summary_rejection():
    """Verify master summary evaluation flags future-dated records in the exercise."""
    current_time = datetime(2026, 10, 12, 10, 0, 0, tzinfo=timezone.utc)
    records = [
        _make_session("S01", "2026-10-12", "08:00:00", "08:30:00"),
        _make_session("S02", "2026-10-14", "08:00:00", "08:30:00"),  # future
    ]
    summary = OperatorAcceptanceEvaluator.evaluate_acceptance_exercise(records, current_time=current_time)
    assert REJECTION_FUTURE_SUMMARY in summary["active_blockers"]
    assert summary["acceptance_status"] == AcceptanceStatus.IN_PROGRESS.value


# =============================================================================
# 3. Dry-Run Exclusion from Acceptance Totals
# =============================================================================
def test_dry_run_exclusion_from_acceptance_totals():
    """Verify dry-run records are strictly excluded from real acceptance metrics."""
    current_time = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)
    records = [
        _make_session("DRY01", "2026-10-12", "08:00:00", "08:30:00", record_type=SessionRecordType.ACCEPTANCE_HARNESS_DRY_RUN),
        _make_session("DRY02", "2026-10-12", "09:00:00", "09:30:00", record_type=SessionRecordType.ACCEPTANCE_HARNESS_DRY_RUN),
    ]
    summary = OperatorAcceptanceEvaluator.evaluate_acceptance_exercise(records, current_time=current_time)
    assert summary["real_operator_sessions_count"] == 0
    assert summary["dry_run_sessions_count"] == 2
    assert summary["total_real_operating_seconds"] == 0.0


# =============================================================================
# 4. Simulated-Session Exclusion from Acceptance Totals
# =============================================================================
def test_simulated_session_exclusion_from_acceptance_totals():
    """Verify simulated session records are strictly excluded from real acceptance totals."""
    current_time = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)
    records = [
        _make_session("SIM01", "2026-10-12", "08:00:00", "08:30:00", record_type=SessionRecordType.SIMULATED_SESSION),
    ]
    summary = OperatorAcceptanceEvaluator.evaluate_acceptance_exercise(records, current_time=current_time)
    assert summary["real_operator_sessions_count"] == 0
    assert summary["simulated_sessions_count"] == 1
    assert summary["total_real_operating_seconds"] == 0.0


# =============================================================================
# 5. Timestamp-Derived Duration Calculation
# =============================================================================
def test_timestamp_derived_duration_calculation():
    """Verify duration is computed strictly from actual ISO 8601 start and end timestamps."""
    current_time = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)
    rec = _make_session("S01", "2026-10-12", "08:00:00", "08:45:30")
    summary = OperatorAcceptanceEvaluator.evaluate_acceptance_exercise([rec], current_time=current_time)

    # 45 minutes and 30 seconds = 2730.0 seconds
    assert summary["total_real_operating_seconds"] == 2730.0
    assert summary["total_real_operating_hours"] == 2730.0 / 3600.0


# =============================================================================
# 6. Duration Mismatch Rejection
# =============================================================================
def test_caller_declared_duration_mismatch_rejection():
    """Verify rejection when caller-declared duration diverges from timestamp delta."""
    current_time = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)
    # Timestamps indicate 10 seconds, but caller declared 1800.0 seconds
    tampered_rec = _make_session("S01", "2026-10-12", "08:00:00", "08:00:10", declared_duration=1800.0)

    errors = OperatorAcceptanceEvaluator.validate_session_record(tampered_rec, current_time=current_time)
    assert REJECTION_DURATION_MISMATCH in errors


# =============================================================================
# 7. Overlapping-Session Rejection
# =============================================================================
def test_overlapping_session_rejection():
    """Verify that concurrent or overlapping session intervals are rejected."""
    current_time = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)
    records = [
        _make_session("S01", "2026-10-12", "08:00:00", "08:30:00"),
        _make_session("S02", "2026-10-12", "08:15:00", "08:45:00"),  # overlaps with S01
    ]
    summary = OperatorAcceptanceEvaluator.evaluate_acceptance_exercise(records, current_time=current_time)
    assert REJECTION_OVERLAPPING_SESSION in summary["active_blockers"]


# =============================================================================
# 8. Duplicate-Session Rejection
# =============================================================================
def test_duplicate_session_rejection():
    """Verify that duplicate session IDs are rejected fail-closed."""
    current_time = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)
    records = [
        _make_session("S01", "2026-10-12", "08:00:00", "08:30:00"),
        _make_session("S01", "2026-10-12", "09:00:00", "09:30:00"),  # duplicate ID
    ]
    summary = OperatorAcceptanceEvaluator.evaluate_acceptance_exercise(records, current_time=current_time)
    assert REJECTION_DUPLICATE_SESSION in summary["active_blockers"]


# =============================================================================
# 9. Five-Distinct-Day Requirement
# =============================================================================
def test_five_distinct_working_dates_requirement():
    """Verify rejection when sessions span fewer than five distinct working dates."""
    current_time = datetime(2026, 10, 16, 18, 0, 0, tzinfo=timezone.utc)
    # 10 sessions spanning only 4 dates
    records = []
    dates = ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15"]
    for i, d in enumerate(dates):
        records.append(_make_session(f"S{2*i+1:02d}", d, "09:00:00", "09:30:00", is_post_restart=(i < 2)))
        records.append(_make_session(f"S{2*i+2:02d}", d, "14:00:00", "14:30:00"))
    # Add two more on 2026-10-15 (still 4 dates total)
    records.append(_make_session("S09", "2026-10-15", "15:00:00", "15:30:00"))
    records.append(_make_session("S10", "2026-10-15", "16:00:00", "16:30:00"))

    summary = OperatorAcceptanceEvaluator.evaluate_acceptance_exercise(records, current_time=current_time)
    assert any(REJECTION_FIVE_DISTINCT_DATES in b for b in summary["active_blockers"])
    assert summary["distinct_working_dates_count"] == 4


# =============================================================================
# 10. Ten-Real-Session Requirement
# =============================================================================
def test_ten_real_sessions_requirement():
    """Verify rejection when fewer than ten real operator sessions are recorded."""
    current_time = datetime(2026, 10, 16, 18, 0, 0, tzinfo=timezone.utc)
    # Only 8 sessions
    records = [
        _make_session(f"S{i:02d}", f"2026-10-1{i%5+2}", "09:00:00", "09:30:00")
        for i in range(1, 9)
    ]
    summary = OperatorAcceptanceEvaluator.evaluate_acceptance_exercise(records, current_time=current_time)
    assert any(REJECTION_TEN_REAL_SESSIONS in b for b in summary["active_blockers"])
    assert summary["real_operator_sessions_count"] == 8


# =============================================================================
# 11. Five-Hour Operating Time Requirement
# =============================================================================
def test_five_hour_operating_time_requirement():
    """Verify rejection when total real operating time is less than 18,000 seconds (5 hours)."""
    current_time = datetime(2026, 10, 16, 18, 0, 0, tzinfo=timezone.utc)
    # 10 sessions on 5 dates, but each only 10 minutes (600s * 10 = 6000s < 18000s)
    records = []
    dates = ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"]
    for i, d in enumerate(dates):
        records.append(_make_session(f"S{2*i+1:02d}", d, "09:00:00", "09:10:00", is_post_restart=(i < 2)))
        records.append(_make_session(f"S{2*i+2:02d}", d, "14:00:00", "14:10:00"))

    summary = OperatorAcceptanceEvaluator.evaluate_acceptance_exercise(records, current_time=current_time)
    assert any(REJECTION_FIVE_HOURS in b for b in summary["active_blockers"])
    assert summary["total_real_operating_seconds"] == 6000.0


# =============================================================================
# 12. Post-Restart Sessions Requirement
# =============================================================================
def test_post_restart_sessions_requirement():
    """Verify rejection when fewer than two genuinely post-restart sessions are recorded."""
    current_time = datetime(2026, 10, 16, 18, 0, 0, tzinfo=timezone.utc)
    # 10 sessions across 5 dates, 1800s each, but only 1 post-restart session
    records = []
    dates = ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"]
    for i, d in enumerate(dates):
        post = (i == 0)  # only 1 post-restart
        records.append(_make_session(f"S{2*i+1:02d}", d, "09:00:00", "09:30:00", is_post_restart=post))
        records.append(_make_session(f"S{2*i+2:02d}", d, "14:00:00", "14:30:00", is_post_restart=False))

    summary = OperatorAcceptanceEvaluator.evaluate_acceptance_exercise(records, current_time=current_time)
    assert any(REJECTION_POST_RESTART in b for b in summary["active_blockers"])
    assert summary["post_restart_sessions_count"] == 1


# =============================================================================
# 13. Premature-Closure Rejection
# =============================================================================
def test_premature_closure_before_end_date_rejection():
    """Verify rejection when evaluation is attempted before the authorized end date (2026-10-16)."""
    # Current date is 2026-10-12
    current_time = datetime(2026, 10, 12, 10, 0, 0, tzinfo=timezone.utc)
    records = [_make_session("S01", "2026-10-12", "08:00:00", "08:30:00")]

    summary = OperatorAcceptanceEvaluator.evaluate_acceptance_exercise(
        records,
        authorized_end_date="2026-10-16",
        current_time=current_time,
    )
    assert any(REJECTION_PREMATURE_CLOSURE in b for b in summary["active_blockers"])
    assert summary["acceptance_status"] == AcceptanceStatus.IN_PROGRESS.value
    assert summary["acceptance_passed"] is False


# =============================================================================
# 14. Correct Acceptance Status When All Requirements Genuinely Met
# =============================================================================
def test_correct_acceptance_status_when_all_requirements_met():
    """Verify PASS status only when 5 distinct dates, 10 sessions, 18000s, 2 post-restarts are met on or after 2026-10-16."""
    current_time = datetime(2026, 10, 16, 18, 0, 0, tzinfo=timezone.utc)
    records = []
    dates = ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"]
    for i, d in enumerate(dates):
        # 1800s per session * 10 = 18,000s total (5.0 hours)
        records.append(_make_session(f"S{2*i+1:02d}", d, "09:00:00", "09:30:00", is_post_restart=(i < 2)))
        records.append(_make_session(f"S{2*i+2:02d}", d, "14:00:00", "14:30:00", is_post_restart=False))

    summary = OperatorAcceptanceEvaluator.evaluate_acceptance_exercise(
        records,
        authorized_end_date="2026-10-16",
        current_time=current_time,
    )
    assert summary["acceptance_status"] == AcceptanceStatus.PASSED.value
    assert summary["acceptance_passed"] is True
    assert summary["real_operator_sessions_count"] == 10
    assert summary["distinct_working_dates_count"] == 5
    assert summary["total_real_operating_seconds"] == 18000.0
    assert summary["total_real_operating_hours"] == 5.0
    assert summary["post_restart_sessions_count"] == 2
    assert len(summary["active_blockers"]) == 0
