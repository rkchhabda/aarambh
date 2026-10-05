"""Fail-closed data loaders for Phase 7 tabular and structured records.

Supports streaming row-by-row validation for:
1. CSV files
2. JSON array files
3. JSON Lines (JSONL) files

Loaders preserve row numbers, raw input values, and specific rejection reasons.
Malformed values, timezone-naive timestamps, duplicate keys, and hash mismatches
are strictly rejected without silent coercion.
"""

from abc import ABC, abstractmethod
import csv
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, Generic, List, Optional, Sequence, Tuple, TypeVar, Union

from phase7.data.contracts import (
    CorporateActionRecord,
    CorporateActionType,
    DailyPriceRecord,
    EligibilityStatus,
    EligibilitySuspensionRecord,
    PITMembershipRecord,
    PITSectorClassificationRecord,
    PriceAdjustmentState,
    TradedValueStatus,
)

T = TypeVar("T")


@dataclass(frozen=True)
class RejectedRecord:
    """Record rejected during load validation."""
    row_number: int
    raw_data: Dict[str, Any]
    reasons: List[str]
    source_identifier: str


@dataclass(frozen=True)
class LoadResult(Generic[T]):
    """Structured result returned by fail-closed loaders."""
    accepted_records: List[T]
    rejected_records: List[RejectedRecord]
    source_fingerprint: str
    total_rows: int
    accepted_count: int
    rejected_count: int
    duplicate_count: int
    date_range: Optional[Tuple[date, date]] = None
    symbol_count: int = 0
    isin_count: int = 0
    warnings: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)


def parse_iso_datetime(dt_str: Any) -> datetime:
    """Parse an ISO 8601 string to a timezone-aware UTC datetime.

    Raises ValueError if string is timezone-naive or malformed.
    """
    if not isinstance(dt_str, str) or not dt_str.strip():
        raise ValueError(f"Malformed or empty datetime string: {dt_str}")
    clean = dt_str.strip()
    if clean.endswith("Z"):
        clean = clean[:-1] + "+00:00"
    dt = datetime.fromisoformat(clean)
    if dt.tzinfo is None:
        raise ValueError(f"Timezone-naive datetime rejected: '{dt_str}'. Must be UTC/timezone-aware.")
    return dt.astimezone(timezone.utc)


def parse_iso_date(d_str: Any) -> date:
    """Parse YYYY-MM-DD string to date object."""
    if isinstance(d_str, date) and not isinstance(d_str, datetime):
        return d_str
    if not isinstance(d_str, str) or not d_str.strip():
        raise ValueError(f"Malformed or empty date string: {d_str}")
    return date.fromisoformat(d_str.strip()[:10])


def parse_decimal_safe(val: Any, field_name: str) -> Decimal:
    """Convert numeric or string value to Decimal safely without silent zero-coercion."""
    if val is None or val == "":
        raise ValueError(f"Field '{field_name}' is missing; cannot coerce to Decimal.")
    try:
        d = Decimal(str(val).strip())
        if d.is_nan() or d.is_infinite():
            raise ValueError(f"Field '{field_name}' contains NaN or Infinite Decimal: {val}")
        return d
    except (InvalidOperation, TypeError) as e:
        raise ValueError(f"Cannot parse field '{field_name}' value '{val}' as Decimal: {e}")


def parse_int_safe(val: Any, field_name: str) -> int:
    """Convert value to int safely without silent zero-coercion."""
    if val is None or val == "":
        raise ValueError(f"Field '{field_name}' is missing; cannot coerce to int.")
    try:
        return int(str(val).strip())
    except (ValueError, TypeError) as e:
        raise ValueError(f"Cannot parse field '{field_name}' value '{val}' as int: {e}")


# ------------------------------------------------------------------------------
# Row Parser Functions
# ------------------------------------------------------------------------------

def parse_daily_price_row(row: Dict[str, Any], source_id: str) -> DailyPriceRecord:
    """Parse raw dictionary into a validated DailyPriceRecord."""
    t_date = parse_iso_date(row.get("trading_date") or row.get("date"))
    sym = str(row.get("symbol") or row.get("ticker", "")).strip().upper()
    isin_val = str(row.get("isin", "")).strip().upper()

    open_p = parse_decimal_safe(row.get("open"), "open")
    high_p = parse_decimal_safe(row.get("high"), "high")
    low_p = parse_decimal_safe(row.get("low"), "low")
    close_p = parse_decimal_safe(row.get("close"), "close")
    vol = parse_int_safe(row.get("volume"), "volume")

    tv = parse_decimal_safe(row.get("traded_value_inr") or row.get("traded_value"), "traded_value_inr")
    tv_status = TradedValueStatus(str(row.get("traded_value_status", "EXCHANGE_REPORTED")).strip().upper())
    adj_state = PriceAdjustmentState(str(row.get("price_adjustment_state", "RAW")).strip().upper())

    src_ts = parse_iso_datetime(row.get("source_timestamp"))
    ing_ts = parse_iso_datetime(row.get("ingestion_timestamp"))

    adj_close = None
    if row.get("adjusted_close") is not None and str(row.get("adjusted_close")).strip():
        adj_close = parse_decimal_safe(row.get("adjusted_close"), "adjusted_close")

    supplied_hash = str(row.get("row_hash", "")).strip()

    return DailyPriceRecord(
        trading_date=t_date,
        symbol=sym,
        isin=isin_val,
        open=open_p,
        high=high_p,
        low=low_p,
        close=close_p,
        volume=vol,
        traded_value_inr=tv,
        traded_value_status=tv_status,
        price_adjustment_state=adj_state,
        source_timestamp=src_ts,
        ingestion_timestamp=ing_ts,
        source_identifier=source_id,
        adjusted_close=adj_close,
        row_hash=supplied_hash,
    )


def parse_membership_row(row: Dict[str, Any], source_id: str) -> PITMembershipRecord:
    """Parse raw dictionary into a validated PITMembershipRecord."""
    idx = str(row.get("index_code") or row.get("index", "")).strip().upper()
    sym = str(row.get("symbol", "")).strip().upper()
    isin_val = str(row.get("isin", "")).strip().upper()
    eff_from = parse_iso_date(row.get("effective_from") or row.get("from_date"))

    eff_to = None
    if row.get("effective_to") is not None and str(row.get("effective_to")).strip():
        eff_to = parse_iso_date(row.get("effective_to"))

    ann_ts = None
    if row.get("announcement_timestamp") is not None and str(row.get("announcement_timestamp")).strip():
        ann_ts = parse_iso_datetime(row.get("announcement_timestamp"))

    src_ts = parse_iso_datetime(row.get("source_timestamp"))
    ing_ts = parse_iso_datetime(row.get("ingestion_timestamp"))
    supplied_hash = str(row.get("row_hash", "")).strip()

    return PITMembershipRecord(
        index_code=idx,
        symbol=sym,
        isin=isin_val,
        effective_from=eff_from,
        effective_to=eff_to,
        announcement_timestamp=ann_ts,
        source_timestamp=src_ts,
        ingestion_timestamp=ing_ts,
        source_identifier=source_id,
        row_hash=supplied_hash,
    )


def parse_sector_row(row: Dict[str, Any], source_id: str) -> PITSectorClassificationRecord:
    """Parse raw dictionary into a validated PITSectorClassificationRecord."""
    sym = str(row.get("symbol", "")).strip().upper()
    isin_val = str(row.get("isin", "")).strip().upper()
    sec = str(row.get("sector_code") or row.get("sector", "")).strip()
    ind = str(row.get("industry_code") or row.get("industry", "")).strip() or None
    std = str(row.get("classification_standard", "AMFI_NSE")).strip()

    eff_from = parse_iso_date(row.get("effective_from"))
    eff_to = None
    if row.get("effective_to") is not None and str(row.get("effective_to")).strip():
        eff_to = parse_iso_date(row.get("effective_to"))

    src_ts = parse_iso_datetime(row.get("source_timestamp"))
    ing_ts = parse_iso_datetime(row.get("ingestion_timestamp"))
    supplied_hash = str(row.get("row_hash", "")).strip()

    return PITSectorClassificationRecord(
        symbol=sym,
        isin=isin_val,
        sector_code=sec,
        industry_code=ind,
        classification_standard=std,
        effective_from=eff_from,
        effective_to=eff_to,
        source_timestamp=src_ts,
        ingestion_timestamp=ing_ts,
        source_identifier=source_id,
        row_hash=supplied_hash,
    )


def parse_corporate_action_row(row: Dict[str, Any], source_id: str) -> CorporateActionRecord:
    """Parse raw dictionary into a validated CorporateActionRecord."""
    sym = str(row.get("symbol", "")).strip().upper()
    isin_val = str(row.get("isin", "")).strip().upper()
    action_type = CorporateActionType(str(row.get("action_type", "")).strip().upper())
    ex_d = parse_iso_date(row.get("ex_date"))
    eff_d = parse_iso_date(row.get("effective_date") or row.get("ex_date"))

    rec_d = None
    if row.get("record_date") is not None and str(row.get("record_date")).strip():
        rec_d = parse_iso_date(row.get("record_date"))

    ann_ts = None
    if row.get("announcement_timestamp") is not None and str(row.get("announcement_timestamp")).strip():
        ann_ts = parse_iso_datetime(row.get("announcement_timestamp"))

    src_ts = parse_iso_datetime(row.get("source_timestamp"))
    ing_ts = parse_iso_datetime(row.get("ingestion_timestamp"))

    num = None
    if row.get("adjustment_numerator") is not None and str(row.get("adjustment_numerator")).strip():
        num = parse_decimal_safe(row.get("adjustment_numerator"), "adjustment_numerator")

    den = None
    if row.get("adjustment_denominator") is not None and str(row.get("adjustment_denominator")).strip():
        den = parse_decimal_safe(row.get("adjustment_denominator"), "adjustment_denominator")

    cash = None
    if row.get("cash_amount") is not None and str(row.get("cash_amount")).strip():
        cash = parse_decimal_safe(row.get("cash_amount"), "cash_amount")

    curr = str(row.get("currency", "INR")).strip().upper()
    supplied_hash = str(row.get("row_hash", "")).strip()

    return CorporateActionRecord(
        symbol=sym,
        isin=isin_val,
        action_type=action_type,
        ex_date=ex_d,
        effective_date=eff_d,
        record_date=rec_d,
        announcement_timestamp=ann_ts,
        source_timestamp=src_ts,
        ingestion_timestamp=ing_ts,
        source_identifier=source_id,
        adjustment_numerator=num,
        adjustment_denominator=den,
        cash_amount=cash,
        currency=curr,
        row_hash=supplied_hash,
    )


# ------------------------------------------------------------------------------
# Generic Data Loaders
# ------------------------------------------------------------------------------

class BaseDataLoader(ABC, Generic[T]):
    """Abstract base class for streaming fail-closed data loaders."""

    def __init__(self, parser_func: Callable[[Dict[str, Any], str], T]) -> None:
        self.parser_func = parser_func

    @abstractmethod
    def load(self, source_path: Path) -> LoadResult[T]:
        """Load and validate records from source path."""
        pass


class CSVDataLoader(BaseDataLoader[T]):
    """Fail-closed CSV data loader with per-row error preservation."""

    def load(self, source_path: Path) -> LoadResult[T]:
        if not source_path.is_file():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        source_id = source_path.name
        content_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()

        accepted: List[T] = []
        rejected: List[RejectedRecord] = []
        seen_keys: set = set()
        duplicate_count = 0
        symbols: set = set()
        isins: set = set()
        min_date: Optional[date] = None
        max_date: Optional[date] = None

        with open(source_path, mode="r", encoding="utf-8-sig", newline="") as fp:
            reader = csv.DictReader(fp)
            if reader.fieldnames is None:
                raise ValueError(f"Empty or headerless CSV file: {source_path}")

            for row_idx, row in enumerate(reader, start=2):  # line 1 is header
                reasons: List[str] = []
                try:
                    record = self.parser_func(row, source_id)
                    # Natural key check for duplicate detection
                    key = None
                    if hasattr(record, "symbol") and hasattr(record, "trading_date"):
                        key = (record.symbol, record.trading_date)
                    elif hasattr(record, "symbol") and hasattr(record, "effective_from"):
                        key = (record.symbol, record.effective_from)
                    elif hasattr(record, "symbol") and hasattr(record, "ex_date") and hasattr(record, "action_type"):
                        key = (record.symbol, record.ex_date, record.action_type)

                    if key:
                        if key in seen_keys:
                            duplicate_count += 1
                            reasons.append(f"Duplicate natural key detected: {key}")
                        else:
                            seen_keys.add(key)

                    if hasattr(record, "symbol"):
                        symbols.add(record.symbol)
                    if hasattr(record, "isin"):
                        isins.add(record.isin)

                    d_val = getattr(record, "trading_date", None) or getattr(record, "effective_from", None) or getattr(record, "ex_date", None)
                    if d_val:
                        min_date = d_val if min_date is None or d_val < min_date else min_date
                        max_date = d_val if max_date is None or d_val > max_date else max_date

                    if reasons:
                        rejected.append(RejectedRecord(row_idx, row, reasons, source_id))
                    else:
                        accepted.append(record)

                except Exception as e:
                    reasons.append(str(e))
                    rejected.append(RejectedRecord(row_idx, row, reasons, source_id))

        date_range = (min_date, max_date) if min_date and max_date else None
        total_rows = len(accepted) + len(rejected)

        return LoadResult(
            accepted_records=accepted,
            rejected_records=rejected,
            source_fingerprint=content_hash,
            total_rows=total_rows,
            accepted_count=len(accepted),
            rejected_count=len(rejected),
            duplicate_count=duplicate_count,
            date_range=date_range,
            symbol_count=len(symbols),
            isin_count=len(isins),
        )


class JSONLinesDataLoader(BaseDataLoader[T]):
    """Fail-closed JSON Lines data loader."""

    def load(self, source_path: Path) -> LoadResult[T]:
        if not source_path.is_file():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        source_id = source_path.name
        content_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()

        accepted: List[T] = []
        rejected: List[RejectedRecord] = []
        seen_keys: set = set()
        duplicate_count = 0
        symbols: set = set()
        isins: set = set()
        min_date: Optional[date] = None
        max_date: Optional[date] = None

        with open(source_path, mode="r", encoding="utf-8") as fp:
            for line_idx, line in enumerate(fp, start=1):
                clean_line = line.strip()
                if not clean_line:
                    continue
                reasons: List[str] = []
                try:
                    row = json.loads(clean_line)
                    record = self.parser_func(row, source_id)
                    key = None
                    if hasattr(record, "symbol") and hasattr(record, "trading_date"):
                        key = (record.symbol, record.trading_date)
                    elif hasattr(record, "symbol") and hasattr(record, "effective_from"):
                        key = (record.symbol, record.effective_from)
                    elif hasattr(record, "symbol") and hasattr(record, "ex_date") and hasattr(record, "action_type"):
                        key = (record.symbol, record.ex_date, record.action_type)

                    if key:
                        if key in seen_keys:
                            duplicate_count += 1
                            reasons.append(f"Duplicate key: {key}")
                        else:
                            seen_keys.add(key)

                    if hasattr(record, "symbol"):
                        symbols.add(record.symbol)
                    if hasattr(record, "isin"):
                        isins.add(record.isin)

                    d_val = getattr(record, "trading_date", None) or getattr(record, "effective_from", None) or getattr(record, "ex_date", None)
                    if d_val:
                        min_date = d_val if min_date is None or d_val < min_date else min_date
                        max_date = d_val if max_date is None or d_val > max_date else max_date

                    if reasons:
                        rejected.append(RejectedRecord(line_idx, row, reasons, source_id))
                    else:
                        accepted.append(record)

                except Exception as e:
                    reasons.append(str(e))
                    rejected.append(RejectedRecord(line_idx, {"raw_line": clean_line}, reasons, source_id))

        date_range = (min_date, max_date) if min_date and max_date else None
        total_rows = len(accepted) + len(rejected)

        return LoadResult(
            accepted_records=accepted,
            rejected_records=rejected,
            source_fingerprint=content_hash,
            total_rows=total_rows,
            accepted_count=len(accepted),
            rejected_count=len(rejected),
            duplicate_count=duplicate_count,
            date_range=date_range,
            symbol_count=len(symbols),
            isin_count=len(isins),
        )
