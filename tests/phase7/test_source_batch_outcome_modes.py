"""Tests for Phase 7 batch outcome modes (Mode 1 vs Mode 2)."""

import hashlib
import json
from pathlib import Path
import tempfile
import pytest

from phase7.sources.batch_audit import generate_batch_audit_payload
from phase7.sources.batch_checkpoint import (
    BatchCheckpoint,
    BatchStatus,
    BatchSymbolStatus,
    SymbolCheckpoint,
    create_initial_batch_checkpoint,
)
from phase7.sources.batch_contract import (
    REQUIRED_AUTHORIZATION_SCOPE,
    REQUIRED_CLASSIFICATION,
    REQUIRED_END_DATE,
    REQUIRED_INTERVAL,
    REQUIRED_PANEL_VERSION,
    REQUIRED_SCHEMA_MAPPING_VERSION,
    REQUIRED_SNAPSHOT_CHECKSUM,
    REQUIRED_START_DATE,
    REQUIRED_SYMBOL_COUNT,
    BatchContract,
    BatchOutcomeMode,
    BatchSymbolOutcome,
    validate_batch_contract,
)


def _build_contract(staging_root: Path, outcome_mode: str = None) -> BatchContract:
    staging_hash = hashlib.sha256(str(staging_root.resolve()).encode("utf-8")).hexdigest()
    return BatchContract(
        batch_id="test_outcome_mode_batch",
        source_panel_version=REQUIRED_PANEL_VERSION,
        source_snapshot_checksum=REQUIRED_SNAPSHOT_CHECKSUM,
        selection_checksum="a" * 64,
        symbol_count=REQUIRED_SYMBOL_COUNT,
        ordered_symbols_hash="b" * 64,
        start_date=REQUIRED_START_DATE,
        end_date=REQUIRED_END_DATE,
        interval=REQUIRED_INTERVAL,
        staging_root_hash=staging_hash,
        schema_mapping_version=REQUIRED_SCHEMA_MAPPING_VERSION,
        maximum_concurrency=1,
        minimum_request_spacing_seconds=2.0,
        maximum_retries=0,
        failure_threshold=1,
        authorization_scope=REQUIRED_AUTHORIZATION_SCOPE,
        classification=REQUIRED_CLASSIFICATION,
        batch_status=BatchStatus.INITIALIZED.value,
        created_timestamp="2026-10-10T12:00:00Z",
        outcome_mode=outcome_mode,
    )


def test_mode_1_and_mode_2_contract_validation():
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)

        # Default / None outcome_mode
        c_default = _build_contract(root, outcome_mode=None)
        validate_batch_contract(c_default)

        # Mode 1
        c_mode1 = _build_contract(root, outcome_mode=BatchOutcomeMode.TWENTY_DATA_BEARING_SECURITIES.value)
        validate_batch_contract(c_mode1)

        # Mode 2
        c_mode2 = _build_contract(root, outcome_mode=BatchOutcomeMode.TWENTY_SELECTED_SECURITY_OUTCOMES.value)
        validate_batch_contract(c_mode2)

        # Invalid mode rejected
        with pytest.raises(ValueError, match="Invalid outcome_mode"):
            c_invalid = _build_contract(root, outcome_mode="INVALID_MODE")
            validate_batch_contract(c_invalid)


def test_mode_2_contract_hash_uniqueness():
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        c_default = _build_contract(root)
        c_mode2 = _build_contract(root, outcome_mode=BatchOutcomeMode.TWENTY_SELECTED_SECURITY_OUTCOMES.value)

        assert c_default.compute_contract_hash() != c_mode2.compute_contract_hash()


def test_mode_2_reports_separate_outcome_counts():
    symbols = [f"SYM{i:02d}" for i in range(20)]
    cp = create_initial_batch_checkpoint("mode2_test_batch", symbols)

    # 19 data-bearing symbols
    for s in symbols[:-1]:
        sc = cp.symbol_states[s]
        sc.status = BatchSymbolStatus.SUCCEEDED
        sc.outcome = BatchSymbolOutcome.DATA_AVAILABLE.value
        sc.source_rows = 60
        sc.normalized_rows = 60
        cp.completed_symbols += 1
        cp.source_rows += 60
        cp.normalized_rows += 60
        cp.data_bearing_count += 1

    # 1 verified pre-listing symbol (e.g. PREMIERENE)
    last_sym = symbols[-1]
    sc_last = cp.symbol_states[last_sym]
    sc_last.status = BatchSymbolStatus.EMPTY
    sc_last.outcome = BatchSymbolOutcome.NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED.value
    sc_last.source_rows = 0
    sc_last.normalized_rows = 0
    cp.completed_symbols += 1  # Completed with valid classified outcome in Mode 2
    cp.verified_prelisting_count += 1

    assert cp.total_symbols == 20
    assert cp.completed_symbols == 20
    assert cp.data_bearing_count == 19
    assert cp.verified_prelisting_count == 1
    assert cp.source_failure_count == 0
    assert cp.unresolved_count == 0

    # Verify audit payload includes separate outcome counts
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        contract = _build_contract(root, outcome_mode=BatchOutcomeMode.TWENTY_SELECTED_SECURITY_OUTCOMES.value)
        audit_payload = generate_batch_audit_payload(cp, contract, duration_seconds=42.0)

        assert audit_payload["data_bearing_count"] == 19
        assert audit_payload["verified_prelisting_count"] == 1
        assert audit_payload["source_failure_count"] == 0
        assert audit_payload["unresolved_count"] == 0
        assert audit_payload["outcome_mode"] == BatchOutcomeMode.TWENTY_SELECTED_SECURITY_OUTCOMES.value


def test_mode_2_rejects_unverified_empty_outcomes():
    # If a security has 0 rows and outcome is EMPTY_RESPONSE_UNEXPLAINED, it cannot pass
    symbols = [f"SYM{i:02d}" for i in range(20)]
    cp = create_initial_batch_checkpoint("mode2_unverified_test", symbols)

    # First symbol unexplained empty
    sym0 = symbols[0]
    sc0 = cp.symbol_states[sym0]
    sc0.status = BatchSymbolStatus.FAILED
    sc0.outcome = BatchSymbolOutcome.EMPTY_RESPONSE_UNEXPLAINED.value
    cp.failed_symbols += 1
    cp.unresolved_count += 1
    cp.final_status = BatchStatus.HALTED
    cp.stop_reason = "Unexplained empty response"

    assert cp.unresolved_count == 1
    assert cp.final_status == BatchStatus.HALTED
