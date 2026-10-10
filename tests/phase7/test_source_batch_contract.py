"""Tests for Phase 7 governed batch contract."""

import pytest
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
    BatchExitCode,
    BatchStatus,
    validate_batch_contract,
)


def _build_valid_contract(**overrides) -> BatchContract:
    defaults = {
        "batch_id": "test_batch_001",
        "source_panel_version": REQUIRED_PANEL_VERSION,
        "source_snapshot_checksum": REQUIRED_SNAPSHOT_CHECKSUM,
        "selection_checksum": "a" * 64,
        "symbol_count": REQUIRED_SYMBOL_COUNT,
        "ordered_symbols_hash": "b" * 64,
        "start_date": REQUIRED_START_DATE,
        "end_date": REQUIRED_END_DATE,
        "interval": REQUIRED_INTERVAL,
        "staging_root_hash": "c" * 64,
        "schema_mapping_version": REQUIRED_SCHEMA_MAPPING_VERSION,
        "maximum_concurrency": 1,
        "minimum_request_spacing_seconds": 2.0,
        "maximum_retries": 0,
        "failure_threshold": 1,
        "authorization_scope": REQUIRED_AUTHORIZATION_SCOPE,
        "classification": REQUIRED_CLASSIFICATION,
        "batch_status": BatchStatus.INITIALIZED.value,
        "created_timestamp": "2026-10-10T11:00:00Z",
    }
    defaults.update(overrides)
    return BatchContract(**defaults)


def test_valid_batch_contract():
    contract = _build_valid_contract()
    validate_batch_contract(contract)
    h = contract.compute_contract_hash()
    assert len(h) == 64


def test_reject_symbol_count_mismatch():
    # 21 symbols rejected
    with pytest.raises(ValueError, match="Invalid symbol_count"):
        validate_batch_contract(_build_valid_contract(symbol_count=21))

    # 19 symbols rejected
    with pytest.raises(ValueError, match="Invalid symbol_count"):
        validate_batch_contract(_build_valid_contract(symbol_count=19))


def test_reject_date_mismatch():
    with pytest.raises(ValueError, match="Invalid start_date"):
        validate_batch_contract(_build_valid_contract(start_date="2023-12-01"))

    with pytest.raises(ValueError, match="Invalid end_date"):
        validate_batch_contract(_build_valid_contract(end_date="2024-04-30"))


def test_reject_interval_mismatch():
    with pytest.raises(ValueError, match="Invalid interval"):
        validate_batch_contract(_build_valid_contract(interval="1h"))


def test_reject_concurrency_and_spacing():
    with pytest.raises(ValueError, match="Invalid maximum_concurrency"):
        validate_batch_contract(_build_valid_contract(maximum_concurrency=2))

    with pytest.raises(ValueError, match="Invalid minimum_request_spacing_seconds"):
        validate_batch_contract(_build_valid_contract(minimum_request_spacing_seconds=1.0))


def test_reject_retries_and_failure_threshold():
    with pytest.raises(ValueError, match="Invalid maximum_retries"):
        validate_batch_contract(_build_valid_contract(maximum_retries=1))

    with pytest.raises(ValueError, match="Invalid failure_threshold"):
        validate_batch_contract(_build_valid_contract(failure_threshold=2))


def test_reject_panel_version_and_checksum_mismatch():
    with pytest.raises(ValueError, match="Invalid source_panel_version"):
        validate_batch_contract(_build_valid_contract(source_panel_version="OTHER_PANEL"))

    with pytest.raises(ValueError, match="Invalid source_snapshot_checksum"):
        validate_batch_contract(_build_valid_contract(source_snapshot_checksum="bad_checksum"))


def test_reject_scope_and_classification_mismatch():
    with pytest.raises(ValueError, match="Invalid authorization_scope"):
        validate_batch_contract(_build_valid_contract(authorization_scope="WRONG_SCOPE"))

    with pytest.raises(ValueError, match="Invalid classification"):
        validate_batch_contract(_build_valid_contract(classification="WRONG_CLASS"))
