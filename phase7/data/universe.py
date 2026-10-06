"""Point-in-Time Universe Builder for GaurviDEEP Phase 7.

Constructs the daily/weekly investable universe from point-in-time constituent
membership, multi-factor liquidity filters, trading history count, sector mapping,
and active suspension status.

Governing Preregistration: docs/PHASE7_RESEARCH_PREREGISTRATION.md
Enforces:
1. Zero survivorship bias (half-open historical index intervals).
2. Fail-closed exclusion on unknown timing or missing data.
3. 252-day valid trading history minimum.
4. 60-day Median Daily Traded Value >= INR 10 crore (INR 100,000,000).
5. Minimum closing price >= INR 20.00.
6. The static legacy universe is prohibited as a Phase 7 universe provider and protected by automated boundary tests.
7. Static current sector mappings may be used only in explicitly labelled synthetic tests or non-historical display contexts. Historical sector-relative research fails closed without valid point-in-time sector classification.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set

from phase7.data.contracts import (
    DailyPriceRecord,
    EligibilityStatus,
    EligibilitySuspensionRecord,
    ExclusionReason,
    PITMembershipRecord,
    PITSectorClassificationRecord,
    PriceAdjustmentState,
    TradedValueStatus,
)


class UniverseBuildStatus(str, Enum):
    """Execution outcome status for point-in-time universe construction."""
    SUCCESS = "SUCCESS"
    BLOCKED_MISSING_MEMBERSHIP = "BLOCKED_MISSING_MEMBERSHIP"
    BLOCKED_MISSING_PRICE_LIQUIDITY = "BLOCKED_MISSING_PRICE_LIQUIDITY"
    BLOCKED_MISSING_SECTOR_HISTORY = "BLOCKED_MISSING_SECTOR_HISTORY"
    VALID_EMPTY_UNIVERSE = "VALID_EMPTY_UNIVERSE"
    DATA_VALIDATION_FAILURE = "DATA_VALIDATION_FAILURE"
    # Documented compatibility alias
    BLOCKED = "BLOCKED_MISSING_MEMBERSHIP"


@dataclass(frozen=True)
class UniverseBuildResult:
    """Immutable audit container reporting point-in-time eligible universe."""
    prediction_timestamp: datetime
    prediction_date: date
    eligible_symbols: List[str]
    eligible_isins: List[str]
    exclusions: Dict[str, List[ExclusionReason]]
    evidence: Dict[str, Dict[str, Any]]
    universe_hash: str
    status: UniverseBuildStatus
    config_version: str
    dataset_version: str
    blockers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    future_records_count: int = 0

    @property
    def is_real_data_blocked(self) -> bool:
        return self.status in (
            UniverseBuildStatus.BLOCKED_MISSING_MEMBERSHIP,
            UniverseBuildStatus.BLOCKED_MISSING_PRICE_LIQUIDITY,
            UniverseBuildStatus.BLOCKED_MISSING_SECTOR_HISTORY,
            UniverseBuildStatus.DATA_VALIDATION_FAILURE,
        )


class PointInTimeUniverseBuilder:
    """Fail-closed universe constructor enforcing Phase 7 Gate 1 eligibility rules."""

    MIN_PRICE_INR = Decimal("20.00")
    MIN_HISTORY_OBSERVATIONS = 252
    MIN_LIQUIDITY_LOOKBACK = 60
    MIN_MDTV_INR = Decimal("100000000.00")  # INR 10 crore (100 million)

    def __init__(
        self,
        min_price_inr: Decimal = MIN_PRICE_INR,
        min_history_observations: int = MIN_HISTORY_OBSERVATIONS,
        min_mdtv_inr: Decimal = MIN_MDTV_INR,
        config_version: str = "1.0.0",
    ) -> None:
        self.min_price_inr = min_price_inr
        self.min_history_observations = min_history_observations
        self.min_mdtv_inr = min_mdtv_inr
        self.config_version = config_version

    def build_universe(
        self,
        prediction_timestamp: datetime,
        membership_records: Sequence[PITMembershipRecord],
        price_records: Sequence[DailyPriceRecord],
        sector_records: Sequence[PITSectorClassificationRecord],
        suspension_records: Optional[Sequence[EligibilitySuspensionRecord]] = None,
        dataset_version: str = "v1.0",
        is_mock_test: bool = False,
    ) -> UniverseBuildResult:
        """Construct the eligible universe as of prediction_timestamp.

        Args:
            prediction_timestamp: UTC timezone-aware prediction instant.
            membership_records: Point-in-time index constituent intervals.
            price_records: Historical daily prices and traded values.
            sector_records: Point-in-time sector classifications.
            suspension_records: Point-in-time regulatory suspensions.
            dataset_version: Provenance identifier for the input data snapshot.
            is_mock_test: Set to True strictly for unit tests with synthetic fixtures.
        """
        if prediction_timestamp.tzinfo is None:
            raise ValueError("prediction_timestamp must be timezone-aware (UTC).")
        pred_utc = prediction_timestamp.astimezone(timezone.utc)
        pred_date = pred_utc.date()

        blockers: List[str] = []
        warnings: List[str] = []

        # Check dataset-wide structural validity
        if not dataset_version or not isinstance(dataset_version, str) or dataset_version.strip() == "" or dataset_version.upper() == "INVALID":
            blockers.append("FATAL: Dataset version is invalid or corrupted.")
            return UniverseBuildResult(
                prediction_timestamp=pred_utc,
                prediction_date=pred_date,
                eligible_symbols=[],
                eligible_isins=[],
                exclusions={},
                evidence={},
                universe_hash=hashlib.sha256(b"DATA_VALIDATION_FAILURE").hexdigest(),
                status=UniverseBuildStatus.DATA_VALIDATION_FAILURE,
                config_version=self.config_version,
                dataset_version=dataset_version,
                blockers=blockers,
                warnings=warnings,
                future_records_count=0,
            )

        if membership_records and any(m.index_code not in ("NIFTY500", "NIFTY_500") for m in membership_records):
            blockers.append("FATAL: Dataset contains unsupported or corrupted index code.")
            return UniverseBuildResult(
                prediction_timestamp=pred_utc,
                prediction_date=pred_date,
                eligible_symbols=[],
                eligible_isins=[],
                exclusions={},
                evidence={},
                universe_hash=hashlib.sha256(b"DATA_VALIDATION_FAILURE").hexdigest(),
                status=UniverseBuildStatus.DATA_VALIDATION_FAILURE,
                config_version=self.config_version,
                dataset_version=dataset_version,
                blockers=blockers,
                warnings=warnings,
                future_records_count=0,
            )

        # Count future records across all input collections
        future_records_count = 0
        for p in price_records:
            if p.source_timestamp > pred_utc or p.trading_date > pred_date:
                future_records_count += 1
        for m in membership_records:
            if m.source_timestamp > pred_utc:
                future_records_count += 1
        for s in sector_records:
            if s.source_timestamp > pred_utc:
                future_records_count += 1
        if suspension_records:
            for susp in suspension_records:
                if susp.source_timestamp > pred_utc:
                    future_records_count += 1

        if future_records_count > 0:
            warnings.append(f"Audit: Detected {future_records_count} future record(s) relative to prediction instant.")

        # If real datasets are empty and not a unit test fixture, fail closed under BLK-01 / BLK-02 / BLK-04
        if not membership_records and not is_mock_test:
            blockers.append("BLK-01: Point-in-time historical Nifty 500 constituent membership is missing.")
            return UniverseBuildResult(
                prediction_timestamp=pred_utc,
                prediction_date=pred_date,
                eligible_symbols=[],
                eligible_isins=[],
                exclusions={},
                evidence={},
                universe_hash=hashlib.sha256(b"BLOCKED_BLK01").hexdigest(),
                status=UniverseBuildStatus.BLOCKED_MISSING_MEMBERSHIP,
                config_version=self.config_version,
                dataset_version=dataset_version,
                blockers=blockers,
                warnings=warnings,
                future_records_count=future_records_count,
            )

        if not price_records and not is_mock_test:
            blockers.append("BLK-02: Complete historical OHLCV and daily traded value are missing.")
            return UniverseBuildResult(
                prediction_timestamp=pred_utc,
                prediction_date=pred_date,
                eligible_symbols=[],
                eligible_isins=[],
                exclusions={},
                evidence={},
                universe_hash=hashlib.sha256(b"BLOCKED_BLK02").hexdigest(),
                status=UniverseBuildStatus.BLOCKED_MISSING_PRICE_LIQUIDITY,
                config_version=self.config_version,
                dataset_version=dataset_version,
                blockers=blockers,
                warnings=warnings,
                future_records_count=future_records_count,
            )

        if not sector_records and not is_mock_test:
            blockers.append(
                "BLK-04: Static current sector mappings are prohibited as historical fallback. "
                "Historical sector-relative research remains blocked without valid point-in-time classification."
            )
            return UniverseBuildResult(
                prediction_timestamp=pred_utc,
                prediction_date=pred_date,
                eligible_symbols=[],
                eligible_isins=[],
                exclusions={},
                evidence={},
                universe_hash=hashlib.sha256(b"BLOCKED_BLK04").hexdigest(),
                status=UniverseBuildStatus.BLOCKED_MISSING_SECTOR_HISTORY,
                config_version=self.config_version,
                dataset_version=dataset_version,
                blockers=blockers,
                warnings=warnings,
                future_records_count=future_records_count,
            )

        # 1. Identify active constituents on pred_date
        membership_symbols = {m.symbol for m in membership_records}
        all_symbols: Set[str] = membership_symbols | {p.symbol for p in price_records}
        symbol_to_isin: Dict[str, str] = {m.symbol: m.isin for m in membership_records}
        active_constituents: Set[str] = set()

        for m in membership_records:
            # Check source timestamp strictly <= prediction_timestamp
            if m.source_timestamp > pred_utc:
                continue
            if m.is_active_on(pred_date):
                active_constituents.add(m.symbol)

        # 2. Group prices by symbol, filtering available prices on or before pred_utc
        prices_by_symbol: Dict[str, List[DailyPriceRecord]] = defaultdict(list)
        for p in price_records:
            if p.source_timestamp <= pred_utc and p.trading_date <= pred_date:
                prices_by_symbol[p.symbol].append(p)
                if p.symbol not in symbol_to_isin:
                    symbol_to_isin[p.symbol] = p.isin

        # 3. Group sectors by symbol
        sectors_by_symbol: Dict[str, List[PITSectorClassificationRecord]] = defaultdict(list)
        for s in sector_records:
            if s.source_timestamp <= pred_utc:
                sectors_by_symbol[s.symbol].append(s)

        # 4. Group suspensions by symbol
        suspensions_by_symbol: Dict[str, List[EligibilitySuspensionRecord]] = defaultdict(list)
        if suspension_records:
            for susp in suspension_records:
                if susp.source_timestamp <= pred_utc:
                    suspensions_by_symbol[susp.symbol].append(susp)

        # 5. Evaluate eligibility for all candidate securities
        eligible_symbols: List[str] = []
        eligible_isins: List[str] = []
        exclusions: Dict[str, List[ExclusionReason]] = {}
        evidence: Dict[str, Dict[str, Any]] = {}

        for sym in sorted(all_symbols):
            reasons: List[ExclusionReason] = []
            ev: Dict[str, Any] = {"symbol": sym, "isin": symbol_to_isin.get(sym, "")}

            # Check for future data
            sym_raw_prices = [p for p in price_records if p.symbol == sym]
            sym_raw_memberships = [m for m in membership_records if m.symbol == sym]
            sym_raw_sectors = [s for s in sector_records if s.symbol == sym]
            sym_future_count = (
                sum(1 for p in sym_raw_prices if p.source_timestamp > pred_utc or p.trading_date > pred_date)
                + sum(1 for m in sym_raw_memberships if m.source_timestamp > pred_utc)
                + sum(1 for s in sym_raw_sectors if s.source_timestamp > pred_utc)
            )
            if sym_future_count > 0:
                reasons.append(ExclusionReason.FUTURE_DATA_DETECTED)
                ev["future_records_count"] = sym_future_count

            # Security-level structural data validation failure checks
            if any(
                p.traded_value_status == TradedValueStatus.INVALID
                or p.price_adjustment_state == PriceAdjustmentState.UNKNOWN
                for p in sym_raw_prices
            ):
                reasons.append(ExclusionReason.DATA_VALIDATION_FAILURE)
                ev["data_validation_error"] = "INVALID_PRICE_RECORD_OR_UNKNOWN_STATE"

            sym_isins = {p.isin for p in sym_raw_prices if p.isin} | {m.isin for m in sym_raw_memberships if m.isin}
            if len(sym_isins) > 1:
                reasons.append(ExclusionReason.DATA_VALIDATION_FAILURE)
                ev["data_validation_error"] = "CONFLICTING_ISINS"

            # Rule 1: Point-in-Time Membership
            if sym not in membership_symbols:
                reasons.append(ExclusionReason.MISSING_MEMBERSHIP_HISTORY)
                ev["membership_status"] = "MISSING_MEMBERSHIP_HISTORY"
            elif sym not in active_constituents:
                reasons.append(ExclusionReason.NOT_IN_PIT_UNIVERSE)
                ev["membership_status"] = "INACTIVE_OR_EXCLUDED"
            else:
                ev["membership_status"] = "ACTIVE"

            # Rule 2: ISIN check
            isin_val = symbol_to_isin.get(sym, "")
            if not isin_val:
                reasons.append(ExclusionReason.MISSING_ISIN)

            # Rule 3: Trading History & Minimum Price
            sym_prices = prices_by_symbol.get(sym, [])

            # Check for duplicate date records with conflicting close
            date_counts: Dict[date, List[DailyPriceRecord]] = defaultdict(list)
            for p in sym_prices:
                date_counts[p.trading_date].append(p)
            for d, plist in date_counts.items():
                if len(plist) > 1 and len(set(x.close for x in plist)) > 1:
                    reasons.append(ExclusionReason.DUPLICATE_SECURITY_RECORD)
                    break

            # Deduplicate by trading date (keep latest)
            date_map: Dict[date, DailyPriceRecord] = {p.trading_date: p for p in sym_prices}
            sorted_dates = sorted(date_map.keys())
            obs_count = len(sorted_dates)
            ev["valid_history_count"] = obs_count

            if obs_count == 0:
                reasons.append(ExclusionReason.MISSING_PRICE_HISTORY)
            elif obs_count < self.min_history_observations:
                reasons.append(ExclusionReason.INSUFFICIENT_HISTORY)
                latest_p = date_map[sorted_dates[-1]].close
                ev["latest_close"] = str(latest_p)
                if latest_p < self.min_price_inr:
                    reasons.append(ExclusionReason.BELOW_MIN_PRICE)
            else:
                latest_p = date_map[sorted_dates[-1]].close
                ev["latest_close"] = str(latest_p)
                if latest_p < self.min_price_inr:
                    reasons.append(ExclusionReason.BELOW_MIN_PRICE)

            # Rule 4: Liquidity (60-day Median Daily Traded Value)
            if obs_count < self.MIN_LIQUIDITY_LOOKBACK:
                reasons.append(ExclusionReason.MISSING_LIQUIDITY_HISTORY)
                ev["mdtv_60d"] = "INSUFFICIENT_OBSERVATIONS"
            else:
                # Take trailing 60 valid trading observations
                trailing_60_dates = sorted_dates[-self.MIN_LIQUIDITY_LOOKBACK:]
                trailing_60_records = [date_map[d] for d in trailing_60_dates]
                trailing_60_turnovers = [p.traded_value_inr for p in trailing_60_records]

                # Check for missing, invalid, or zero turnover
                has_missing_status = any(p.traded_value_status == TradedValueStatus.MISSING for p in trailing_60_records)
                has_invalid_status = any(p.traded_value_status == TradedValueStatus.INVALID for p in trailing_60_records)
                has_zero_or_none = any(t is None or t <= Decimal("0") for t in trailing_60_turnovers)

                if has_invalid_status:
                    reasons.append(ExclusionReason.DATA_VALIDATION_FAILURE)
                    reasons.append(ExclusionReason.MISSING_LIQUIDITY_HISTORY)
                    ev["mdtv_60d"] = "INVALID_TURNOVER_STATUS"
                elif has_missing_status or has_zero_or_none:
                    reasons.append(ExclusionReason.MISSING_LIQUIDITY_HISTORY)
                    ev["mdtv_60d"] = "MISSING_OR_ZERO_TURNOVER"
                else:
                    # Calculate median turnover
                    sorted_turnover = sorted(trailing_60_turnovers)
                    mid = len(sorted_turnover) // 2
                    if len(sorted_turnover) % 2 == 0:
                        median_turnover = (sorted_turnover[mid - 1] + sorted_turnover[mid]) / Decimal("2")
                    else:
                        median_turnover = sorted_turnover[mid]

                    ev["mdtv_60d"] = str(median_turnover)
                    if median_turnover < self.min_mdtv_inr:
                        reasons.append(ExclusionReason.BELOW_MIN_LIQUIDITY)

            # Rule 5: Sector Classification
            sym_sectors = sectors_by_symbol.get(sym, [])
            active_sectors = [s for s in sym_sectors if s.is_active_on(pred_date)]
            if not active_sectors:
                reasons.append(ExclusionReason.MISSING_SECTOR_CLASSIFICATION)
                ev["sector"] = "MISSING"
            elif len(active_sectors) > 1:
                reasons.append(ExclusionReason.CONFLICTING_SECTOR_CLASSIFICATION)
                ev["sector"] = "CONFLICTING"
            else:
                ev["sector"] = active_sectors[0].sector_code

            # Rule 6: Regulatory Suspensions
            sym_susps = suspensions_by_symbol.get(sym, [])
            for susp in sym_susps:
                if susp.is_active_on(pred_date):
                    if susp.status == EligibilityStatus.SUSPENDED:
                        reasons.append(ExclusionReason.SUSPENDED)
                    elif susp.status == EligibilityStatus.PROLONGED_NON_TRADING:
                        reasons.append(ExclusionReason.PROLONGED_NON_TRADING)
                    elif susp.status == EligibilityStatus.RESTRICTED:
                        reasons.append(ExclusionReason.RESTRICTED_SECURITY)
                    elif susp.status == EligibilityStatus.UNKNOWN:
                        reasons.append(ExclusionReason.UNKNOWN_POINT_IN_TIME_STATUS)
                    ev["suspension_status"] = susp.status.value

            evidence[sym] = ev

            if reasons:
                # Deduplicate reasons while preserving order
                seen_r: Set[ExclusionReason] = set()
                deduped_reasons: List[ExclusionReason] = []
                for r in reasons:
                    if r not in seen_r:
                        seen_r.add(r)
                        deduped_reasons.append(r)
                exclusions[sym] = deduped_reasons
            else:
                eligible_symbols.append(sym)
                eligible_isins.append(isin_val)

        # Sort eligible outputs deterministically
        eligible_symbols.sort()
        eligible_isins.sort()

        # Compute deterministic universe hash
        hash_payload = {
            "prediction_timestamp": pred_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "eligible_symbols": eligible_symbols,
            "eligible_isins": eligible_isins,
            "exclusions": {s: [r.value for r in r_list] for s, r_list in sorted(exclusions.items())},
            "config_version": self.config_version,
            "dataset_version": dataset_version,
        }
        universe_hash = hashlib.sha256(
            json.dumps(hash_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        # Determine final status
        if eligible_symbols:
            status = UniverseBuildStatus.SUCCESS
        else:
            if is_mock_test and not membership_records:
                status = UniverseBuildStatus.BLOCKED_MISSING_MEMBERSHIP
            elif is_mock_test and not price_records:
                status = UniverseBuildStatus.BLOCKED_MISSING_PRICE_LIQUIDITY
            elif is_mock_test and not sector_records:
                status = UniverseBuildStatus.BLOCKED_MISSING_SECTOR_HISTORY
            else:
                status = UniverseBuildStatus.VALID_EMPTY_UNIVERSE
                warnings.append("Universe is valid but empty under active filters.")

        evidence["__audit__"] = {
            "future_records_count": future_records_count,
            "total_candidate_symbols": len(all_symbols),
        }

        return UniverseBuildResult(
            prediction_timestamp=pred_utc,
            prediction_date=pred_date,
            eligible_symbols=eligible_symbols,
            eligible_isins=eligible_isins,
            exclusions=exclusions,
            evidence=evidence,
            universe_hash=universe_hash,
            status=status,
            config_version=self.config_version,
            dataset_version=dataset_version,
            blockers=blockers,
            warnings=warnings,
            future_records_count=future_records_count,
        )
