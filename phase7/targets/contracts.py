"""Canonical data contracts for Phase 7 target construction and forward return calculations.

Defines immutable records, target statuses, reason codes, and deterministic
SHA-256 row hashing for:
1. TargetSpecificationRecord
2. PredictionEventRecord
3. ForwardPriceObservationRecord
4. SectorBenchmarkObservationRecord
5. BetaInputRecord
6. TargetResultRecord
7. TargetAuditRecord
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from phase7.data.contracts import (
    ISIN_REGEX,
    PriceAdjustmentState,
    compute_row_hash,
)


# ------------------------------------------------------------------------------
# Target Status and Reason Code Enumerations
# ------------------------------------------------------------------------------

class TargetStatus(str, Enum):
    """Lifecycle and validity status for forward target outcomes."""
    VALID = "VALID"
    BLOCKED_REAL_DATA_UNAVAILABLE = "BLOCKED_REAL_DATA_UNAVAILABLE"
    INVALID = "INVALID"
    BLOCKED = "BLOCKED"


class TargetReasonCode(str, Enum):
    """Canonical reason codes for invalid or blocked target calculations."""
    MISSING_ENTRY_PRICE = "MISSING_ENTRY_PRICE"
    MISSING_EXIT_PRICE = "MISSING_EXIT_PRICE"
    INSUFFICIENT_FORWARD_OBSERVATIONS = "INSUFFICIENT_FORWARD_OBSERVATIONS"
    FUTURE_DATA_DETECTED = "FUTURE_DATA_DETECTED"
    INVALID_ADJUSTMENT_STATE = "INVALID_ADJUSTMENT_STATE"
    CORPORATE_ACTION_REVIEW_REQUIRED = "CORPORATE_ACTION_REVIEW_REQUIRED"
    SUSPENDED_DURING_HORIZON = "SUSPENDED_DURING_HORIZON"
    DELISTED_DURING_HORIZON = "DELISTED_DURING_HORIZON"
    INVALID_BETA = "INVALID_BETA"
    FUTURE_BETA_DETECTED = "FUTURE_BETA_DETECTED"
    MISSING_BENCHMARK = "MISSING_BENCHMARK"
    INVALID_BENCHMARK = "INVALID_BENCHMARK"
    TARGET_SPECIFICATION_MISMATCH = "TARGET_SPECIFICATION_MISMATCH"
    DATA_VALIDATION_FAILURE = "DATA_VALIDATION_FAILURE"
    MISSING_PIT_SECTOR = "MISSING_PIT_SECTOR"
    CONFLICTING_PIT_SECTOR = "CONFLICTING_PIT_SECTOR"
    FUTURE_SECTOR_DETECTED = "FUTURE_SECTOR_DETECTED"
    SAME_DAY_ENTRY_PROHIBITED = "SAME_DAY_ENTRY_PROHIBITED"
    DUPLICATE_DATE_OBSERVATION = "DUPLICATE_DATE_OBSERVATION"


# ------------------------------------------------------------------------------
# Immutable Target Records
# ------------------------------------------------------------------------------

@dataclass(frozen=True)
class TargetSpecificationRecord:
    """Formal specification parameters for a preregistered target variable."""
    target_name: str
    target_version: str
    horizon_trading_days: int
    execution_lag_trading_days: int
    entry_price_field: str
    exit_price_field: str
    return_type: str
    benchmark_type: str
    adjustment_state_requirement: PriceAdjustmentState
    missing_terminal_policy: str
    suspension_policy: str
    delisting_policy: str
    created_timestamp: datetime
    specification_hash: str = ""

    def __post_init__(self) -> None:
        if not self.target_name.strip():
            raise ValueError("target_name must not be empty.")
        if not self.target_version.strip():
            raise ValueError("target_version must not be empty.")
        if self.horizon_trading_days <= 0:
            raise ValueError(f"horizon_trading_days must be positive, got {self.horizon_trading_days}")
        if self.execution_lag_trading_days < 1:
            raise ValueError(f"execution_lag_trading_days must be >= 1 (no same-day execution), got {self.execution_lag_trading_days}")
        if self.created_timestamp.tzinfo is None:
            raise ValueError("created_timestamp must be timezone-aware (UTC required).")

        computed = compute_row_hash(self.__dict__)
        if self.specification_hash and self.specification_hash != computed:
            raise ValueError(f"Supplied specification_hash '{self.specification_hash}' does not match computed '{computed}'")
        if not self.specification_hash:
            object.__setattr__(self, "specification_hash", computed)


@dataclass(frozen=True)
class PredictionEventRecord:
    """Prediction event instant defining the point-in-time origin t."""
    prediction_timestamp: datetime
    prediction_trading_date: date
    symbol: str
    isin: str
    universe_hash: str
    dataset_version: str
    source_cutoff_timestamp: datetime
    target_specification_hash: str
    row_hash: str = ""

    def __post_init__(self) -> None:
        sym = self.symbol.strip().upper()
        isin_val = self.isin.strip().upper()
        if not sym:
            raise ValueError("symbol must not be empty.")
        if not isin_val or not ISIN_REGEX.match(isin_val):
            raise ValueError(f"Invalid ISIN format: '{self.isin}'")
        if self.prediction_timestamp.tzinfo is None:
            raise ValueError("prediction_timestamp must be timezone-aware (UTC).")
        if self.source_cutoff_timestamp.tzinfo is None:
            raise ValueError("source_cutoff_timestamp must be timezone-aware (UTC).")
        if self.source_cutoff_timestamp > self.prediction_timestamp:
            raise ValueError("source_cutoff_timestamp cannot be later than prediction_timestamp.")

        object.__setattr__(self, "symbol", sym)
        object.__setattr__(self, "isin", isin_val)

        computed = compute_row_hash(self.__dict__)
        if self.row_hash and self.row_hash != computed:
            raise ValueError(f"Supplied row_hash '{self.row_hash}' does not match computed '{computed}'")
        if not self.row_hash:
            object.__setattr__(self, "row_hash", computed)


@dataclass(frozen=True)
class ForwardPriceObservationRecord:
    """Individual forward trading session price observation for a security."""
    trading_date: date
    symbol: str
    isin: str
    price: Decimal
    adjustment_state: PriceAdjustmentState
    source_timestamp: datetime
    source_identifier: str
    row_hash: str = ""

    def __post_init__(self) -> None:
        sym = self.symbol.strip().upper()
        isin_val = self.isin.strip().upper()
        if not sym:
            raise ValueError("symbol must not be empty.")
        if not isin_val or not ISIN_REGEX.match(isin_val):
            raise ValueError(f"Invalid ISIN format: '{self.isin}'")
        if not self.price.is_finite() or self.price <= Decimal("0"):
            raise ValueError(f"price must be positive and finite, got {self.price}")
        if self.adjustment_state == PriceAdjustmentState.UNKNOWN:
            raise ValueError("adjustment_state must not be UNKNOWN.")
        if self.source_timestamp.tzinfo is None:
            raise ValueError("source_timestamp must be timezone-aware (UTC).")

        object.__setattr__(self, "symbol", sym)
        object.__setattr__(self, "isin", isin_val)

        computed = compute_row_hash(self.__dict__)
        if self.row_hash and self.row_hash != computed:
            raise ValueError(f"Supplied row_hash '{self.row_hash}' does not match computed '{computed}'")
        if not self.row_hash:
            object.__setattr__(self, "row_hash", computed)


@dataclass(frozen=True)
class SectorBenchmarkObservationRecord:
    """Sector benchmark observation for a forward trading date."""
    sector_code: str
    trading_date: date
    benchmark_identifier: str
    price: Optional[Decimal] = None
    return_value: Optional[Decimal] = None
    adjustment_state: PriceAdjustmentState = PriceAdjustmentState.TOTAL_RETURN_ADJUSTED
    source_timestamp: datetime = field(default_factory=lambda: datetime(2025, 1, 1, 16, 0, 0, tzinfo=timezone.utc))
    dataset_version: str = "1.0.0"
    row_hash: str = ""

    def __post_init__(self) -> None:
        sec = self.sector_code.strip().upper()
        b_id = self.benchmark_identifier.strip().upper()
        if not sec:
            raise ValueError("sector_code must not be empty.")
        if not b_id:
            raise ValueError("benchmark_identifier must not be empty.")
        if self.price is None and self.return_value is None:
            raise ValueError("At least one of price or return_value must be provided.")
        if self.price is not None and (not self.price.is_finite() or self.price <= Decimal("0")):
            raise ValueError(f"benchmark price must be positive and finite, got {self.price}")
        if self.return_value is not None and not self.return_value.is_finite():
            raise ValueError(f"benchmark return_value must be finite, got {self.return_value}")
        if self.source_timestamp.tzinfo is None:
            raise ValueError("source_timestamp must be timezone-aware (UTC).")

        object.__setattr__(self, "sector_code", sec)
        object.__setattr__(self, "benchmark_identifier", b_id)

        computed = compute_row_hash(self.__dict__)
        if self.row_hash and self.row_hash != computed:
            raise ValueError(f"Supplied row_hash '{self.row_hash}' does not match computed '{computed}'")
        if not self.row_hash:
            object.__setattr__(self, "row_hash", computed)


@dataclass(frozen=True)
class BetaInputRecord:
    """Input beta estimate calculated strictly from information available at or before t."""
    symbol: str
    isin: str
    beta: Decimal
    estimation_end_timestamp: datetime
    estimation_method: str
    benchmark_identifier: str
    dataset_version: str
    row_hash: str = ""

    def __post_init__(self) -> None:
        sym = self.symbol.strip().upper()
        isin_val = self.isin.strip().upper()
        b_id = self.benchmark_identifier.strip().upper()
        if not sym:
            raise ValueError("symbol must not be empty.")
        if not isin_val or not ISIN_REGEX.match(isin_val):
            raise ValueError(f"Invalid ISIN format: '{self.isin}'")
        if not b_id:
            raise ValueError("benchmark_identifier must not be empty.")
        if not self.beta.is_finite():
            raise ValueError(f"beta must be a finite Decimal, got {self.beta}")
        if self.estimation_end_timestamp.tzinfo is None:
            raise ValueError("estimation_end_timestamp must be timezone-aware (UTC).")

        object.__setattr__(self, "symbol", sym)
        object.__setattr__(self, "isin", isin_val)
        object.__setattr__(self, "benchmark_identifier", b_id)

        computed = compute_row_hash(self.__dict__)
        if self.row_hash and self.row_hash != computed:
            raise ValueError(f"Supplied row_hash '{self.row_hash}' does not match computed '{computed}'")
        if not self.row_hash:
            object.__setattr__(self, "row_hash", computed)


@dataclass(frozen=True)
class TargetResultRecord:
    """Computed target result for a single prediction event."""
    target_name: str
    target_version: str
    prediction_timestamp: datetime
    symbol: str
    isin: str
    horizon_trading_days: int
    entry_date: Optional[date]
    exit_date: Optional[date]
    stock_total_return: Optional[Decimal]
    benchmark_total_return: Optional[Decimal]
    beta_used: Optional[Decimal]
    target_value: Optional[Decimal]
    target_status: TargetStatus
    invalid_reason_codes: List[TargetReasonCode] = field(default_factory=list)
    source_dataset_versions: Dict[str, str] = field(default_factory=dict)
    universe_hash: str = ""
    target_hash: str = ""

    def __post_init__(self) -> None:
        sym = self.symbol.strip().upper()
        isin_val = self.isin.strip().upper()
        object.__setattr__(self, "symbol", sym)
        object.__setattr__(self, "isin", isin_val)

        # Invariant checks
        if self.target_status == TargetStatus.VALID:
            if self.target_value is None or not self.target_value.is_finite():
                raise ValueError("Valid target must have a finite Decimal target_value.")
            if self.entry_date is None or self.exit_date is None:
                raise ValueError("Valid target must have entry_date and exit_date.")
            if self.stock_total_return is None or not self.stock_total_return.is_finite():
                raise ValueError("Valid target must have a finite stock_total_return.")

        # Compute deterministic row hash excluding target_hash itself
        clean_dict = {k: v for k, v in self.__dict__.items() if k != "target_hash"}
        computed = compute_row_hash(clean_dict)
        if self.target_hash and self.target_hash != computed:
            raise ValueError(f"Supplied target_hash '{self.target_hash}' does not match computed '{computed}'")
        if not self.target_hash:
            object.__setattr__(self, "target_hash", computed)


@dataclass(frozen=True)
class TargetAuditRecord:
    """Audit report capturing provenance and dataset-wide target construction counts."""
    input_record_count: int
    accepted_target_count: int
    rejected_target_count: int
    blocked_target_count: int
    future_data_count: int
    missing_entry_count: int
    missing_exit_count: int
    adjustment_state_failure_count: int
    suspension_count: int
    delisting_count: int
    invalid_beta_count: int
    target_specification_hash: str
    dataset_version: str
    corporate_action_review_count: int = 0
    missing_benchmark_count: int = 0
    overlap_count: int = 0
    overlapping_label_count: int = 0
    audit_hash: str = ""

    def __post_init__(self) -> None:
        if self.overlapping_label_count == 0 and self.overlap_count != 0:
            object.__setattr__(self, "overlapping_label_count", self.overlap_count)
        elif self.overlap_count == 0 and self.overlapping_label_count != 0:
            object.__setattr__(self, "overlap_count", self.overlapping_label_count)

        clean_dict = {k: v for k, v in self.__dict__.items() if k != "audit_hash"}
        computed = compute_row_hash(clean_dict)
        if self.audit_hash and self.audit_hash != computed:
            raise ValueError(f"Supplied audit_hash '{self.audit_hash}' does not match computed '{computed}'")
        if not self.audit_hash:
            object.__setattr__(self, "audit_hash", computed)

    def to_dict(self) -> Dict[str, Any]:
        """Convert audit record to serializable dictionary with zero performance metrics."""
        return {
            "input_record_count": self.input_record_count,
            "accepted_target_count": self.accepted_target_count,
            "rejected_target_count": self.rejected_target_count,
            "blocked_target_count": self.blocked_target_count,
            "future_data_count": self.future_data_count,
            "missing_entry_count": self.missing_entry_count,
            "missing_exit_count": self.missing_exit_count,
            "adjustment_state_failure_count": self.adjustment_state_failure_count,
            "suspension_count": self.suspension_count,
            "delisting_count": self.delisting_count,
            "corporate_action_review_count": self.corporate_action_review_count,
            "invalid_beta_count": self.invalid_beta_count,
            "missing_benchmark_count": self.missing_benchmark_count,
            "overlap_count": self.overlap_count,
            "overlapping_label_count": self.overlapping_label_count,
            "target_specification_hash": self.target_specification_hash,
            "dataset_version": self.dataset_version,
            "audit_hash": self.audit_hash,
        }
