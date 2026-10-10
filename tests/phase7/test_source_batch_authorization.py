"""Tests for Phase 7 single-use batch authorization markers."""

from pathlib import Path
import tempfile
import time
import pytest

from phase7.sources.batch_authorization import (
    MARKER_FILENAME,
    consume_batch_authorization_marker,
    create_batch_authorization_marker,
    validate_batch_authorization,
)
from phase7.sources.batch_contract import (
    REQUIRED_AUTHORIZATION_SCOPE,
    REQUIRED_END_DATE,
    REQUIRED_INTERVAL,
    REQUIRED_PANEL_VERSION,
    REQUIRED_SNAPSHOT_CHECKSUM,
    REQUIRED_START_DATE,
    REQUIRED_SYMBOL_COUNT,
    BatchContract,
    BatchStatus,
)


def _build_test_contract(staging_root: Path, **overrides) -> BatchContract:
    import hashlib
    staging_hash = hashlib.sha256(str(staging_root.resolve()).encode("utf-8")).hexdigest()
    defaults = {
        "batch_id": "test_batch_auth_01",
        "source_panel_version": REQUIRED_PANEL_VERSION,
        "source_snapshot_checksum": REQUIRED_SNAPSHOT_CHECKSUM,
        "selection_checksum": "a" * 64,
        "symbol_count": REQUIRED_SYMBOL_COUNT,
        "ordered_symbols_hash": "b" * 64,
        "start_date": REQUIRED_START_DATE,
        "end_date": REQUIRED_END_DATE,
        "interval": REQUIRED_INTERVAL,
        "staging_root_hash": staging_hash,
        "schema_mapping_version": "NSE_4_0_1_HISTORICAL_CAMELCASE_V1",
        "maximum_concurrency": 1,
        "minimum_request_spacing_seconds": 2.0,
        "maximum_retries": 0,
        "failure_threshold": 1,
        "authorization_scope": REQUIRED_AUTHORIZATION_SCOPE,
        "classification": "DETERMINISTIC_CURRENT_PANEL_OPERATIONAL_SAMPLE",
        "batch_status": BatchStatus.INITIALIZED.value,
        "created_timestamp": "2026-10-10T11:00:00Z",
    }
    defaults.update(overrides)
    return BatchContract(**defaults)


def test_batch_authorization_lifecycle():
    with tempfile.TemporaryDirectory() as tmp_dir:
        staging_root = Path(tmp_dir)
        contract = _build_test_contract(staging_root)

        # 1. Create marker
        record, marker_path = create_batch_authorization_marker(
            staging_root=staging_root,
            selection_checksum=contract.selection_checksum,
            ordered_symbols_hash=contract.ordered_symbols_hash,
            expires_minutes=15,
        )
        assert marker_path.exists()
        assert record.single_use is True

        # 2. Validate marker
        validated = validate_batch_authorization(marker_path, contract, staging_root)
        assert validated.authorization_hash == record.authorization_hash

        # 3. Consume marker
        consumed_path = consume_batch_authorization_marker(marker_path, contract, staging_root)
        assert not marker_path.exists()
        assert consumed_path.exists()
        assert "batch_authorization.consumed." in consumed_path.name

        # 4. Attempting to consume again fails
        with pytest.raises(FileNotFoundError):
            consume_batch_authorization_marker(marker_path, contract, staging_root)


def test_reject_mismatched_selection_and_symbol_count():
    with tempfile.TemporaryDirectory() as tmp_dir:
        staging_root = Path(tmp_dir)
        contract = _build_test_contract(staging_root)

        record, marker_path = create_batch_authorization_marker(
            staging_root=staging_root,
            selection_checksum=contract.selection_checksum,
            ordered_symbols_hash=contract.ordered_symbols_hash,
        )

        # Mismatched selection checksum
        mismatched_contract = _build_test_contract(staging_root, selection_checksum="0" * 64)
        with pytest.raises(ValueError, match="Selection checksum mismatch"):
            validate_batch_authorization(marker_path, mismatched_contract, staging_root)

        # Mismatched ordered symbols hash (e.g. reordered symbols)
        reordered_contract = _build_test_contract(staging_root, ordered_symbols_hash="f" * 64)
        with pytest.raises(ValueError, match="Ordered symbols hash mismatch"):
            validate_batch_authorization(marker_path, reordered_contract, staging_root)


def test_reject_mismatched_dates_and_panel_version():
    with tempfile.TemporaryDirectory() as tmp_dir:
        staging_root = Path(tmp_dir)
        contract = _build_test_contract(staging_root)

        record, marker_path = create_batch_authorization_marker(
            staging_root=staging_root,
            selection_checksum=contract.selection_checksum,
            ordered_symbols_hash=contract.ordered_symbols_hash,
        )

        # Mismatched date range
        bad_dates = _build_test_contract(staging_root, start_date="2024-02-01")
        with pytest.raises(ValueError, match="Start date mismatch"):
            validate_batch_authorization(marker_path, bad_dates, staging_root)

        # Mismatched panel version
        bad_panel = _build_test_contract(staging_root, source_panel_version="DIFF_PANEL")
        with pytest.raises(ValueError, match="Panel version mismatch"):
            validate_batch_authorization(marker_path, bad_panel, staging_root)


def test_reject_tampered_authorization_hash():
    with tempfile.TemporaryDirectory() as tmp_dir:
        staging_root = Path(tmp_dir)
        contract = _build_test_contract(staging_root)

        record, marker_path = create_batch_authorization_marker(
            staging_root=staging_root,
            selection_checksum=contract.selection_checksum,
            ordered_symbols_hash=contract.ordered_symbols_hash,
        )

        # Tamper payload
        import json
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
        payload["symbol_count"] = 50  # Unauthorized expansion
        marker_path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(ValueError, match="Symbol count mismatch|Cryptographic authorization hash tampering"):
            validate_batch_authorization(marker_path, contract, staging_root)
