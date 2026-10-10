"""Operational Drill Program: 16 Governed Fault-Injection Drills.

Module docstring:
- Protected production invariants: All 16 fault-injection drills must execute against external staging,
  verify fail-closed stops, ensure zero false success, preserve uncorrupted evidence, verify exit codes,
  and write auditable drill JSON records strictly to C:\\Users\\r_chh\\gaurvideep_phase7_staging\\nse500\\production_readiness_4_11\\drills\\.
- Fault classes covered: DRILL-01 through DRILL-16: pre/post authorization crashes, mid-pipeline crashes,
  raw/normalized checksum corruption, manifest deletion, concurrent process collision, disk full (ENOSPC),
  permission denied (EACCES), client close failure, consumed-marker replay, repo path escape, backup/restore,
  and accelerated 1,000-cycle state-machine soak simulation.
- Why tests are not duplicates: These 16 drills form the formal operational verification battery required
  for internal production-readiness signoff.
"""

from pathlib import Path
import pytest

from phase7.operations.drill_runner import (
    DEFAULT_DRILL_STAGING_DIR,
    OperationalDrillRunner,
)

pytestmark = [pytest.mark.drill]


@pytest.fixture(scope="module")
def drill_runner(repo_root: Path) -> OperationalDrillRunner:
    """Instantiate the operational drill runner configured for external staging."""
    return OperationalDrillRunner(staging_root=DEFAULT_DRILL_STAGING_DIR, repo_root=repo_root)


# DRILL-01: Crash immediately before authorization consumption
def test_drill_01_pre_consumption_crash(drill_runner: OperationalDrillRunner):
    rec = drill_runner.run_drill_01()
    assert rec.passed is True
    assert rec.exit_code == 1
    assert rec.checksum_status == "VERIFIED_UNCHANGED"
    assert rec.operator_decision == "PROCEED_PASS"


# DRILL-02: Crash immediately after authorization consumption
def test_drill_02_post_consumption_crash(drill_runner: OperationalDrillRunner):
    rec = drill_runner.run_drill_02()
    assert rec.passed is True
    assert rec.exit_code == 1
    assert rec.checksum_status == "VERIFIED_CONSUMED"
    assert rec.operator_decision == "PROCEED_PASS"


# DRILL-03: Crash after response receipt before raw persistence
def test_drill_03_pre_raw_persistence_crash(drill_runner: OperationalDrillRunner):
    rec = drill_runner.run_drill_03()
    assert rec.passed is True
    assert rec.exit_code == 1
    assert rec.checksum_status == "NO_FILE_PRESENT"
    assert rec.operator_decision == "PROCEED_PASS"


# DRILL-04: Crash after raw persistence but before normalization
def test_drill_04_pre_normalization_crash(drill_runner: OperationalDrillRunner):
    rec = drill_runner.run_drill_04()
    assert rec.passed is True
    assert rec.exit_code == 1
    assert rec.checksum_status == "RAW_VALID_NORM_ABSENT"
    assert rec.operator_decision == "PROCEED_PASS"


# DRILL-05: Crash after normalized persistence before manifest finalization
def test_drill_05_pre_manifest_crash(drill_runner: OperationalDrillRunner):
    rec = drill_runner.run_drill_05()
    assert rec.passed is True
    assert rec.exit_code == 1
    assert rec.checksum_status == "RAW_NORM_PRESENT_MANIFEST_ABSENT"
    assert rec.operator_decision == "PROCEED_PASS"


# DRILL-06: Corrupt a raw checksum
def test_drill_06_corrupt_raw_checksum(drill_runner: OperationalDrillRunner):
    rec = drill_runner.run_drill_06()
    assert rec.passed is True
    assert rec.exit_code == 1
    assert rec.checksum_status == "CORRUPTION_DETECTED"
    assert rec.operator_decision == "PROCEED_PASS"


# DRILL-07: Corrupt a normalized checksum
def test_drill_07_corrupt_normalized_checksum(drill_runner: OperationalDrillRunner):
    rec = drill_runner.run_drill_07()
    assert rec.passed is True
    assert rec.exit_code == 1
    assert rec.checksum_status == "CORRUPTION_DETECTED"
    assert rec.operator_decision == "PROCEED_PASS"


# DRILL-08: Delete a finalized manifest
def test_drill_08_delete_finalized_manifest(drill_runner: OperationalDrillRunner):
    rec = drill_runner.run_drill_08()
    assert rec.passed is True
    assert rec.checksum_status == "MANIFEST_MISSING_DETECTED"
    assert rec.operator_decision == "PROCEED_PASS"


# DRILL-09: Attempt two concurrent batch processes
def test_drill_09_concurrent_processes_lock(drill_runner: OperationalDrillRunner):
    rec = drill_runner.run_drill_09()
    assert rec.passed is True
    assert rec.checksum_status == "EXCLUSIVE_LOCK_ENFORCED"
    assert rec.operator_decision == "PROCEED_PASS"


# DRILL-10: Simulate disk full during raw write
def test_drill_10_disk_full_raw_write(drill_runner: OperationalDrillRunner):
    rec = drill_runner.run_drill_10()
    assert rec.passed is True
    assert rec.exit_code == 28
    assert rec.cleanup_status == "TEMP_CLEANED"
    assert rec.operator_decision == "PROCEED_PASS"


# DRILL-11: Simulate permission denied during manifest finalization
def test_drill_11_permission_denied_manifest(drill_runner: OperationalDrillRunner):
    rec = drill_runner.run_drill_11()
    assert rec.passed is True
    assert rec.exit_code == 13
    assert rec.checksum_status == "NO_FALSE_SUCCESS"
    assert rec.operator_decision == "PROCEED_PASS"


# DRILL-12: Simulate client-close failure
def test_drill_12_client_close_failure(drill_runner: OperationalDrillRunner):
    rec = drill_runner.run_drill_12()
    assert rec.passed is True
    assert rec.exit_code == 9
    assert rec.checksum_status == "SUCCESS_PROHIBITED"
    assert rec.operator_decision == "PROCEED_PASS"


# DRILL-13: Attempt consumed-marker replay
def test_drill_13_consumed_marker_replay(drill_runner: OperationalDrillRunner):
    rec = drill_runner.run_drill_13()
    assert rec.passed is True
    assert rec.exit_code == 1
    assert rec.checksum_status == "REPLAY_REJECTED"
    assert rec.operator_decision == "PROCEED_PASS"


# DRILL-14: Attempt repository-path escape through symlink or traversal
def test_drill_14_repository_escape_attempt(drill_runner: OperationalDrillRunner):
    rec = drill_runner.run_drill_14()
    assert rec.passed is True
    assert rec.exit_code == 1
    assert rec.checksum_status == "NO_REPO_WRITE"
    assert rec.operator_decision == "PROCEED_PASS"


# DRILL-15: Restore synthetic batch from backup and revalidate checksums
def test_drill_15_backup_restore_reconciliation(drill_runner: OperationalDrillRunner):
    rec = drill_runner.run_drill_15()
    assert rec.passed is True
    assert rec.exit_code == 0
    assert rec.checksum_status == "ALL_CHECKSUMS_VERIFIED"
    assert rec.operator_decision == "PROCEED_PASS"


# DRILL-16: Accelerated state-machine soak simulation (1,000 cycles)
def test_drill_16_accelerated_soak_simulation(drill_runner: OperationalDrillRunner):
    rec = drill_runner.run_drill_16(cycle_count=1000)
    assert rec.passed is True
    assert rec.exit_code == 0
    assert rec.checksum_status == "SOAK_CHECKSUMS_STABLE"
    assert rec.cleanup_status == "NO_LEAKED_TEMPORARY_FILES"
    assert rec.operator_decision == "PROCEED_PASS"
