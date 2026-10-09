"""Cutoff truncation and temporal boundary enforcement engine for Phase 7 targets.

Enforces:
1. Rejection of outcomes extending beyond the authorized research cutoff.
2. Counting of valid discrete trading observations (no calendar-day filling or invented sessions).
3. Preservation of immutable truncation records with deterministic hashes.
4. Handling of security-specific terminal histories and weekend/holiday gaps.
5. Tracking of blocked events for governance audits.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from phase7.data.contracts import compute_row_hash
from phase7.targets.contracts import (
    ForwardPriceObservationRecord,
    PredictionEventRecord,
)


class TruncationStatus(str, Enum):
    """Lifecycle and boundary status for target cutoff truncation."""
    COMPLETE = "COMPLETE"
    INSUFFICIENT_FORWARD_OBSERVATIONS = "INSUFFICIENT_FORWARD_OBSERVATIONS"
    OUTCOME_EXCEEDS_AUTHORIZED_CUTOFF = "OUTCOME_EXCEEDS_AUTHORIZED_CUTOFF"
    MISSING_ENTRY = "MISSING_ENTRY"
    MISSING_EXIT = "MISSING_EXIT"
    DATA_VALIDATION_FAILURE = "DATA_VALIDATION_FAILURE"


@dataclass(frozen=True)
class CutoffTruncationResult:
    """Immutable audit record representing the outcome of cutoff evaluation."""
    prediction_timestamp: datetime
    symbol: str
    isin: str
    target_name: str
    horizon_endpoint: int
    required_outcome_start: Optional[date]
    required_outcome_end: Optional[date]
    authorized_cutoff: datetime
    available_observation_count: int
    required_observation_count: int
    truncation_status: TruncationStatus
    reason_codes: Tuple[str, ...] = field(default_factory=tuple)
    removed_event_count: int = 0
    dataset_version: str = "1.0.0"
    result_hash: str = ""

    def __post_init__(self) -> None:
        clean_dict = {k: v for k, v in self.__dict__.items() if k != "result_hash"}
        computed = compute_row_hash(clean_dict)
        if self.result_hash and self.result_hash != computed:
            raise ValueError(f"Supplied result_hash '{self.result_hash}' does not match computed '{computed}'")
        if not self.result_hash:
            object.__setattr__(self, "result_hash", computed)


def evaluate_cutoff_truncation(
    prediction_event: PredictionEventRecord,
    observations: Sequence[ForwardPriceObservationRecord],
    horizon_endpoint: int,
    authorized_cutoff: datetime,
    target_name: str = "target_20d_sector_relative",
    dataset_version: str = "1.0.0",
) -> CutoffTruncationResult:
    """Evaluate whether forward trading observations for a prediction event fit within the authorized cutoff.

    Args:
        prediction_event: Validated prediction event at origin t.
        observations: Candidate forward price observations for the security.
        horizon_endpoint: Required forward observation count (e.g., 20 or 60).
        authorized_cutoff: Timezone-aware UTC datetime defining the strict cutoff.
        target_name: Name of target specification.
        dataset_version: Version of candidate dataset.

    Returns:
        CutoffTruncationResult capturing boundary adherence and observation counts.
    """
    if horizon_endpoint <= 0:
        raise ValueError(f"horizon_endpoint must be positive, got {horizon_endpoint}")
    if authorized_cutoff.tzinfo is None:
        raise ValueError("authorized_cutoff must be timezone-aware (UTC required).")
    if prediction_event.prediction_timestamp.tzinfo is None:
        raise ValueError("prediction_timestamp must be timezone-aware (UTC required).")

    # 1. Identity validation
    for obs in observations:
        if obs.symbol != prediction_event.symbol or obs.isin != prediction_event.isin:
            return CutoffTruncationResult(
                prediction_timestamp=prediction_event.prediction_timestamp,
                symbol=prediction_event.symbol,
                isin=prediction_event.isin,
                target_name=target_name,
                horizon_endpoint=horizon_endpoint,
                required_outcome_start=None,
                required_outcome_end=None,
                authorized_cutoff=authorized_cutoff,
                available_observation_count=len(observations),
                required_observation_count=horizon_endpoint,
                truncation_status=TruncationStatus.DATA_VALIDATION_FAILURE,
                reason_codes=("SECURITY_IDENTITY_MISMATCH",),
                removed_event_count=1,
                dataset_version=dataset_version,
            )

    # 2. Filter strictly forward trading observations
    sorted_obs = sorted(observations, key=lambda x: x.trading_date)
    forward_obs = [obs for obs in sorted_obs if obs.trading_date > prediction_event.prediction_trading_date]

    if not forward_obs:
        return CutoffTruncationResult(
            prediction_timestamp=prediction_event.prediction_timestamp,
            symbol=prediction_event.symbol,
            isin=prediction_event.isin,
            target_name=target_name,
            horizon_endpoint=horizon_endpoint,
            required_outcome_start=None,
            required_outcome_end=None,
            authorized_cutoff=authorized_cutoff,
            available_observation_count=0,
            required_observation_count=horizon_endpoint,
            truncation_status=TruncationStatus.MISSING_ENTRY,
            reason_codes=("ZERO_FORWARD_OBSERVATIONS",),
            removed_event_count=1,
            dataset_version=dataset_version,
        )

    entry_obs = forward_obs[0]
    required_start = entry_obs.trading_date

    # Check if entry observation itself violates authorized cutoff
    if entry_obs.source_timestamp > authorized_cutoff or entry_obs.trading_date > authorized_cutoff.date():
        return CutoffTruncationResult(
            prediction_timestamp=prediction_event.prediction_timestamp,
            symbol=prediction_event.symbol,
            isin=prediction_event.isin,
            target_name=target_name,
            horizon_endpoint=horizon_endpoint,
            required_outcome_start=required_start,
            required_outcome_end=None,
            authorized_cutoff=authorized_cutoff,
            available_observation_count=len(forward_obs),
            required_observation_count=horizon_endpoint,
            truncation_status=TruncationStatus.OUTCOME_EXCEEDS_AUTHORIZED_CUTOFF,
            reason_codes=("ENTRY_OBSERVATION_EXCEEDS_CUTOFF",),
            removed_event_count=1,
            dataset_version=dataset_version,
        )

    # 3. Check sufficiency of forward observations
    if len(forward_obs) < horizon_endpoint:
        # Check if the truncation happened because later dates exceed cutoff
        any_exceeds = any(
            obs.source_timestamp > authorized_cutoff or obs.trading_date > authorized_cutoff.date()
            for obs in forward_obs
        )
        status = (
            TruncationStatus.OUTCOME_EXCEEDS_AUTHORIZED_CUTOFF
            if any_exceeds
            else TruncationStatus.INSUFFICIENT_FORWARD_OBSERVATIONS
        )
        return CutoffTruncationResult(
            prediction_timestamp=prediction_event.prediction_timestamp,
            symbol=prediction_event.symbol,
            isin=prediction_event.isin,
            target_name=target_name,
            horizon_endpoint=horizon_endpoint,
            required_outcome_start=required_start,
            required_outcome_end=None,
            authorized_cutoff=authorized_cutoff,
            available_observation_count=len(forward_obs),
            required_observation_count=horizon_endpoint,
            truncation_status=status,
            reason_codes=("MISSING_EXIT", "OBSERVATION_COUNT_DEFICIENT"),
            removed_event_count=1,
            dataset_version=dataset_version,
        )

    # Observation at the horizon endpoint (0-indexed: horizon_endpoint - 1)
    exit_obs = forward_obs[horizon_endpoint - 1]
    required_end = exit_obs.trading_date

    # 4. Check if required exit observation or any observation in the window exceeds authorized cutoff
    cutoff_date = authorized_cutoff.date()
    window_obs = forward_obs[:horizon_endpoint]
    for obs in window_obs:
        if obs.source_timestamp > authorized_cutoff or obs.trading_date > cutoff_date:
            return CutoffTruncationResult(
                prediction_timestamp=prediction_event.prediction_timestamp,
                symbol=prediction_event.symbol,
                isin=prediction_event.isin,
                target_name=target_name,
                horizon_endpoint=horizon_endpoint,
                required_outcome_start=required_start,
                required_outcome_end=required_end,
                authorized_cutoff=authorized_cutoff,
                available_observation_count=len(forward_obs),
                required_observation_count=horizon_endpoint,
                truncation_status=TruncationStatus.OUTCOME_EXCEEDS_AUTHORIZED_CUTOFF,
                reason_codes=("WINDOW_OBSERVATION_EXCEEDS_CUTOFF",),
                removed_event_count=1,
                dataset_version=dataset_version,
            )

    return CutoffTruncationResult(
        prediction_timestamp=prediction_event.prediction_timestamp,
        symbol=prediction_event.symbol,
        isin=prediction_event.isin,
        target_name=target_name,
        horizon_endpoint=horizon_endpoint,
        required_outcome_start=required_start,
        required_outcome_end=required_end,
        authorized_cutoff=authorized_cutoff,
        available_observation_count=len(forward_obs),
        required_observation_count=horizon_endpoint,
        truncation_status=TruncationStatus.COMPLETE,
        reason_codes=(),
        removed_event_count=0,
        dataset_version=dataset_version,
    )
