"""Unit tests for Phase 7 forward trading date alignment engine.

Verifies:
1. Normal forward session alignment (t+1 entry, t+H exit).
2. Skipping non-trading days (weekends, holidays) by session counting.
3. Strict rejection of same-day entry at t.
4. Fail-closed handling of missing entry observations.
5. Fail-closed handling of duplicate observation dates.
6. Fail-closed handling of insufficient forward sessions (truncation).
7. Deterministic sorting of unordered observation inputs.
8. Security identity validation (symbol and ISIN matching).
9. Validation of configuration arguments (horizon and lag).
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest

from phase7.data.contracts import PriceAdjustmentState
from phase7.targets.alignment import align_forward_observations, TargetAlignmentResult
from phase7.targets.contracts import (
    ForwardPriceObservationRecord,
    PredictionEventRecord,
    TargetReasonCode,
    TargetStatus,
)

PRED_TIME = datetime(2025, 1, 15, 15, 30, tzinfo=timezone.utc)
PRED_DATE = date(2025, 1, 15)  # Wednesday


def make_prediction_event(symbol: str = "INFY", isin: str = "INE009A01021") -> PredictionEventRecord:
    return PredictionEventRecord(
        prediction_timestamp=PRED_TIME,
        prediction_trading_date=PRED_DATE,
        symbol=symbol,
        isin=isin,
        universe_hash="u" * 64,
        dataset_version="v2025.1",
        source_cutoff_timestamp=PRED_TIME,
        target_specification_hash="s" * 64,
    )


def make_obs(
    trading_date: date,
    price: str = "100.00",
    symbol: str = "INFY",
    isin: str = "INE009A01021",
    adj_state: PriceAdjustmentState = PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
) -> ForwardPriceObservationRecord:
    return ForwardPriceObservationRecord(
        trading_date=trading_date,
        symbol=symbol,
        isin=isin,
        price=Decimal(price),
        adjustment_state=adj_state,
        source_timestamp=datetime(2025, 1, 1, 16, 0, 0, tzinfo=timezone.utc),
        source_identifier="NSE_BHAVCOPY",
    )


def test_normal_t_plus_1_alignment_20d():
    """Verify normal alignment selecting t+1 entry and t+20 exit."""
    pred = make_prediction_event()
    # 25 daily observations starting from t+1 (Jan 16)
    obs_list = [make_obs(date(2025, 1, 16) + timedelta(days=i)) for i in range(25)]

    result = align_forward_observations(
        prediction_event=pred,
        observations=obs_list,
        horizon_trading_days=20,
        execution_lag_trading_days=1,
    )

    assert result.status == TargetStatus.VALID
    assert result.entry_record is not None
    assert result.exit_record is not None
    assert result.entry_record.trading_date == date(2025, 1, 16)  # t+1
    assert result.exit_record.trading_date == date(2025, 1, 16) + timedelta(days=19)  # 20th session
    assert len(result.forward_observations) == 20
    assert result.reason_codes == []


def test_session_counting_skips_weekends_and_holidays():
    """Verify alignment counts trading sessions, not calendar days."""
    pred = make_prediction_event()
    trading_dates = [
        date(2025, 1, 16),  # Session 1 (Thu) - Entry
        date(2025, 1, 17),  # Session 2 (Fri)
        date(2025, 1, 20),  # Session 3 (Mon, skipped Sat/Sun)
        date(2025, 1, 21),  # Session 4 (Tue)
        date(2025, 1, 22),  # Session 5 (Wed) - Exit for 5-session horizon
    ]
    obs_list = [make_obs(d) for d in trading_dates]

    result = align_forward_observations(
        prediction_event=pred,
        observations=obs_list,
        horizon_trading_days=5,
        execution_lag_trading_days=1,
    )

    assert result.status == TargetStatus.VALID
    assert result.entry_record.trading_date == date(2025, 1, 16)
    assert result.exit_record.trading_date == date(2025, 1, 22)
    assert len(result.forward_observations) == 5


def test_same_day_entry_prohibited():
    """Verify observation on prediction date t is never used as entry."""
    pred = make_prediction_event()
    obs_list = [make_obs(PRED_DATE)]

    result = align_forward_observations(
        prediction_event=pred,
        observations=obs_list,
        horizon_trading_days=20,
        execution_lag_trading_days=1,
    )

    assert result.status == TargetStatus.INVALID
    assert TargetReasonCode.SAME_DAY_ENTRY_PROHIBITED in result.reason_codes
    assert TargetReasonCode.MISSING_ENTRY_PRICE in result.reason_codes
    assert result.entry_record is None
    assert result.exit_record is None


def test_missing_entry_price_when_empty():
    """Verify empty observation list fails closed with MISSING_ENTRY_PRICE."""
    pred = make_prediction_event()
    result = align_forward_observations(
        prediction_event=pred,
        observations=[],
        horizon_trading_days=20,
        execution_lag_trading_days=1,
    )

    assert result.status == TargetStatus.INVALID
    assert TargetReasonCode.MISSING_ENTRY_PRICE in result.reason_codes
    assert result.entry_record is None
    assert result.exit_record is None


def test_duplicate_date_observation_fails_closed():
    """Verify duplicate observation on same trading date is detected and rejected."""
    pred = make_prediction_event()
    obs_list = [
        make_obs(date(2025, 1, 16)),
        make_obs(date(2025, 1, 16)),  # Duplicate
        make_obs(date(2025, 1, 17)),
    ]

    result = align_forward_observations(
        prediction_event=pred,
        observations=obs_list,
        horizon_trading_days=20,
        execution_lag_trading_days=1,
    )

    assert result.status == TargetStatus.INVALID
    assert TargetReasonCode.DUPLICATE_DATE_OBSERVATION in result.reason_codes
    assert TargetReasonCode.DATA_VALIDATION_FAILURE in result.reason_codes


def test_insufficient_forward_observations_at_truncation():
    """Verify dataset truncation before horizon returns INSUFFICIENT_FORWARD_OBSERVATIONS."""
    pred = make_prediction_event()
    # Only 12 forward sessions when 20 are required
    obs_list = [make_obs(date(2025, 1, 16) + timedelta(days=i)) for i in range(12)]

    result = align_forward_observations(
        prediction_event=pred,
        observations=obs_list,
        horizon_trading_days=20,
        execution_lag_trading_days=1,
    )

    assert result.status == TargetStatus.INVALID
    assert TargetReasonCode.INSUFFICIENT_FORWARD_OBSERVATIONS in result.reason_codes
    assert TargetReasonCode.MISSING_EXIT_PRICE in result.reason_codes
    assert result.entry_record is not None
    assert result.entry_record.trading_date == date(2025, 1, 16)
    assert result.exit_record is None


def test_unordered_observation_inputs_sorted_deterministically():
    """Verify observations passed in reverse order are sorted deterministically."""
    pred = make_prediction_event()
    dates = [date(2025, 1, 16) + timedelta(days=i) for i in reversed(range(20))]
    obs_list = [make_obs(d) for d in dates]

    result = align_forward_observations(
        prediction_event=pred,
        observations=obs_list,
        horizon_trading_days=20,
        execution_lag_trading_days=1,
    )

    assert result.status == TargetStatus.VALID
    assert result.entry_record.trading_date == date(2025, 1, 16)
    assert result.exit_record.trading_date == date(2025, 1, 16) + timedelta(days=19)


def test_identity_mismatch_fails_closed():
    """Verify observation symbol or ISIN mismatch fails closed."""
    pred = make_prediction_event(symbol="INFY", isin="INE009A01021")

    # Mismatched symbol
    obs_bad_sym = [make_obs(date(2025, 1, 16), symbol="TCS", isin="INE009A01021")]
    res_sym = align_forward_observations(pred, obs_bad_sym, horizon_trading_days=20)
    assert res_sym.status == TargetStatus.INVALID
    assert TargetReasonCode.DATA_VALIDATION_FAILURE in res_sym.reason_codes

    # Mismatched ISIN
    obs_bad_isin = [make_obs(date(2025, 1, 16), symbol="INFY", isin="INE467B01029")]
    res_isin = align_forward_observations(pred, obs_bad_isin, horizon_trading_days=20)
    assert res_isin.status == TargetStatus.INVALID
    assert TargetReasonCode.DATA_VALIDATION_FAILURE in res_isin.reason_codes


def test_invalid_horizon_or_lag_raises_value_error():
    """Verify configuration validation for horizon and lag."""
    pred = make_prediction_event()
    obs_list = [make_obs(date(2025, 1, 16))]

    with pytest.raises(ValueError, match="horizon_trading_days must be positive"):
        align_forward_observations(pred, obs_list, horizon_trading_days=0)

    with pytest.raises(ValueError, match="execution_lag_trading_days must be >= 1"):
        align_forward_observations(pred, obs_list, horizon_trading_days=20, execution_lag_trading_days=0)


def test_frozen_endpoint_semantics_20d_and_60d():
    """Verify frozen Phase 7 endpoint semantics:
    - Horizon 20 selects observation 1 and observation 20; does NOT select observation 21.
    - Horizon 20 forward_observations contains 20 observations (19 intervals).
    - Horizon 60 selects observation 1 and observation 60; does NOT select observation 61.
    - Horizon 60 forward_observations contains 60 observations (59 intervals).
    - Same-day observation t is never selected.
    - Entry and exit dates are strictly preserved.
    """
    pred = make_prediction_event()
    same_day_obs = make_obs(PRED_DATE, price="99.00")

    # Generate 70 distinct post-prediction sessions
    forward_dates = [PRED_DATE + timedelta(days=i + 1) for i in range(70)]
    forward_obs = [make_obs(d, price=f"{100 + i}.00") for i, d in enumerate(forward_dates)]

    # Include same-day t observation in candidate pool to prove it is excluded
    all_obs = [same_day_obs] + forward_obs

    # --- Horizon 20 Evaluation ---
    res_20 = align_forward_observations(pred, all_obs, horizon_trading_days=20)
    assert res_20.status == TargetStatus.VALID
    # Obs 1 is selected as entry (t+1)
    assert res_20.entry_record.trading_date == forward_dates[0]
    assert res_20.entry_record.price == Decimal("100.00")
    # Obs 20 is selected as exit (t+20)
    assert res_20.exit_record.trading_date == forward_dates[19]
    assert res_20.exit_record.price == Decimal("119.00")
    # Obs 21 is NOT selected
    assert res_20.exit_record.trading_date != forward_dates[20]
    assert forward_obs[20] not in res_20.forward_observations
    # Count of observations in window is exactly 20, representing 19 intervals
    assert len(res_20.forward_observations) == 20
    assert len(res_20.forward_observations) - 1 == 19
    # Same day t is excluded
    assert same_day_obs not in res_20.forward_observations
    assert res_20.entry_record.trading_date > PRED_DATE

    # --- Horizon 60 Evaluation ---
    res_60 = align_forward_observations(pred, all_obs, horizon_trading_days=60)
    assert res_60.status == TargetStatus.VALID
    # Obs 1 is selected as entry (t+1)
    assert res_60.entry_record.trading_date == forward_dates[0]
    assert res_60.entry_record.price == Decimal("100.00")
    # Obs 60 is selected as exit (t+60)
    assert res_60.exit_record.trading_date == forward_dates[59]
    assert res_60.exit_record.price == Decimal("159.00")
    # Obs 61 is NOT selected
    assert res_60.exit_record.trading_date != forward_dates[60]
    assert forward_obs[60] not in res_60.forward_observations
    # Count of observations in window is exactly 60, representing 59 intervals
    assert len(res_60.forward_observations) == 60
    assert len(res_60.forward_observations) - 1 == 59
    # Same day t is excluded
    assert same_day_obs not in res_60.forward_observations
    assert res_60.entry_record.trading_date > PRED_DATE
