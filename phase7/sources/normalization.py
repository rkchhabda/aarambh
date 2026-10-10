"""Canonical data normalization and mathematical validation for EOD records.

Enforces zero-inference rules for turnover, ISIN, delivery, and adjustment state.
Implements versioned schema mappings (NSE_4_0_1_HISTORICAL_CAMELCASE_V1) and
deterministic, locale-independent date parsing (%d-%b-%Y).
Computes deterministic cryptographic row hashes.
"""

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Dict, Optional, Tuple

from phase7.sources.contracts import (
    AdjustmentState,
    FieldStatus,
    HistoricalEODRecord,
)
from phase7.sources.schema_mappings import (
    NSE_4_0_1_SCHEMA_VERSION,
    detect_payload_schema_version,
    parse_nse_d_b_y,
    parse_strict_float,
    parse_strict_int,
)


def _compute_row_hash(data: Dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash across sorted canonical record keys."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _parse_float(val: Any) -> Optional[float]:
    """Backward-compatible float parser helper."""
    if val is None:
        return None
    try:
        clean = str(val).replace(",", "").strip()
        return float(clean)
    except (ValueError, TypeError):
        return None


def _parse_int(val: Any) -> Optional[int]:
    """Backward-compatible integer parser helper."""
    if val is None:
        return None
    try:
        clean = str(val).replace(",", "").strip()
        return int(float(clean))
    except (ValueError, TypeError):
        return None


def normalize_historical_row(
    raw_row: Dict[str, Any],
    symbol: str,
    ingestion_ts: Optional[str] = None,
    source_identifier: str = "NSE_DATA_FETCHER_EOD",
    ingestion_timestamp: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> HistoricalEODRecord:
    """Normalize a raw historical EOD dictionary into a validated canonical HistoricalEODRecord.

    Supports:
    - NSE_4_0_1_HISTORICAL_CAMELCASE_V1 (mtimestamp, chOpeningPrice, chClosingPrice, etc.)
    - PHASE7_LEGACY_UPPERCASE_EOD_V1 (CH_TIMESTAMP, CH_OPENING_PRICE, etc.)

    Raises:
        ValueError: If dates are invalid/out-of-range, OHLC bounds are violated, values are negative,
                    or symbol conflicts with requested security.
    """
    ts = ingestion_ts or ingestion_timestamp or datetime.now(timezone.utc).isoformat()
    if not isinstance(raw_row, dict):
        raise ValueError(f"Expected dict row payload, got {type(raw_row).__name__}")

    # Detect version and reject unsupported future schema versions (e.g. nse 5.x)
    schema_ver = detect_payload_schema_version(raw_row)

    # 1. Symbol Validation
    raw_sym = (
        raw_row.get("chSymbol")
        or raw_row.get("CH_SYMBOL")
        or raw_row.get("symbol")
        or raw_row.get("Symbol")
    )
    if raw_sym is not None and str(raw_sym).strip():
        clean_row_sym = str(raw_sym).strip().upper()
        if clean_row_sym != symbol.strip().upper():
            raise ValueError(
                f"SYMBOL_IDENTITY_CONFLICT: row symbol '{clean_row_sym}' does not match requested '{symbol.strip().upper()}'"
            )

    # 2. Date Extraction & Locale-Independent Normalization
    date_val = (
        raw_row.get("mtimestamp")
        or raw_row.get("mTIMESTAMP")
        or raw_row.get("CH_TIMESTAMP")
        or raw_row.get("date")
        or raw_row.get("Date")
        or raw_row.get("trading_date")
    )
    if not date_val:
        raise ValueError("Missing trading date in row payload")

    date_str = str(date_val).strip()
    trading_date: Optional[str] = None

    # First attempt deterministic locale-independent %d-%b-%Y parsing (e.g. '01-Jan-2024')
    if "-" in date_str and len(date_str.split("-")) == 3:
        try:
            trading_date = parse_nse_d_b_y(date_str)
        except ValueError as dby_err:
            # If it had letters in month but failed, re-raise error
            parts = date_str.split("-")
            if len(parts) == 3 and any(c.isalpha() for c in parts[1]):
                raise ValueError(f"Invalid date format or calendar date: {dby_err}") from dby_err

    # Fallback to standard ISO patterns if not %d-%b-%Y
    if not trading_date:
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d-%m-%Y"):
            try:
                trading_date = datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                pass

    if not trading_date:
        # Fallback regex match for YYYY-MM-DD
        match = re.search(r"(\d{4}-\d{2}-\d{2})", date_str)
        if match:
            trading_date = match.group(1)
        else:
            raise ValueError(f"Cannot parse trading date format from '{date_str}'")

    # Validate date window boundaries if provided
    if start_date and trading_date < start_date:
        raise ValueError(f"Trading date {trading_date} precedes start_date {start_date}")
    if end_date and trading_date > end_date:
        raise ValueError(f"Trading date {trading_date} exceeds end_date {end_date}")

    # 3. Exchange Series Mapping
    raw_series = (
        raw_row.get("chSeries")
        or raw_row.get("CH_SERIES")
        or raw_row.get("series")
    )
    if raw_series and str(raw_series).strip():
        series = str(raw_series).strip().upper()
    else:
        series = "NOT_PROVIDED"

    # 4. Mandatory OHLC Validation & Extraction
    open_raw = (
        raw_row.get("chOpeningPrice")
        or raw_row.get("CH_OPENING_PRICE")
        or raw_row.get("open")
        or raw_row.get("Open")
    )
    high_raw = (
        raw_row.get("chTradeHighPrice")
        or raw_row.get("CH_TRADE_HIGH_PRICE")
        or raw_row.get("high")
        or raw_row.get("High")
    )
    low_raw = (
        raw_row.get("chTradeLowPrice")
        or raw_row.get("CH_TRADE_LOW_PRICE")
        or raw_row.get("low")
        or raw_row.get("Low")
    )
    close_raw = (
        raw_row.get("chClosingPrice")
        or raw_row.get("CH_CLOSING_PRICE")
        or raw_row.get("close")
        or raw_row.get("Close")
    )

    open_val = parse_strict_float(open_raw, "open", mandatory=True)
    high_val = parse_strict_float(high_raw, "high", mandatory=True)
    low_val = parse_strict_float(low_raw, "low", mandatory=True)
    close_val = parse_strict_float(close_raw, "close", mandatory=True)

    if open_val <= 0 or high_val <= 0 or low_val <= 0 or close_val <= 0:
        raise ValueError(f"Non-positive price detected: open={open_val}, high={high_val}, low={low_val}, close={close_val}")

    if low_val > high_val:
        raise ValueError(f"Invalid OHLC: low ({low_val}) exceeds high ({high_val})")

    if open_val < low_val or open_val > high_val:
        raise ValueError(f"Invalid OHLC: open ({open_val}) outside [low, high] range [{low_val}, {high_val}]")

    if close_val < low_val or close_val > high_val:
        raise ValueError(f"Invalid OHLC: close ({close_val}) outside [low, high] range [{low_val}, {high_val}]")

    # 5. Optional Price Fields
    prev_close_raw = (
        raw_row.get("chPreviousClsPrice")
        or raw_row.get("CH_PREVIOUS_CLS_PRICE")
        or raw_row.get("previous_close")
    )
    prev_close = parse_strict_float(prev_close_raw, "previous_close", mandatory=False)
    if prev_close is not None and prev_close <= 0:
        raise ValueError(f"previous_close must be positive, got {prev_close}")

    last_price_raw = (
        raw_row.get("chLastTradedPrice")
        or raw_row.get("CH_LAST_TRADED_PRICE")
        or raw_row.get("last_price")
    )
    last_price = parse_strict_float(last_price_raw, "last_price", mandatory=False)
    if last_price is not None and (last_price < low_val or last_price > high_val):
        raise ValueError(f"Invalid OHLC: last_price ({last_price}) outside [low, high] range [{low_val}, {high_val}]")

    vwap_raw = (
        raw_row.get("vwap")
        or raw_row.get("VWAP")
    )
    vwap_val = parse_strict_float(vwap_raw, "vwap", mandatory=False)
    if vwap_val is not None and vwap_val <= 0:
        raise ValueError(f"vwap must be positive, got {vwap_val}")

    # 6. Volume Validation
    qty_raw = (
        raw_row.get("chTotTradedQty")
        or raw_row.get("CH_TOT_TRADED_QTY")
        or raw_row.get("volume")
        or raw_row.get("Volume")
    )
    qty_val = parse_strict_int(qty_raw, "total_traded_quantity", mandatory=True)
    if qty_val < 0:
        raise ValueError(f"Negative volume detected: {qty_val}")

    # 7. Turnover Validation (Never derived from Close * Volume)
    turnover_raw = (
        raw_row.get("chTotTradedVal")
        or raw_row.get("CH_TOT_TRADED_VAL")
        or raw_row.get("turnover")
        or raw_row.get("total_traded_value_inr")
    )
    turnover_val = parse_strict_float(turnover_raw, "total_traded_value_inr", mandatory=False)
    if turnover_val is not None and turnover_val < 0:
        raise ValueError(f"Negative traded value detected: {turnover_val}")
    traded_value_status = FieldStatus.SOURCE_REPORTED if turnover_val is not None else FieldStatus.NOT_PROVIDED

    # 8. Trade Count Validation
    trades_raw = (
        raw_row.get("chTotalTrades")
        or raw_row.get("CH_TOTAL_TRADES")
        or raw_row.get("number_of_trades")
    )
    num_trades = parse_strict_int(trades_raw, "number_of_trades", mandatory=False)
    if num_trades is not None and num_trades < 0:
        raise ValueError(f"Negative trade count detected: {num_trades}")

    # 9. Delivery Information (Never inferred)
    deliv_qty = parse_strict_int(raw_row.get("COP_DELIV_QTY") or raw_row.get("deliverable_quantity"), "deliverable_quantity", mandatory=False)
    deliv_pct = parse_strict_float(raw_row.get("COP_DELIV_PERC") or raw_row.get("delivery_percentage"), "delivery_percentage", mandatory=False)

    # 10. ISIN (Never inferred)
    isin_val = raw_row.get("CH_ISIN") or raw_row.get("isin")
    isin = str(isin_val).strip() if (isin_val and str(isin_val).strip()) else None

    # 11. Source Publication Timestamp
    # Do not represent mtimestamp as an actual publication timestamp without time-of-day
    src_ts_raw = raw_row.get("TIMESTAMP") or raw_row.get("source_timestamp")
    if src_ts_raw and str(src_ts_raw).strip():
        src_ts = str(src_ts_raw).strip()
    else:
        src_ts = "NOT_PROVIDED"

    # 12. Adjustment State & Trading Status (Never invent or infer)
    if schema_ver == NSE_4_0_1_SCHEMA_VERSION:
        adjustment_state = AdjustmentState.UNKNOWN
        trading_status = "UNKNOWN"
    else:
        raw_adj = raw_row.get("adjustment_state")
        if raw_adj and str(raw_adj) in AdjustmentState.__members__:
            adjustment_state = AdjustmentState(str(raw_adj))
        else:
            adjustment_state = AdjustmentState.UNADJUSTED
        trading_status = str(raw_row.get("trading_status") or "ACTIVE")

    # 13. Deterministic Row Hash
    hash_payload = {
        "trading_date": trading_date,
        "symbol": symbol.upper().strip(),
        "open": round(open_val, 4),
        "high": round(high_val, 4),
        "low": round(low_val, 4),
        "close": round(close_val, 4),
        "volume": qty_val,
        "turnover": round(turnover_val, 4) if turnover_val is not None else None,
        "series": series,
    }
    row_hash = _compute_row_hash(hash_payload)

    return HistoricalEODRecord(
        trading_date=trading_date,
        symbol=symbol.upper().strip(),
        isin=isin,
        exchange_series=series,
        previous_close=prev_close,
        open=open_val,
        high=high_val,
        low=low_val,
        close=close_val,
        last_price=last_price,
        vwap=vwap_val,
        total_traded_quantity=qty_val,
        total_traded_value_inr=turnover_val,
        number_of_trades=num_trades,
        deliverable_quantity=deliv_qty,
        delivery_percentage=deliv_pct,
        trading_status=trading_status,
        adjustment_state=adjustment_state,
        traded_value_status=traded_value_status,
        source_timestamp=src_ts,
        ingestion_timestamp=ts,
        source_identifier=source_identifier,
        row_hash=row_hash,
        mapping_version=schema_ver,
    )
