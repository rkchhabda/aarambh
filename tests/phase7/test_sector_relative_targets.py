"""Unit tests for Phase 7 20-trading-day sector-relative target calculation engine.

Verifies:
1. Exact calculation: target = stock_return_20d - sector_return_20d.
2. Identical trading date matching between stock and sector benchmark.
3. Point-in-time sector classification resolution (no future leak, no static fallback).
4. Fail-closed handling when PIT sector classification is missing (status BLOCKED).
5. Fail-closed handling when conflicting PIT sector classifications exist.
6. Fail-closed handling when only future sector classifications exist.
7. Fail-closed handling when sector benchmark data is missing.
8. Price adjustment state validation (TOTAL_RETURN_ADJUSTED required).
9. Benchmark return provided via return_value field.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
import pytest

from phase7.data.contracts import (
    PITSectorClassificationRecord,
    PriceAdjustmentState,
)
from phase7.targets.contracts import (
    ForwardPriceObservationRecord,
    PredictionEventRecord,
    SectorBenchmarkObservationRecord,
    TargetReasonCode,
    TargetResultRecord,
    TargetSpecificationRecord,
    TargetStatus,
)
from phase7.targets.sector_relative import (
    calculate_20d_sector_relative_target,
    resolve_pit_sector_classification,
)

PRED_TIME = datetime(2025, 1, 15, 15, 30, tzinfo=timezone.utc)
PRED_DATE = date(2025, 1, 15)


def make_spec() -> TargetSpecificationRecord:
    return TargetSpecificationRecord(
        target_name="target_20d_sector_relative",
        target_version="1.0.0",
        horizon_trading_days=20,
        execution_lag_trading_days=1,
        entry_price_field="open",
        exit_price_field="close",
        return_type="TOTAL_RETURN_ADJUSTED",
        benchmark_type="SECTOR",
        adjustment_state_requirement=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
        missing_terminal_policy="FAIL_CLOSED",
        suspension_policy="INVALIDATE_ON_SUSPENSION",
        delisting_policy="INVALIDATE_ON_DELISTING",
        created_timestamp=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )


def make_prediction_event(symbol: str = "TCS", isin: str = "INE467B01029") -> PredictionEventRecord:
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
    symbol: str = "TCS",
    isin: str = "INE467B01029",
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


def make_sec_obs(
    trading_date: date,
    sector_code: str = "IT",
    price: Optional[str] = "1000.00",
    return_value: Optional[str] = None,
    adj_state: PriceAdjustmentState = PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
) -> SectorBenchmarkObservationRecord:
    return SectorBenchmarkObservationRecord(
        sector_code=sector_code,
        trading_date=trading_date,
        benchmark_identifier="NIFTY_IT",
        price=Decimal(price) if price is not None else None,
        return_value=Decimal(return_value) if return_value is not None else None,
        adjustment_state=adj_state,
        source_timestamp=datetime(2025, 1, 1, 16, 0, 0, tzinfo=timezone.utc),
        dataset_version="v2025.1",
    )


def make_pit_sector(
    symbol: str = "TCS",
    isin: str = "INE467B01029",
    sector_code: str = "IT",
    effective_from: date = date(2024, 1, 1),
    effective_to: Optional[date] = None,
    source_timestamp: Optional[datetime] = None,
) -> PITSectorClassificationRecord:
    if source_timestamp is None:
        source_timestamp = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    return PITSectorClassificationRecord(
        symbol=symbol,
        isin=isin,
        sector_code=sector_code,
        effective_from=effective_from,
        effective_to=effective_to,
        source_timestamp=source_timestamp,
        ingestion_timestamp=datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        source_identifier="AMFI_INDUSTRY_CLASSIFICATION",
    )


def test_20d_sector_relative_target_calculation_success():
    """Verify exact formula: stock return - sector return."""
    spec = make_spec()
    pred = make_prediction_event()

    # 20 trading dates starting from t+1
    start_d = date(2025, 1, 16)
    trading_dates = [start_d + timedelta(days=i) for i in range(20)]

    # Stock: Entry 100.00 on day 0, Exit 110.00 on day 19 -> Return +0.10 (+10%)
    stock_obs = []
    for i, d in enumerate(trading_dates):
        p = "100.00" if i == 0 else ("110.00" if i == 19 else "105.00")
        stock_obs.append(make_stock_obs(d, price=p))

    # Sector IT: Entry 1000.00 on day 0, Exit 1040.00 on day 19 -> Return +0.04 (+4%)
    sec_obs = [
        make_sec_obs(trading_dates[0], sector_code="IT", price="1000.00"),
        make_sec_obs(trading_dates[-1], sector_code="IT", price="1040.00"),
    ]

    sector_records = [make_pit_sector()]

    res = calculate_20d_sector_relative_target(
        specification=spec,
        prediction_event=pred,
        stock_observations=stock_obs,
        sector_classifications=sector_records,
        sector_benchmarks=sec_obs,
    )

    assert res.target_status == TargetStatus.VALID
    assert res.stock_total_return == Decimal("0.10000000")
    assert res.benchmark_total_return == Decimal("0.04000000")
    assert res.target_value == Decimal("0.06000000")
    assert res.entry_date == trading_dates[0]
    assert res.exit_date == trading_dates[-1]
    assert res.invalid_reason_codes == []
    assert len(res.target_hash) == 64


def test_missing_pit_sector_fails_closed_as_blocked():
    """Missing PIT sector classification returns BLOCKED status with MISSING_PIT_SECTOR."""
    spec = make_spec()
    pred = make_prediction_event(symbol="UNKNOWN_CO", isin="INE999A01099")

    stock_obs = [
        make_stock_obs(date(2025, 1, 16) + timedelta(days=i), price="100.00", symbol="UNKNOWN_CO", isin="INE999A01099")
        for i in range(20)
    ]
    sector_records = [make_pit_sector(symbol="TCS", isin="INE467B01029")]  # Only TCS available

    res = calculate_20d_sector_relative_target(
        specification=spec,
        prediction_event=pred,
        stock_observations=stock_obs,
        sector_classifications=sector_records,
        sector_benchmarks=[],
    )

    assert res.target_status == TargetStatus.BLOCKED
    assert TargetReasonCode.MISSING_PIT_SECTOR in res.invalid_reason_codes
    assert res.target_value is None


def test_conflicting_pit_sector_fails_closed():
    """Multiple overlapping sector records for the same symbol at t fail closed."""
    spec = make_spec()
    pred = make_prediction_event()

    stock_obs = [make_stock_obs(date(2025, 1, 16) + timedelta(days=i), price="100.00") for i in range(20)]
    sector_records = [
        make_pit_sector(symbol="TCS", sector_code="IT"),
        make_pit_sector(symbol="TCS", sector_code="FINANCIALS"),
    ]

    res = calculate_20d_sector_relative_target(
        specification=spec,
        prediction_event=pred,
        stock_observations=stock_obs,
        sector_classifications=sector_records,
        sector_benchmarks=[],
    )

    assert res.target_status == TargetStatus.INVALID
    assert TargetReasonCode.CONFLICTING_PIT_SECTOR in res.invalid_reason_codes


def test_future_sector_record_leak_prevention():
    """Sector record with source_timestamp > t is rejected as FUTURE_SECTOR_DETECTED."""
    spec = make_spec()
    pred = make_prediction_event()

    stock_obs = [make_stock_obs(date(2025, 1, 16) + timedelta(days=i), price="100.00") for i in range(20)]
    future_time = datetime(2025, 2, 1, 0, 0, tzinfo=timezone.utc)
    sector_records = [
        make_pit_sector(symbol="TCS", source_timestamp=future_time),
    ]

    res = calculate_20d_sector_relative_target(
        specification=spec,
        prediction_event=pred,
        stock_observations=stock_obs,
        sector_classifications=sector_records,
        sector_benchmarks=[],
    )

    assert res.target_status == TargetStatus.INVALID
    assert TargetReasonCode.FUTURE_SECTOR_DETECTED in res.invalid_reason_codes


def test_missing_sector_benchmark_observations():
    """Missing benchmark observation on exit date fails closed with MISSING_BENCHMARK."""
    spec = make_spec()
    pred = make_prediction_event()

    stock_obs = [make_stock_obs(date(2025, 1, 16) + timedelta(days=i), price="100.00") for i in range(20)]
    sector_records = [make_pit_sector()]

    # Only entry benchmark observation provided, exit missing
    sec_obs = [
        make_sec_obs(date(2025, 1, 16), sector_code="IT", price="1000.00"),
    ]

    res = calculate_20d_sector_relative_target(
        specification=spec,
        prediction_event=pred,
        stock_observations=stock_obs,
        sector_classifications=sector_records,
        sector_benchmarks=sec_obs,
    )

    assert res.target_status == TargetStatus.INVALID
    assert TargetReasonCode.MISSING_BENCHMARK in res.invalid_reason_codes


def test_incompatible_adjustment_state_rejected():
    """Stock observation with UNADJUSTED state violates specification requirement."""
    spec = make_spec()
    pred = make_prediction_event()

    # Entry is UNADJUSTED
    stock_obs = [
        make_stock_obs(
            date(2025, 1, 16) + timedelta(days=i),
            price="100.00",
            adj_state=PriceAdjustmentState.RAW if i == 0 else PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
        )
        for i in range(20)
    ]
    sector_records = [make_pit_sector()]
    sec_obs = [
        make_sec_obs(date(2025, 1, 16), sector_code="IT", price="1000.00"),
        make_sec_obs(date(2025, 1, 16) + timedelta(days=19), sector_code="IT", price="1040.00"),
    ]

    res = calculate_20d_sector_relative_target(
        specification=spec,
        prediction_event=pred,
        stock_observations=stock_obs,
        sector_classifications=sector_records,
        sector_benchmarks=sec_obs,
    )

    assert res.target_status == TargetStatus.INVALID
    assert TargetReasonCode.INVALID_ADJUSTMENT_STATE in res.invalid_reason_codes


def test_sector_benchmark_with_direct_return_value():
    """Verify sector benchmark providing return_value directly is supported."""
    spec = make_spec()
    pred = make_prediction_event()

    stock_obs = [
        make_stock_obs(
            date(2025, 1, 16) + timedelta(days=i),
            price="100.00" if i == 0 else ("115.00" if i == 19 else "105.00"),
        )
        for i in range(20)
    ]
    sector_records = [make_pit_sector()]

    # Exit record specifies return_value directly (+5%)
    sec_obs = [
        make_sec_obs(date(2025, 1, 16), sector_code="IT", price=None, return_value=Decimal("0.0")),
        make_sec_obs(date(2025, 1, 16) + timedelta(days=19), sector_code="IT", price=None, return_value="0.05000000"),
    ]

    res = calculate_20d_sector_relative_target(
        specification=spec,
        prediction_event=pred,
        stock_observations=stock_obs,
        sector_classifications=sector_records,
        sector_benchmarks=sec_obs,
    )

    assert res.target_status == TargetStatus.VALID
    assert res.stock_total_return == Decimal("0.15000000")
    assert res.benchmark_total_return == Decimal("0.05000000")
    assert res.target_value == Decimal("0.10000000")
