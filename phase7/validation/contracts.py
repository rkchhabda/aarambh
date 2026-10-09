"""Canonical data contracts and deterministic record hashing for Phase 7 Walk-Forward Validation.

Defines immutable records, configuration structures, and deterministic hashing for:
1. WalkForwardFold
2. WalkForwardConfig
3. PurgeEmbargoInterval
4. PreprocessingParameterRecord
5. ValidationAuditRecord
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from phase7.data.contracts import compute_row_hash


class ValidationStatus(str, Enum):
    """Execution status for walk-forward validation operations."""
    INITIALIZED = "INITIALIZED"
    GENERATED = "GENERATED"
    AUDITED = "AUDITED"
    FAILED = "FAILED"


class ValidationLeakageError(ValueError):
    """Raised when temporal lookahead, label overlap, or cross-fold leakage is detected."""
    pass


class InvalidPurgeEmbargoConfigError(ValueError):
    """Raised when purge or embargo configurations violate preregistered minimums."""
    pass


class InsufficientDataForWalkForwardError(ValueError):
    """Raised when available trading history is insufficient to construct required folds."""
    pass


class PreprocessingNotFittedError(RuntimeError):
    """Raised when transform is attempted on an unfitted transformer."""
    pass


class PreprocessingLeakageError(ValueError):
    """Raised when a transformer is illicitly fitted on validation or test fold data."""
    pass


@dataclass(frozen=True)
class WalkForwardConfig:
    """Preregistered configuration for expanding walk-forward validation."""
    min_expanding_windows: int = 10
    target_name: str = "target_20d_sector_relative"
    primary_target_purge_days: int = 20
    primary_target_embargo_days: int = 5
    secondary_target_purge_days: int = 60
    secondary_target_embargo_days: int = 10
    min_train_trading_days: int = 252
    test_trading_days: Optional[int] = None
    fold_local_preprocessing: bool = True
    fold_local_hyperparameter_selection: bool = True
    deterministic_seed: int = 42
    config_hash: str = ""

    def __post_init__(self) -> None:
        if self.min_expanding_windows < 10:
            raise InvalidPurgeEmbargoConfigError(
                f"min_expanding_windows must be >= 10, got {self.min_expanding_windows}"
            )
        if self.primary_target_purge_days < 20:
            raise InvalidPurgeEmbargoConfigError(
                f"primary_target_purge_days must be >= 20, got {self.primary_target_purge_days}"
            )
        if self.primary_target_embargo_days < 5:
            raise InvalidPurgeEmbargoConfigError(
                f"primary_target_embargo_days must be >= 5, got {self.primary_target_embargo_days}"
            )
        if self.secondary_target_purge_days < 60:
            raise InvalidPurgeEmbargoConfigError(
                f"secondary_target_purge_days must be >= 60, got {self.secondary_target_purge_days}"
            )
        if self.secondary_target_embargo_days < 10:
            raise InvalidPurgeEmbargoConfigError(
                f"secondary_target_embargo_days must be >= 10, got {self.secondary_target_embargo_days}"
            )
        if self.min_train_trading_days < 20:
            raise InvalidPurgeEmbargoConfigError(
                f"min_train_trading_days must be >= 20, got {self.min_train_trading_days}"
            )
        if not self.fold_local_preprocessing:
            raise InvalidPurgeEmbargoConfigError(
                "fold_local_preprocessing must be True per Phase 7 preregistration."
            )

        computed = compute_row_hash(self.__dict__)
        if self.config_hash and self.config_hash != computed:
            raise ValueError(
                f"Supplied config_hash '{self.config_hash}' does not match computed '{computed}'"
            )
        object.__setattr__(self, "config_hash", computed)

    def get_purge_days(self) -> int:
        """Resolve required purge days based on target horizon."""
        if "60d" in self.target_name.lower() or "residual" in self.target_name.lower():
            return self.secondary_target_purge_days
        return self.primary_target_purge_days

    def get_embargo_days(self) -> int:
        """Resolve required embargo days based on target horizon."""
        if "60d" in self.target_name.lower() or "residual" in self.target_name.lower():
            return self.secondary_target_embargo_days
        return self.primary_target_embargo_days


@dataclass(frozen=True)
class PurgeEmbargoInterval:
    """Formal interval boundaries and masked dates for a specific validation fold."""
    fold_index: int
    train_end_date: date
    purge_start_date: date
    purge_end_date: date
    purge_trading_days: int
    test_start_date: date
    test_end_date: date
    test_trading_days: int
    embargo_start_date: Optional[date]
    embargo_end_date: Optional[date]
    embargo_trading_days: int
    purged_trading_dates: Tuple[date, ...]
    embargoed_trading_dates: Tuple[date, ...]
    interval_hash: str = ""

    def __post_init__(self) -> None:
        if self.fold_index < 0:
            raise ValueError(f"fold_index must be >= 0, got {self.fold_index}")
        if self.purge_trading_days < 0:
            raise ValueError(f"purge_trading_days cannot be negative, got {self.purge_trading_days}")
        if self.embargo_trading_days < 0:
            raise ValueError(f"embargo_trading_days cannot be negative, got {self.embargo_trading_days}")
        if self.test_trading_days <= 0:
            raise ValueError(f"test_trading_days must be positive, got {self.test_trading_days}")
        if self.purge_start_date > self.purge_end_date:
            raise ValueError(f"purge_start_date {self.purge_start_date} cannot be after purge_end_date {self.purge_end_date}")
        if self.test_start_date > self.test_end_date:
            raise ValueError(f"test_start_date {self.test_start_date} cannot be after test_end_date {self.test_end_date}")
        if self.purge_end_date >= self.test_start_date:
            raise ValidationLeakageError(
                f"purge_end_date {self.purge_end_date} must be strictly before test_start_date {self.test_start_date}"
            )
        if self.embargo_start_date and self.embargo_end_date:
            if self.embargo_start_date > self.embargo_end_date:
                raise ValueError("embargo_start_date cannot be after embargo_end_date")
            if self.test_end_date >= self.embargo_start_date:
                raise ValidationLeakageError("test_end_date must be strictly before embargo_start_date")

        computed = compute_row_hash(self.__dict__)
        if self.interval_hash and self.interval_hash != computed:
            raise ValueError(f"Supplied interval_hash '{self.interval_hash}' does not match computed '{computed}'")
        object.__setattr__(self, "interval_hash", computed)


@dataclass(frozen=True)
class WalkForwardFold:
    """Immutable representation of a single expanding walk-forward fold."""
    fold_index: int
    train_start_date: date
    train_end_date: date
    purge_start_date: date
    purge_end_date: date
    test_start_date: date
    test_end_date: date
    embargo_start_date: Optional[date]
    embargo_end_date: Optional[date]
    train_trading_days: int
    purge_trading_days: int
    test_trading_days: int
    embargo_trading_days: int
    target_name: str
    dataset_version: str
    fold_hash: str = ""

    def __post_init__(self) -> None:
        if self.fold_index < 0:
            raise ValueError(f"fold_index must be >= 0, got {self.fold_index}")
        if self.train_start_date > self.train_end_date:
            raise ValueError("train_start_date cannot be after train_end_date")
        if self.train_end_date >= self.purge_start_date:
            raise ValidationLeakageError("train_end_date must be strictly before purge_start_date")
        if self.purge_start_date > self.purge_end_date:
            raise ValueError("purge_start_date cannot be after purge_end_date")
        if self.purge_end_date >= self.test_start_date:
            raise ValidationLeakageError("purge_end_date must be strictly before test_start_date")
        if self.test_start_date > self.test_end_date:
            raise ValueError("test_start_date cannot be after test_end_date")
        if self.embargo_start_date and self.embargo_end_date:
            if self.embargo_start_date > self.embargo_end_date:
                raise ValueError("embargo_start_date cannot be after embargo_end_date")
            if self.test_end_date >= self.embargo_start_date:
                raise ValidationLeakageError("test_end_date must be strictly before embargo_start_date")
        if not self.target_name.strip():
            raise ValueError("target_name must not be empty")
        if not self.dataset_version.strip():
            raise ValueError("dataset_version must not be empty")

        computed = compute_row_hash(self.__dict__)
        if self.fold_hash and self.fold_hash != computed:
            raise ValueError(f"Supplied fold_hash '{self.fold_hash}' does not match computed '{computed}'")
        object.__setattr__(self, "fold_hash", computed)


@dataclass(frozen=True)
class PreprocessingParameterRecord:
    """Immutable provenance record of fitted fold-local preprocessing parameters."""
    fold_index: int
    transformer_name: str
    feature_names: Tuple[str, ...]
    parameters: Dict[str, Any]
    fitted_row_count: int
    fitted_timestamp: datetime
    dataset_version: str
    parameter_hash: str = ""

    def __post_init__(self) -> None:
        if self.fold_index < 0:
            raise ValueError(f"fold_index must be >= 0, got {self.fold_index}")
        if not self.transformer_name.strip():
            raise ValueError("transformer_name must not be empty")
        if self.fitted_row_count <= 0:
            raise ValueError(f"fitted_row_count must be positive, got {self.fitted_row_count}")
        if self.fitted_timestamp.tzinfo is None:
            raise ValueError("fitted_timestamp must be timezone-aware (UTC required)")

        computed = compute_row_hash(self.__dict__)
        if self.parameter_hash and self.parameter_hash != computed:
            raise ValueError(f"Supplied parameter_hash '{self.parameter_hash}' does not match computed '{computed}'")
        object.__setattr__(self, "parameter_hash", computed)


@dataclass(frozen=True)
class ValidationAuditRecord:
    """Quality and governance audit record for a completed walk-forward validation run."""
    total_folds: int
    target_name: str
    min_expanding_windows: int
    expanding_property_verified: bool
    zero_label_leakage_verified: bool
    fold_local_preprocessing_verified: bool
    total_trading_days: int
    total_test_trading_days: int
    earliest_train_date: date
    latest_test_date: date
    dataset_version: str
    audit_hash: str = ""

    def __post_init__(self) -> None:
        if self.total_folds < self.min_expanding_windows:
            raise ValueError(
                f"total_folds ({self.total_folds}) is less than min_expanding_windows ({self.min_expanding_windows})"
            )
        if not self.expanding_property_verified:
            raise ValidationLeakageError("expanding_property_verified must be True")
        if not self.zero_label_leakage_verified:
            raise ValidationLeakageError("zero_label_leakage_verified must be True")
        if not self.fold_local_preprocessing_verified:
            raise ValidationLeakageError("fold_local_preprocessing_verified must be True")
        if self.earliest_train_date >= self.latest_test_date:
            raise ValueError("earliest_train_date must be before latest_test_date")

        computed = compute_row_hash(self.__dict__)
        if self.audit_hash and self.audit_hash != computed:
            raise ValueError(f"Supplied audit_hash '{self.audit_hash}' does not match computed '{computed}'")
        object.__setattr__(self, "audit_hash", computed)
