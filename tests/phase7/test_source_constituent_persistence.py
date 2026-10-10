"""Unit tests for Phase 7 constituent snapshot external persistence layer.

Tests:
- Raw JSON snapshot persistence and SHA-256 calculation
- Normalized JSONL snapshot persistence and SHA-256 calculation
- Overwrite protection raises FileExistsError
- Manifest serialization and persistence
- Clean isolation in external directory outside Git
"""

import json
from pathlib import Path
import pytest

from phase7.sources.constituent_persistence import (
    compute_file_sha256,
    compute_sha256,
    save_normalized_snapshot,
    save_raw_snapshot,
    save_rejected_rows,
    save_snapshot_manifest,
)
from phase7.sources.contracts import (
    ConstituentClassification,
    ConstituentRecord,
    ConstituentSnapshotManifest,
    RejectedRowRecord,
    RequestStatus,
)


@pytest.fixture
def mock_staging_root(tmp_path):
    root = tmp_path / "mock_staging_pers"
    root.mkdir()
    return root


def test_save_raw_snapshot_and_sha256(mock_staging_root):
    """Raw snapshot is serialized with SHA-256 and verified on disk."""
    payload = {"data": [{"symbol": "RELIANCE", "companyName": "Reliance Industries"}]}
    raw_path, raw_hash = save_raw_snapshot(payload, mock_staging_root, timestamp_str="20261010T120000Z")

    assert raw_path.exists()
    assert raw_path.parent == mock_staging_root / "raw" / "constituents"
    disk_hash = compute_file_sha256(raw_path)
    assert disk_hash == raw_hash
    assert raw_hash[:8] in raw_path.name


def test_raw_snapshot_overwrite_prohibited(mock_staging_root):
    """Saving to an identical raw path raises FileExistsError."""
    payload = {"data": [{"symbol": "TCS"}]}
    save_raw_snapshot(payload, mock_staging_root, timestamp_str="20261010T120000Z")

    with pytest.raises(FileExistsError, match="Target raw file already exists"):
        save_raw_snapshot(payload, mock_staging_root, timestamp_str="20261010T120000Z")


def test_save_normalized_snapshot_and_sha256(mock_staging_root):
    """Normalized constituent records are persisted as JSONL with verified SHA-256."""
    rec = ConstituentRecord(
        symbol="INFY",
        security_name="Infosys Limited",
        isin="INE009A01021",
        index_name="NIFTY 500",
        classification=ConstituentClassification.CURRENT_SNAPSHOT_ONLY,
        source_timestamp="2026-10-10T10:00:00Z",
        ingestion_timestamp="2026-10-10T10:00:00Z",
        source_identifier="NSEDataFetcher",
        row_hash="abc12345",
        index_code="NIFTY 500",
        exchange_series="EQ",
        sector=None,
        industry="Information Technology",
    )
    norm_path, norm_hash = save_normalized_snapshot([rec], mock_staging_root, timestamp_str="20261010T120000Z")

    assert norm_path.exists()
    assert norm_path.parent == mock_staging_root / "normalized" / "constituents"
    disk_hash = compute_file_sha256(norm_path)
    assert disk_hash == norm_hash

    # Verify JSONL lines content
    lines = norm_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["symbol"] == "INFY"
    assert data["classification"] == "CURRENT_SNAPSHOT_ONLY"


def test_normalized_snapshot_overwrite_prohibited(mock_staging_root):
    """Saving to an identical normalized path raises FileExistsError."""
    rec = ConstituentRecord(
        symbol="INFY",
        security_name="Infosys",
        isin=None,
        index_name="NIFTY 500",
        classification=ConstituentClassification.CURRENT_SNAPSHOT_ONLY,
        source_timestamp="2026-10-10T10:00:00Z",
        ingestion_timestamp="2026-10-10T10:00:00Z",
        source_identifier="NSEDataFetcher",
        row_hash="hash1",
    )
    save_normalized_snapshot([rec], mock_staging_root, timestamp_str="20261010T120000Z")

    with pytest.raises(FileExistsError, match="Target normalized file already exists"):
        save_normalized_snapshot([rec], mock_staging_root, timestamp_str="20261010T120000Z")


def test_save_snapshot_manifest(mock_staging_root):
    """Manifest is persisted cleanly in manifests directory."""
    manifest = ConstituentSnapshotManifest(
        request_id="req-123",
        index_name="NIFTY 500",
        retrieval_timestamp="2026-10-10T10:00:00Z",
        client_version="nse-4.0.1",
        source_identifier="NSEDataFetcher",
        status=RequestStatus.SUCCEEDED,
        source_row_count=501,
        normalized_row_count=500,
        rejected_row_count=1,
        unique_symbols=500,
        duplicate_symbols=0,
        missing_symbols=0,
        unique_isins=498,
        duplicate_isins=0,
        missing_isins=2,
        missing_series=0,
        missing_sectors=500,
        missing_industries=0,
        classification="CURRENT_SNAPSHOT_ONLY",
        raw_checksum="rawhash123",
        normalized_checksum="normhash123",
        panel_version_id="CURRENT_NIFTY500_20261010_NORMTEMP",
    )
    manifest_path = save_snapshot_manifest(manifest, mock_staging_root)

    assert manifest_path.exists()
    assert manifest_path.name == "manifest_NIFTY_500_req-123.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["status"] == "SUCCEEDED"
    assert data["panel_version_id"] == "CURRENT_NIFTY500_20261010_NORMTEMP"
    assert data["unique_symbols"] == 500
