"""Unit tests for Phase 7 60-trading-day beta-adjusted residual target calculation engine.

Verifies:
1. Exact formula: target = stock_return_60d - (beta * market_return_60d).
2. Separate preservation of stock return, market return, and beta in result record.
3. Strict point-in-time beta validation (estimation_end_timestamp <= prediction_timestamp).
4. Rejection of future beta estimates (FUTURE_BETA_DETECTED).
5. Fail-closed handling when beta record is missing or non-finite.
6. Beta security identity validation (symbol and ISIN matching).
7. Benchmark identifier consistency between beta and market observations.
8. Missing market benchmark observations handling.
9. Price adjustment state validation (TOTAL_RETURN_ADJUSTED required).
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
import pytest

from phase7.data.contracts import PriceAdjustmentState
from phase7.targets.contracts import (
    BetaInputRecord,
    ForwardPriceObservationRecord,
    PredictionEventRecord,
    TargetReasonCode,
    TargetResultRecord,
    TargetSpecificationRecord,
    TargetStatus,
)
from phase7.targets.residual import (
    calculate_60d_residual_target,
    validate_beta_record,
)

PRED_TIME = datetime(2025, 1, 15, 15, 30, tzinfo=timezone.utc)
PRED_DATE = date(2025, 1, 15)


def make_spec() -> TargetSpecificationRecord:
    return TargetSpecificationRecord(
        target_name="target_60d_residual",
        target_version="1.0.0",
        horizon_trading_days=60,
        execution_lag_trading_days=1,
        entry_price_field="open",
        exit_price_field="close",
        return_type="TOTAL_RETURN_ADJUSTED",
        benchmark_type="MARKET",
        adjustment_state_requirement=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
        missing_terminal_policy="FAIL_CLOSED",
        suspension_policy="INVALIDATE_ON_SUSPENSION",
        delisting_policy="INVALIDATE_ON_DELISTING",
        created_timestamp=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )


def make_prediction_event(symbol: str = "RELIANCE", isin: str = "INE002A01018") -> PredictionEventRecord:
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


def make_stock_obs(
    trading_date: date,
    price: str,
    symbol: str = "RELIANCE",
    isin: str = "INE002A01018",
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


def make_market_obs(
    trading_date: date,
    price: str,
    adj_state: PriceAdjustmentState = PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
) -> ForwardPriceObservationRecord:
    return ForwardPriceObservationRecord(
        trading_date=trading_date,
        symbol="NIFTY500",
        isin="INX000000001",
        price=Decimal(price),
        adjustment_state=adj_state,
        source_timestamp=datetime(2025, 1, 1, 16, 0, 0, tzinfo=timezone.utc),
        source_identifier="NSE_INDICES",
    )


def make_beta(
    beta_str: str = "1.25000000",
    symbol: str = "RELIANCE",
    isin: str = "INE002A01018",
    benchmark_id: str = "NIFTY500",
    end_time: Optional[datetime] = None,
) -> BetaInputRecord:
    if end_time is None:
        end_time = datetime(2025, 1, 15, 15, 30, tzinfo=timezone.utc)
    return BetaInputRecord(
        symbol=symbol,
        isin=isin,
        beta=Decimal(beta_str),
        estimation_end_timestamp=end_time,
        estimation_method="OLS_252D",
        benchmark_identifier=benchmark_id,
        dataset_version="v2025.1",
    )


def test_60d_residual_target_calculation_success():
    """Verify formula: stock_ret - (beta * mkt_ret) and field preservation."""
    spec = make_spec()
    pred = make_prediction_event()

    start_d = date(2025, 1, 16)
    dates = [start_d + timedelta(days=i) for i in range(60)]

    # Stock: Entry 1000.00, Exit 1120.00 -> Return +0.12 (+12%)
    stock_obs = []
    for i, d in enumerate(dates):
        p = "1000.00" if i == 0 else ("1120.00" if i == 59 else "1050.00")
        stock_obs.append(make_stock_obs(d, price=p))

    # Market (Nifty 500): Entry 20000.00, Exit 21600.00 -> Return +0.08 (+8%)
    mkt_obs = [
        make_market_obs(dates[0], price="20000.00"),
        make_market_obs(dates[-1], price="21600.00"),
    ]

    # Beta = 1.25
    # Expected: stock_ret = 0.12000000, mkt_ret = 0.08000000
    # Expected target: 0.12 - (1.25 * 0.08) = 0.12 - 0.10 = 0.02
    beta_rec = make_beta("1.25000000")

    res = calculate_60d_residual_target(
        specification=spec,
        prediction_event=pred,
        stock_observations=stock_obs,
        market_observations=mkt_obs,
        beta_record=beta_rec,
        market_benchmark_identifier="NIFTY500",
    )

    assert res.target_status == TargetStatus.VALID
    assert res.stock_total_return == Decimal("0.12000000")
    assert res.benchmark_total_return == Decimal("0.08000000")
    assert res.beta_used == Decimal("1.25000000")
    assert res.target_value == Decimal("0.02000000")
    assert res.entry_date == dates[0]
    assert res.exit_date == dates[-1]
    assert res.invalid_reason_codes == []
    assert len(res.target_hash) == 64


def test_future_beta_estimate_rejected():
    """Beta estimated using data strictly after prediction instant fails closed."""
    spec = make_spec()
    pred = make_prediction_event()
    start_d = date(2025, 1, 16)
    dates = [start_d + timedelta(days=i) for i in range(60)]
    stock_obs = [make_stock_obs(d, price="1000.00") for d in dates]
    mkt_obs = [make_market_obs(dates[0], price="20000.00"), make_market_obs(dates[-1], price="21000.00")]

    # Beta end time is Jan 20 (future relative to prediction date Jan 15)
    future_time = datetime(2025, 1, 20, 15, 30, tzinfo=timezone.utc)
    beta_rec = make_beta(end_time=future_time)

    res = calculate_60d_residual_target(
        specification=spec,
        prediction_event=pred,
        stock_observations=stock_obs,
        market_observations=mkt_obs,
        beta_record=beta_rec,
        market_benchmark_identifier="NIFTY500",
    )

    assert res.target_status == TargetStatus.INVALID
    assert TargetReasonCode.FUTURE_BETA_DETECTED in res.invalid_reason_codes
    assert res.target_value is None


def test_missing_beta_fails_closed():
    """Missing beta record produces INVALID_BETA and fails closed."""
    spec = make_spec()
    pred = make_prediction_event()
    start_d = date(2025, 1, 16)
    dates = [start_d + timedelta(days=i) for i in range(60)]
    stock_obs = [make_stock_obs(d, price="1000.00") for d in dates]
    mkt_obs = [make_market_obs(dates[0], price="20000.00"), make_market_obs(dates[-1], price="21000.00")]

    res = calculate_60d_residual_target(
        specification=spec,
        prediction_event=pred,
        stock_observations=stock_obs,
        market_observations=mkt_obs,
        beta_record=None,
        market_benchmark_identifier="NIFTY500",
    )

    assert res.target_status == TargetStatus.INVALID
    assert TargetReasonCode.INVALID_BETA in res.invalid_reason_codes


def test_non_finite_beta_rejected():
    """Non-finite beta (NaN, Inf) produces INVALID_BETA."""
    pred = make_prediction_event()

    is_valid, reason, _ = validate_beta_record(
        prediction_event=pred,
        beta_record=None,
        expected_benchmark_identifier="NIFTY500",
    )
    assert not is_valid
    assert reason == TargetReasonCode.INVALID_BETA


def test_beta_identity_mismatch_rejected():
    """Beta record for different symbol/ISIN produces INVALID_BETA."""
    pred = make_prediction_event(symbol="RELIANCE", isin="INE002A01018")

    # Mismatched symbol
    beta_bad_sym = make_beta(symbol="INFY", isin="INE002A01018")
    is_v1, r1, _ = validate_beta_record(pred, beta_bad_sym, "NIFTY500")
    assert not is_v1
    assert r1 == TargetReasonCode.INVALID_BETA

    # Mismatched ISIN
    beta_bad_isin = make_beta(symbol="RELIANCE", isin="INE009A01021")
    is_v2, r2, _ = validate_beta_record(pred, beta_bad_isin, "NIFTY500")
    assert not is_v2
    assert r2 == TargetReasonCode.INVALID_BETA


def test_beta_benchmark_mismatch_rejected():
    """Beta estimated on NIFTY50 while target uses NIFTY500 produces INVALID_BENCHMARK."""
    pred = make_prediction_event()
    beta_nifty50 = make_beta(benchmark_id="NIFTY50")

    is_v, r, _ = validate_beta_record(pred, beta_nifty50, "NIFTY500")
    assert not is_v
    assert r == TargetReasonCode.INVALID_BENCHMARK


def test_missing_market_benchmark_observation():
    """Missing market observation on exit date fails closed with MISSING_BENCHMARK."""
    spec = make_spec()
    pred = make_prediction_event()
    start_d = date(2025, 1, 16)
    dates = [start_d + timedelta(days=i) for i in range(60)]
    stock_obs = [make_stock_obs(d, price="1000.00") for d in dates]
    # Only entry market obs provided
    mkt_obs = [make_market_obs(dates[0], price="20000.00")]
    beta_rec = make_beta("1.00000000")

    res = calculate_60d_residual_target(
        specification=spec,
        prediction_event=pred,
        stock_observations=stock_obs,
        market_observations=mkt_obs,
        beta_record=beta_rec,
        market_benchmark_identifier="NIFTY500",
    )

    assert res.target_status == TargetStatus.INVALID
    assert TargetReasonCode.MISSING_BENCHMARK in res.invalid_reason_codes


def test_market_benchmark_adjustment_state_violation():
    """Market benchmark with unadjusted prices fails closed with INVALID_ADJUSTMENT_STATE."""
    spec = make_spec()
    pred = make_prediction_event()
    start_d = date(2025, 1, 16)
    dates = [start_d + timedelta(days=i) for i in range(60)]
    stock_obs = [make_stock_obs(d, price="1000.00") for d in dates]
    # Market exit observation has RAW state
    mkt_obs = [
        make_market_obs(dates[0], price="20000.00"),
        make_market_obs(dates[-1], price="21000.00", adj_state=PriceAdjustmentState.RAW),
    ]
    beta_rec = make_beta("1.00000000")

    res = calculate_60d_residual_target(
        specification=spec,
        prediction_event=pred,
        stock_observations=stock_obs,
        market_observations=mkt_obs,
        beta_record=beta_rec,
        market_benchmark_identifier="NIFTY500",
    )

    assert res.target_status == TargetStatus.INVALID
    assert TargetReasonCode.INVALID_ADJUSTMENT_STATE in res.invalid_reason_codes
