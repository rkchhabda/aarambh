"""Unit tests for Phase 7 source data contracts and immutability invariants."""

import pytest
from phase7.sources.contracts import (
    AdjustmentState,
    ConstituentClassification,
    FieldStatus,
    HistoricalEODRecord,
    RequestManifest,
    RequestStatus,
)


def test_contracts_immutability():
    """Verify that canonical contracts are frozen dataclasses."""
    record = HistoricalEODRecord(
        trading_date="2024-01-15",
        symbol="RELIANCE",
        isin="INE002A01018",
        exchange_series="EQ",
        previous_close=2500.0,
        open=2510.0,
        high=2530.0,
        low=2505.0,
        close=2520.0,
        last_price=2522.0,
        vwap=2518.0,
        total_traded_quantity=100000,
        total_traded_value_inr=251800000.0,
        number_of_trades=15000,
        deliverable_quantity=45000,
        delivery_percentage=45.0,
        trading_status="ACTIVE",
        adjustment_state=AdjustmentState.UNADJUSTED,
        traded_value_status=FieldStatus.SOURCE_REPORTED,
        source_timestamp="2024-01-15T16:00:00Z",
        ingestion_timestamp="2026-10-10T10:00:00Z",
        source_identifier="NSE_TEST",
        row_hash="abc123hash",
    )

    with pytest.raises(AttributeError):
        record.close = 2550.0  # type: ignore

    with pytest.raises(AttributeError):
        record.symbol = "TCS"  # type: ignore


def test_status_enumerations():
    """Verify enum values and membership."""
    assert FieldStatus.SOURCE_REPORTED.value == "SOURCE_REPORTED"
    assert FieldStatus.NOT_PROVIDED.value == "NOT_PROVIDED"
    assert FieldStatus.DERIVED.value == "DERIVED"

    assert AdjustmentState.UNADJUSTED.value == "UNADJUSTED"
    assert ConstituentClassification.CURRENT_SNAPSHOT_ONLY.value == "CURRENT_SNAPSHOT_ONLY"
    assert RequestStatus.EMPTY.value == "EMPTY"
    assert RequestStatus.PARTIAL.value == "PARTIAL"
