"""Canonical data normalization and mathematical validation for EOD records.

Enforces zero-inference rules for turnover, ISIN, and adjustment state.
Computes deterministic cryptographic row hashes.
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from phase7.sources.contracts import (
    AdjustmentState,
    FieldStatus,
    HistoricalEODRecord,
)


def _compute_row_hash(data: Dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash across sorted canonical record keys."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _parse_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        f = float(str(val).replace(",", "").strip())
        return f
    except (ValueError, TypeError):
        return None


def _parse_int(val: Any) -> Optional[int]:
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
) -> HistoricalEODRecord:
    """Normalize a raw historical EOD dictionary into a validated canonical HistoricalEODRecord.

    Raises:
        ValueError: If dates are invalid, OHLC values are negative, or low > high.
    """
    ts = ingestion_ts or ingestion_timestamp or datetime.now(timezone.utc).isoformat()
    if not isinstance(raw_row, dict):
        raise ValueError(f"Expected dict row payload, got {type(raw_row).__name__}")

    # Check symbol identity conflict if symbol is present in row
    raw_sym = raw_row.get("CH_SYMBOL") or raw_row.get("symbol") or raw_row.get("Symbol")
    if raw_sym and str(raw_sym).strip().upper() != symbol.strip().upper():
        raise ValueError(f"SYMBOL_IDENTITY_CONFLICT: row symbol '{raw_sym}' does not match requested '{symbol}'")

    # Extract date
    date_val = (
        raw_row.get("CH_TIMESTAMP")
        or raw_row.get("mTIMESTAMP")
        or raw_row.get("date")
        or raw_row.get("Date")
        or raw_row.get("trading_date")
    )
    if not date_val:
        raise ValueError("Missing trading date in row payload")

    # Normalize date to YYYY-MM-DD
    date_str = str(date_val).strip()
    trading_date: Optional[str] = None
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S", "%d-%b-%Y %H:%M:%S"):
        try:
            trading_date = datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
            break
        except ValueError:
            pass

    if not trading_date:
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%b-%Y"):
            try:
                prefix = date_str[:11] if "-" in date_str and len(date_str) >= 11 else date_str[:10]
                trading_date = datetime.strptime(prefix, fmt).strftime("%Y-%m-%d")
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

    # Extract OHLC
    open_val = _parse_float(raw_row.get("CH_OPENING_PRICE") or raw_row.get("open") or raw_row.get("Open"))
    high_val = _parse_float(raw_row.get("CH_TRADE_HIGH_PRICE") or raw_row.get("high") or raw_row.get("High"))
    low_val = _parse_float(raw_row.get("CH_TRADE_LOW_PRICE") or raw_row.get("low") or raw_row.get("Low"))
    close_val = _parse_float(raw_row.get("CH_CLOSING_PRICE") or raw_row.get("close") or raw_row.get("Close"))

    if open_val is None or high_val is None or low_val is None or close_val is None:
        raise ValueError(f"Missing mandatory OHLC fields in row: {raw_row}")

    if open_val <= 0 or high_val <= 0 or low_val <= 0 or close_val <= 0:
        raise ValueError(f"Non-positive price detected: open={open_val}, high={high_val}, low={low_val}, close={close_val}")

    if low_val > high_val:
        raise ValueError(f"Invalid OHLC: low ({low_val}) exceeds high ({high_val})")

    if open_val < low_val or open_val > high_val:
        raise ValueError(f"Invalid OHLC: open ({open_val}) outside [low, high] range [{low_val}, {high_val}]")

    if close_val < low_val or close_val > high_val:
        raise ValueError(f"Invalid OHLC: close ({close_val}) outside [low, high] range [{low_val}, {high_val}]")

    # Volume
    qty_val = (
        _parse_int(raw_row.get("CH_TOT_TRADED_QTY"))
        or _parse_int(raw_row.get("volume"))
        or _parse_int(raw_row.get("Volume"))
        or 0
    )
    if qty_val < 0:
        raise ValueError(f"Negative volume detected: {qty_val}")

    # Traded Value / Turnover (Do NOT derive from Close * Volume)
    raw_val = raw_row.get("CH_TOT_TRADED_VAL") or raw_row.get("turnover") or raw_row.get("total_traded_value_inr")
    turnover_val = _parse_float(raw_val)
    if turnover_val is not None and turnover_val < 0:
        raise ValueError(f"Negative traded value detected: {turnover_val}")

    traded_value_status = FieldStatus.SOURCE_REPORTED if turnover_val is not None else FieldStatus.NOT_PROVIDED

    # Previous close
    prev_close = _parse_float(raw_row.get("CH_PREVIOUS_CLS_PRICE") or raw_row.get("previous_close"))

    # Last price & VWAP
    last_price = _parse_float(raw_row.get("CH_LAST_TRADED_PRICE") or raw_row.get("last_price"))
    vwap_val = _parse_float(raw_row.get("VWAP") or raw_row.get("vwap"))

    # Trades & Delivery
    num_trades = _parse_int(raw_row.get("CH_TOTAL_TRADES") or raw_row.get("number_of_trades"))
    deliv_qty = _parse_int(raw_row.get("COP_DELIV_QTY") or raw_row.get("deliverable_quantity"))
    deliv_pct = _parse_float(raw_row.get("COP_DELIV_PERC") or raw_row.get("delivery_percentage"))

    # Series & ISIN (Never infer ISIN)
    series = str(raw_row.get("CH_SERIES") or raw_row.get("series") or "EQ").strip().upper()
    isin_val = raw_row.get("CH_ISIN") or raw_row.get("isin")
    isin = str(isin_val).strip() if isin_val else None

    # Source timestamp
    src_ts = str(raw_row.get("TIMESTAMP") or raw_row.get("source_timestamp") or trading_date)

    # Compute row hash
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
        trading_status="ACTIVE",
        adjustment_state=AdjustmentState.UNADJUSTED,
        traded_value_status=traded_value_status,
        source_timestamp=src_ts,
        ingestion_timestamp=ts,
        source_identifier=source_identifier,
        row_hash=row_hash,
    )
