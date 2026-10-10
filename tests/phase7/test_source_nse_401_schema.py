"""Mocked unit and contract tests for NSE 4.0.1 historical payload normalization.

Tests all requirements using synthetic records matching the observed nse==4.0.1 shape:
- Keys: mtimestamp, chSymbol, chSeries, chPreviousClsPrice, chOpeningPrice, chTradeHighPrice,
        chTradeLowPrice, chClosingPrice, chLastTradedPrice, vwap, chTotTradedQty, chTotTradedVal,
        chTotalTrades, ch52WeekHighPrice, ch52WeekLowPrice
- Zero real live market prices/volumes are committed.
"""

import math
import pytest

from phase7.sources.contracts import (
    AdjustmentState,
    FieldStatus,
    HistoricalEODRecord,
    RequestStatus,
)
from phase7.sources.manifest import check_audit_conservation
from phase7.sources.normalization import normalize_historical_row
from phase7.sources.schema_mappings import (
    NSE_4_0_1_SCHEMA_VERSION,
    detect_payload_schema_version,
    parse_nse_d_b_y,
    parse_strict_float,
    parse_strict_int,
)


def _make_synthetic_row(
    symbol: str = "SYNTHETIC",
    date: str = "15-Jan-2024",
    open_p: float = 100.0,
    high_p: float = 105.0,
    low_p: float = 95.0,
    close_p: float = 102.0,
    qty: int = 10000,
    turnover: float = 1020000.0,
    trades: int = 500,
    prev_close: float = 99.0,
    last_price: float = 101.5,
    vwap: float = 101.0,
    series: str = "EQ",
) -> dict:
    """Create synthetic row matching the exact observed nse==4.0.1 key set."""
    return {
        "ch52WeekHighPrice": 120.0,
        "ch52WeekLowPrice": 80.0,
        "chClosingPrice": close_p,
        "chLastTradedPrice": last_price,
        "chOpeningPrice": open_p,
        "chPreviousClsPrice": prev_close,
        "chSeries": series,
        "chSymbol": symbol,
        "chTotTradedQty": qty,
        "chTotTradedVal": turnover,
        "chTotalTrades": trades,
        "chTradeHighPrice": high_p,
        "chTradeLowPrice": low_p,
        "mtimestamp": date,
        "vwap": vwap,
    }


def test_lowercase_mtimestamp_is_normalized():
    """Regression test: proves lowercase 'mtimestamp' from nse==4.0.1 is normalized to ISO YYYY-MM-DD."""
    row = _make_synthetic_row(date="01-Jan-2024")
    rec = normalize_historical_row(row, "SYNTHETIC")
    assert rec.trading_date == "2024-01-01"


def test_mtimestamp_parses_d_b_y():
    """Verify %d-%b-%Y parsing across various months."""
    assert parse_nse_d_b_y("15-Jan-2024") == "2024-01-15"
    assert parse_nse_d_b_y("29-Feb-2024") == "2024-02-29"
    assert parse_nse_d_b_y("31-Dec-2024") == "2024-12-31"


def test_locale_independent_month_parsing():
    """Verify English months are parsed deterministically independent of machine locale."""
    for mon_str, mon_num in [
        ("Jan", "01"), ("Feb", "02"), ("Mar", "03"), ("Apr", "04"),
        ("May", "05"), ("Jun", "06"), ("Jul", "07"), ("Aug", "08"),
        ("Sep", "09"), ("Oct", "10"), ("Nov", "11"), ("Dec", "12"),
    ]:
        raw_date = f"10-{mon_str}-2024"
        assert parse_nse_d_b_y(raw_date) == f"2024-{mon_num}-10"


def test_invalid_source_date_rejected():
    """Verify impossible calendar dates and bad formats fail closed."""
    with pytest.raises(ValueError, match="Impossible calendar date|day is out of range"):
        parse_nse_d_b_y("31-Feb-2024")

    with pytest.raises(ValueError, match="Invalid date format"):
        parse_nse_d_b_y("2024-01-01")

    with pytest.raises(ValueError, match="Unrecognized month abbreviation"):
        parse_nse_d_b_y("10-Xyz-2024")


def test_out_of_range_date_rejected():
    """Verify row validator rejects trading dates outside requested calendar window."""
    row = _make_synthetic_row(date="15-Feb-2024")
    with pytest.raises(ValueError, match="exceeds end_date"):
        normalize_historical_row(row, "SYNTHETIC", start_date="2024-01-01", end_date="2024-01-31")


def test_mtimestamp_not_misrepresented_as_publication_timestamp():
    """Verify mtimestamp is treated strictly as trading_date, and source_timestamp is NOT_PROVIDED."""
    row = _make_synthetic_row(date="01-Jan-2024")
    rec = normalize_historical_row(row, "SYNTHETIC")
    assert rec.trading_date == "2024-01-01"
    assert rec.source_timestamp == "NOT_PROVIDED"


def test_chSymbol_mapping_and_conflict_rejection():
    """Verify chSymbol maps to symbol and conflicts raise SYMBOL_IDENTITY_CONFLICT."""
    row = _make_synthetic_row(symbol="RELIANCE")
    rec = normalize_historical_row(row, "RELIANCE")
    assert rec.symbol == "RELIANCE"

    with pytest.raises(ValueError, match="SYMBOL_IDENTITY_CONFLICT"):
        normalize_historical_row(row, "TCS")


def test_chSeries_mapping_and_missing_handling():
    """Verify chSeries maps to exchange_series and missing series becomes NOT_PROVIDED."""
    row = _make_synthetic_row(series="EQ")
    rec = normalize_historical_row(row, "SYNTHETIC")
    assert rec.exchange_series == "EQ"

    row_no_series = _make_synthetic_row()
    del row_no_series["chSeries"]
    rec_no_series = normalize_historical_row(row_no_series, "SYNTHETIC")
    assert rec_no_series.exchange_series == "NOT_PROVIDED"


def test_ohlc_field_mappings():
    """Verify exact mappings for previous close, open, high, low, close, last price, and vwap."""
    row = _make_synthetic_row(
        open_p=101.5,
        high_p=108.0,
        low_p=98.5,
        close_p=106.0,
        prev_close=100.0,
        last_price=105.5,
        vwap=104.2,
    )
    rec = normalize_historical_row(row, "SYNTHETIC")
    assert rec.open == 101.5
    assert rec.high == 108.0
    assert rec.low == 98.5
    assert rec.close == 106.0
    assert rec.previous_close == 100.0
    assert rec.last_price == 105.5
    assert rec.vwap == 104.2


def test_volume_turnover_trades_mapping():
    """Verify total traded quantity, turnover, and trade count mappings."""
    row = _make_synthetic_row(qty=50000, turnover=5250000.0, trades=1200)
    rec = normalize_historical_row(row, "SYNTHETIC")
    assert rec.total_traded_quantity == 50000
    assert rec.total_traded_value_inr == 5250000.0
    assert rec.traded_value_status == FieldStatus.SOURCE_REPORTED
    assert rec.number_of_trades == 1200


def test_turnover_not_derived_when_missing():
    """Verify that omitting chTotTradedVal does not derive turnover from Close * Volume."""
    row = _make_synthetic_row(close_p=100.0, qty=1000)
    del row["chTotTradedVal"]
    rec = normalize_historical_row(row, "SYNTHETIC")
    assert rec.total_traded_value_inr is None
    assert rec.traded_value_status == FieldStatus.NOT_PROVIDED
    assert rec.total_traded_value_inr != 100000.0


def test_isin_and_adjustment_state_not_inferred():
    """Verify ISIN is None, delivery is None, and adjustment_state is UNKNOWN for nse 4.0.1."""
    row = _make_synthetic_row()
    rec = normalize_historical_row(row, "SYNTHETIC")
    assert rec.isin is None
    assert rec.deliverable_quantity is None
    assert rec.delivery_percentage is None
    assert rec.trading_status == "UNKNOWN"
    assert rec.adjustment_state == AdjustmentState.UNKNOWN


def test_invalid_ohlc_rejection():
    """Verify low > high, open outside bounds, and close outside bounds raise ValueError."""
    # Low > High
    with pytest.raises(ValueError, match="low .* exceeds high"):
        normalize_historical_row(_make_synthetic_row(low_p=110.0, high_p=100.0), "SYNTHETIC")

    # Open < Low
    with pytest.raises(ValueError, match="open .* outside"):
        normalize_historical_row(_make_synthetic_row(open_p=90.0, low_p=95.0, high_p=105.0), "SYNTHETIC")

    # Close > High
    with pytest.raises(ValueError, match="close .* outside"):
        normalize_historical_row(_make_synthetic_row(close_p=115.0, low_p=95.0, high_p=105.0), "SYNTHETIC")

    # Last price outside bounds
    with pytest.raises(ValueError, match="last_price .* outside"):
        normalize_historical_row(_make_synthetic_row(last_price=120.0, low_p=95.0, high_p=105.0), "SYNTHETIC")


def test_negative_values_rejected():
    """Verify negative volume, turnover, trade count, and prices fail closed."""
    with pytest.raises(ValueError, match="Negative volume"):
        normalize_historical_row(_make_synthetic_row(qty=-100), "SYNTHETIC")

    with pytest.raises(ValueError, match="Negative traded value"):
        normalize_historical_row(_make_synthetic_row(turnover=-500.0), "SYNTHETIC")

    with pytest.raises(ValueError, match="Negative trade count"):
        normalize_historical_row(_make_synthetic_row(trades=-10), "SYNTHETIC")

    with pytest.raises(ValueError, match="Non-positive price"):
        normalize_historical_row(_make_synthetic_row(open_p=-10.0), "SYNTHETIC")


def test_nan_and_infinity_rejected():
    """Verify NaN and Infinity in numerics fail closed."""
    with pytest.raises(ValueError, match="NaN or Infinity rejected"):
        parse_strict_float(float("nan"), "test_nan")

    with pytest.raises(ValueError, match="NaN or Infinity rejected"):
        parse_strict_float(float("inf"), "test_inf")

    with pytest.raises(ValueError, match="NaN or Infinity rejected"):
        parse_strict_int(float("nan"), "test_nan_int")


def test_blank_mandatory_numerics_rejected():
    """Verify blank or empty string for mandatory numerics raises ValueError."""
    with pytest.raises(ValueError, match="missing or blank"):
        parse_strict_float("   ", "mandatory_open", mandatory=True)

    with pytest.raises(ValueError, match="missing or blank"):
        parse_strict_int("", "mandatory_volume", mandatory=True)


def test_numeric_strings_handled_cleanly():
    """Verify comma-separated numeric strings are parsed cleanly."""
    assert parse_strict_float("2,590.25", "price") == 2590.25
    assert parse_strict_int("1,500,000", "qty") == 1500000


def test_schema_version_detection_and_recording():
    """Verify schema version is detected as NSE_4_0_1_HISTORICAL_CAMELCASE_V1 and recorded."""
    row = _make_synthetic_row()
    assert detect_payload_schema_version(row) == NSE_4_0_1_SCHEMA_VERSION
    rec = normalize_historical_row(row, "SYNTHETIC")
    assert rec.mapping_version == NSE_4_0_1_SCHEMA_VERSION


def test_unsupported_nse_5_schema_rejected():
    """Verify payloads with nse 5.x version indicators raise SCHEMA_MISMATCH."""
    row = _make_synthetic_row()
    row["nse_version"] = "5.0.0"
    with pytest.raises(ValueError, match="SCHEMA_MISMATCH: nse 5.x"):
        normalize_historical_row(row, "SYNTHETIC")


def test_audit_conservation_invariant():
    """Verify conservation rule: source = normalized + rejected."""
    assert check_audit_conservation(source_row_count=22, normalized_row_count=22, rejected_row_count=0) is True
    assert check_audit_conservation(source_row_count=22, normalized_row_count=20, rejected_row_count=2) is True
    assert check_audit_conservation(source_row_count=22, normalized_row_count=20, rejected_row_count=0) is False
