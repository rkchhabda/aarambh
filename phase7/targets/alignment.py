"""T+1 forward trading date alignment engine for Phase 7 targets.

Enforces:
1. Rejection of same-day entry at t (execution lag >= 1 trading day).
2. Selection of entry at the first authorized forward trading session (t+1).
3. Counting forward trading observations (not calendar days).
4. Selection of exit at the exact horizon-th forward observation (e.g. t+20 or t+60).
5. Validation that observations match prediction symbol and ISIN.
6. Rejection of duplicate dates and missing terminal observations.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Sequence

from phase7.targets.contracts import (
    ForwardPriceObservationRecord,
    PredictionEventRecord,
    TargetReasonCode,
    TargetStatus,
)


@dataclass(frozen=True)
class TargetAlignmentResult:
    """Outcome of forward trading date alignment."""
    entry_record: Optional[ForwardPriceObservationRecord]
    exit_record: Optional[ForwardPriceObservationRecord]
    forward_observations: List[ForwardPriceObservationRecord]
    horizon_trading_days: int
    status: TargetStatus
    reason_codes: List[TargetReasonCode] = field(default_factory=list)
    audit_notes: List[str] = field(default_factory=list)


def align_forward_observations(
    prediction_event: PredictionEventRecord,
    observations: Sequence[ForwardPriceObservationRecord],
    horizon_trading_days: int,
    execution_lag_trading_days: int = 1,
) -> TargetAlignmentResult:
    """Align forward price observations strictly following T+1 entry and horizon exit rules.

    Args:
        prediction_event: Validated prediction event containing origin t.
        observations: Available forward price observations for the security.
        horizon_trading_days: Configured forward horizon count (e.g. 20 or 60).
        execution_lag_trading_days: Minimum trading lag before entry (default 1, representing t+1).

    Returns:
        TargetAlignmentResult with entry, exit, status, and reason codes.
    """
    if horizon_trading_days <= 0:
        raise ValueError(f"horizon_trading_days must be positive, got {horizon_trading_days}")
    if execution_lag_trading_days < 1:
        raise ValueError(f"execution_lag_trading_days must be >= 1 (same-day execution prohibited), got {execution_lag_trading_days}")

    notes: List[str] = []
    reasons: List[TargetReasonCode] = []

    if not observations:
        return TargetAlignmentResult(
            entry_record=None,
            exit_record=None,
            forward_observations=[],
            horizon_trading_days=horizon_trading_days,
            status=TargetStatus.INVALID,
            reason_codes=[TargetReasonCode.MISSING_ENTRY_PRICE],
            audit_notes=["No observations provided for candidate security."],
        )

    # 1. Identity validation (all records must match prediction symbol & ISIN)
    for obs in observations:
        if obs.symbol != prediction_event.symbol:
            reasons.append(TargetReasonCode.DATA_VALIDATION_FAILURE)
            notes.append(f"Observation symbol '{obs.symbol}' does not match prediction symbol '{prediction_event.symbol}'.")
            return TargetAlignmentResult(
                entry_record=None,
                exit_record=None,
                forward_observations=[],
                horizon_trading_days=horizon_trading_days,
                status=TargetStatus.INVALID,
                reason_codes=reasons,
                audit_notes=notes,
            )
        if obs.isin != prediction_event.isin:
            reasons.append(TargetReasonCode.DATA_VALIDATION_FAILURE)
            notes.append(f"Observation ISIN '{obs.isin}' does not match prediction ISIN '{prediction_event.isin}'.")
            return TargetAlignmentResult(
                entry_record=None,
                exit_record=None,
                forward_observations=[],
                horizon_trading_days=horizon_trading_days,
                status=TargetStatus.INVALID,
                reason_codes=reasons,
                audit_notes=notes,
            )

    # 2. Duplicate date detection
    seen_dates = set()
    for obs in observations:
        if obs.trading_date in seen_dates:
            reasons.append(TargetReasonCode.DUPLICATE_DATE_OBSERVATION)
            reasons.append(TargetReasonCode.DATA_VALIDATION_FAILURE)
            notes.append(f"Duplicate observation detected for trading date {obs.trading_date}.")
            return TargetAlignmentResult(
                entry_record=None,
                exit_record=None,
                forward_observations=[],
                horizon_trading_days=horizon_trading_days,
                status=TargetStatus.INVALID,
                reason_codes=reasons,
                audit_notes=notes,
            )
        seen_dates.add(obs.trading_date)

    # 3. Filter strictly forward trading observations (trading_date > prediction_trading_date)
    # Sort deterministically by trading_date
    sorted_obs = sorted(observations, key=lambda x: x.trading_date)
    forward_obs = [obs for obs in sorted_obs if obs.trading_date > prediction_event.prediction_trading_date]

    if not forward_obs:
        # Check if an observation on or before t was mistakenly supplied
        notes.append(f"Zero forward trading sessions found strictly after prediction date {prediction_event.prediction_trading_date}.")
        if any(obs.trading_date == prediction_event.prediction_trading_date for obs in sorted_obs):
            reasons.append(TargetReasonCode.SAME_DAY_ENTRY_PROHIBITED)
        reasons.append(TargetReasonCode.MISSING_ENTRY_PRICE)
        return TargetAlignmentResult(
            entry_record=None,
            exit_record=None,
            forward_observations=[],
            horizon_trading_days=horizon_trading_days,
            status=TargetStatus.INVALID,
            reason_codes=reasons,
            audit_notes=notes,
        )

    # Entry observation is the first authorized forward observation (t+1)
    entry_record = forward_obs[0]
    notes.append(f"Entry selected at t+1 session: {entry_record.trading_date}.")

    # 4. Check if we have sufficient observations to reach horizon exit
    if len(forward_obs) < horizon_trading_days:
        notes.append(
            f"Insufficient forward observations: found {len(forward_obs)}, required {horizon_trading_days} sessions."
        )
        reasons.append(TargetReasonCode.INSUFFICIENT_FORWARD_OBSERVATIONS)
        reasons.append(TargetReasonCode.MISSING_EXIT_PRICE)
        return TargetAlignmentResult(
            entry_record=entry_record,
            exit_record=None,
            forward_observations=forward_obs,
            horizon_trading_days=horizon_trading_days,
            status=TargetStatus.INVALID,
            reason_codes=reasons,
            audit_notes=notes,
        )

    # Exit observation is the horizon-th forward observation
    exit_record = forward_obs[horizon_trading_days - 1]
    notes.append(f"Exit selected at horizon session ({horizon_trading_days}th): {exit_record.trading_date}.")

    return TargetAlignmentResult(
        entry_record=entry_record,
        exit_record=exit_record,
        forward_observations=forward_obs[:horizon_trading_days],
        horizon_trading_days=horizon_trading_days,
        status=TargetStatus.VALID,
        reason_codes=[],
        audit_notes=notes,
    )
