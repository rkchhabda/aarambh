"""Phase 7 data acquisition contracts, dataclasses, and status enumerations.

Strictly governs schemas, natural keys, field statuses, and immutability invariants.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class FieldStatus(str, Enum):
    SOURCE_REPORTED = "SOURCE_REPORTED"
    DERIVED = "DERIVED"
    NOT_PROVIDED = "NOT_PROVIDED"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"


class AdjustmentState(str, Enum):
    UNADJUSTED = "UNADJUSTED"
    SPLIT_ADJUSTED = "SPLIT_ADJUSTED"
    DIVIDEND_ADJUSTED = "DIVIDEND_ADJUSTED"
    UNKNOWN = "UNKNOWN"


class ConstituentClassification(str, Enum):
    CURRENT_SNAPSHOT_ONLY = "CURRENT_SNAPSHOT_ONLY"
    HISTORICAL_MEMBERSHIP = "HISTORICAL_MEMBERSHIP"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"


class RequestStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    EMPTY = "EMPTY"


@dataclass(frozen=True)
class HistoricalEODRecord:
    trading_date: str
    symbol: str
    isin: Optional[str]
    exchange_series: str
    previous_close: Optional[float]
    open: float
    high: float
    low: float
    close: float
    last_price: Optional[float]
    vwap: Optional[float]
    total_traded_quantity: int
    total_traded_value_inr: Optional[float]
    number_of_trades: Optional[int]
    deliverable_quantity: Optional[int]
    delivery_percentage: Optional[float]
    trading_status: str
    adjustment_state: AdjustmentState
    traded_value_status: FieldStatus
    source_timestamp: str
    ingestion_timestamp: str
    source_identifier: str
    row_hash: str


@dataclass(frozen=True)
class ConstituentRecord:
    symbol: str
    security_name: str
    isin: Optional[str]
    index_name: str
    classification: ConstituentClassification
    source_timestamp: str
    ingestion_timestamp: str
    source_identifier: str
    row_hash: str


@dataclass(frozen=True)
class CorporateActionRecord:
    symbol: str
    isin: Optional[str]
    action_type: str
    announcement_timestamp: Optional[str]
    ex_date: str
    record_date: Optional[str]
    effective_date: Optional[str]
    ratio_numerator: Optional[float]
    ratio_denominator: Optional[float]
    cash_amount: Optional[float]
    currency: str
    status: str
    source_identifier: str
    ingestion_timestamp: str
    row_hash: str


@dataclass(frozen=True)
class RejectedSymbolRecord:
    symbol: str
    reason: str
    timestamp: str
    requested_range: Optional[str] = None


@dataclass(frozen=True)
class RejectedRowRecord:
    symbol: str
    raw_payload: Dict[str, Any]
    reason: str
    timestamp: str


@dataclass(frozen=True)
class RequestManifest:
    request_id: str
    symbol: str
    start_date: str
    end_date: str
    interval: str
    retrieval_timestamp: str
    client_version: str
    source_identifier: str
    status: RequestStatus
    row_count: int
    raw_checksum: str
    normalized_checksum: str
    failure_reason: Optional[str] = None
    retry_count: int = 0
    is_partial: bool = False
