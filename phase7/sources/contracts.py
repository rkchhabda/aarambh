"""Phase 7 data acquisition contracts, dataclasses, and status enumerations.

Strictly governs schemas, natural keys, field statuses, and immutability invariants.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


class CapabilityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    PARTIAL = "PARTIAL"
    UNVERIFIED = "UNVERIFIED"
    UNSAFE = "UNSAFE"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


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
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    EMPTY = "EMPTY"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"
    HALTED = "HALTED"


class PilotStopReason(str, Enum):
    CONNECTION_ERROR = "CONNECTION_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    HTML_PAYLOAD_REJECTED = "HTML_PAYLOAD_REJECTED"
    CAPTCHA_DETECTED = "CAPTCHA_DETECTED"
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    UNEXPECTED_RESPONSE_TYPE = "UNEXPECTED_RESPONSE_TYPE"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    OUT_OF_RANGE_DATE = "OUT_OF_RANGE_DATE"
    SYMBOL_IDENTITY_CONFLICT = "SYMBOL_IDENTITY_CONFLICT"
    INVALID_OHLC = "INVALID_OHLC"
    NEGATIVE_VALUE = "NEGATIVE_VALUE"
    DUPLICATE_NATURAL_KEY = "DUPLICATE_NATURAL_KEY"
    RAW_PERSISTENCE_FAILURE = "RAW_PERSISTENCE_FAILURE"
    NORMALIZED_PERSISTENCE_FAILURE = "NORMALIZED_PERSISTENCE_FAILURE"
    MANIFEST_FAILURE = "MANIFEST_FAILURE"
    AUDIT_CONSERVATION_FAILURE = "AUDIT_CONSERVATION_FAILURE"
    CLIENT_CLOSE_FAILURE = "CLIENT_CLOSE_FAILURE"
    UNEXPECTED_INTERNAL_ERROR = "UNEXPECTED_INTERNAL_ERROR"


class PilotExitCode(int, Enum):
    SUCCESS = 0
    ARGUMENT_ERROR = 2
    AUTHORIZATION_ERROR = 3
    CLIENT_CONSTRUCTION_ERROR = 4
    RETRIEVAL_ERROR = 5
    SCHEMA_NORMALIZATION_ERROR = 6
    PERSISTENCE_MANIFEST_ERROR = 7
    INCOMPLETE_EXECUTION_ERROR = 8
    CLIENT_CLOSE_ERROR = 9
    UNEXPECTED_INTERNAL_ERROR = 10


class PilotOutcome(str, Enum):
    PASSED = "NSE_FIVE_STOCK_PILOT_PASSED"
    FAILED = "NSE_FIVE_STOCK_PILOT_FAILED"
    HALTED_ON_SAFETY_CONTROL = "NSE_FIVE_STOCK_PILOT_HALTED_ON_SAFETY_CONTROL"


@dataclass
class SessionBootstrapAudit:
    client_initialization_count: int = 0
    session_bootstrap_network_activity_detected: bool = False
    historical_retrieval_request_count: int = 0
    historical_retrieval_response_count: int = 0
    symbols_completed: int = 0
    client_close_count: int = 0


@runtime_checkable
class NSEDataFetcherProtocol(Protocol):
    """Protocol matching the authoritative NSEDataFetcher interface."""

    def get_live_quote(self, symbol: str) -> Dict[str, Any]:
        ...

    def get_market_status(self) -> Dict[str, Any]:
        ...

    def get_historical_data(self, symbol: str, start: str, end: str) -> List[Dict[str, Any]]:
        ...


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
    mapping_version: Optional[str] = None


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
    row_index: Optional[int] = None
    request_id: Optional[str] = None
    row_hash: Optional[str] = None


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
    raw_file_path: Optional[str] = None
    normalized_file_path: Optional[str] = None
    schema_version: str = "phase7-eod-v1.0"
    missing_fields: Optional[Dict[str, int]] = None
    rejected_row_count: int = 0
    duration_seconds: Optional[float] = None
    mapping_version: Optional[str] = None


@dataclass(frozen=True)
class PilotAuthorizationRecord:
    authorization_version: str
    milestone: str
    scope: str
    approved_symbols: List[str]
    start_date: str
    end_date: str
    interval: str
    staging_root_hash: str
    issued_timestamp: str
    expires_timestamp: str
    single_use: bool
    nonce: str
    authorization_hash: str
