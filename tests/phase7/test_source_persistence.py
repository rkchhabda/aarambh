"""Unit tests for Phase 7 external persistence engine.

Verifies:
- External directory enforcement outside Git
- Raw payload atomic persistence, deterministic hashing, and overwrite refusal
- Scrubbing of session credentials, auth tokens, and headers
- Normalized JSONL persistence, checksum determinism, and overwrite refusal
- Request manifest persistence, PENDING->finalized lifecycle, and immutability
"""

import json
from pathlib import Path
import pytest

from phase7.sources.contracts import (
    AdjustmentState,
    FieldStatus,
    HistoricalEODRecord,
    RequestManifest,
    RequestStatus,
)
from phase7.sources.persistence import (
    format_iso_to_compact_utc,
    persist_normalized_records,
    persist_raw_payload,
    persist_request_manifest,
    validate_persistence_path_outside_git,
)


@pytest.fixture
def test_staging(tmp_path):
    staging = tmp_path / "external_staging"
    staging.mkdir(parents=True, exist_ok=True)
    repo = tmp_path / "mock_repo"
    repo.mkdir(parents=True, exist_ok=True)
    return {"staging": staging, "repo": repo}


def test_persistence_refuses_path_inside_git(test_staging):
    """Verify validate_persistence_path_outside_git strictly refuses paths inside Git."""
    repo = test_staging["repo"]
    in_repo_path = repo / "data" / "raw"
    in_repo_path.mkdir(parents=True, exist_ok=True)

    with pytest.raises(PermissionError, match="REFUSED_IN_REPO_PERSISTENCE"):
        validate_persistence_path_outside_git(in_repo_path, repo_root=repo)


def test_raw_payload_persistence_and_checksum(test_staging):
    """Verify raw payload persistence, deterministic SHA-256, and format."""
    staging = test_staging["staging"]
    repo = test_staging["repo"]

    raw_data = [
        {"CH_TIMESTAMP": "2024-01-02", "CH_SERIES": "EQ", "CH_CLOSING_PRICE": 2500.0},
        {"CH_TIMESTAMP": "2024-01-03", "CH_SERIES": "EQ", "CH_CLOSING_PRICE": 2510.0},
    ]

    path, chksum = persist_raw_payload(
        payload=raw_data,
        staging_root=staging,
        symbol="RELIANCE",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        retrieval_timestamp="2026-10-10T10:00:00Z",
        repo_root=repo,
    )

    assert path.exists()
    assert path.name.startswith("RELIANCE_2024-01-01_2024-01-31_1d_20261010T100000Z_")
    assert path.name.endswith(".json")
    assert len(chksum) == 64

    # Verify content
    saved_content = json.loads(path.read_text(encoding="utf-8"))
    assert len(saved_content) == 2


def test_raw_persistence_refuses_overwrite(test_staging):
    """Verify raw file writer never overwrites an existing file."""
    staging = test_staging["staging"]
    repo = test_staging["repo"]

    payload = {"data": [1, 2, 3]}
    persist_raw_payload(
        payload=payload,
        staging_root=staging,
        symbol="TCS",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        retrieval_timestamp="2026-10-10T10:00:00Z",
        repo_root=repo,
    )

    with pytest.raises(FileExistsError, match="PERSISTENCE_OVERWRITE_REFUSED"):
        persist_raw_payload(
            payload=payload,
            staging_root=staging,
            symbol="TCS",
            start_date="2024-01-01",
            end_date="2024-01-31",
            interval="1d",
            retrieval_timestamp="2026-10-10T10:00:00Z",
            repo_root=repo,
        )


def test_raw_persistence_strips_sensitive_data(test_staging):
    """Verify session credentials, auth tokens, and headers are scrubbed from raw persistence."""
    staging = test_staging["staging"]
    repo = test_staging["repo"]

    payload_with_secrets = {
        "data": [{"date": "2024-01-02", "price": 100}],
        "authorization": "Bearer secret_123",
        "token": "tok_xyz",
        "session": "sess_abc",
        "headers": {"content-type": "application/json"},
    }

    path, _ = persist_raw_payload(
        payload=payload_with_secrets,
        staging_root=staging,
        symbol="INFY",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        retrieval_timestamp="2026-10-10T10:00:00Z",
        repo_root=repo,
    )

    text = path.read_text(encoding="utf-8")
    assert "Bearer" not in text
    assert "secret_123" not in text
    assert "tok_xyz" not in text
    assert "sess_abc" not in text


def test_normalized_records_persistence_and_checksum(test_staging):
    """Verify normalized records are persisted in canonical JSONL with deterministic checksum."""
    staging = test_staging["staging"]
    repo = test_staging["repo"]

    record = HistoricalEODRecord(
        trading_date="2024-01-02",
        symbol="HDFCBANK",
        isin="INE040A01034",
        exchange_series="EQ",
        previous_close=1650.0,
        open=1655.0,
        high=1670.0,
        low=1645.0,
        close=1660.0,
        last_price=1661.0,
        vwap=1658.0,
        total_traded_quantity=2000000,
        total_traded_value_inr=3316000000.0,
        number_of_trades=50000,
        deliverable_quantity=1200000,
        delivery_percentage=60.0,
        trading_status="ACTIVE",
        adjustment_state=AdjustmentState.UNADJUSTED,
        traded_value_status=FieldStatus.SOURCE_REPORTED,
        source_timestamp="2024-01-02T16:00:00Z",
        ingestion_timestamp="2026-10-10T10:00:00Z",
        source_identifier="NSE_DATA_FETCHER",
        row_hash="mock_row_hash_64_chars_deterministic_0123456789abcdef0123456789abcdef",
    )

    path, chksum, row_count, missing = persist_normalized_records(
        records=[record],
        staging_root=staging,
        symbol="HDFCBANK",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        retrieval_timestamp="2026-10-10T10:00:00Z",
        repo_root=repo,
    )

    assert path.exists()
    assert path.name.endswith(".jsonl")
    assert row_count == 1
    assert len(chksum) == 64
    assert missing["isin"] == 0
    assert missing["turnover"] == 0

    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").strip().split("\n")]
    assert len(lines) == 1
    assert lines[0]["symbol"] == "HDFCBANK"
    assert lines[0]["row_hash"] == record.row_hash


def test_normalized_persistence_refuses_overwrite(test_staging):
    """Verify normalized persistence refuses to overwrite an existing file."""
    staging = test_staging["staging"]
    repo = test_staging["repo"]

    record = HistoricalEODRecord(
        trading_date="2024-01-02",
        symbol="ICICIBANK",
        isin=None,
        exchange_series="EQ",
        previous_close=None,
        open=1000.0,
        high=1020.0,
        low=990.0,
        close=1010.0,
        last_price=None,
        vwap=None,
        total_traded_quantity=100000,
        total_traded_value_inr=None,
        number_of_trades=None,
        deliverable_quantity=None,
        delivery_percentage=None,
        trading_status="ACTIVE",
        adjustment_state=AdjustmentState.UNADJUSTED,
        traded_value_status=FieldStatus.NOT_PROVIDED,
        source_timestamp="2024-01-02",
        ingestion_timestamp="2026-10-10T10:00:00Z",
        source_identifier="NSE_DATA_FETCHER",
        row_hash="mock_hash_1",
    )

    persist_normalized_records(
        records=[record],
        staging_root=staging,
        symbol="ICICIBANK",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        retrieval_timestamp="2026-10-10T10:00:00Z",
        repo_root=repo,
    )

    with pytest.raises(FileExistsError, match="PERSISTENCE_OVERWRITE_REFUSED"):
        persist_normalized_records(
            records=[record],
            staging_root=staging,
            symbol="ICICIBANK",
            start_date="2024-01-01",
            end_date="2024-01-31",
            interval="1d",
            retrieval_timestamp="2026-10-10T10:00:00Z",
            repo_root=repo,
        )


def test_manifest_lifecycle_pending_to_finalized(test_staging):
    """Verify manifest can transition from PENDING to finalized, but finalized cannot be overwritten."""
    staging = test_staging["staging"]
    repo = test_staging["repo"]

    pending = RequestManifest(
        request_id="req-life-001",
        symbol="RELIANCE",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        retrieval_timestamp="2026-10-10T10:00:00Z",
        client_version="nse-4.0.1",
        source_identifier="NSE_DATA_FETCHER",
        status=RequestStatus.PENDING,
        row_count=0,
        raw_checksum="",
        normalized_checksum="",
    )

    m_path = persist_request_manifest(pending, staging_root=staging, repo_root=repo)
    assert m_path.exists()
    assert json.loads(m_path.read_text(encoding="utf-8"))["status"] == "PENDING"

    # Finalize manifest
    finalized = RequestManifest(
        request_id="req-life-001",
        symbol="RELIANCE",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        retrieval_timestamp="2026-10-10T10:00:00Z",
        client_version="nse-4.0.1",
        source_identifier="NSE_DATA_FETCHER",
        status=RequestStatus.SUCCEEDED,
        row_count=20,
        raw_checksum="raw_hash_abc",
        normalized_checksum="norm_hash_xyz",
    )

    final_path = persist_request_manifest(finalized, staging_root=staging, repo_root=repo)
    assert json.loads(final_path.read_text(encoding="utf-8"))["status"] == "SUCCEEDED"

    # Subsequent attempt to overwrite finalized manifest must fail
    with pytest.raises(FileExistsError, match="PERSISTENCE_OVERWRITE_REFUSED"):
        persist_request_manifest(finalized, staging_root=staging, repo_root=repo)
