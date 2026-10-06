"""60-Day Beta-Adjusted Residual Target Calculation Engine for Phase 7.

Implements the frozen 60-trading-day residual target:
    target_60d_residual = stock_return_60d - (beta_at_t * market_return_60d)

Enforces:
1. Strict T+1 entry and 60th forward session exit alignment.
2. Beta estimate provenance and point-in-time validity (estimation_end <= t).
3. Rejection of future beta estimates (FUTURE_BETA_DETECTED).
4. Finite decimal validation for beta and returns.
5. Consistent market benchmark identifier alignment.
6. Preservation of stock return, market return, and beta separately in TargetResultRecord.
7. Terminal event handling (suspension, delisting, corporate actions requiring review).
"""

from datetime import date
from decimal import Decimal
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from phase7.data.contracts import (
    CorporateActionRecord,
    CorporateActionType,
    EligibilityStatus,
    EligibilitySuspensionRecord,
    PriceAdjustmentState,
)
from phase7.targets.alignment import align_forward_observations
from phase7.targets.contracts import (
    BetaInputRecord,
    ForwardPriceObservationRecord,
    PredictionEventRecord,
    TargetReasonCode,
    TargetResultRecord,
    TargetSpecificationRecord,
    TargetStatus,
)
from phase7.targets.returns import calculate_discrete_return, validate_adjustment_compatibility


def validate_beta_record(
    prediction_event: PredictionEventRecord,
    beta_record: Optional[BetaInputRecord],
    expected_benchmark_identifier: str,
) -> Tuple[bool, Optional[TargetReasonCode], str]:
    """Validate that the supplied beta estimate satisfies point-in-time constraints.

    Rules:
    1. Beta record must not be None (missing beta produces INVALID_BETA).
    2. Symbol and ISIN must match the prediction event.
    3. estimation_end_timestamp <= prediction_timestamp (future beta produces FUTURE_BETA_DETECTED).
    4. beta value must be finite.
    5. benchmark_identifier must match expected market benchmark.
    """
    if beta_record is None:
        return False, TargetReasonCode.INVALID_BETA, "Beta estimate is missing for prediction event."

    if beta_record.symbol != prediction_event.symbol:
        return (
            False,
            TargetReasonCode.INVALID_BETA,
            f"Beta symbol '{beta_record.symbol}' does not match prediction symbol '{prediction_event.symbol}'.",
        )

    if beta_record.isin != prediction_event.isin:
        return (
            False,
            TargetReasonCode.INVALID_BETA,
            f"Beta ISIN '{beta_record.isin}' does not match prediction ISIN '{prediction_event.isin}'.",
        )

    # Point-in-time check: beta must be estimated strictly prior to or at prediction instant
    if beta_record.estimation_end_timestamp > prediction_event.prediction_timestamp:
        return (
            False,
            TargetReasonCode.FUTURE_BETA_DETECTED,
            f"Beta estimation timestamp ({beta_record.estimation_end_timestamp}) is strictly after prediction timestamp ({prediction_event.prediction_timestamp}).",
        )

    if not beta_record.beta.is_finite():
        return False, TargetReasonCode.INVALID_BETA, f"Beta value is non-finite: {beta_record.beta}"

    clean_b_id = beta_record.benchmark_identifier.strip().upper()
    clean_expected = expected_benchmark_identifier.strip().upper()
    if clean_b_id != clean_expected:
        return (
            False,
            TargetReasonCode.INVALID_BENCHMARK,
            f"Beta benchmark identifier '{clean_b_id}' does not match market benchmark '{clean_expected}'.",
        )

    return True, None, "Beta record validated."


def calculate_60d_residual_target(
    specification: TargetSpecificationRecord,
    prediction_event: PredictionEventRecord,
    stock_observations: Sequence[ForwardPriceObservationRecord],
    market_observations: Sequence[ForwardPriceObservationRecord],
    beta_record: Optional[BetaInputRecord],
    market_benchmark_identifier: str,
    suspensions: Sequence[EligibilitySuspensionRecord] = (),
    corporate_actions: Sequence[CorporateActionRecord] = (),
    source_dataset_versions: Optional[Dict[str, str]] = None,
) -> TargetResultRecord:
    """Calculate the 60-trading-day beta-adjusted residual forward target.

    Formula:
        target_60d_residual = stock_return_60d - (beta_at_t * market_return_60d)
    """
    if source_dataset_versions is None:
        source_dataset_versions = {"dataset_version": prediction_event.dataset_version}

    target_name = specification.target_name
    target_version = specification.target_version
    horizon = specification.horizon_trading_days

    # 1. Align stock forward observations (T+1 entry, horizon-th exit)
    alignment = align_forward_observations(
        prediction_event=prediction_event,
        observations=stock_observations,
        horizon_trading_days=horizon,
        execution_lag_trading_days=specification.execution_lag_trading_days,
    )

    if alignment.status != TargetStatus.VALID:
        return TargetResultRecord(
            target_name=target_name,
            target_version=target_version,
            prediction_timestamp=prediction_event.prediction_timestamp,
            symbol=prediction_event.symbol,
            isin=prediction_event.isin,
            horizon_trading_days=horizon,
            entry_date=alignment.entry_record.trading_date if alignment.entry_record else None,
            exit_date=alignment.exit_record.trading_date if alignment.exit_record else None,
            stock_total_return=None,
            benchmark_total_return=None,
            beta_used=None,
            target_value=None,
            target_status=TargetStatus.INVALID,
            invalid_reason_codes=list(alignment.reason_codes),
            source_dataset_versions=source_dataset_versions,
        )

    entry_rec = alignment.entry_record
    exit_rec = alignment.exit_record
    assert entry_rec is not None and exit_rec is not None

    entry_date = entry_rec.trading_date
    exit_date = exit_rec.trading_date

    # 2. Validate stock price adjustment compatibility
    is_compat, adj_reason, _ = validate_adjustment_compatibility(
        entry_state=entry_rec.adjustment_state,
        exit_state=exit_rec.adjustment_state,
        required_state=specification.adjustment_state_requirement,
    )
    if not is_compat:
        assert adj_reason is not None
        return TargetResultRecord(
            target_name=target_name,
            target_version=target_version,
            prediction_timestamp=prediction_event.prediction_timestamp,
            symbol=prediction_event.symbol,
            isin=prediction_event.isin,
            horizon_trading_days=horizon,
            entry_date=entry_date,
            exit_date=exit_date,
            stock_total_return=None,
            benchmark_total_return=None,
            beta_used=None,
            target_value=None,
            target_status=TargetStatus.INVALID,
            invalid_reason_codes=[adj_reason],
            source_dataset_versions=source_dataset_versions,
        )

    # 3. Validate beta record
    is_beta_valid, beta_reason, _ = validate_beta_record(
        prediction_event=prediction_event,
        beta_record=beta_record,
        expected_benchmark_identifier=market_benchmark_identifier,
    )
    if not is_beta_valid:
        assert beta_reason is not None
        return TargetResultRecord(
            target_name=target_name,
            target_version=target_version,
            prediction_timestamp=prediction_event.prediction_timestamp,
            symbol=prediction_event.symbol,
            isin=prediction_event.isin,
            horizon_trading_days=horizon,
            entry_date=entry_date,
            exit_date=exit_date,
            stock_total_return=None,
            benchmark_total_return=None,
            beta_used=beta_record.beta if beta_record else None,
            target_value=None,
            target_status=TargetStatus.INVALID,
            invalid_reason_codes=[beta_reason],
            source_dataset_versions=source_dataset_versions,
        )

    assert beta_record is not None
    beta_val = beta_record.beta

    # 4. Check for regulatory suspension during forward horizon
    for susp in suspensions:
        if susp.symbol == prediction_event.symbol:
            end_d = susp.effective_to or date(9999, 12, 31)
            if susp.effective_from <= exit_date and end_d >= entry_date:
                status_str = str(getattr(susp.status, "value", susp.status)).upper()
                source_id = str(getattr(susp, "source_identifier", "")).lower()
                reason = (
                    TargetReasonCode.DELISTED_DURING_HORIZON
                    if (status_str == "DELISTED" or "delist" in source_id)
                    else TargetReasonCode.SUSPENDED_DURING_HORIZON
                )
                return TargetResultRecord(
                    target_name=target_name,
                    target_version=target_version,
                    prediction_timestamp=prediction_event.prediction_timestamp,
                    symbol=prediction_event.symbol,
                    isin=prediction_event.isin,
                    horizon_trading_days=horizon,
                    entry_date=entry_date,
                    exit_date=exit_date,
                    stock_total_return=None,
                    benchmark_total_return=None,
                    beta_used=beta_val,
                    target_value=None,
                    target_status=TargetStatus.INVALID,
                    invalid_reason_codes=[reason],
                    source_dataset_versions=source_dataset_versions,
                )

    # 5. Check for complex corporate actions requiring review or delisting during forward horizon
    for ca in corporate_actions:
        if getattr(ca, "symbol", "") == prediction_event.symbol:
            ex_d = getattr(ca, "ex_date", None)
            if ex_d is not None and entry_date <= ex_d <= exit_date:
                act_type = getattr(ca, "action_type", None)
                tot_factor = getattr(ca, "total_return_factor", None)
                num = getattr(ca, "adjustment_numerator", None)
                if act_type in (CorporateActionType.DELISTING, "DELISTING"):
                    return TargetResultRecord(
                        target_name=target_name,
                        target_version=target_version,
                        prediction_timestamp=prediction_event.prediction_timestamp,
                        symbol=prediction_event.symbol,
                        isin=prediction_event.isin,
                        horizon_trading_days=horizon,
                        entry_date=entry_date,
                        exit_date=exit_date,
                        stock_total_return=None,
                        benchmark_total_return=None,
                        beta_used=beta_val,
                        target_value=None,
                        target_status=TargetStatus.INVALID,
                        invalid_reason_codes=[TargetReasonCode.DELISTED_DURING_HORIZON],
                        source_dataset_versions=source_dataset_versions,
                    )
                complex_types = (
                    CorporateActionType.RIGHTS,
                    CorporateActionType.MERGER,
                    CorporateActionType.DEMERGER,
                    CorporateActionType.SYMBOL_CHANGE,
                    "RIGHTS",
                    "MERGER",
                    "DEMERGER",
                    "SYMBOL_CHANGE",
                )
                if (
                    act_type in complex_types
                    or (tot_factor is not None and tot_factor <= Decimal("0"))
                    or (num is not None and num <= Decimal("0"))
                ):
                    return TargetResultRecord(
                        target_name=target_name,
                        target_version=target_version,
                        prediction_timestamp=prediction_event.prediction_timestamp,
                        symbol=prediction_event.symbol,
                        isin=prediction_event.isin,
                        horizon_trading_days=horizon,
                        entry_date=entry_date,
                        exit_date=exit_date,
                        stock_total_return=None,
                        benchmark_total_return=None,
                        beta_used=beta_val,
                        target_value=None,
                        target_status=TargetStatus.INVALID,
                        invalid_reason_codes=[TargetReasonCode.CORPORATE_ACTION_REVIEW_REQUIRED],
                        source_dataset_versions=source_dataset_versions,
                    )

    # 6. Align market benchmark observations on exact same entry and exit dates
    mkt_obs_by_date = {m.trading_date: m for m in market_observations}
    if entry_date not in mkt_obs_by_date or exit_date not in mkt_obs_by_date:
        return TargetResultRecord(
            target_name=target_name,
            target_version=target_version,
            prediction_timestamp=prediction_event.prediction_timestamp,
            symbol=prediction_event.symbol,
            isin=prediction_event.isin,
            horizon_trading_days=horizon,
            entry_date=entry_date,
            exit_date=exit_date,
            stock_total_return=None,
            benchmark_total_return=None,
            beta_used=beta_val,
            target_value=None,
            target_status=TargetStatus.INVALID,
            invalid_reason_codes=[TargetReasonCode.MISSING_BENCHMARK],
            source_dataset_versions=source_dataset_versions,
        )

    mkt_entry_obs = mkt_obs_by_date[entry_date]
    mkt_exit_obs = mkt_obs_by_date[exit_date]

    # Validate market benchmark adjustment state compatibility
    is_mkt_compat, mkt_adj_reason, _ = validate_adjustment_compatibility(
        entry_state=mkt_entry_obs.adjustment_state,
        exit_state=mkt_exit_obs.adjustment_state,
        required_state=specification.adjustment_state_requirement,
    )
    if not is_mkt_compat:
        assert mkt_adj_reason is not None
        return TargetResultRecord(
            target_name=target_name,
            target_version=target_version,
            prediction_timestamp=prediction_event.prediction_timestamp,
            symbol=prediction_event.symbol,
            isin=prediction_event.isin,
            horizon_trading_days=horizon,
            entry_date=entry_date,
            exit_date=exit_date,
            stock_total_return=None,
            benchmark_total_return=None,
            beta_used=beta_val,
            target_value=None,
            target_status=TargetStatus.INVALID,
            invalid_reason_codes=[mkt_adj_reason],
            source_dataset_versions=source_dataset_versions,
        )

    # 7. Compute returns
    try:
        stock_ret = calculate_discrete_return(entry_rec.price, exit_rec.price)
        mkt_ret = calculate_discrete_return(mkt_entry_obs.price, mkt_exit_obs.price)
    except Exception:
        return TargetResultRecord(
            target_name=target_name,
            target_version=target_version,
            prediction_timestamp=prediction_event.prediction_timestamp,
            symbol=prediction_event.symbol,
            isin=prediction_event.isin,
            horizon_trading_days=horizon,
            entry_date=entry_date,
            exit_date=exit_date,
            stock_total_return=None,
            benchmark_total_return=None,
            beta_used=beta_val,
            target_value=None,
            target_status=TargetStatus.INVALID,
            invalid_reason_codes=[TargetReasonCode.DATA_VALIDATION_FAILURE],
            source_dataset_versions=source_dataset_versions,
        )

    # 8. Compute residual target: stock_return - (beta * market_return)
    target_value = stock_ret - (beta_val * mkt_ret)

    return TargetResultRecord(
        target_name=target_name,
        target_version=target_version,
        prediction_timestamp=prediction_event.prediction_timestamp,
        symbol=prediction_event.symbol,
        isin=prediction_event.isin,
        horizon_trading_days=horizon,
        entry_date=entry_date,
        exit_date=exit_date,
        stock_total_return=stock_ret,
        benchmark_total_return=mkt_ret,
        beta_used=beta_val,
        target_value=target_value,
        target_status=TargetStatus.VALID,
        invalid_reason_codes=[],
        source_dataset_versions=source_dataset_versions,
    )
