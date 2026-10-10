"""Tests for EOD row normalization, mathematical boundaries, and field status contracts."""

import pytest

from phase7.sources.contracts import (
    AdjustmentState,
    FieldStatus,
    HistoricalEODRecord,
)
from phase7.sources.normalization import normalize_historical_row


def test_valid_ohlc_normalization():
    """Verify valid OHLC relationships are accepted and correctly typed."""
    raw = {
        "CH_TIMESTAMP": "2024-01-10",
        "CH_SERIES": "EQ",
        "CH_OPENING_PRICE": 100.0,
        "CH_TRADE_HIGH_PRICE": 105.0,
        "CH_TRADE_LOW_PRICE": 98.0,
        "CH_CLOSING_PRICE": 102.0,
        "CH_TOT_TRADED_QTY": 50000,
        "CH_TOT_TRADED_VAL": 5100000.0,
    }
    rec = normalize_historical_row(raw, "INFY", "2026-10-10T10:00:00Z")
    assert rec.open == 100.0
    assert rec.high == 105.0
    assert rec.low == 98.0
    assert rec.close == 102.0
    assert rec.total_traded_quantity == 50000
    assert rec.total_traded_value_inr == 5100000.0
    assert rec.traded_value_status == FieldStatus.SOURCE_REPORTED
    assert rec.row_hash is not None and len(rec.row_hash) == 64


def test_invalid_ohlc_rejected():
    """Verify invalid OHLC structures (high < low, negative prices) are rejected."""
    # High < Low
    raw_high_low = {
        "CH_TIMESTAMP": "2024-01-10",
        "CH_OPENING_PRICE": 100.0,
        "CH_TRADE_HIGH_PRICE": 95.0,
        "CH_TRADE_LOW_PRICE": 105.0,
        "CH_CLOSING_PRICE": 100.0,
        "CH_TOT_TRADED_QTY": 50000,
    }
    with pytest.raises(ValueError, match="exceeds high|High .* cannot be less than Low"):
        normalize_historical_row(raw_high_low, "INFY", "2026-10-10T10:00:00Z")

    # Negative price
    raw_neg = {
        "CH_TIMESTAMP": "2024-01-10",
        "CH_OPENING_PRICE": -100.0,
        "CH_TRADE_HIGH_PRICE": 105.0,
        "CH_TRADE_LOW_PRICE": 95.0,
        "CH_CLOSING_PRICE": 100.0,
        "CH_TOT_TRADED_QTY": 50000,
    }
    with pytest.raises(ValueError, match="Non-positive price|strictly positive"):
        normalize_historical_row(raw_neg, "INFY", "2026-10-10T10:00:00Z")


def test_negative_volume_rejected():
    """Verify negative volume is strictly rejected."""
    raw = {
        "CH_TIMESTAMP": "2024-01-10",
        "CH_OPENING_PRICE": 100.0,
        "CH_TRADE_HIGH_PRICE": 105.0,
        "CH_TRADE_LOW_PRICE": 95.0,
        "CH_CLOSING_PRICE": 100.0,
        "CH_TOT_TRADED_QTY": -500,
    }
    with pytest.raises(ValueError, match="Negative volume|Total traded quantity cannot be negative"):
        normalize_historical_row(raw, "INFY", "2026-10-10T10:00:00Z")


def test_turnover_not_derived_from_close():
    """Verify turnover is NOT computed as Close * Volume when missing."""
    raw = {
        "CH_TIMESTAMP": "2024-01-10",
        "CH_OPENING_PRICE": 100.0,
        "CH_TRADE_HIGH_PRICE": 105.0,
        "CH_TRADE_LOW_PRICE": 95.0,
        "CH_CLOSING_PRICE": 100.0,
        "CH_TOT_TRADED_QTY": 50000,
        # CH_TOT_TRADED_VAL missing
    }
    rec = normalize_historical_row(raw, "INFY", "2026-10-10T10:00:00Z")
    assert rec.total_traded_value_inr is None
    assert rec.traded_value_status == FieldStatus.NOT_PROVIDED


def test_isin_not_inferred():
    """Verify ISIN is None and never fabricated when missing from payload."""
    raw = {
        "CH_TIMESTAMP": "2024-01-10",
        "CH_OPENING_PRICE": 100.0,
        "CH_TRADE_HIGH_PRICE": 105.0,
        "CH_TRADE_LOW_PRICE": 95.0,
        "CH_CLOSING_PRICE": 100.0,
        "CH_TOT_TRADED_QTY": 50000,
    }
    rec = normalize_historical_row(raw, "INFY", "2026-10-10T10:00:00Z")
    assert rec.isin is None


def test_adjustment_state_not_invented():
    """Verify adjustment state is strictly UNADJUSTED or UNKNOWN, never invented."""
    raw = {
        "CH_TIMESTAMP": "2024-01-10",
        "CH_OPENING_PRICE": 100.0,
        "CH_TRADE_HIGH_PRICE": 105.0,
        "CH_TRADE_LOW_PRICE": 95.0,
        "CH_CLOSING_PRICE": 100.0,
        "CH_TOT_TRADED_QTY": 50000,
    }
    rec = normalize_historical_row(raw, "INFY", "2026-10-10T10:00:00Z")
    assert rec.adjustment_state in (AdjustmentState.UNADJUSTED, AdjustmentState.UNKNOWN)
    assert rec.adjustment_state != AdjustmentState.SPLIT_ADJUSTED


def test_deterministic_stable_row_hash():
    """Verify row_hash produces identical SHA-256 for identical logical content."""
    raw = {
        "CH_TIMESTAMP": "2024-01-10",
        "CH_OPENING_PRICE": 100.0,
        "CH_TRADE_HIGH_PRICE": 105.0,
        "CH_TRADE_LOW_PRICE": 95.0,
        "CH_CLOSING_PRICE": 100.0,
        "CH_TOT_TRADED_QTY": 50000,
    }
    rec1 = normalize_historical_row(raw, "INFY", "2026-10-10T10:00:00Z")
    rec2 = normalize_historical_row(raw, "INFY", "2026-10-10T10:00:00Z")
    assert rec1.row_hash == rec2.row_hash
