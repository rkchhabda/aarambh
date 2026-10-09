"""Purge and embargo interval masking and temporal leakage validation.

Implements strict trading-day (market session) interval calculations to ensure:
1. Purge gap >= 20 trading days for primary 20d target.
2. Purge gap >= 60 trading days for secondary 60d target.
3. Post-test embargo >= 5 trading days for primary 20d target.
4. Post-test embargo >= 10 trading days for secondary 60d target.
5. Mathematical verification of zero label leakage between training forward outcomes and test windows.
"""

from datetime import date
from typing import List, Optional, Sequence, Set, Tuple

from phase7.validation.contracts import (
    InvalidPurgeEmbargoConfigError,
    PurgeEmbargoInterval,
    ValidationLeakageError,
)


def validate_purge_embargo_days(
    target_name: str,
    purge_days: int,
    embargo_days: int,
) -> Tuple[int, int]:
    """Validate that purge and embargo trading days meet preregistered thresholds.

    Args:
        target_name: Name of target variable (e.g. 'target_20d_sector_relative', 'target_60d_residual').
        purge_days: Configured purge gap in trading days.
        embargo_days: Configured embargo gap in trading days.

    Returns:
        Tuple of (validated_purge_days, validated_embargo_days).

    Raises:
        InvalidPurgeEmbargoConfigError: If either parameter violates preregistered thresholds.
    """
    is_60d = "60d" in target_name.lower() or "residual" in target_name.lower()

    min_purge = 60 if is_60d else 20
    min_embargo = 10 if is_60d else 5

    if purge_days < min_purge:
        raise InvalidPurgeEmbargoConfigError(
            f"Purge days for {target_name} must be >= {min_purge} trading days, got {purge_days}"
        )
    if embargo_days < min_embargo:
        raise InvalidPurgeEmbargoConfigError(
            f"Embargo days for {target_name} must be >= {min_embargo} trading days, got {embargo_days}"
        )

    return purge_days, embargo_days


def compute_purge_interval(
    trading_calendar: Sequence[date],
    train_end_idx: int,
    purge_days: int,
) -> Tuple[date, date, Tuple[date, ...]]:
    """Compute the purge date range and individual purged trading sessions.

    The purge interval starts on the session immediately following train_end (train_end_idx + 1)
    and spans exactly `purge_days` trading sessions.

    Args:
        trading_calendar: Monotonically increasing list of trading dates.
        train_end_idx: Zero-based index of the final training session in the calendar.
        purge_days: Number of forward trading sessions to purge.

    Returns:
        Tuple of (purge_start_date, purge_end_date, purged_trading_dates).

    Raises:
        IndexError: If trading_calendar does not have enough sessions to cover the purge window.
        ValueError: If train_end_idx or purge_days is invalid.
    """
    if train_end_idx < 0 or train_end_idx >= len(trading_calendar):
        raise ValueError(f"train_end_idx {train_end_idx} out of bounds for calendar of length {len(trading_calendar)}")
    if purge_days <= 0:
        raise ValueError(f"purge_days must be positive, got {purge_days}")

    purge_start_idx = train_end_idx + 1
    purge_end_idx = train_end_idx + purge_days

    if purge_end_idx >= len(trading_calendar):
        raise IndexError(
            f"Trading calendar insufficient: requires index {purge_end_idx} for purge, but calendar ends at {len(trading_calendar) - 1}"
        )

    purged_dates = tuple(trading_calendar[purge_start_idx : purge_end_idx + 1])
    return purged_dates[0], purged_dates[-1], purged_dates


def compute_embargo_interval(
    trading_calendar: Sequence[date],
    test_end_idx: int,
    embargo_days: int,
) -> Tuple[Optional[date], Optional[date], Tuple[date, ...]]:
    """Compute the post-test embargo date range and individual embargoed trading sessions.

    The embargo starts on the session immediately following test_end (test_end_idx + 1)
    and spans `embargo_days` trading sessions.

    Args:
        trading_calendar: Monotonically increasing list of trading dates.
        test_end_idx: Zero-based index of the final test session in the calendar.
        embargo_days: Number of trading sessions to embargo.

    Returns:
        Tuple of (embargo_start_date, embargo_end_date, embargoed_trading_dates).
    """
    if test_end_idx < 0 or test_end_idx >= len(trading_calendar):
        raise ValueError(f"test_end_idx {test_end_idx} out of bounds for calendar of length {len(trading_calendar)}")
    if embargo_days < 0:
        raise ValueError(f"embargo_days cannot be negative, got {embargo_days}")
    if embargo_days == 0:
        return None, None, ()

    embargo_start_idx = test_end_idx + 1
    embargo_end_idx = test_end_idx + embargo_days

    # Cap at calendar boundary if calendar ends before full embargo
    available_end_idx = min(embargo_end_idx, len(trading_calendar) - 1)
    if embargo_start_idx > available_end_idx:
        return None, None, ()

    embargoed_dates = tuple(trading_calendar[embargo_start_idx : available_end_idx + 1])
    return embargoed_dates[0], embargoed_dates[-1], embargoed_dates


def verify_zero_label_leakage(
    train_dates: Sequence[date],
    test_dates: Sequence[date],
    horizon_trading_days: int,
    trading_calendar: Sequence[date],
) -> bool:
    """Mathematically verify that zero training label forward return horizons reach test observations.

    For each training date t_train, forward outcome return is finalized on t_train + H trading days.
    If any test observation t_test occurs on or before t_train + H, this constitutes label leakage.

    Args:
        train_dates: Collection of dates included in the training fold.
        test_dates: Collection of dates included in the test fold.
        horizon_trading_days: Target forward horizon in trading sessions (e.g. 20 or 60).
        trading_calendar: Full chronological calendar of trading sessions.

    Returns:
        True if zero label leakage is verified.

    Raises:
        ValidationLeakageError: If any training label outcome overlaps with any test date.
    """
    if not train_dates or not test_dates:
        return True

    cal_map = {d: idx for idx, d in enumerate(trading_calendar)}
    test_date_set = set(test_dates)

    latest_train_date = max(train_dates)
    earliest_test_date = min(test_dates)

    if latest_train_date not in cal_map:
        raise ValueError(f"Train date {latest_train_date} not in trading calendar.")
    if earliest_test_date not in cal_map:
        raise ValueError(f"Test date {earliest_test_date} not in trading calendar.")

    latest_train_idx = cal_map[latest_train_date]
    earliest_test_idx = cal_map[earliest_test_date]

    # Required separation: test start must be strictly greater than train_end + horizon
    required_earliest_test_idx = latest_train_idx + horizon_trading_days + 1

    if earliest_test_idx < required_earliest_test_idx:
        actual_gap = earliest_test_idx - latest_train_idx - 1
        raise ValidationLeakageError(
            f"[LABEL LEAKAGE] Training ends at session {latest_train_date} (idx {latest_train_idx}). "
            f"Forward {horizon_trading_days}d outcome extends through index {latest_train_idx + horizon_trading_days}. "
            f"Test starts prematurely at session {earliest_test_date} (idx {earliest_test_idx}). "
            f"Actual gap is {actual_gap} sessions; required purge gap is {horizon_trading_days} sessions."
        )

    # Check for direct set intersection
    overlap = set(train_dates).intersection(test_date_set)
    if overlap:
        raise ValidationLeakageError(
            f"[SET LEAKAGE] Train and test sets share {len(overlap)} identical dates: {sorted(list(overlap))[:5]}"
        )

    return True


def build_purge_embargo_interval(
    fold_index: int,
    trading_calendar: Sequence[date],
    train_end_idx: int,
    test_start_idx: int,
    test_end_idx: int,
    purge_days: int,
    embargo_days: int,
) -> PurgeEmbargoInterval:
    """Construct an immutable PurgeEmbargoInterval record.

    Args:
        fold_index: Zero-based fold identifier.
        trading_calendar: Monotonically increasing list of trading dates.
        train_end_idx: Calendar index of training set end.
        test_start_idx: Calendar index of test set start.
        test_end_idx: Calendar index of test set end.
        purge_days: Required purge trading sessions.
        embargo_days: Required embargo trading sessions.

    Returns:
        Immutable PurgeEmbargoInterval instance.
    """
    actual_purge_gap = test_start_idx - train_end_idx - 1
    if actual_purge_gap < purge_days:
        raise ValidationLeakageError(
            f"Actual gap between train end ({trading_calendar[train_end_idx]}) and test start "
            f"({trading_calendar[test_start_idx]}) is {actual_purge_gap} sessions; requires >= {purge_days}."
        )

    p_start, p_end, p_dates = compute_purge_interval(trading_calendar, train_end_idx, purge_days)
    e_start, e_end, e_dates = compute_embargo_interval(trading_calendar, test_end_idx, embargo_days)

    return PurgeEmbargoInterval(
        fold_index=fold_index,
        train_end_date=trading_calendar[train_end_idx],
        purge_start_date=p_start,
        purge_end_date=p_end,
        purge_trading_days=purge_days,
        test_start_date=trading_calendar[test_start_idx],
        test_end_date=trading_calendar[test_end_idx],
        test_trading_days=test_end_idx - test_start_idx + 1,
        embargo_start_date=e_start,
        embargo_end_date=e_end,
        embargo_trading_days=embargo_days,
        purged_trading_dates=p_dates,
        embargoed_trading_dates=e_dates,
    )
