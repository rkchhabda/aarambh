"""Unit tests for historical EOD normalization and mathematical validation."""

import pytest
from phase7.sources.contracts import AdjustmentState, FieldStatus
from phase7.sources.normalization import normalize_historical_row


def test_valid_row_normalization():
    """Verify clean normalization of valid upstream OHLCV payload."""
    raw = {
        "CH_TIMESTAMP": "2024-01-15",
        "CH_OPENING_PRICE": "2500.00",
        "CH_TRADE_HIGH_PRICE": "2550.00",
        "CH_TRADE_LOW_PRICE": "2490.00",
        "CH_CLOSING_PRICE": "2525.00",
        "CH_PREVIOUS_CLS_PRICE": "2495.00",
        "CH_LAST_TRADED_PRICE": "2524.50",
        "VWAP": "2520.10",
        "CH_TOT_TRADED_QTY": "1,500,000",
        "CH_TOT_TRADED_VAL": "3,780,150,000.00",
        "CH_TOTAL_TRADES": "45,000",
        "CH_SERIES": "EQ",
        "CH_ISIN": "INE002A01018",
    }
    record = normalize_historical_row(raw, "RELIANCE", "2026-10-10T10:00:00Z")

    assert record.symbol == "RELIANCE"
    assert record.trading_date == "2024-01-15"
    assert record.open == 2500.0
    assert record.high == 2550.0
    assert record.low == 2490.0
    assert record.close == 2525.0
    assert record.total_traded_quantity == 1500000
    assert record.total_traded_value_inr == 3780150000.0
    assert record.traded_value_status == FieldStatus.SOURCE_REPORTED
    assert record.isin == "INE002A01018"
    assert record.exchange_series == "EQ"
    assert record.adjustment_state == AdjustmentState.UNADJUSTED
    assert len(record.row_hash) == 64


def test_missing_turnover_not_derived():
    """Verify that missing turnover is strictly marked NOT_PROVIDED and never derived."""
    raw = {
        "CH_TIMESTAMP": "2024-01-15",
        "open": 100.0,
        "high": 110.0,
        "low": 95.0,
        "close": 105.0,
        "volume": 5000,
        # CH_TOT_TRADED_VAL / turnover omitted
    }
    record = normalize_historical_row(raw, "TCS", "2026-10-10T10:00:00Z")

    assert record.total_traded_value_inr is None
    assert record.traded_value_status == FieldStatus.NOT_PROVIDED
    # Must NOT calculate 105 * 5000 = 525000
    assert record.total_traded_value_inr != 525000.0


def test_missing_isin_not_inferred():
    """Verify that missing ISIN is left as None and not inferred from ticker."""
    raw = {
        "CH_TIMESTAMP": "2024-01-15",
        "open": 100.0,
        "high": 110.0,
        "low": 95.0,
        "close": 105.0,
        "volume": 5000,
    }
    record = normalize_historical_row(raw, "INFY", "2026-10-10T10:00:00Z")
    assert record.isin is None


def test_invalid_ohlc_relationships_rejected():
    """Verify strict rejection of invalid OHLC bounds."""
    # Low > High
    with pytest.raises(ValueError, match="low .* exceeds high"):
        normalize_historical_row(
            {"date": "2024-01-15", "open": 100, "high": 90, "low": 110, "close": 95, "volume": 100},
            "HDFCBANK",
            "ts",
        )

    # Open outside [low, high]
    with pytest.raises(ValueError, match="open .* outside"):
        normalize_historical_row(
            {"date": "2024-01-15", "open": 120, "high": 110, "low": 90, "close": 100, "volume": 100},
            "HDFCBANK",
            "ts",
        )

    # Close outside [low, high]
    with pytest.raises(ValueError, match="close .* outside"):
        normalize_historical_row(
            {"date": "2024-01-15", "open": 100, "high": 110, "low": 90, "close": 85, "volume": 100},
            "HDFCBANK",
            "ts",
        )

    # Negative prices
    with pytest.raises(ValueError, match="Non-positive price"):
        normalize_historical_row(
            {"date": "2024-01-15", "open": -10, "high": 110, "low": 90, "close": 100, "volume": 100},
            "HDFCBANK",
            "ts",
        )

    # Negative volume
    with pytest.raises(ValueError, match="Negative volume"):
        normalize_historical_row(
            {"date": "2024-01-15", "open": 100, "high": 110, "low": 90, "close": 105, "volume": -50},
            "HDFCBANK",
            "ts",
        )


def test_deterministic_row_hash():
    """Verify that identical row data produces identical hashes."""
    raw1 = {"date": "2024-01-15", "open": 100.0, "high": 110.0, "low": 90.0, "close": 105.0, "volume": 1000}
    raw2 = {"date": "2024-01-15", "open": 100.0, "high": 110.0, "low": 90.0, "close": 105.0, "volume": 1000}

    rec1 = normalize_historical_row(raw1, "TCS", "ts1")
    rec2 = normalize_historical_row(raw2, "TCS", "ts2")

    assert rec1.row_hash == rec2.row_hash
