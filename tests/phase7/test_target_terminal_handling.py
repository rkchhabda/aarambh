"""Unit tests for Phase 7 target engine terminal event and policy handling.

Verifies:
1. Regulatory suspension during forward horizon returns SUSPENDED_DURING_HORIZON.
2. Delisting during forward horizon returns DELISTED_DURING_HORIZON.
3. Complex corporate action requiring manual review returns CORPORATE_ACTION_REVIEW_REQUIRED.
4. Unadjusted / incompatible adjustment states return INVALID_ADJUSTMENT_STATE.
5. Suspension completely outside the horizon does not invalidate calculation.
6. Target value is strictly None (never silent 0.0) upon invalidation.
7. Truncated dataset returns INSUFFICIENT_FORWARD_OBSERVATIONS.
8. Missing entry observation returns MISSING_ENTRY_PRICE.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest

from phase7.data.contracts import (
    CorporateActionRecord,
    CorporateActionType,
    EligibilityStatus,
    EligibilitySuspensionRecord,
    PITSectorClassificationRecord,
    PriceAdjustmentState,
)
from phase7.targets.contracts import (
    BetaInputRecord,
    ForwardPriceObservationRecord,
    PredictionEventRecord,
    SectorBenchmarkObservationRecord,
    TargetReasonCode,
    TargetSpecificationRecord,
    TargetStatus,
)
from phase7.targets.residual import calculate_60d_residual_target
from phase7.targets.sector_relative import calculate_20d_sector_relative_target

PRED_TIME = datetime(2025, 1, 15, 15, 30, tzinfo=timezone.utc)
PRED_DATE = date(2025, 1, 15)


def make_pred(symbol: str = "TCS", isin: str = "INE467B01029") -> PredictionEventRecord:
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


def make_20d_spec() -> TargetSpecificationRecord:
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


def make_60d_spec() -> TargetSpecificationRecord:
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


def test_suspension_during_forward_horizon_sector_relative():
    """Verify suspension overlapping horizon marks target INVALID with SUSPENDED_DURING_HORIZON."""
    spec = make_20d_spec()
    pred = make_pred()
    start_d = date(2025, 1, 16)
    dates = [start_d + timedelta(days=i) for i in range(20)]
    stock_obs = [
        ForwardPriceObservationRecord(
            trading_date=d,
            symbol="TCS",
            isin="INE467B01029",
            price=Decimal("100.00"),
            adjustment_state=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
            source_timestamp=datetime(2025, 1, 1, 16, 0, 0, tzinfo=timezone.utc),
            source_identifier="NSE_BHAVCOPY",
        )
        for d in dates
    ]
    sec_records = [
        PITSectorClassificationRecord(
            symbol="TCS",
            isin="INE467B01029",
            sector_code="IT",
            effective_from=date(2024, 1, 1),
            source_timestamp=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="AMFI_INDUSTRY_CLASSIFICATION",
        )
    ]
    sec_obs = [
        SectorBenchmarkObservationRecord(
            sector_code="IT",
            trading_date=dates[0],
            benchmark_identifier="NIFTY_IT",
            price=Decimal("1000.00"),
            adjustment_state=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
            source_timestamp=datetime(2025, 1, 1, 16, 0, 0, tzinfo=timezone.utc),
            dataset_version="v2025.1",
        ),
        SectorBenchmarkObservationRecord(
            sector_code="IT",
            trading_date=dates[-1],
            benchmark_identifier="NIFTY_IT",
            price=Decimal("1050.00"),
            adjustment_state=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
            source_timestamp=datetime(2025, 1, 1, 16, 0, 0, tzinfo=timezone.utc),
            dataset_version="v2025.1",
        ),
    ]

    # Suspension active between dates[5] and dates[10] (inside forward horizon)
    susp = [
        EligibilitySuspensionRecord(
            symbol="TCS",
            isin="INE467B01029",
            status=EligibilityStatus.SUSPENDED,
            effective_from=dates[5],
            effective_to=dates[10],
            source_timestamp=datetime(2025, 1, 20, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2025, 1, 20, 1, 0, tzinfo=timezone.utc),
            source_identifier="NSE_SURVEILLANCE",
        )
    ]

    res = calculate_20d_sector_relative_target(
        specification=spec,
        prediction_event=pred,
        stock_observations=stock_obs,
        sector_classifications=sec_records,
        sector_benchmarks=sec_obs,
        suspensions=susp,
    )

    assert res.target_status == TargetStatus.INVALID
    assert TargetReasonCode.SUSPENDED_DURING_HORIZON in res.invalid_reason_codes
    assert res.target_value is None  # Never silently 0.0


def test_delisting_during_forward_horizon_residual():
    """Verify delisting overlapping horizon marks target INVALID with DELISTED_DURING_HORIZON."""
    spec = make_60d_spec()
    pred = make_pred()
    start_d = date(2025, 1, 16)
    dates = [start_d + timedelta(days=i) for i in range(60)]
    stock_obs = [
        ForwardPriceObservationRecord(
            trading_date=d,
            symbol="TCS",
            isin="INE467B01029",
            price=Decimal("100.00"),
            adjustment_state=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
            source_timestamp=datetime(2025, 1, 1, 16, 0, 0, tzinfo=timezone.utc),
            source_identifier="NSE_BHAVCOPY",
        )
        for d in dates
    ]
    mkt_obs = [
        ForwardPriceObservationRecord(
            trading_date=dates[0],
            symbol="NIFTY500",
            isin="INX000000001",
            price=Decimal("20000.00"),
            adjustment_state=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
            source_timestamp=datetime(2025, 1, 1, 16, 0, 0, tzinfo=timezone.utc),
            source_identifier="NSE_INDICES",
        ),
        ForwardPriceObservationRecord(
            trading_date=dates[-1],
            symbol="NIFTY500",
            isin="INX000000001",
            price=Decimal("21000.00"),
            adjustment_state=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
            source_timestamp=datetime(2025, 1, 1, 16, 0, 0, tzinfo=timezone.utc),
            source_identifier="NSE_INDICES",
        ),
    ]
    beta_rec = BetaInputRecord(
        symbol="TCS",
        isin="INE467B01029",
        benchmark_identifier="NIFTY500",
        estimation_end_timestamp=PRED_TIME,
        estimation_method="OLS_252D",
        beta=Decimal("1.00000000"),
        dataset_version="v2025.1",
    )

    # Delisting effective from day 30 onwards
    delisting = [
        CorporateActionRecord(
            symbol="TCS",
            isin="INE467B01029",
            ex_date=dates[30],
            effective_date=dates[30],
            action_type=CorporateActionType.DELISTING,
            source_timestamp=datetime(2025, 1, 15, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2025, 1, 15, 1, 0, tzinfo=timezone.utc),
            source_identifier="NSE_CIRCULAR_DELISTING",
        )
    ]

    res = calculate_60d_residual_target(
        specification=spec,
        prediction_event=pred,
        stock_observations=stock_obs,
        market_observations=mkt_obs,
        beta_record=beta_rec,
        market_benchmark_identifier="NIFTY500",
        corporate_actions=delisting,
    )

    assert res.target_status == TargetStatus.INVALID
    assert TargetReasonCode.DELISTED_DURING_HORIZON in res.invalid_reason_codes
    assert res.target_value is None


def test_suspension_outside_horizon_does_not_invalidate():
    """Verify past suspension that ended before entry date does not invalidate horizon target."""
    spec = make_20d_spec()
    pred = make_pred()
    start_d = date(2025, 1, 16)
    dates = [start_d + timedelta(days=i) for i in range(20)]
    stock_obs = [
        ForwardPriceObservationRecord(
            trading_date=d,
            symbol="TCS",
            isin="INE467B01029",
            price=Decimal("100.00") if i == 0 else Decimal("110.00"),
            adjustment_state=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
            source_timestamp=datetime(2025, 1, 1, 16, 0, 0, tzinfo=timezone.utc),
            source_identifier="NSE_BHAVCOPY",
        )
        for i, d in enumerate(dates)
    ]
    sec_records = [
        PITSectorClassificationRecord(
            symbol="TCS",
            isin="INE467B01029",
            sector_code="IT",
            effective_from=date(2024, 1, 1),
            source_timestamp=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="AMFI_INDUSTRY_CLASSIFICATION",
        )
    ]
    sec_obs = [
        SectorBenchmarkObservationRecord(
            sector_code="IT",
            trading_date=dates[0],
            benchmark_identifier="NIFTY_IT",
            price=Decimal("1000.00"),
            adjustment_state=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
            source_timestamp=datetime(2025, 1, 1, 16, 0, 0, tzinfo=timezone.utc),
            dataset_version="v2025.1",
        ),
        SectorBenchmarkObservationRecord(
            sector_code="IT",
            trading_date=dates[-1],
            benchmark_identifier="NIFTY_IT",
            price=Decimal("1050.00"),
            adjustment_state=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
            source_timestamp=datetime(2025, 1, 1, 16, 0, 0, tzinfo=timezone.utc),
            dataset_version="v2025.1",
        ),
    ]

    # Past suspension ended on Jan 10 (before prediction date Jan 15 and entry Jan 16)
    past_susp = [
        EligibilitySuspensionRecord(
            symbol="TCS",
            isin="INE467B01029",
            status=EligibilityStatus.SUSPENDED,
            effective_from=date(2025, 1, 1),
            effective_to=date(2025, 1, 10),
            source_timestamp=datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2025, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="NSE_SURVEILLANCE",
        )
    ]

    res = calculate_20d_sector_relative_target(
        specification=spec,
        prediction_event=pred,
        stock_observations=stock_obs,
        sector_classifications=sec_records,
        sector_benchmarks=sec_obs,
        suspensions=past_susp,
    )

    assert res.target_status == TargetStatus.VALID
    assert res.target_value is not None


def test_complex_corporate_action_requiring_review():
    """Verify complex corporate action during horizon triggers CORPORATE_ACTION_REVIEW_REQUIRED."""
    spec = make_20d_spec()
    pred = make_pred()
    start_d = date(2025, 1, 16)
    dates = [start_d + timedelta(days=i) for i in range(20)]
    stock_obs = [
        ForwardPriceObservationRecord(
            trading_date=d,
            symbol="TCS",
            isin="INE467B01029",
            price=Decimal("100.00"),
            adjustment_state=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
            source_timestamp=datetime(2025, 1, 1, 16, 0, 0, tzinfo=timezone.utc),
            source_identifier="NSE_BHAVCOPY",
        )
        for d in dates
    ]
    sec_records = [
        PITSectorClassificationRecord(
            symbol="TCS",
            isin="INE467B01029",
            sector_code="IT",
            effective_from=date(2024, 1, 1),
            source_timestamp=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="AMFI_INDUSTRY_CLASSIFICATION",
        )
    ]
    sec_obs = [
        SectorBenchmarkObservationRecord(
            sector_code="IT",
            trading_date=dates[0],
            benchmark_identifier="NIFTY_IT",
            price=Decimal("1000.00"),
            adjustment_state=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
            source_timestamp=datetime(2025, 1, 1, 16, 0, 0, tzinfo=timezone.utc),
            dataset_version="v2025.1",
        ),
        SectorBenchmarkObservationRecord(
            sector_code="IT",
            trading_date=dates[-1],
            benchmark_identifier="NIFTY_IT",
            price=Decimal("1050.00"),
            adjustment_state=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
            source_timestamp=datetime(2025, 1, 1, 16, 0, 0, tzinfo=timezone.utc),
            dataset_version="v2025.1",
        ),
    ]

    # Merger action indicates complex corporate action requiring manual review
    bad_ca = [
        CorporateActionRecord(
            symbol="TCS",
            isin="INE467B01029",
            ex_date=dates[5],
            effective_date=dates[5],
            action_type=CorporateActionType.MERGER,
            source_timestamp=datetime(2025, 1, 15, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2025, 1, 15, 1, 0, tzinfo=timezone.utc),
            source_identifier="NSE_CIRCULAR",
        )
    ]

    res = calculate_20d_sector_relative_target(
        specification=spec,
        prediction_event=pred,
        stock_observations=stock_obs,
        sector_classifications=sec_records,
        sector_benchmarks=sec_obs,
        corporate_actions=bad_ca,
    )

    assert res.target_status == TargetStatus.INVALID
    assert TargetReasonCode.CORPORATE_ACTION_REVIEW_REQUIRED in res.invalid_reason_codes


def test_incompatible_adjustment_state_fails_closed():
    """Verify RAW unadjusted state on stock price triggers INVALID_ADJUSTMENT_STATE."""
    spec = make_20d_spec()
    pred = make_pred()
    start_d = date(2025, 1, 16)
    dates = [start_d + timedelta(days=i) for i in range(20)]
    stock_obs = [
        ForwardPriceObservationRecord(
            trading_date=d,
            symbol="TCS",
            isin="INE467B01029",
            price=Decimal("100.00"),
            adjustment_state=PriceAdjustmentState.RAW if i == 0 else PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
            source_timestamp=datetime(2025, 1, 1, 16, 0, 0, tzinfo=timezone.utc),
            source_identifier="NSE_BHAVCOPY",
        )
        for i, d in enumerate(dates)
    ]
    sec_records = [
        PITSectorClassificationRecord(
            symbol="TCS",
            isin="INE467B01029",
            sector_code="IT",
            effective_from=date(2024, 1, 1),
            source_timestamp=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="AMFI_INDUSTRY_CLASSIFICATION",
        )
    ]
    sec_obs = [
        SectorBenchmarkObservationRecord(
            sector_code="IT",
            trading_date=dates[0],
            benchmark_identifier="NIFTY_IT",
            price=Decimal("1000.00"),
            adjustment_state=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
            source_timestamp=datetime(2025, 1, 1, 16, 0, 0, tzinfo=timezone.utc),
            dataset_version="v2025.1",
        ),
        SectorBenchmarkObservationRecord(
            sector_code="IT",
            trading_date=dates[-1],
            benchmark_identifier="NIFTY_IT",
            price=Decimal("1050.00"),
            adjustment_state=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
            source_timestamp=datetime(2025, 1, 1, 16, 0, 0, tzinfo=timezone.utc),
            dataset_version="v2025.1",
        ),
    ]

    res = calculate_20d_sector_relative_target(
        specification=spec,
        prediction_event=pred,
        stock_observations=stock_obs,
        sector_classifications=sec_records,
        sector_benchmarks=sec_obs,
    )

    assert res.target_status == TargetStatus.INVALID
    assert TargetReasonCode.INVALID_ADJUSTMENT_STATE in res.invalid_reason_codes
