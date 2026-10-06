"""20-Day Sector-Relative Target Calculation Engine for Phase 7.

Implements the frozen 20-trading-day sector-relative target:
    target_20d_sector_relative = stock_return_20d - sector_return_20d

Enforces:
1. Strict T+1 entry and 20th forward session exit alignment.
2. Identical entry and exit trading dates for stock and sector benchmark.
3. Point-in-time sector classification valid as of t (no static fallback, no future leak).
4. Compatible adjustment states between stock and sector benchmark.
5. Terminal event handling (suspension, delisting, corporate actions requiring review).
6. Fail-closed error handling with explicit reason codes.
"""

from decimal import Decimal
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from phase7.data.contracts import (
    CorporateActionRecord,
    CorporateActionType,
    EligibilityStatus,
    EligibilitySuspensionRecord,
    PITSectorClassificationRecord,
    PriceAdjustmentState,
)
from phase7.targets.alignment import align_forward_observations
from phase7.targets.contracts import (
    ForwardPriceObservationRecord,
    PredictionEventRecord,
    SectorBenchmarkObservationRecord,
    TargetReasonCode,
    TargetResultRecord,
    TargetSpecificationRecord,
    TargetStatus,
)
from phase7.targets.returns import calculate_discrete_return, validate_adjustment_compatibility


def resolve_pit_sector_classification(
    prediction_event: PredictionEventRecord,
    sector_records: Sequence[PITSectorClassificationRecord],
) -> Tuple[Optional[str], Optional[TargetReasonCode], str]:
    """Resolve point-in-time sector code active at prediction instant t.

    Rules:
    1. Must belong to the prediction symbol.
    2. source_timestamp <= prediction_event.prediction_timestamp (no lookahead).
    3. Half-open interval [effective_from, effective_to) covers prediction_trading_date.
    4. Conflicting classifications covering t return CONFLICTING_PIT_SECTOR.
    5. Future records only return FUTURE_SECTOR_DETECTED.
    6. If no valid record covers t, return MISSING_PIT_SECTOR (fails closed).
    """
    sym = prediction_event.symbol
    t_date = prediction_event.prediction_trading_date
    t_time = prediction_event.prediction_timestamp

    sym_records = [r for r in sector_records if r.symbol == sym]
    if not sym_records:
        return None, TargetReasonCode.MISSING_PIT_SECTOR, f"No sector classification history for symbol {sym}."

    # Check for future source timestamps
    future_records = [r for r in sym_records if r.source_timestamp > t_time]
    active_candidates: List[PITSectorClassificationRecord] = []

    for r in sym_records:
        # PIT boundary: source must be known before or at prediction time
        if r.source_timestamp > t_time:
            continue
        # Temporal validity range
        if r.effective_from <= t_date:
            if r.effective_to is None or r.effective_to > t_date:
                active_candidates.append(r)

    if not active_candidates:
        if future_records:
            return None, TargetReasonCode.FUTURE_SECTOR_DETECTED, f"Sector classifications for {sym} exist only after prediction instant {t_time}."
        return None, TargetReasonCode.MISSING_PIT_SECTOR, f"No valid point-in-time sector classification covering {t_date} for {sym}."

    # Check for multiple conflicting sector codes active simultaneously
    distinct_sectors = {r.sector_code for r in active_candidates}
    if len(distinct_sectors) > 1:
        return None, TargetReasonCode.CONFLICTING_PIT_SECTOR, f"Conflicting sector classifications on {t_date} for {sym}: {distinct_sectors}."

    # Exactly one valid active sector
    return active_candidates[0].sector_code, None, "Valid PIT sector classification resolved."


def calculate_20d_sector_relative_target(
    specification: TargetSpecificationRecord,
    prediction_event: PredictionEventRecord,
    stock_observations: Sequence[ForwardPriceObservationRecord],
    sector_classifications: Sequence[PITSectorClassificationRecord],
    sector_benchmarks: Sequence[SectorBenchmarkObservationRecord],
    suspensions: Sequence[EligibilitySuspensionRecord] = (),
    corporate_actions: Sequence[CorporateActionRecord] = (),
    source_dataset_versions: Optional[Dict[str, str]] = None,
) -> TargetResultRecord:
    """Calculate the 20-trading-day sector-relative forward target.

    Formula:
        target_20d_sector_relative = stock_return_20d - sector_return_20d
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

    # 2. Validate price adjustment compatibility
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

    # 3. Check for terminal events: regulatory suspension during forward horizon
    for susp in suspensions:
        if susp.symbol == prediction_event.symbol:
            # Active interval [effective_from, effective_to) intersects [entry_date, exit_date]
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
                    beta_used=None,
                    target_value=None,
                    target_status=TargetStatus.INVALID,
                    invalid_reason_codes=[reason],
                    source_dataset_versions=source_dataset_versions,
                )

    # 4. Check for corporate actions requiring manual review or delisting during forward horizon
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
                        beta_used=None,
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
                        beta_used=None,
                        target_value=None,
                        target_status=TargetStatus.INVALID,
                        invalid_reason_codes=[TargetReasonCode.CORPORATE_ACTION_REVIEW_REQUIRED],
                        source_dataset_versions=source_dataset_versions,
                    )

    # 5. Resolve point-in-time sector classification as of t
    sector_code, sector_reason, _ = resolve_pit_sector_classification(
        prediction_event=prediction_event,
        sector_records=sector_classifications,
    )
    if sector_code is None:
        assert sector_reason is not None
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
            target_status=TargetStatus.BLOCKED if sector_reason == TargetReasonCode.MISSING_PIT_SECTOR else TargetStatus.INVALID,
            invalid_reason_codes=[sector_reason],
            source_dataset_versions=source_dataset_versions,
        )

    # 6. Align sector benchmark observations on the exact same entry and exit dates
    sec_obs_by_date = {b.trading_date: b for b in sector_benchmarks if b.sector_code == sector_code}
    if entry_date not in sec_obs_by_date or exit_date not in sec_obs_by_date:
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
            invalid_reason_codes=[TargetReasonCode.MISSING_BENCHMARK],
            source_dataset_versions=source_dataset_versions,
        )

    sec_entry_obs = sec_obs_by_date[entry_date]
    sec_exit_obs = sec_obs_by_date[exit_date]

    # Validate benchmark adjustment state compatibility
    is_sec_compat, sec_adj_reason, _ = validate_adjustment_compatibility(
        entry_state=sec_entry_obs.adjustment_state,
        exit_state=sec_exit_obs.adjustment_state,
        required_state=specification.adjustment_state_requirement,
    )
    if not is_sec_compat:
        assert sec_adj_reason is not None
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
            invalid_reason_codes=[sec_adj_reason],
            source_dataset_versions=source_dataset_versions,
        )

    # 7. Compute returns
    try:
        stock_ret = calculate_discrete_return(entry_rec.price, exit_rec.price)
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
            beta_used=None,
            target_value=None,
            target_status=TargetStatus.INVALID,
            invalid_reason_codes=[TargetReasonCode.DATA_VALIDATION_FAILURE],
            source_dataset_versions=source_dataset_versions,
        )

    # Benchmark discrete return calculation
    if sec_entry_obs.price is not None and sec_exit_obs.price is not None:
        sec_ret = calculate_discrete_return(sec_entry_obs.price, sec_exit_obs.price)
    elif sec_exit_obs.return_value is not None:
        sec_ret = sec_exit_obs.return_value
    else:
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
            benchmark_total_return=None,
            beta_used=None,
            target_value=None,
            target_status=TargetStatus.INVALID,
            invalid_reason_codes=[TargetReasonCode.INVALID_BENCHMARK],
            source_dataset_versions=source_dataset_versions,
        )

    # 8. Compute sector-relative target
    target_value = stock_ret - sec_ret

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
        benchmark_total_return=sec_ret,
        beta_used=None,
        target_value=target_value,
        target_status=TargetStatus.VALID,
        invalid_reason_codes=[],
        source_dataset_versions=source_dataset_versions,
    )
