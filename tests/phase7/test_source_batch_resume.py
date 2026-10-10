"""Tests for Phase 7 batch checkpoint resume validation rules."""

import hashlib
import json
from pathlib import Path
import tempfile
import pytest

from phase7.sources.batch_checkpoint import (
    BatchCheckpoint,
    BatchSymbolStatus,
    InvalidResumeCheckpointError,
    create_initial_batch_checkpoint,
    save_checkpoint,
    validate_resume_checkpoint,
)
from phase7.sources.batch_contract import (
    REQUIRED_PANEL_VERSION,
    REQUIRED_SNAPSHOT_CHECKSUM,
    BatchContract,
    BatchStatus,
)


def _setup_completed_symbol(staging_root: Path, symbol: str, contract: BatchContract) -> dict:
    """Create actual valid files on disk for a completed symbol."""
    raw_dir = staging_root / "raw" / "historical"
    norm_dir = staging_root / "normalized" / "historical"
    man_dir = staging_root / "manifests"
    raw_dir.mkdir(parents=True, exist_ok=True)
    norm_dir.mkdir(parents=True, exist_ok=True)
    man_dir.mkdir(parents=True, exist_ok=True)

    raw_file = raw_dir / f"{symbol}_raw.json"
    raw_content = json.dumps([{"chSymbol": symbol, "mtimestamp": "01-Jan-2024"}]).encode("utf-8")
    raw_file.write_bytes(raw_content)
    raw_hash = hashlib.sha256(raw_content).hexdigest()

    norm_file = norm_dir / f"{symbol}_norm.jsonl"
    norm_content = json.dumps({"symbol": symbol, "trading_date": "2024-01-01"}).encode("utf-8")
    norm_file.write_bytes(norm_content)
    norm_hash = hashlib.sha256(norm_content).hexdigest()

    manifest_file = man_dir / f"manifest_{symbol}.json"
    manifest_data = {
        "symbol": symbol,
        "status": "SUCCEEDED",
        "source_row_count": 1,
        "normalized_row_count": 1,
        "rejected_row_count": 0,
        "raw_checksum": raw_hash,
        "normalized_checksum": norm_hash,
        "raw_file_path": str(raw_file),
        "normalized_file_path": str(norm_file),
        "start_date": contract.start_date,
        "end_date": contract.end_date,
        "interval": contract.interval,
        "schema_mapping_version": contract.schema_mapping_version,
    }
    manifest_bytes = json.dumps(manifest_data, indent=2).encode("utf-8")
    manifest_file.write_bytes(manifest_bytes)
    man_hash = hashlib.sha256(manifest_bytes).hexdigest()

    return {
        "raw_file": raw_file,
        "raw_hash": raw_hash,
        "norm_file": norm_file,
        "norm_hash": norm_hash,
        "manifest_file": manifest_file,
        "man_hash": man_hash,
    }


def _build_contract(staging_root: Path) -> BatchContract:
    return BatchContract(
        batch_id="resume_test_batch",
        source_panel_version=REQUIRED_PANEL_VERSION,
        source_snapshot_checksum=REQUIRED_SNAPSHOT_CHECKSUM,
        selection_checksum="a" * 64,
        symbol_count=2,
        ordered_symbols_hash="b" * 64,
        start_date="2024-01-01",
        end_date="2024-03-31",
        interval="1d",
        staging_root_hash="c" * 64,
        schema_mapping_version="NSE_4_0_1_HISTORICAL_CAMELCASE_V1",
        maximum_concurrency=1,
        minimum_request_spacing_seconds=2.0,
        maximum_retries=0,
        failure_threshold=1,
        authorization_scope="TWENTY_STOCK_THREE_MONTH_NSE_BATCH_PILOT",
        classification="DETERMINISTIC_CURRENT_PANEL_OPERATIONAL_SAMPLE",
        batch_status=BatchStatus.IN_PROGRESS.value,
        created_timestamp="2026-10-10T11:00:00Z",
    )


def test_resume_validation_succeeds_for_valid_checkpoint():
    with tempfile.TemporaryDirectory() as tmp_dir:
        staging_root = Path(tmp_dir)
        symbols = ["SYM01", "SYM02"]
        contract = _build_contract(staging_root)

        # Setup files for SYM01
        sym1_info = _setup_completed_symbol(staging_root, "SYM01", contract)

        cp = create_initial_batch_checkpoint("resume_test_batch", symbols)
        sc1 = cp.symbol_states["SYM01"]
        sc1.status = BatchSymbolStatus.SUCCEEDED
        sc1.raw_file_path = str(sym1_info["raw_file"])
        sc1.normalized_file_path = str(sym1_info["norm_file"])
        sc1.manifest_file_path = str(sym1_info["manifest_file"])
        sc1.raw_checksum = sym1_info["raw_hash"]
        sc1.normalized_checksum = sym1_info["norm_hash"]
        sc1.manifest_checksum = sym1_info["man_hash"]
        sc1.source_rows = 1
        sc1.normalized_rows = 1

        trusted = validate_resume_checkpoint(cp, contract, symbols)
        assert trusted == {"SYM01"}


def test_resume_fails_on_corrupt_raw_checksum():
    with tempfile.TemporaryDirectory() as tmp_dir:
        staging_root = Path(tmp_dir)
        symbols = ["SYM01", "SYM02"]
        contract = _build_contract(staging_root)
        sym1_info = _setup_completed_symbol(staging_root, "SYM01", contract)

        cp = create_initial_batch_checkpoint("resume_test_batch", symbols)
        sc1 = cp.symbol_states["SYM01"]
        sc1.status = BatchSymbolStatus.SUCCEEDED
        sc1.raw_file_path = str(sym1_info["raw_file"])
        sc1.normalized_file_path = str(sym1_info["norm_file"])
        sc1.manifest_file_path = str(sym1_info["manifest_file"])
        sc1.raw_checksum = "corrupted_raw_hash"
        sc1.normalized_checksum = sym1_info["norm_hash"]
        sc1.manifest_checksum = sym1_info["man_hash"]

        with pytest.raises(InvalidResumeCheckpointError, match="Raw checksum mismatch"):
            validate_resume_checkpoint(cp, contract, symbols)


def test_resume_fails_on_missing_manifest_file():
    with tempfile.TemporaryDirectory() as tmp_dir:
        staging_root = Path(tmp_dir)
        symbols = ["SYM01", "SYM02"]
        contract = _build_contract(staging_root)
        sym1_info = _setup_completed_symbol(staging_root, "SYM01", contract)

        # Delete manifest file
        sym1_info["manifest_file"].unlink()

        cp = create_initial_batch_checkpoint("resume_test_batch", symbols)
        sc1 = cp.symbol_states["SYM01"]
        sc1.status = BatchSymbolStatus.SUCCEEDED
        sc1.raw_file_path = str(sym1_info["raw_file"])
        sc1.normalized_file_path = str(sym1_info["norm_file"])
        sc1.manifest_file_path = str(sym1_info["manifest_file"])
        sc1.raw_checksum = sym1_info["raw_hash"]
        sc1.normalized_checksum = sym1_info["norm_hash"]

        with pytest.raises(InvalidResumeCheckpointError, match="missing manifest file"):
            validate_resume_checkpoint(cp, contract, symbols)


def test_resume_fails_on_mismatched_date_range():
    with tempfile.TemporaryDirectory() as tmp_dir:
        staging_root = Path(tmp_dir)
        symbols = ["SYM01", "SYM02"]
        contract = _build_contract(staging_root)
        sym1_info = _setup_completed_symbol(staging_root, "SYM01", contract)

        # Alter manifest start date
        m_data = json.loads(sym1_info["manifest_file"].read_text(encoding="utf-8"))
        m_data["start_date"] = "2023-01-01"
        sym1_info["manifest_file"].write_text(json.dumps(m_data), encoding="utf-8")

        cp = create_initial_batch_checkpoint("resume_test_batch", symbols)
        sc1 = cp.symbol_states["SYM01"]
        sc1.status = BatchSymbolStatus.SUCCEEDED
        sc1.raw_file_path = str(sym1_info["raw_file"])
        sc1.normalized_file_path = str(sym1_info["norm_file"])
        sc1.manifest_file_path = str(sym1_info["manifest_file"])
        sc1.raw_checksum = sym1_info["raw_hash"]
        sc1.normalized_checksum = sym1_info["norm_hash"]

        with pytest.raises(InvalidResumeCheckpointError, match="Start date mismatch"):
            validate_resume_checkpoint(cp, contract, symbols)


def test_resume_fails_on_corrupt_normalized_checksum():
    with tempfile.TemporaryDirectory() as tmp_dir:
        staging_root = Path(tmp_dir)
        symbols = ["SYM01", "SYM02"]
        contract = _build_contract(staging_root)
        sym1_info = _setup_completed_symbol(staging_root, "SYM01", contract)

        cp = create_initial_batch_checkpoint("resume_test_batch", symbols)
        sc1 = cp.symbol_states["SYM01"]
        sc1.status = BatchSymbolStatus.SUCCEEDED
        sc1.raw_file_path = str(sym1_info["raw_file"])
        sc1.normalized_file_path = str(sym1_info["norm_file"])
        sc1.manifest_file_path = str(sym1_info["manifest_file"])
        sc1.raw_checksum = sym1_info["raw_hash"]
        sc1.normalized_checksum = "corrupted_norm_hash"

        with pytest.raises(InvalidResumeCheckpointError, match="Normalized checksum mismatch"):
            validate_resume_checkpoint(cp, contract, symbols)


def test_resume_fails_on_wrong_schema_version():
    with tempfile.TemporaryDirectory() as tmp_dir:
        staging_root = Path(tmp_dir)
        symbols = ["SYM01", "SYM02"]
        contract = _build_contract(staging_root)
        sym1_info = _setup_completed_symbol(staging_root, "SYM01", contract)

        m_data = json.loads(sym1_info["manifest_file"].read_text(encoding="utf-8"))
        m_data["schema_mapping_version"] = "OLD_SCHEMA_V0"
        sym1_info["manifest_file"].write_text(json.dumps(m_data), encoding="utf-8")

        cp = create_initial_batch_checkpoint("resume_test_batch", symbols)
        sc1 = cp.symbol_states["SYM01"]
        sc1.status = BatchSymbolStatus.SUCCEEDED
        sc1.raw_file_path = str(sym1_info["raw_file"])
        sc1.normalized_file_path = str(sym1_info["norm_file"])
        sc1.manifest_file_path = str(sym1_info["manifest_file"])
        sc1.raw_checksum = sym1_info["raw_hash"]
        sc1.normalized_checksum = sym1_info["norm_hash"]

        with pytest.raises(InvalidResumeCheckpointError, match="Schema mapping mismatch"):
            validate_resume_checkpoint(cp, contract, symbols)


def test_resume_fails_on_foreign_symbol():
    with tempfile.TemporaryDirectory() as tmp_dir:
        staging_root = Path(tmp_dir)
        symbols = ["SYM01", "SYM02"]
        contract = _build_contract(staging_root)

        cp = create_initial_batch_checkpoint("resume_test_batch", symbols)
        # Inject foreign symbol
        from phase7.sources.batch_checkpoint import SymbolCheckpoint
        cp.symbol_states["FOREIGN_SYM"] = SymbolCheckpoint(
            symbol="FOREIGN_SYM",
            status=BatchSymbolStatus.NOT_STARTED,
        )

        with pytest.raises(InvalidResumeCheckpointError, match="does not belong to governed batch selection"):
            validate_resume_checkpoint(cp, contract, symbols)

