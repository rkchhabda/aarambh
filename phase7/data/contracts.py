"""Canonical data contracts and deterministic row hashing for Phase 7.

Implements strict immutable data records for:
1. Daily price and liquidity history (Decimal-safe).
2. Point-in-time constituent membership (half-open intervals).
3. Point-in-time sector classification (temporal intervals).
4. Corporate actions (splits, bonuses, cash dividends, complex actions).
5. Point-in-time financial statements (publication-timestamp bound).
6. Shareholding and promoter pledging.
7. Corporate announcements.
8. Eligibility and suspension records.

All records enforce UTC timezone-awareness, non-coercive type validation,
and deterministic SHA-256 row hashing.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
import hashlib
import json
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, Union


# ------------------------------------------------------------------------------
# Enums
# ------------------------------------------------------------------------------

class TradedValueStatus(str, Enum):
    """Provenance and derivation status of daily traded value (turnover)."""
    EXCHANGE_REPORTED = "EXCHANGE_REPORTED"
    DERIVED_FROM_PRICE_VOLUME = "DERIVED_FROM_PRICE_VOLUME"
    MISSING = "MISSING"
    INVALID = "INVALID"


class PriceAdjustmentState(str, Enum):
    """Adjustment state of incoming price series."""
    RAW = "RAW"
    SPLIT_ADJUSTED = "SPLIT_ADJUSTED"
    TOTAL_RETURN_ADJUSTED = "TOTAL_RETURN_ADJUSTED"
    UNKNOWN = "UNKNOWN"


class CorporateActionType(str, Enum):
    """Supported canonical corporate action categories."""
    SPLIT = "SPLIT"
    BONUS = "BONUS"
    CASH_DIVIDEND = "CASH_DIVIDEND"
    RIGHTS = "RIGHTS"
    MERGER = "MERGER"
    DEMERGER = "DEMERGER"
    SYMBOL_CHANGE = "SYMBOL_CHANGE"
    DELISTING = "DELISTING"


CORPORATE_ACTION_SOURCE_ALIASES: Dict[str, CorporateActionType] = {
    "SPLIT": CorporateActionType.SPLIT,
    "STOCK_SPLIT": CorporateActionType.SPLIT,
    "SUB_DIVISION": CorporateActionType.SPLIT,
    "FACE_VALUE_SPLIT": CorporateActionType.SPLIT,
    "BONUS": CorporateActionType.BONUS,
    "BONUS_ISSUE": CorporateActionType.BONUS,
    "CASH_DIVIDEND": CorporateActionType.CASH_DIVIDEND,
    "DIVIDEND": CorporateActionType.CASH_DIVIDEND,
    "SPECIAL_DIVIDEND": CorporateActionType.CASH_DIVIDEND,
    "INTERIM_DIVIDEND": CorporateActionType.CASH_DIVIDEND,
    "FINAL_DIVIDEND": CorporateActionType.CASH_DIVIDEND,
    "RIGHTS": CorporateActionType.RIGHTS,
    "RIGHTS_ISSUE": CorporateActionType.RIGHTS,
    "MERGER": CorporateActionType.MERGER,
    "AMALGAMATION": CorporateActionType.MERGER,
    "DEMERGER": CorporateActionType.DEMERGER,
    "SPINOFF": CorporateActionType.DEMERGER,
    "SPIN_OFF": CorporateActionType.DEMERGER,
    "SYMBOL_CHANGE": CorporateActionType.SYMBOL_CHANGE,
    "NAME_CHANGE": CorporateActionType.SYMBOL_CHANGE,
    "TICKER_CHANGE": CorporateActionType.SYMBOL_CHANGE,
    "DELISTING": CorporateActionType.DELISTING,
    "SUSPENSION_DELISTING": CorporateActionType.DELISTING,
}


class CorporateActionResolution(str, Enum):
    """Resolution status for corporate action handling."""
    APPLIED = "APPLIED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    UNSUPPORTED_ACTION = "UNSUPPORTED_ACTION"
    CONFLICTING_ACTIONS = "CONFLICTING_ACTIONS"
    INVALID_ACTION = "INVALID_ACTION"


def canonicalize_corporate_action_type(
    action_type: Union[str, CorporateActionType]
) -> Tuple[Optional[CorporateActionType], CorporateActionResolution, str]:
    """Canonicalize a raw corporate action string or enum into a canonical CorporateActionType.

    Returns:
        (canonical_type, resolution, reason_note)
        If the type is unknown or ambiguous, canonical_type is None and resolution is MANUAL_REVIEW.
    """
    if isinstance(action_type, CorporateActionType):
        raw_str = action_type.value
    elif isinstance(action_type, str):
        raw_str = action_type.strip().upper()
    else:
        return (None, CorporateActionResolution.INVALID_ACTION, f"Invalid action_type object: {type(action_type)}")

    if raw_str in CORPORATE_ACTION_SOURCE_ALIASES:
        canon = CORPORATE_ACTION_SOURCE_ALIASES[raw_str]
        return (canon, CorporateActionResolution.APPLIED, f"Canonicalized from '{raw_str}' to '{canon.value}'")

    return (
        None,
        CorporateActionResolution.MANUAL_REVIEW,
        f"Unknown or ambiguous corporate action type '{raw_str}'; routed to MANUAL_REVIEW.",
    )


class EligibilityStatus(str, Enum):
    """Point-in-time trading eligibility or suspension state."""
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    PROLONGED_NON_TRADING = "PROLONGED_NON_TRADING"
    RESTRICTED = "RESTRICTED"
    UNKNOWN = "UNKNOWN"


class ExclusionReason(str, Enum):
    """Deterministic exclusion reason codes for Phase 7 universe construction."""
    NOT_IN_PIT_UNIVERSE = "NOT_IN_PIT_UNIVERSE"
    MISSING_MEMBERSHIP_HISTORY = "MISSING_MEMBERSHIP_HISTORY"
    MISSING_ISIN = "MISSING_ISIN"
    BELOW_MIN_PRICE = "BELOW_MIN_PRICE"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    MISSING_PRICE_HISTORY = "MISSING_PRICE_HISTORY"
    MISSING_LIQUIDITY_HISTORY = "MISSING_LIQUIDITY_HISTORY"
    BELOW_MIN_LIQUIDITY = "BELOW_MIN_LIQUIDITY"
    MISSING_SECTOR_CLASSIFICATION = "MISSING_SECTOR_CLASSIFICATION"
    CONFLICTING_SECTOR_CLASSIFICATION = "CONFLICTING_SECTOR_CLASSIFICATION"
    SUSPENDED = "SUSPENDED"
    PROLONGED_NON_TRADING = "PROLONGED_NON_TRADING"
    RESTRICTED_SECURITY = "RESTRICTED_SECURITY"
    INVALID_CORPORATE_ACTION_HISTORY = "INVALID_CORPORATE_ACTION_HISTORY"
    UNKNOWN_POINT_IN_TIME_STATUS = "UNKNOWN_POINT_IN_TIME_STATUS"
    DUPLICATE_SECURITY_RECORD = "DUPLICATE_SECURITY_RECORD"
    FUTURE_DATA_DETECTED = "FUTURE_DATA_DETECTED"
    DATA_VALIDATION_FAILURE = "DATA_VALIDATION_FAILURE"
    REAL_DATA_BLOCKED = "REAL_DATA_BLOCKED"
    CIRCUIT_FILTER_LOCKED = "CIRCUIT_FILTER_LOCKED"
    # Documented compatibility aliases
    BELOW_TURNOVER_THRESHOLD = "BELOW_MIN_LIQUIDITY"
    BELOW_PRICE_THRESHOLD = "BELOW_MIN_PRICE"
    TRADING_SUSPENDED = "SUSPENDED"
    MISSING_PRICE_DATA = "MISSING_PRICE_HISTORY"
    UNVERIFIED_CORPORATE_ACTION = "INVALID_CORPORATE_ACTION_HISTORY"


# ------------------------------------------------------------------------------
# Deterministic Hashing Utilities
# ------------------------------------------------------------------------------

ISIN_REGEX = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def _canonicalize_value(val: Any) -> Any:
    """Recursively canonicalize field values for deterministic hashing."""
    if val is None:
        return None
    if isinstance(val, (int, bool)):
        return val
    if isinstance(val, Decimal):
        # Format without scientific notation, trim trailing zeros after decimal point
        val_norm = val.normalize()
        sign, digits, exponent = val_norm.as_tuple()
        if exponent >= 0:
            return f"{val_norm:f}"
        s = f"{val_norm:f}"
        return s.rstrip("0").rstrip(".") if "." in s else s
    if isinstance(val, float):
        raise TypeError("Binary float is prohibited in canonical hashing; use Decimal or int.")
    if isinstance(val, Enum):
        return val.value
    if isinstance(val, date) and not isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, datetime):
        if val.tzinfo is None:
            raise ValueError(f"Cannot canonicalize timezone-naive datetime: {val}")
        val_utc = val.astimezone(timezone.utc)
        return val_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(val, Mapping):
        return {str(k): _canonicalize_value(v) for k, v in sorted(val.items())}
    if isinstance(val, (list, tuple)):
        return [_canonicalize_value(item) for item in val]
    return str(val).strip()


def compute_row_hash(data: Mapping[str, Any]) -> str:
    """Compute a deterministic SHA-256 hash for a structured data dictionary.

    The row_hash field itself is strictly excluded from input calculation.
    Symbols and ISINs are normalized to uppercase.
    All timezone-aware datetimes are converted to UTC ISO 8601 strings.
    Decimals are formatted without exponent ambiguity.
    """
    clean_dict: Dict[str, Any] = {}
    for k, v in sorted(data.items()):
        if k == "row_hash":
            continue
        canon_val = _canonicalize_value(v)
        if k.lower() in ("symbol", "isin") and isinstance(canon_val, str):
            canon_val = canon_val.upper()
        clean_dict[k] = canon_val

    serialized = json.dumps(clean_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------
# Data Records (Frozen Dataclasses)
# ------------------------------------------------------------------------------

@dataclass(frozen=True)
class DailyPriceRecord:
    """Canonical daily price and liquidity record for a single equity session."""
    trading_date: date
    symbol: str
    isin: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    traded_value_inr: Decimal
    traded_value_status: TradedValueStatus
    price_adjustment_state: PriceAdjustmentState
    source_timestamp: datetime
    ingestion_timestamp: datetime
    source_identifier: str
    adjusted_close: Optional[Decimal] = None
    traded_value_derivation_method: Optional[str] = None
    row_hash: str = ""

    def __post_init__(self) -> None:
        # Field normalization via object.__setattr__
        sym = self.symbol.strip().upper()
        isin_val = self.isin.strip().upper()
        if not sym:
            raise ValueError("Symbol must not be empty.")
        if not isin_val or not ISIN_REGEX.match(isin_val):
            raise ValueError(f"Invalid ISIN format: '{self.isin}'")
        object.__setattr__(self, "symbol", sym)
        object.__setattr__(self, "isin", isin_val)

        # Price sanity validations
        if self.open <= Decimal("0"):
            raise ValueError(f"Open price must be positive, got {self.open}")
        if self.high <= Decimal("0"):
            raise ValueError(f"High price must be positive, got {self.high}")
        if self.low <= Decimal("0"):
            raise ValueError(f"Low price must be positive, got {self.low}")
        if self.close <= Decimal("0"):
            raise ValueError(f"Close price must be positive, got {self.close}")
        if self.adjusted_close is not None and self.adjusted_close <= Decimal("0"):
            raise ValueError(f"Adjusted close must be positive, got {self.adjusted_close}")

        # OHLC logical inequalities
        if self.high < self.open or self.high < self.close or self.high < self.low:
            raise ValueError(f"High ({self.high}) cannot be lower than Open ({self.open}), Close ({self.close}), or Low ({self.low})")
        if self.low > self.open or self.low > self.close or self.low > self.high:
            raise ValueError(f"Low ({self.low}) cannot be higher than Open ({self.open}), Close ({self.close}), or High ({self.high})")

        # Volume and turnover checks
        if self.volume < 0:
            raise ValueError(f"Volume cannot be negative: {self.volume}")
        if self.traded_value_inr < Decimal("0"):
            raise ValueError(f"Traded value cannot be negative: {self.traded_value_inr}")

        # Traded value status and derivation method rules
        if self.traded_value_status == TradedValueStatus.EXCHANGE_REPORTED:
            if self.traded_value_derivation_method is not None and self.traded_value_derivation_method.strip() not in ("", "EXCHANGE_OFFICIAL"):
                raise ValueError("EXCHANGE_REPORTED traded value cannot have a derivation method.")
        elif self.traded_value_status == TradedValueStatus.DERIVED_FROM_PRICE_VOLUME:
            if not self.traded_value_derivation_method or not self.traded_value_derivation_method.strip():
                raise ValueError("DERIVED_FROM_PRICE_VOLUME traded value requires a recorded derivation method.")
            method_clean = self.traded_value_derivation_method.strip().upper()
            if method_clean in ("CLOSE_X_VOLUME", "CLOSE_VOLUME", "CLOSE_ONLY"):
                raise ValueError("Deriving traded value from Close alone is strictly prohibited.")
        elif self.traded_value_status in (TradedValueStatus.MISSING, TradedValueStatus.INVALID):
            if self.traded_value_inr > Decimal("0"):
                raise ValueError(f"Traded value must be zero when status is {self.traded_value_status.value}")

        # Timestamps
        if self.source_timestamp.tzinfo is None:
            raise ValueError(f"source_timestamp must be timezone-aware: {self.source_timestamp}")
        if self.ingestion_timestamp.tzinfo is None:
            raise ValueError(f"ingestion_timestamp must be timezone-aware: {self.ingestion_timestamp}")

        # Hash computation / verification
        computed = compute_row_hash(self.__dict__)
        if self.row_hash and self.row_hash != computed:
            raise ValueError(f"Supplied row_hash '{self.row_hash}' does not match computed hash '{computed}'")
        if not self.row_hash:
            object.__setattr__(self, "row_hash", computed)


@dataclass(frozen=True)
class PITMembershipRecord:
    """Point-in-Time index constituent membership interval.

    Convention: Half-open interval [effective_from, effective_to).
    If effective_to is None, membership is open-ended.
    """
    index_code: str
    symbol: str
    isin: str
    effective_from: date
    source_timestamp: datetime
    ingestion_timestamp: datetime
    source_identifier: str
    effective_to: Optional[date] = None
    announcement_timestamp: Optional[datetime] = None
    row_hash: str = ""

    def __post_init__(self) -> None:
        sym = self.symbol.strip().upper()
        isin_val = self.isin.strip().upper()
        idx = self.index_code.strip().upper()
        if not sym:
            raise ValueError("Symbol must not be empty.")
        if not isin_val or not ISIN_REGEX.match(isin_val):
            raise ValueError(f"Invalid ISIN: '{self.isin}'")
        if not idx:
            raise ValueError("Index code must not be empty.")
        object.__setattr__(self, "symbol", sym)
        object.__setattr__(self, "isin", isin_val)
        object.__setattr__(self, "index_code", idx)

        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError(
                f"effective_to ({self.effective_to}) must be strictly later than effective_from ({self.effective_from})"
            )

        if self.source_timestamp.tzinfo is None:
            raise ValueError("source_timestamp must be timezone-aware")
        if self.ingestion_timestamp.tzinfo is None:
            raise ValueError("ingestion_timestamp must be timezone-aware")
        if self.announcement_timestamp and self.announcement_timestamp.tzinfo is None:
            raise ValueError("announcement_timestamp must be timezone-aware")

        computed = compute_row_hash(self.__dict__)
        if self.row_hash and self.row_hash != computed:
            raise ValueError(f"Supplied row_hash mismatch: '{self.row_hash}' != '{computed}'")
        if not self.row_hash:
            object.__setattr__(self, "row_hash", computed)

    def is_active_on(self, d: date) -> bool:
        """Check if security is an active constituent on date d under [from, to) interval."""
        if d < self.effective_from:
            return False
        if self.effective_to is not None and d >= self.effective_to:
            return False
        return True

    def is_active_as_of(self, prediction_timestamp: datetime) -> bool:
        """Check if security is active as of prediction_timestamp.

        Enforces:
        1. source_timestamp <= prediction_timestamp (no lookahead / future leaks).
        2. effective_from <= prediction_timestamp.date() < (effective_to or max_date) (half-open interval).
        """
        if prediction_timestamp.tzinfo is None:
            raise ValueError("prediction_timestamp must be timezone-aware (UTC)")
        pred_utc = prediction_timestamp.astimezone(timezone.utc)
        if self.source_timestamp > pred_utc:
            return False
        return self.is_active_on(pred_utc.date())


@dataclass(frozen=True)
class PITMembershipEventRecord:
    """Raw index constituent change event (ADD or REMOVE)."""
    index_code: str
    symbol: str
    isin: str
    effective_date: date
    action: str  # "ADD" or "REMOVE"
    source_timestamp: datetime
    ingestion_timestamp: datetime
    source_identifier: str
    circular_number: Optional[str] = None
    row_hash: str = ""

    def __post_init__(self) -> None:
        sym = self.symbol.strip().upper()
        isin_val = self.isin.strip().upper()
        idx = self.index_code.strip().upper()
        act = self.action.strip().upper()
        if not sym:
            raise ValueError("symbol cannot be empty")
        if not isin_val or not ISIN_REGEX.match(isin_val):
            raise ValueError(f"Invalid ISIN: '{self.isin}'")
        if not idx:
            raise ValueError("index_code cannot be empty")
        if act not in ("ADD", "REMOVE"):
            raise ValueError(f"action must be 'ADD' or 'REMOVE', got '{self.action}'")
        object.__setattr__(self, "symbol", sym)
        object.__setattr__(self, "isin", isin_val)
        object.__setattr__(self, "index_code", idx)
        object.__setattr__(self, "action", act)
        if self.source_timestamp.tzinfo is None or self.ingestion_timestamp.tzinfo is None:
            raise ValueError("source_timestamp and ingestion_timestamp must be timezone-aware (UTC)")
        computed = compute_row_hash(self.__dict__)
        if self.row_hash and self.row_hash != computed:
            raise ValueError(f"Supplied row_hash mismatch: '{self.row_hash}' != '{computed}'")
        if not self.row_hash:
            object.__setattr__(self, "row_hash", computed)


def convert_membership_events_to_intervals(
    events: Sequence[PITMembershipEventRecord],
    prediction_timestamp: Optional[datetime] = None,
) -> Tuple[List[PITMembershipRecord], List[str]]:
    """Convert raw constituent ADD and REMOVE events into non-overlapping half-open intervals [from, to).

    Enforces strict point-in-time constraints:
    1. Unknown initial membership fails closed (securities without a prior ADD event are ignored/excluded).
    2. Removal without prior addition produces an error log and fails closed.
    3. Duplicate addition while already active produces an error log and fails closed.
    4. Duplicate removal while inactive produces an error log and fails closed.
    5. Conflicting same-day ADD and REMOVE events fail closed.
    6. Overlapping intervals for the same security are detected and rejected.
    7. If prediction_timestamp is provided:
       - Events with source_timestamp > prediction_timestamp are excluded from conversion.
    8. Normal add then remove produces [effective_from, effective_to).
    9. Open-ended addition produces [effective_from, None).
    10. Re-addition after removal produces separate non-overlapping intervals.

    Returns:
        (validated_intervals, error_log)
    """
    pred_utc: Optional[datetime] = None
    if prediction_timestamp is not None:
        if prediction_timestamp.tzinfo is None:
            raise ValueError("prediction_timestamp must be timezone-aware (UTC)")
        pred_utc = prediction_timestamp.astimezone(timezone.utc)

    # Filter out events with future source timestamps relative to prediction_timestamp
    eligible_events: List[PITMembershipEventRecord] = []
    errors: List[str] = []

    for ev in events:
        if pred_utc is not None and ev.source_timestamp > pred_utc:
            errors.append(
                f"Future source timestamp ignored for {ev.symbol} on {ev.effective_date}: "
                f"{ev.source_timestamp.isoformat()} > {pred_utc.isoformat()}"
            )
            continue
        eligible_events.append(ev)

    # Group by (index_code, symbol)
    by_symbol: Dict[Tuple[str, str], List[PITMembershipEventRecord]] = defaultdict(list)
    for ev in eligible_events:
        by_symbol[(ev.index_code, ev.symbol)].append(ev)

    intervals: List[PITMembershipRecord] = []

    for (idx_code, symbol), sym_events in sorted(by_symbol.items()):
        # Check for same-date conflicting events (both ADD and REMOVE on same effective_date)
        date_actions: Dict[date, Set[str]] = defaultdict(set)
        for e in sym_events:
            date_actions[e.effective_date].add(e.action)
        conflicts = [d for d, acts in sorted(date_actions.items()) if len(acts) > 1]
        if conflicts:
            errors.append(
                f"Conflicting same-day events for {symbol} on dates {conflicts}; security fails closed."
            )
            continue

        # Sort events deterministically: effective_date ascending, then source_timestamp ascending,
        # then action (ADD before REMOVE if same date, though conflict check caught it), then row_hash
        sorted_evs = sorted(
            sym_events,
            key=lambda e: (e.effective_date, e.source_timestamp, 0 if e.action == "ADD" else 1, e.row_hash),
        )

        active_start: Optional[date] = None
        active_ev: Optional[PITMembershipEventRecord] = None
        sym_has_error = False

        for e in sorted_evs:
            if e.action == "ADD":
                if active_start is not None:
                    errors.append(
                        f"Duplicate addition for {symbol} on {e.effective_date} while already active since {active_start}."
                    )
                    sym_has_error = True
                    break
                active_start = e.effective_date
                active_ev = e
            elif e.action == "REMOVE":
                if active_start is None:
                    errors.append(
                        f"Removal without prior addition for {symbol} on {e.effective_date}."
                    )
                    sym_has_error = True
                    break
                if e.effective_date <= active_start:
                    errors.append(
                        f"Removal date {e.effective_date} <= addition date {active_start} for {symbol}."
                    )
                    sym_has_error = True
                    break

                intervals.append(
                    PITMembershipRecord(
                        index_code=active_ev.index_code,
                        symbol=symbol,
                        isin=active_ev.isin,
                        effective_from=active_start,
                        effective_to=e.effective_date,
                        source_timestamp=max(active_ev.source_timestamp, e.source_timestamp),
                        ingestion_timestamp=max(active_ev.ingestion_timestamp, e.ingestion_timestamp),
                        source_identifier=f"{active_ev.source_identifier}->{e.source_identifier}",
                    )
                )
                active_start = None
                active_ev = None

        if sym_has_error:
            continue

        # Open-ended addition remaining
        if active_start is not None and active_ev is not None:
            intervals.append(
                PITMembershipRecord(
                    index_code=active_ev.index_code,
                    symbol=symbol,
                    isin=active_ev.isin,
                    effective_from=active_start,
                    effective_to=None,
                    source_timestamp=active_ev.source_timestamp,
                    ingestion_timestamp=active_ev.ingestion_timestamp,
                    source_identifier=active_ev.source_identifier,
                )
            )

    # Final validation: assert no intervals for same security overlap
    created_by_sym: Dict[Tuple[str, str], List[PITMembershipRecord]] = defaultdict(list)
    for iv in intervals:
        created_by_sym[(iv.index_code, iv.symbol)].append(iv)

    validated_intervals: List[PITMembershipRecord] = []
    for (idx_code, symbol), iv_list in sorted(created_by_sym.items()):
        sorted_ivs = sorted(iv_list, key=lambda x: x.effective_from)
        overlap = False
        for i in range(len(sorted_ivs) - 1):
            curr_to = sorted_ivs[i].effective_to
            next_from = sorted_ivs[i + 1].effective_from
            if curr_to is None or curr_to > next_from:
                errors.append(f"Overlapping intervals detected for {symbol}: {sorted_ivs[i]} and {sorted_ivs[i+1]}")
                overlap = True
                break
        if not overlap:
            validated_intervals.extend(sorted_ivs)

    return sorted(validated_intervals, key=lambda x: (x.symbol, x.effective_from)), errors


@dataclass(frozen=True)
class PITSectorClassificationRecord:
    """Point-in-Time sector and industry classification record.

    Convention: Half-open interval [effective_from, effective_to).
    """
    symbol: str
    isin: str
    sector_code: str
    effective_from: date
    source_timestamp: datetime
    ingestion_timestamp: datetime
    source_identifier: str
    industry_code: Optional[str] = None
    classification_standard: Optional[str] = "AMFI_NSE"
    effective_to: Optional[date] = None
    row_hash: str = ""

    def __post_init__(self) -> None:
        sym = self.symbol.strip().upper()
        isin_val = self.isin.strip().upper()
        sec = self.sector_code.strip()
        if not sym or not isin_val or not sec:
            raise ValueError("symbol, isin, and sector_code cannot be empty")
        if not ISIN_REGEX.match(isin_val):
            raise ValueError(f"Invalid ISIN: '{self.isin}'")
        object.__setattr__(self, "symbol", sym)
        object.__setattr__(self, "isin", isin_val)
        object.__setattr__(self, "sector_code", sec)

        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError(f"effective_to ({self.effective_to}) must be later than effective_from ({self.effective_from})")

        if self.source_timestamp.tzinfo is None or self.ingestion_timestamp.tzinfo is None:
            raise ValueError("Timestamps must be timezone-aware")

        computed = compute_row_hash(self.__dict__)
        if self.row_hash and self.row_hash != computed:
            raise ValueError(f"Supplied row_hash mismatch: '{self.row_hash}' != '{computed}'")
        if not self.row_hash:
            object.__setattr__(self, "row_hash", computed)

    def is_active_on(self, d: date) -> bool:
        """Check if classification is active on date d under [from, to) interval."""
        if d < self.effective_from:
            return False
        if self.effective_to is not None and d >= self.effective_to:
            return False
        return True

    def is_active_as_of(self, prediction_timestamp: datetime) -> bool:
        """Check if classification is active as of prediction_timestamp.

        Enforces:
        1. source_timestamp <= prediction_timestamp (no lookahead / future leaks).
        2. effective_from <= prediction_timestamp.date() < (effective_to or max_date) (half-open interval).
        """
        if prediction_timestamp.tzinfo is None:
            raise ValueError("prediction_timestamp must be timezone-aware (UTC)")
        pred_utc = prediction_timestamp.astimezone(timezone.utc)
        if self.source_timestamp > pred_utc:
            return False
        return self.is_active_on(pred_utc.date())


@dataclass(frozen=True)
class CorporateActionRecord:
    """Normalized corporate action disclosure record."""
    symbol: str
    isin: str
    action_type: CorporateActionType
    ex_date: date
    effective_date: date
    source_timestamp: datetime
    ingestion_timestamp: datetime
    source_identifier: str
    record_date: Optional[date] = None
    announcement_timestamp: Optional[datetime] = None
    adjustment_numerator: Optional[Decimal] = None
    adjustment_denominator: Optional[Decimal] = None
    cash_amount: Optional[Decimal] = None
    currency: str = "INR"
    row_hash: str = ""

    def __post_init__(self) -> None:
        sym = self.symbol.strip().upper()
        isin_val = self.isin.strip().upper()
        if not sym:
            raise ValueError("Symbol must not be empty.")
        if not isin_val or not ISIN_REGEX.match(isin_val):
            raise ValueError(f"Invalid ISIN: '{self.isin}'")
        object.__setattr__(self, "symbol", sym)
        object.__setattr__(self, "isin", isin_val)

        # Validation per action type
        canon_type, _, _ = canonicalize_corporate_action_type(self.action_type)
        if canon_type in (CorporateActionType.SPLIT, CorporateActionType.BONUS):
            if self.adjustment_numerator is None or self.adjustment_denominator is None:
                raise ValueError(f"{self.action_type} requires adjustment_numerator and adjustment_denominator.")
            if self.adjustment_numerator <= Decimal("0") or self.adjustment_denominator <= Decimal("0"):
                raise ValueError(f"Adjustment ratios must be positive, got {self.adjustment_numerator}:{self.adjustment_denominator}")

        if canon_type == CorporateActionType.CASH_DIVIDEND:
            if self.cash_amount is None or self.cash_amount <= Decimal("0"):
                raise ValueError(f"Cash dividend requires positive cash_amount, got {self.cash_amount}")

        if self.source_timestamp.tzinfo is None or self.ingestion_timestamp.tzinfo is None:
            raise ValueError("Timestamps must be timezone-aware")

        computed = compute_row_hash(self.__dict__)
        if self.row_hash and self.row_hash != computed:
            raise ValueError(f"Supplied row_hash mismatch: '{self.row_hash}' != '{computed}'")
        if not self.row_hash:
            object.__setattr__(self, "row_hash", computed)


@dataclass(frozen=True)
class EligibilitySuspensionRecord:
    """Point-in-Time trading eligibility, restriction, or suspension record."""
    symbol: str
    isin: str
    status: EligibilityStatus
    effective_from: date
    source_timestamp: datetime
    ingestion_timestamp: datetime
    source_identifier: str
    effective_to: Optional[date] = None
    row_hash: str = ""

    def __post_init__(self) -> None:
        sym = self.symbol.strip().upper()
        isin_val = self.isin.strip().upper()
        if not sym or not isin_val:
            raise ValueError("Symbol and ISIN must not be empty.")
        if not ISIN_REGEX.match(isin_val):
            raise ValueError(f"Invalid ISIN: '{self.isin}'")
        object.__setattr__(self, "symbol", sym)
        object.__setattr__(self, "isin", isin_val)

        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be later than effective_from")

        if self.source_timestamp.tzinfo is None or self.ingestion_timestamp.tzinfo is None:
            raise ValueError("Timestamps must be timezone-aware")

        computed = compute_row_hash(self.__dict__)
        if self.row_hash and self.row_hash != computed:
            raise ValueError(f"Supplied row_hash mismatch: '{self.row_hash}' != '{computed}'")
        if not self.row_hash:
            object.__setattr__(self, "row_hash", computed)

    def is_active_on(self, d: date) -> bool:
        if d < self.effective_from:
            return False
        if self.effective_to is not None and d >= self.effective_to:
            return False
        return True


# ------------------------------------------------------------------------------
# Interface-Only Records (Gated on Future Real PIT Feeds)
# ------------------------------------------------------------------------------

@dataclass(frozen=True)
class PITFinancialStatementRecord:
    """Point-in-Time financial statement disclosure metadata interface."""
    symbol: str
    isin: str
    period_end_date: date
    exchange_publication_timestamp: datetime
    statement_type: str
    reporting_basis: str
    source_identifier: str
    ingestion_timestamp: datetime
    period_start_date: Optional[date] = None
    filing_timestamp: Optional[datetime] = None
    first_seen_timestamp: Optional[datetime] = None
    currency: str = "INR"
    line_items: Mapping[str, Decimal] = field(default_factory=dict)
    row_hash: str = ""

    def __post_init__(self) -> None:
        sym = self.symbol.strip().upper()
        isin_val = self.isin.strip().upper()
        object.__setattr__(self, "symbol", sym)
        object.__setattr__(self, "isin", isin_val)
        if self.exchange_publication_timestamp.tzinfo is None:
            raise ValueError("exchange_publication_timestamp must be timezone-aware")
        computed = compute_row_hash(self.__dict__)
        if not self.row_hash:
            object.__setattr__(self, "row_hash", computed)


@dataclass(frozen=True)
class PITShareholdingRecord:
    """Point-in-Time shareholding pattern and promoter pledge interface."""
    symbol: str
    isin: str
    reporting_period_end: date
    publication_timestamp: datetime
    source_identifier: str
    ingestion_timestamp: datetime
    first_seen_timestamp: Optional[datetime] = None
    promoter_holding_percent: Optional[Decimal] = None
    pledged_promoter_holding_percent: Optional[Decimal] = None
    row_hash: str = ""

    def __post_init__(self) -> None:
        sym = self.symbol.strip().upper()
        isin_val = self.isin.strip().upper()
        object.__setattr__(self, "symbol", sym)
        object.__setattr__(self, "isin", isin_val)
        if self.publication_timestamp.tzinfo is None:
            raise ValueError("publication_timestamp must be timezone-aware")
        computed = compute_row_hash(self.__dict__)
        if not self.row_hash:
            object.__setattr__(self, "row_hash", computed)


@dataclass(frozen=True)
class PITCorporateAnnouncementRecord:
    """Point-in-Time corporate announcement dissemination interface."""
    symbol: str
    isin: str
    exchange_dissemination_timestamp: datetime
    category: str
    source_identifier: str
    source_document_identifier: str
    source_document_hash: str
    ingestion_timestamp: datetime
    event_timestamp: Optional[datetime] = None
    first_seen_timestamp: Optional[datetime] = None
    row_hash: str = ""

    def __post_init__(self) -> None:
        sym = self.symbol.strip().upper()
        isin_val = self.isin.strip().upper()
        object.__setattr__(self, "symbol", sym)
        object.__setattr__(self, "isin", isin_val)
        if self.exchange_dissemination_timestamp.tzinfo is None:
            raise ValueError("exchange_dissemination_timestamp must be timezone-aware")
        computed = compute_row_hash(self.__dict__)
        if not self.row_hash:
            object.__setattr__(self, "row_hash", computed)
