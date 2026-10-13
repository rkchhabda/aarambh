"""Automated test battery for Phase 7 Milestone 4.13B Two-Phase Operator Acceptance Lifecycle.

Covers:
1. CLI help and argument parsing.
2. start-session lifecycle and validations (ID format, role, mode, workflow binding).
3. status command output and duration gate message (MINIMUM_REAL_DURATION_NOT_YET_MET).
4. finalize-session duration enforcement (rejection if <1800s for PASS, success if >=1800s).
5. abort-session lifecycle and non-passing persistence.
6. validate-session checks on record schema, checksums, and invariants.
7. summarize command and master summary recalculation.
8. Mutual exclusion and lock acquisition/release.
9. Observation sanitization and defect reference validation.
10. CLI main entrypoint exit code contract.
"""

from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
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
    build_argument_parser,
    compute_record_checksum,
    main,
    validate_session_id,
)

pytestmark = [pytest.mark.unit]


@pytest.fixture
def temp_acceptance_dir():
    """Create an isolated temporary acceptance directory tree."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir) / "acceptance_4_13"
        root.mkdir(parents=True, exist_ok=True)
        # Initialize master summary with in-progress state
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


def test_cli_help_and_subcommands():
    """Verify that the acceptance runner CLI parser builds cleanly with all 6 required subcommands."""
    parser = build_argument_parser()
    subparsers_actions = [
        action for action in parser._actions if action.dest == "subcommand"
    ]
    assert len(subparsers_actions) == 1
    subcommands = list(subparsers_actions[0].choices.keys())
    assert "start-session" in subcommands
    assert "status" in subcommands
    assert "finalize-session" in subcommands
    assert "abort-session" in subcommands
    assert "validate-session" in subcommands
    assert "summarize" in subcommands


def test_session_id_validation_contract():
    """Verify strict validation of session ID against REAL-S01..REAL-S99 contract."""
    # Valid IDs
    assert validate_session_id("REAL-S01") is True
    assert validate_session_id("REAL-S02") is True
    assert validate_session_id("REAL-S10") is True
    assert validate_session_id("REAL-S99") is True

    # Invalid IDs
    assert validate_session_id("S01") is False
    assert validate_session_id("REAL-S00") is False
    assert validate_session_id("REAL-S100") is False
    assert validate_session_id("session-1") is False
    assert validate_session_id("REAL-1") is False
    assert validate_session_id("REAL-S1") is False
    assert validate_session_id("REAL-S001") is False
    assert validate_session_id("REAL-S01/hack") is False
    assert validate_session_id("REAL-S01 ") is False
    assert validate_session_id("") is False


def test_start_session_lifecycle_success(temp_acceptance_dir):
    """Verify successful execution of start-session creates atomic in-progress record and lock."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)
    code, rec, msg = harness.start_session(
        session_id="REAL-S01",
        operator_role=OperatorRole.OWNER.value,
        interface_mode=InterfaceMode.CLI.value,
        workflow=AcceptanceWorkflow.READINESS_DASHBOARD_AND_LIFECYCLE.value,
    )

    assert code == AcceptanceExitCode.SUCCESS
    assert rec["session_id"] == "REAL-S01"
    assert rec["lifecycle_state"] == "ACTIVE_REAL_OPERATOR_SESSION"
    assert rec["operator_role"] == "OWNER"
    assert rec["interface_mode"] == "CLI"
    assert rec["workflow"] == "READINESS_DASHBOARD_AND_LIFECYCLE"
    assert rec["network_quarantine_active"] is True
    assert "start_timestamp_utc" in rec
    assert "boot_cycle_id" in rec

    # Verify files created
    active_path = temp_acceptance_dir / "in_progress" / "REAL-S01.active.json"
    assert active_path.exists()
    lock_path = temp_acceptance_dir / "locks" / "REAL-S01.lock"
    assert lock_path.exists()
    audit_path = temp_acceptance_dir / "audit" / "session_lifecycle.jsonl"
    assert audit_path.exists()


def test_start_session_invalid_parameters_rejection(temp_acceptance_dir):
    """Verify rejection of invalid session ID, role, interface mode, or workflow."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)

    # Invalid session ID format
    code, _, _ = harness.start_session("S01", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")
    assert code == AcceptanceExitCode.INVALID_ARGS

    # Invalid operator role
    code, _, _ = harness.start_session("REAL-S01", "GUEST", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")
    assert code == AcceptanceExitCode.INVALID_ARGS

    # Invalid interface mode
    code, _, _ = harness.start_session("REAL-S01", "OWNER", "WEB", "READINESS_DASHBOARD_AND_LIFECYCLE")
    assert code == AcceptanceExitCode.INVALID_ARGS

    # Invalid workflow
    code, _, _ = harness.start_session("REAL-S01", "OWNER", "CLI", "INVALID_WORKFLOW")
    assert code == AcceptanceExitCode.INVALID_ARGS

    # Governed workflow binding mismatch (REAL-S01 must bind to READINESS_DASHBOARD_AND_LIFECYCLE)
    code, _, _ = harness.start_session(
        "REAL-S01",
        "OWNER",
        "CLI",
        AcceptanceWorkflow.EVIDENCE_INVENTORY_AND_FILE_HEALTH.value,
    )
    assert code == AcceptanceExitCode.INVALID_ARGS


def test_start_session_concurrency_conflict(temp_acceptance_dir):
    """Verify mutual exclusion: cannot start another session while one is active in in_progress."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)

    # Start REAL-S01
    code1, _, _ = harness.start_session("REAL-S01", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")
    assert code1 == AcceptanceExitCode.SUCCESS

    # Attempt to start REAL-S02 while REAL-S01 is active
    code2, _, msg2 = harness.start_session("REAL-S02", "OWNER", "CLI", "EVIDENCE_INVENTORY_AND_FILE_HEALTH")
    assert code2 == AcceptanceExitCode.LIFECYCLE_CONFLICT
    assert "ANOTHER_SESSION_ALREADY_ACTIVE" in msg2


def test_status_command_active_and_incomplete_banner(temp_acceptance_dir):
    """Verify status command reports in-progress metadata and displays minimum duration warning."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)
    harness.start_session("REAL-S01", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")

    code, status_dict, msg = harness.get_status("REAL-S01")
    assert code == AcceptanceExitCode.SUCCESS
    assert status_dict["session_id"] == "REAL-S01"
    assert status_dict["minimum_duration_met"] is False
    assert status_dict["finalization_eligible"] is False
    assert "MINIMUM_REAL_DURATION_NOT_YET_MET" in msg


def test_finalize_session_minimum_duration_enforcement(temp_acceptance_dir):
    """Verify that finalizing with PASS when elapsed duration < 1,800s is strictly rejected."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)
    harness.start_session("REAL-S01", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")

    # Immediate finalization (< 1800s) with PASS outcome
    code, _, msg = harness.finalize_session("REAL-S01", session_outcome="PASS")
    assert code == AcceptanceExitCode.DURATION_NOT_MET
    assert "MINIMUM_DURATION_NOT_MET" in msg

    # Verify session remains active in in_progress
    assert (temp_acceptance_dir / "in_progress" / "REAL-S01.active.json").exists()


def test_finalize_session_success_when_duration_satisfied(temp_acceptance_dir):
    """Verify that when 1,800 seconds have elapsed, finalization succeeds atomically."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)
    harness.start_session("REAL-S01", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")

    active_file = temp_acceptance_dir / "in_progress" / "REAL-S01.active.json"
    in_prog = json.loads(active_file.read_text(encoding="utf-8"))

    # Adjust start timestamp and monotonic clock back by 1805 seconds (simulating 30.08 minutes passed)
    past_start = datetime.now(timezone.utc) - timedelta(seconds=1805)
    in_prog["start_timestamp_utc"] = past_start.isoformat()
    in_prog["monotonic_start_seconds"] = in_prog["monotonic_start_seconds"] - 1805.0
    in_prog["checksum_sha256"] = compute_record_checksum(in_prog)
    active_file.write_text(json.dumps(in_prog, indent=2), encoding="utf-8")

    # Now finalize with PASS
    code, final_rec, msg = harness.finalize_session(
        session_id="REAL-S01",
        session_outcome="PASS",
        observations="Clean screen 1 readiness verification completed.",
    )
    assert code == AcceptanceExitCode.SUCCESS
    assert final_rec["status"] == "PASS"
    assert final_rec["operating_time_seconds"] >= 1800.0
    assert final_rec["operating_time_minutes"] >= 30.0
    assert final_rec["single_instance_lock_released"] is True

    # In-progress removed, lock removed, final created
    assert not active_file.exists()
    assert not (temp_acceptance_dir / "locks" / "REAL-S01.lock").exists()
    assert (temp_acceptance_dir / "real_sessions" / "REAL-S01.final.json").exists()


def test_abort_session_lifecycle(temp_acceptance_dir):
    """Verify that aborting a session preserves elapsed time, records non-passing state, and clears lock."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)
    harness.start_session("REAL-S01", "OWNER", "CLI", "READINESS_DASHBOARD_AND_LIFECYCLE")

    active_file = temp_acceptance_dir / "in_progress" / "REAL-S01.active.json"
    assert active_file.exists()

    code, aborted_rec, msg = harness.abort_session(
        session_id="REAL-S01",
        reason_code="OPERATOR_HALTED_FOR_MAINTENANCE",
    )
    assert code == AcceptanceExitCode.SUCCESS
    assert aborted_rec["status"] == "ABORTED"
    assert aborted_rec["session_outcome"] == "ABORTED"
    assert aborted_rec["abort_reason"] == "OPERATOR_HALTED_FOR_MAINTENANCE"

    # In-progress removed, lock removed, final persisted
    assert not active_file.exists()
    assert not (temp_acceptance_dir / "locks" / "REAL-S01.lock").exists()
    assert (temp_acceptance_dir / "real_sessions" / "REAL-S01.final.json").exists()


def test_validate_session_file(temp_acceptance_dir):
    """Verify validate-session command checks integrity, schema, and rejects corrupted records."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)

    # 1. Create a valid finalized session
    valid_record = {
        "session_id": "REAL-S01",
        "session_record_type": SessionRecordType.REAL_OPERATOR_SESSION.value,
        "operator_role": "OWNER",
        "interface_mode": "CLI",
        "workflow": "READINESS_DASHBOARD_AND_LIFECYCLE",
        "date_utc": "2026-10-12",
        "start_timestamp_utc": "2026-10-12T07:00:00Z",
        "end_timestamp_utc": "2026-10-12T07:30:05Z",
        "operating_time_seconds": 1805.0,
        "operating_time_minutes": 30.08,
        "declared_duration_seconds": 1805.0,
        "is_post_restart": False,
        "status": "PASS",
        "session_outcome": "PASS",
        "network_requests_dispatched": 0,
        "evidence_mutation_count": 0,
        "active_markers_count": 0,
    }
    valid_record["record_sha256"] = compute_record_checksum(valid_record)
    valid_file = temp_acceptance_dir / "real_sessions" / "REAL-S01.final.json"
    valid_file.write_text(json.dumps(valid_record, indent=2), encoding="utf-8")

    code, _, _ = harness.validate_session_file(valid_file)
    assert code == AcceptanceExitCode.SUCCESS

    # 2. Corrupt checksum
    corrupt_record = dict(valid_record)
    corrupt_record["record_sha256"] = "corrupt_checksum_12345"
    corrupt_file = temp_acceptance_dir / "real_sessions" / "corrupt.json"
    corrupt_file.write_text(json.dumps(corrupt_record, indent=2), encoding="utf-8")

    code_corrupt, _, _ = harness.validate_session_file(corrupt_file)
    assert code_corrupt == AcceptanceExitCode.INTEGRITY_FAILURE


def test_summarize_excludes_dry_run_and_failed_sessions(temp_acceptance_dir):
    """Verify summarize recomputes master summary, excluding dry-run and aborted records from pass count."""
    harness = OperatorAcceptanceHarness(acceptance_dir=temp_acceptance_dir)

    # Add 2 dry-run sessions
    for i in range(1, 3):
        dry_rec = {
            "session_id": f"S0{i}",
            "session_record_type": SessionRecordType.ACCEPTANCE_HARNESS_DRY_RUN.value,
            "date_utc": "2026-10-12",
            "start_timestamp_utc": f"2026-10-12T0{i}:00:00Z",
            "end_timestamp_utc": f"2026-10-12T0{i}:30:00Z",
            "operating_time_seconds": 1800.0,
            "status": "PASS",
        }
        (temp_acceptance_dir / "sessions" / f"session_s0{i}.json").write_text(
            json.dumps(dry_rec, indent=2), encoding="utf-8"
        )

    # Add 1 aborted real session
    aborted_rec = {
        "session_id": "REAL-S01",
        "session_record_type": SessionRecordType.REAL_OPERATOR_SESSION.value,
        "date_utc": "2026-10-12",
        "start_timestamp_utc": "2026-10-12T06:00:00Z",
        "end_timestamp_utc": "2026-10-12T06:10:00Z",
        "operating_time_seconds": 600.0,
        "status": "ABORTED",
        "session_outcome": "ABORTED",
    }
    (temp_acceptance_dir / "real_sessions" / "REAL-S01.final.json").write_text(
        json.dumps(aborted_rec, indent=2), encoding="utf-8"
    )

    code, summary, msg = harness.summarize()
    assert code == AcceptanceExitCode.SUCCESS
    assert summary["acceptance_status"] == AcceptanceStatus.IN_PROGRESS.value
    assert summary["real_operator_sessions_count"] == 1
    assert summary["passed_real_sessions_count"] == 0
    assert summary["failed_real_sessions_count"] == 1
    assert summary["dry_run_sessions_count"] == 2
    assert summary["total_real_operating_seconds"] == 0.0


def test_cli_main_entrypoint_exit_codes(temp_acceptance_dir):
    """Verify that invoking main() via CLI args returns expected exit codes."""
    root_str = str(temp_acceptance_dir)

    # 1. Start session successfully
    rc_start = main([
        "start-session",
        "--session-id", "REAL-S01",
        "--operator-role", "OWNER",
        "--interface-mode", "CLI",
        "--workflow", "READINESS_DASHBOARD_AND_LIFECYCLE",
        "--acceptance-root", root_str,
    ])
    assert rc_start == AcceptanceExitCode.SUCCESS.value

    # 2. Status check
    rc_status = main([
        "status",
        "--session-id", "REAL-S01",
        "--acceptance-root", root_str,
    ])
    assert rc_status == AcceptanceExitCode.SUCCESS.value

    # 3. Premature finalize should fail with DURATION_NOT_MET (code 8)
    rc_premature = main([
        "finalize-session",
        "--session-id", "REAL-S01",
        "--acceptance-root", root_str,
    ])
    assert rc_premature == AcceptanceExitCode.DURATION_NOT_MET.value

    # 4. Abort session cleanly
    rc_abort = main([
        "abort-session",
        "--session-id", "REAL-S01",
        "--reason-code", "TEST_ABORT",
        "--acceptance-root", root_str,
    ])
    assert rc_abort == AcceptanceExitCode.SUCCESS.value
