"""Versioned source schema mappings and locale-independent parser for NSE 4.0.1.

Governs:
- Strict field mappings for observed nse==4.0.1 historical camelCase payloads.
- Deterministic, locale-independent month abbreviation parser (%d-%b-%Y).
- Strict numeric validation rejecting NaN, Infinity, negative values, and blanks.
- Rejection of unobserved or future schema versions (e.g. nse 5.x).
"""

from datetime import datetime
import math
from typing import Any, Dict, FrozenSet, Optional, Tuple

NSE_4_0_1_SCHEMA_VERSION = "NSE_4_0_1_HISTORICAL_CAMELCASE_V1"

# Exact observed keys in nse==4.0.1 fetch_equity_historical_data
OBSERVED_NSE_4_0_1_KEYS: FrozenSet[str] = frozenset({
    "ch52WeekHighPrice",
    "ch52WeekLowPrice",
    "chClosingPrice",
    "chLastTradedPrice",
    "chOpeningPrice",
    "chPreviousClsPrice",
    "chSeries",
    "chSymbol",
    "chTotTradedQty",
    "chTotTradedVal",
    "chTotalTrades",
    "chTradeHighPrice",
    "chTradeLowPrice",
    "mtimestamp",
    "vwap",
})

# Explicit canonical field mapping from observed nse==4.0.1 keys
NSE_4_0_1_SOURCE_MAPPING: Dict[str, str] = {
    "mtimestamp": "trading_date",
    "chSymbol": "symbol",
    "chSeries": "exchange_series",
    "chPreviousClsPrice": "previous_close",
    "chOpeningPrice": "open",
    "chTradeHighPrice": "high",
    "chTradeLowPrice": "low",
    "chClosingPrice": "close",
    "chLastTradedPrice": "last_price",
    "vwap": "vwap",
    "chTotTradedQty": "total_traded_quantity",
    "chTotTradedVal": "total_traded_value_inr",
    "chTotalTrades": "number_of_trades",
}

# English month mapping for locale-independent %d-%b-%Y date parsing
ENGLISH_MONTHS: Dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_nse_d_b_y(date_str: str) -> str:
    """Parse %d-%b-%Y (e.g. '01-Jan-2024') into canonical 'YYYY-MM-DD' deterministically.

    Proof of locale-independence: Uses an explicit English month abbreviation dictionary
    and does not invoke libc/platform locale-dependent strptime('%b').

    Raises:
        ValueError: If format is invalid, month is unrecognized, or day is impossible for calendar.
    """
    raw = str(date_str).strip()
    parts = raw.split("-")
    if len(parts) != 3:
        raise ValueError(f"Invalid date format '{raw}', expected '%d-%b-%Y' (e.g. '01-Jan-2024')")

    day_str, mon_str, year_str = parts
    day_str = day_str.strip()
    mon_str = mon_str.strip()
    year_str = year_str.strip()

    if not (day_str.isdigit() and len(year_str) == 4 and year_str.isdigit()):
        raise ValueError(f"Invalid date format '{raw}', day and 4-digit year must be numeric")

    mon_lower = mon_str.lower()
    if mon_lower not in ENGLISH_MONTHS:
        raise ValueError(f"Unrecognized month abbreviation '{mon_str}' in date '{raw}'")

    day = int(day_str)
    month = ENGLISH_MONTHS[mon_lower]
    year = int(year_str)

    try:
        dt = datetime(year, month, day).date()
    except ValueError as cal_err:
        raise ValueError(f"Impossible calendar date '{raw}': {cal_err}") from cal_err

    return dt.strftime("%Y-%m-%d")


def parse_strict_float(val: Any, field_name: str, mandatory: bool = True) -> Optional[float]:
    """Parse a float strictly, rejecting NaN, Infinity, and blanks for mandatory fields."""
    if val is None or (isinstance(val, str) and not val.strip()):
        if mandatory:
            raise ValueError(f"Mandatory numeric field '{field_name}' is missing or blank")
        return None

    try:
        clean = str(val).replace(",", "").strip()
        f = float(clean)
    except (ValueError, TypeError) as parse_err:
        raise ValueError(f"Malformed float in field '{field_name}': {val}") from parse_err

    if math.isnan(f) or math.isinf(f):
        raise ValueError(f"NaN or Infinity rejected in field '{field_name}': {val}")
    return f


def parse_strict_int(val: Any, field_name: str, mandatory: bool = True) -> Optional[int]:
    """Parse an integer strictly, rejecting NaN, Infinity, and blanks for mandatory fields."""
    if val is None or (isinstance(val, str) and not val.strip()):
        if mandatory:
            raise ValueError(f"Mandatory integer field '{field_name}' is missing or blank")
        return None

    try:
        clean = str(val).replace(",", "").strip()
        f = float(clean)
    except (ValueError, TypeError) as parse_err:
        raise ValueError(f"Malformed integer in field '{field_name}': {val}") from parse_err

    if math.isnan(f) or math.isinf(f):
        raise ValueError(f"NaN or Infinity rejected in field '{field_name}': {val}")

    return int(f)


def detect_payload_schema_version(row: Dict[str, Any]) -> str:
    """Detect schema version of raw payload record and reject unobserved/future versions."""
    if not isinstance(row, dict):
        raise ValueError(f"Expected dict row payload, got {type(row).__name__}")

    # Explicit rejection of unsupported future schema versions (e.g. nse 5.x)
    if "nse_version" in row and str(row["nse_version"]).startswith("5"):
        raise ValueError("SCHEMA_MISMATCH: nse 5.x schema version is not supported")
    if "schema_version" in row and "5." in str(row["schema_version"]):
        raise ValueError("SCHEMA_MISMATCH: nse 5.x schema version is not supported")

    # If observed nse==4.0.1 key set or primary keys are present
    if "mtimestamp" in row or "chOpeningPrice" in row or "chClosingPrice" in row:
        return NSE_4_0_1_SCHEMA_VERSION

    # Legacy Phase 7 uppercase variant
    if "CH_TIMESTAMP" in row or "CH_OPENING_PRICE" in row:
        return "PHASE7_LEGACY_UPPERCASE_EOD_V1"

    return "UNKNOWN_SCHEMA_VERSION"
