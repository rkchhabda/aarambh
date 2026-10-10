"""Unit tests for immutable request manifest construction and checksum verification."""

import json
from pathlib import Path
import pytest
from phase7.sources.contracts import AdjustmentState, FieldStatus, HistoricalEODRecord, RequestStatus
from phase7.sources.manifest import build_manifest, compute_sha256_bytes, compute_sha256_records, write_manifest


def test_manifest_construction_and_checksums():
    """Verify manifest creation with raw and normalized checksum generation."""
    rec = HistoricalEODRecord(
        trading_date="2024-01-15",
        symbol="RELIANCE",
        isin=None,
        exchange_series="EQ",
        previous_close=2500.0,
        open=2510.0,
        high=2530.0,
        low=2505.0,
        close=2520.0,
        last_price=2522.0,
        vwap=2518.0,
        total_traded_quantity=100000,
        total_traded_value_inr=None,
        number_of_trades=None,
        deliverable_quantity=None,
        delivery_percentage=None,
        trading_status="ACTIVE",
        adjustment_state=AdjustmentState.UNADJUSTED,
        traded_value_status=FieldStatus.NOT_PROVIDED,
        source_timestamp="2024-01-15",
        ingestion_timestamp="2026-10-10T10:00:00Z",
        source_identifier="TEST",
        row_hash="hash123",
    )

    raw_payload = [{"date": "2024-01-15", "open": 2510.0, "close": 2520.0}]

    manifest = build_manifest(
        request_id="req-1",
        symbol="RELIANCE",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        retrieval_timestamp="2026-10-10T10:00:00Z",
        raw_payload=raw_payload,
        normalized_records=[rec],
        status=RequestStatus.SUCCESS,
    )

    assert manifest.symbol == "RELIANCE"
    assert manifest.row_count == 1
    assert len(manifest.raw_checksum) == 64
    assert len(manifest.normalized_checksum) == 64
    assert manifest.status == RequestStatus.SUCCESS


def test_manifest_checksum_sensitivity():
    """Verify that any modification to normalized records alters the manifest checksum."""
    rec1 = HistoricalEODRecord(
        trading_date="2024-01-15",
        symbol="RELIANCE",
        isin=None,
        exchange_series="EQ",
        previous_close=2500.0,
        open=2510.0,
        high=2530.0,
        low=2505.0,
        close=2520.0,
        last_price=2522.0,
        vwap=2518.0,
        total_traded_quantity=100000,
        total_traded_value_inr=None,
        number_of_trades=None,
        deliverable_quantity=None,
        delivery_percentage=None,
        trading_status="ACTIVE",
        adjustment_state=AdjustmentState.UNADJUSTED,
        traded_value_status=FieldStatus.NOT_PROVIDED,
        source_timestamp="2024-01-15",
        ingestion_timestamp="2026-10-10T10:00:00Z",
        source_identifier="TEST",
        row_hash="hash_a",
    )
    rec2 = HistoricalEODRecord(
        trading_date="2024-01-15",
        symbol="RELIANCE",
        isin=None,
        exchange_series="EQ",
        previous_close=2500.0,
        open=2510.0,
        high=2530.0,
        low=2505.0,
        close=2520.0,
        last_price=2522.0,
        vwap=2518.0,
        total_traded_quantity=100000,
        total_traded_value_inr=None,
        number_of_trades=None,
        deliverable_quantity=None,
        delivery_percentage=None,
        trading_status="ACTIVE",
        adjustment_state=AdjustmentState.UNADJUSTED,
        traded_value_status=FieldStatus.NOT_PROVIDED,
        source_timestamp="2024-01-15",
        ingestion_timestamp="2026-10-10T10:00:00Z",
        source_identifier="TEST",
        row_hash="hash_b",  # Different row hash
    )

    c1 = compute_sha256_records([rec1])
    c2 = compute_sha256_records([rec2])
    assert c1 != c2


def test_write_manifest_to_disk(tmp_path):
    """Verify JSON file persistence of manifest records."""
    manifest = build_manifest(
        request_id="req-disk",
        symbol="TCS",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        retrieval_timestamp="2026-10-10T10:00:00Z",
        raw_payload={"test": 1},
        normalized_records=[],
        status=RequestStatus.EMPTY,
    )
    out_file = write_manifest(manifest, tmp_path)
    assert out_file.exists()

    with out_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["symbol"] == "TCS"
    assert data["status"] == "EMPTY"
