"""Automated test suite for Phase 7 Unified Offline Operator Application.

Milestone 4.12: Validates the read-only, fail-closed, single-instance,
network-quarantined operator application across all 10 views and governance invariants.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import tempfile
import tkinter as tk
from typing import Any, Dict, List
import urllib.request
from unittest.mock import patch

import pytest

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
    ReadOnlyViolationError,
    SingleInstanceLock,
    SingleInstanceLockError,
)
from phase7.operator.cli import OperatorCLI
from phase7.operator.gui import OperatorGUI

pytestmark = [pytest.mark.unit]


# =============================================================================
# 1. Mandatory Governance Banners
# =============================================================================
def test_mandatory_banners_exact_content():
    """Verify all 4 required governance banners are present and unaltered."""
    assert BANNER_INTERNAL_USE == "INTERNAL NON-DISTRIBUTED USE ONLY"
    assert BANNER_ACQUISITION_DEFERRED == "EXTERNAL ACQUISITION DEFERRED BY OWNER"
    assert BANNER_GATE1_NOT_PASSED == "GATE 1 NOT PASSED"
    assert BANNER_MILESTONE5_BLOCKED == "MILESTONE 5 BLOCKED"
    assert len(MANDATORY_BANNERS) == 4
    for b in MANDATORY_BANNERS:
        assert isinstance(b, str) and len(b) > 0


# =============================================================================
# 2. Network Quarantine Tests
# =============================================================================
def test_network_quarantine_blocks_sockets():
    """Verify runtime quarantine intercepts sockets and logs sanitized audit events."""
    audit_events: List[Dict[str, Any]] = []

    def on_audit(evt):
        audit_events.append(evt)

    mgr = NetworkQuarantineManager(audit_callback=on_audit)
    with mgr:
        # socket.socket.connect
        s = socket.socket()
        with pytest.raises(NetworkOperationBlockedError) as exc_info:
            s.connect(("192.0.2.1", 80))
        assert NETWORK_BLOCKED_MESSAGE in str(exc_info.value)

        # socket.create_connection
        with pytest.raises(NetworkOperationBlockedError) as exc_info:
            socket.create_connection(("192.0.2.1", 80))
        assert NETWORK_BLOCKED_MESSAGE in str(exc_info.value)

        # urllib.request.urlopen
        with pytest.raises(NetworkOperationBlockedError) as exc_info:
            urllib.request.urlopen("http://192.0.2.1")
        assert NETWORK_BLOCKED_MESSAGE in str(exc_info.value)

        # httpx.Client.send
        import httpx
        with httpx.Client() as client:
            with pytest.raises(NetworkOperationBlockedError) as exc_info:
                client.get("http://192.0.2.1")
            assert NETWORK_BLOCKED_MESSAGE in str(exc_info.value)

    assert len(audit_events) == 4
    for ev in audit_events:
        assert ev["event"] == "NETWORK_OPERATION_BLOCKED"
        assert ev["status"] == "BLOCKED"
        assert ev["message"] == NETWORK_BLOCKED_MESSAGE
        assert ev["retry_performed"] is False
        assert ev["read_only_preserved"] is True


# =============================================================================
# 3. Single-Instance Locking Tests
# =============================================================================
def test_single_instance_locking_and_rejection():
    """Verify single-instance application lock prevents concurrent execution."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        lock1 = SingleInstanceLock(lock_dir=tmp_path)
        lock2 = SingleInstanceLock(lock_dir=tmp_path)

        lock1.acquire()
        assert lock1.is_locked is True

        # Second acquisition attempt must fail
        with pytest.raises(SingleInstanceLockError):
            lock2.acquire()

        assert lock2.is_locked is False

        # Release first lock allows second to acquire
        lock1.release()
        assert lock1.is_locked is False

        lock2.acquire()
        assert lock2.is_locked is True
        lock2.release()


# =============================================================================
# 4. Read-Only Guard Tests
# =============================================================================
def test_read_only_guard_prohibits_mutations():
    """Verify read-only guard refuses all repairs, edits, resumes, or fallbacks."""
    guard = ReadOnlyEvidenceGuard()

    with pytest.raises(ReadOnlyViolationError):
        guard.refuse_manifest_repair(r"C:\Users\r_chh\gaurvideep_phase7_staging\nse500\batch_4_10c\manifests\m.json")

    with pytest.raises(ReadOnlyViolationError):
        guard.refuse_checkpoint_repair(r"C:\Users\r_chh\gaurvideep_phase7_staging\nse500\batch_4_10c\checkpoints\c.json")

    with pytest.raises(ReadOnlyViolationError):
        guard.refuse_marker_restoration(r"C:\Users\r_chh\gaurvideep_phase7_staging\nse500\batch_4_10c\auth\marker.json")

    with pytest.raises(ReadOnlyViolationError):
        guard.refuse_marker_consumption(r"C:\Users\r_chh\gaurvideep_phase7_staging\nse500\batch_4_10c\auth\marker.json")

    with pytest.raises(ReadOnlyViolationError):
        guard.refuse_automatic_resume("BATCH_4_10C")

    with pytest.raises(ReadOnlyViolationError):
        guard.refuse_fallback_generation("PREMIERENE")


def test_inspect_file_health_non_mutating():
    """Verify file health inspection returns governed statuses without modifying files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        test_file = tmp_path / "sample.csv"
        test_file.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
        expected_sha = hashlib.sha256(test_file.read_bytes()).hexdigest()

        # Valid file
        res = ReadOnlyEvidenceGuard.inspect_file_health(test_file, expected_sha)
        assert res["status"] == "PRESERVED_VALID"
        assert res["valid"] is True

        # Missing file
        missing_file = tmp_path / "missing.csv"
        res_missing = ReadOnlyEvidenceGuard.inspect_file_health(missing_file, expected_sha)
        assert res_missing["status"] == "EVIDENCE_MISSING"
        assert res_missing["valid"] is False
        assert not missing_file.exists()  # Ensure no file was created

        # Corrupted checksum
        res_corrupt = ReadOnlyEvidenceGuard.inspect_file_health(test_file, "0000000000000000000000000000000000000000000000000000000000000000")
        assert res_corrupt["status"] == "CHECKSUM_MISMATCH_CORRUPT"
        assert res_corrupt["valid"] is False


# =============================================================================
# 5. Screen 1: Readiness Dashboard Tests
# =============================================================================
def test_screen_1_readiness_dashboard():
    """Verify readiness dashboard returns confirmed status and 15 passing domains."""
    core = OperatorCore()
    data = core.get_readiness_dashboard()

    assert data["classification"] == READINESS_CLASSIFICATION
    assert data["test_summary"]["total_passing"] == 794
    assert data["test_summary"]["baseline_passing"] == 544
    assert data["test_summary"]["new_passing"] == 250
    assert data["drill_summary"]["passed_drills"] == 16
    assert data["drill_summary"]["total_drills"] == 16

    domains = data["scorecard"]["domains"]
    assert len(domains) == 15
    for d_id, sc in domains.items():
        assert sc["status"] == "PASS"


# =============================================================================
# 6. Screen 2: Evidence Inventory Tests
# =============================================================================
def test_screen_2_evidence_inventory():
    """Verify evidence inventory indexes preserved files and computes SHA-256."""
    core = OperatorCore()
    inv = core.get_evidence_inventory()

    assert inv["total_assets"] >= 50
    for asset in inv["assets"]:
        assert asset["status"] == "PRESERVED_IMMUTABLE"
        assert len(asset["sha256"]) == 64
        assert asset["size_bytes"] >= 0


# =============================================================================
# 7. Screen 3: Manifest Verifier Tests
# =============================================================================
def test_screen_3_manifest_verifier():
    """Verify manifest verification checks row conservation and checksums."""
    core = OperatorCore()
    data = core.verify_manifests()

    assert data["total_manifests"] > 0
    assert data["verified"] >= 10
    for m in data["manifests"]:
        assert "symbol" in m
        assert "verification_status" in m
        assert m["repair_attempted"] is False


# =============================================================================
# 8. Screen 4: Batch-State Viewer Tests
# =============================================================================
def test_screen_4_batch_state():
    """Verify halted batch state displays contract, checkpoint, and markers."""
    core = OperatorCore()
    bs = core.get_batch_state()

    assert bs["governing_state"] == "HALTED_BY_OWNER_DECISION"
    assert bs["acquisition_state"] == "EXTERNAL_EVIDENCE_ACQUISITION_DEFERRED_BY_OWNER"
    assert bs["resume_policy"] == "AUTOMATIC_RESUME_STRICTLY_PROHIBITED"
    assert bs["resume_disabled"] is True
    assert bs["status"] == "HALTED"
    assert bs["failed_symbol"] == "PREMIERENE"
    assert bs["listing_date_status"] == "LISTING_DATE_UNVERIFIED"
    assert bs["retrospective_outcome"] == "EMPTY_RESPONSE_UNEXPLAINED"
    assert bs["checkpoint"]["total_governed_symbols"] == 20
    assert bs["authorization_markers"]["active_markers_count"] == 0


# =============================================================================
# 9. Screen 5: Operational-Drill Viewer Tests
# =============================================================================
def test_screen_5_operational_drills():
    """Verify all 16 drills loaded with exit-code disambiguation."""
    core = OperatorCore()
    drills_data = core.get_drill_results()

    assert drills_data["total_drills"] == 16
    assert drills_data["all_drills_passed"] is True

    drills_by_id = {d["drill_id"]: d for d in drills_data["drills"]}

    # Verify DRILL-08 exit-code semantics
    d8 = drills_by_id["DRILL-08"]
    assert d8["drill_runner_exit_code"] == 0
    assert d8["system_under_test_exit_code"] == 1
    assert d8["expected_system_exit_code"] == 1
    assert d8["drill_passed"] is True

    # Verify DRILL-09 exit-code semantics
    d9 = drills_by_id["DRILL-09"]
    assert d9["drill_runner_exit_code"] == 0
    assert d9["system_under_test_exit_code"] == 1
    assert d9["expected_system_exit_code"] == 1
    assert d9["drill_passed"] is True


# =============================================================================
# 10. Screen 6: Backup and Restore Verifier Tests
# =============================================================================
def test_screen_6_backup_restore_verification():
    """Verify backup verification validates bit-for-bit SHA-256 and temp exclusion."""
    core = OperatorCore()
    data = core.verify_backup_restoration()

    assert data["files_inventoried"] > 0
    assert data["files_verified_bit_for_bit"] == data["files_inventoried"]
    assert data["mismatches"] == 0
    assert data["temporary_files_excluded"] is True
    assert data["zero_data_loss_confirmed"] is True

    # Test rejection of Git destination
    git_res = core.verify_backup_restoration(restore_target=core.repo_root / "data")
    assert git_res["status"] == "GIT_DESTINATION_REJECTED"

    # Test rejection of non-empty destination
    with tempfile.TemporaryDirectory() as tmp_dir:
        non_empty = Path(tmp_dir) / "target"
        non_empty.mkdir()
        (non_empty / "existing.txt").write_text("pre-existing")
        rej_res = core.verify_backup_restoration(restore_target=non_empty)
        assert rej_res["status"] == "RESTORE_TARGET_REJECTED"


# =============================================================================
# 11. Screen 7: Governance and Blockers Tests
# =============================================================================
def test_screen_7_governance_and_blockers():
    """Verify blocker registry reflects Owner Decision and Gate 1 blockers."""
    core = OperatorCore()
    gov = core.get_governance_and_blockers()

    assert gov["owner_decision"]["decision_id"] == "DEC-20261010-36"
    assert gov["gate_status"]["gate_1"] == "NOT_PASSED"
    assert gov["gate_status"]["milestone_5"] == "BLOCKED"

    blocker_map = {b["blocker_id"]: b["status"] for b in gov["blockers"]}
    assert blocker_map["BLK-01"] == "STILL_BLOCKED"
    assert blocker_map["BLK-02"] == "STILL_BLOCKED"
    assert blocker_map["BLK-03"] == "RESOLVED"
    assert blocker_map["BLK-04"] == "STILL_BLOCKED"


# =============================================================================
# 12. Screen 8: Authorization Registry Tests
# =============================================================================
def test_screen_8_authorization_registry():
    """Verify authorization registry shows 0 active markers and consumed count."""
    core = OperatorCore()
    reg = core.get_authorization_registry()

    assert reg["active_authorization_markers"] == 0
    assert reg["consumed_authorization_markers"] >= 5
    assert reg["marker_creation_allowed"] is False
    assert reg["marker_replay_allowed"] is False


# =============================================================================
# 13. Screen 9: Metadata-Only Audit Export Tests
# =============================================================================
def test_screen_9_metadata_audit_export():
    """Verify metadata audit export generates sanitized JSON with SHA-256."""
    core = OperatorCore()
    with tempfile.TemporaryDirectory() as tmp_dir:
        res = core.export_metadata_audit(output_dir=Path(tmp_dir))

        assert res["status"] == "METADATA_AUDIT_EXPORT_SUCCESSFUL"
        assert Path(res["export_file"]).exists()
        assert len(res["export_sha256"]) == 64
        assert res["total_evidence_hashes"] >= 50

        # Read exported payload and verify sanitization
        content = Path(res["export_file"]).read_text(encoding="utf-8")
        payload = json.loads(content)
        assert payload["contains_market_prices"] is False
        assert payload["contains_credentials"] is False
        assert payload["quarantine_status"] == "ZERO_NETWORK_CALLS_ENFORCED"


# =============================================================================
# 14. Screen 10: Synthetic Demonstration Mode Tests
# =============================================================================
def test_screen_10_synthetic_demonstration_mode():
    """Verify synthetic demo processes 5 fixtures and catches fault fail-closed."""
    core = OperatorCore()
    demo = core.run_synthetic_demonstration()

    assert demo["symbols_processed"] == 5
    assert demo["clean_symbols_passed"] == 4
    assert demo["tampered_symbols_detected"] == 1
    assert demo["fail_closed_verified"] is True
    assert demo["zero_staging_mutation_confirmed"] is True


# =============================================================================
# 15. CLI Rendering Across All 10 Screens Tests
# =============================================================================
def test_cli_renders_all_10_screens():
    """Verify CLI formats all 10 screens with mandatory banners."""
    cli = OperatorCLI()
    for s in range(1, 11):
        output = cli.render_screen(s)
        assert BANNER_INTERNAL_USE in output
        assert BANNER_ACQUISITION_DEFERRED in output
        assert BANNER_GATE1_NOT_PASSED in output
        assert BANNER_MILESTONE5_BLOCKED in output
        assert f"SCREEN {s}:" in output


# =============================================================================
# 16. Tkinter GUI Headless Initialization Tests
# =============================================================================
def test_gui_headless_initialization():
    """Verify Tkinter desktop application initializes headlessly and populates tabs."""
    root = tk.Tk()
    root.withdraw()
    try:
        core = OperatorCore()
        gui = OperatorGUI(root, core=core)

        assert gui.notebook.index("end") == 10
        assert gui.export_text is not None
        assert gui.demo_text is not None

        # Verify export and demo handlers inside GUI
        gui._handle_audit_export()
        assert "METADATA_AUDIT_EXPORT_SUCCESSFUL" in gui.export_text.get("1.0", tk.END)

        gui._handle_synthetic_demo()
        assert "SYNTHETIC_DEMO_RUN" in gui.demo_text.get("1.0", tk.END)
    finally:
        root.destroy()
