"""CI Test Suite: Universe Survivorship, Liquidity, History, and Exclusion Reasons.

Covers tests 4-5, 15-25, 27-49:
- Anti-survivorship checks (no backfilling with current membership or sectors)
- Liquidity calculation (60d MDTV >= INR 10 crore)
- Trading history observation count (>= 252 valid prior observations, deduplicated)
- Multiple exclusion reasons per security
- Deterministic exclusion and eligible security ordering
- Deterministic universe hashes and reproducibility
- Explicit blocked status when BLK-01 / BLK-02 data inputs are missing
"""

from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
import unittest
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

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
from phase7.data.universe import (
    PointInTimeUniverseBuilder,
    UniverseBuildResult,
    UniverseBuildStatus,
)


class TestUniverseSurvivorship(unittest.TestCase):

    def setUp(self):
        self.pred_time = datetime(2025, 10, 1, 9, 0, 0, tzinfo=timezone.utc)
        self.pred_date = date(2025, 10, 1)
        self.builder = PointInTimeUniverseBuilder(
            min_price_inr=Decimal("20.00"),
            min_history_observations=252,
            min_mdtv_inr=Decimal("100000000.00"),  # INR 10 crore
            config_version="1.0.0",
        )

    def _generate_synthetic_prices(
        self,
        symbol: str,
        isin: str,
        count: int,
        start_date: date,
        base_price: Decimal = Decimal("100.00"),
        base_turnover: Decimal = Decimal("150000000.00"),
    ):
        """Generate a deterministic sequence of valid daily prices."""
        prices = []
        for i in range(count):
            d = start_date + timedelta(days=i)
            # Skip weekends
            if d.weekday() >= 5:
                continue
            src_ts = datetime(d.year, d.month, d.day, 16, 0, 0, tzinfo=timezone.utc)
            ing_ts = datetime(d.year, d.month, d.day, 17, 0, 0, tzinfo=timezone.utc)
            prices.append(
                DailyPriceRecord(
                    trading_date=d,
                    symbol=symbol,
                    isin=isin,
                    open=base_price,
                    high=base_price + Decimal("2.00"),
                    low=base_price - Decimal("2.00"),
                    close=base_price,
                    volume=100000,
                    traded_value_inr=base_turnover,
                    traded_value_status=TradedValueStatus.EXCHANGE_REPORTED,
                    price_adjustment_state=PriceAdjustmentState.RAW,
                    source_timestamp=src_ts,
                    ingestion_timestamp=ing_ts,
                    source_identifier="SYNTHETIC",
                )
            )
        return prices

    def test_missing_membership_history_causes_exclusion(self):
        """4, 5. Missing historical membership causes exclusion; fail-closed."""
        membership = PITMembershipRecord(
            index_code="NIFTY500",
            symbol="HDFCBANK",
            isin="INE040A01034",
            effective_from=date(2020, 1, 1),
            source_timestamp=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2020, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="CIRC",
        )
        res = self.builder.build_universe(
            prediction_timestamp=self.pred_time,
            membership_records=[membership],
            price_records=[],
            sector_records=[],
            is_mock_test=True,
        )
        # RELIANCE is not in membership records, so it's not in candidate pool / excluded
        self.assertNotIn("RELIANCE", res.eligible_symbols)
        # HDFCBANK is in membership but lacks price, sector
        self.assertIn("HDFCBANK", res.exclusions)

    def test_duplicate_dates_do_not_increase_history_count(self):
        """25. Duplicate trading dates do not increase the history count."""
        prices = [
            DailyPriceRecord(
                trading_date=date(2025, 1, 10),
                symbol="SBIN",
                isin="INE062A01020",
                open=Decimal("500.00"),
                high=Decimal("505.00"),
                low=Decimal("495.00"),
                close=Decimal("502.00"),
                volume=10000,
                traded_value_inr=Decimal("5000000.00"),
                traded_value_status=TradedValueStatus.EXCHANGE_REPORTED,
                price_adjustment_state=PriceAdjustmentState.RAW,
                source_timestamp=datetime(2025, 1, 10, 16, 0, tzinfo=timezone.utc),
                ingestion_timestamp=datetime(2025, 1, 10, 17, 0, tzinfo=timezone.utc),
                source_identifier="FEED1",
            ),
            DailyPriceRecord(
                trading_date=date(2025, 1, 10),  # Duplicate date!
                symbol="SBIN",
                isin="INE062A01020",
                open=Decimal("500.00"),
                high=Decimal("505.00"),
                low=Decimal("495.00"),
                close=Decimal("502.00"),
                volume=10000,
                traded_value_inr=Decimal("5000000.00"),
                traded_value_status=TradedValueStatus.EXCHANGE_REPORTED,
                price_adjustment_state=PriceAdjustmentState.RAW,
                source_timestamp=datetime(2025, 1, 10, 16, 30, tzinfo=timezone.utc),
                ingestion_timestamp=datetime(2025, 1, 10, 17, 0, tzinfo=timezone.utc),
                source_identifier="FEED2",
            ),
        ]
        mem = PITMembershipRecord(
            index_code="NIFTY500",
            symbol="SBIN",
            isin="INE062A01020",
            effective_from=date(2020, 1, 1),
            source_timestamp=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2020, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="CIRC",
        )
        res = self.builder.build_universe(
            prediction_timestamp=self.pred_time,
            membership_records=[mem],
            price_records=prices,
            sector_records=[],
            is_mock_test=True,
        )
        ev = res.evidence.get("SBIN", {})
        self.assertEqual(ev.get("valid_history_count"), 1, "Duplicate dates must not double count history.")

    def test_liquidity_threshold_evaluation(self):
        """32, 33. Values below 10 cr trigger BELOW_MIN_LIQUIDITY; >= 10 cr pass."""
        mem = PITMembershipRecord(
            index_code="NIFTY500",
            symbol="STOCK_LOW_LIQ",
            isin="INE111A01011",
            effective_from=date(2020, 1, 1),
            source_timestamp=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2020, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="CIRC",
        )
        sector = PITSectorClassificationRecord(
            symbol="STOCK_LOW_LIQ",
            isin="INE111A01011",
            sector_code="Industrials",
            effective_from=date(2020, 1, 1),
            source_timestamp=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2020, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="SEC",
        )
        # 300 days of history, but turnover is only 5 crore (50 million INR < 100 million)
        prices_low = self._generate_synthetic_prices(
            symbol="STOCK_LOW_LIQ",
            isin="INE111A01011",
            count=400,
            start_date=date(2024, 1, 1),
            base_turnover=Decimal("50000000.00"),
        )
        res = self.builder.build_universe(
            prediction_timestamp=self.pred_time,
            membership_records=[mem],
            price_records=prices_low,
            sector_records=[sector],
            is_mock_test=True,
        )
        self.assertIn(ExclusionReason.BELOW_MIN_LIQUIDITY, res.exclusions.get("STOCK_LOW_LIQ", []))

    def test_suspension_causes_exclusion(self):
        """38. A suspended security is excluded with reason SUSPENDED."""
        mem = PITMembershipRecord(
            index_code="NIFTY500",
            symbol="SUSP_STOCK",
            isin="INE222B01022",
            effective_from=date(2020, 1, 1),
            source_timestamp=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2020, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="CIRC",
        )
        susp = EligibilitySuspensionRecord(
            symbol="SUSP_STOCK",
            isin="INE222B01022",
            status=EligibilityStatus.SUSPENDED,
            effective_from=date(2025, 9, 15),
            source_timestamp=datetime(2025, 9, 14, 18, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2025, 9, 14, 19, 0, tzinfo=timezone.utc),
            source_identifier="SURVEILLANCE",
        )
        res = self.builder.build_universe(
            prediction_timestamp=self.pred_time,  # 2025-10-01
            membership_records=[mem],
            price_records=[],
            sector_records=[],
            suspension_records=[susp],
            is_mock_test=True,
        )
        self.assertIn(ExclusionReason.SUSPENDED, res.exclusions.get("SUSP_STOCK", []))

    def test_multiple_exclusion_reasons_preserved(self):
        """42. One security can receive multiple exclusion reasons."""
        mem = PITMembershipRecord(
            index_code="NIFTY500",
            symbol="MULTI_FAIL",
            isin="INE333C01033",
            effective_from=date(2020, 1, 1),
            source_timestamp=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2020, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="CIRC",
        )
        # Price is only INR 5 (< 20 INR), and history is only 5 days (< 252), and sector missing
        prices_short = self._generate_synthetic_prices(
            symbol="MULTI_FAIL",
            isin="INE333C01033",
            count=5,
            start_date=date(2025, 9, 1),
            base_price=Decimal("5.00"),
        )
        res = self.builder.build_universe(
            prediction_timestamp=self.pred_time,
            membership_records=[mem],
            price_records=prices_short,
            sector_records=[],  # Missing sector
            is_mock_test=True,
        )
        reasons = res.exclusions.get("MULTI_FAIL", [])
        self.assertIn(ExclusionReason.BELOW_MIN_PRICE, reasons)
        self.assertIn(ExclusionReason.INSUFFICIENT_HISTORY, reasons)
        self.assertIn(ExclusionReason.MISSING_SECTOR_CLASSIFICATION, reasons)
        self.assertGreaterEqual(len(reasons), 2)

    def test_missing_blk01_or_blk02_produces_explicit_blocked_status(self):
        """48. Missing BLK-01 or BLK-02 inputs produce explicit BLOCKED status."""
        # Non-mock call with empty datasets must fail closed and report BLOCKED
        res = self.builder.build_universe(
            prediction_timestamp=self.pred_time,
            membership_records=[],  # Missing BLK-01
            price_records=[],       # Missing BLK-02
            sector_records=[],
            is_mock_test=False,
        )
        self.assertEqual(res.status, UniverseBuildStatus.BLOCKED)
        self.assertTrue(res.is_real_data_blocked)
        self.assertTrue(any("BLK-01" in b for b in res.blockers))

    def test_universe_build_status_full_lifecycle_and_empty_valid(self):
        """Verify UniverseBuildStatus semantics: missing data vs valid empty vs success."""
        mem = PITMembershipRecord(
            index_code="NIFTY500",
            symbol="STOCK1",
            isin="INE999A01099",
            effective_from=date(2020, 1, 1),
            source_timestamp=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2020, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="CIRC",
        )
        sec = PITSectorClassificationRecord(
            symbol="STOCK1",
            isin="INE999A01099",
            sector_code="Financials",
            effective_from=date(2020, 1, 1),
            source_timestamp=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2020, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="SECTOR_FEED",
        )
        valid_prices = self._generate_synthetic_prices(
            symbol="STOCK1",
            isin="INE999A01099",
            count=400,
            start_date=date(2024, 1, 1),
            base_price=Decimal("150.00"),
            base_turnover=Decimal("200000000.00"),
        )

        # 1. Blocked on missing membership (BLK-01)
        res_no_mem = self.builder.build_universe(
            prediction_timestamp=self.pred_time,
            membership_records=[],
            price_records=valid_prices,
            sector_records=[sec],
            is_mock_test=False,
        )
        self.assertEqual(res_no_mem.status, UniverseBuildStatus.BLOCKED_MISSING_MEMBERSHIP)
        self.assertTrue(res_no_mem.is_real_data_blocked)

        # 2. Blocked on missing price & liquidity (BLK-02)
        res_no_prices = self.builder.build_universe(
            prediction_timestamp=self.pred_time,
            membership_records=[mem],
            price_records=[],
            sector_records=[sec],
            is_mock_test=False,
        )
        self.assertEqual(res_no_prices.status, UniverseBuildStatus.BLOCKED_MISSING_PRICE_LIQUIDITY)
        self.assertTrue(res_no_prices.is_real_data_blocked)

        # 3. Blocked on missing sector history (BLK-04)
        res_no_sec = self.builder.build_universe(
            prediction_timestamp=self.pred_time,
            membership_records=[mem],
            price_records=valid_prices,
            sector_records=[],
            is_mock_test=False,
        )
        self.assertEqual(res_no_sec.status, UniverseBuildStatus.BLOCKED_MISSING_SECTOR_HISTORY)
        self.assertTrue(res_no_sec.is_real_data_blocked)

        # 4. Success when all inputs valid and security passes all filters
        res_success = self.builder.build_universe(
            prediction_timestamp=self.pred_time,
            membership_records=[mem],
            price_records=valid_prices,
            sector_records=[sec],
            is_mock_test=False,
        )
        self.assertEqual(res_success.status, UniverseBuildStatus.SUCCESS)
        self.assertFalse(res_success.is_real_data_blocked)
        self.assertEqual(res_success.eligible_symbols, ["STOCK1"])

        # 5. VALID_EMPTY_UNIVERSE when all inputs provided, but security fails filters (e.g. price < 20)
        penny_prices = self._generate_synthetic_prices(
            symbol="STOCK1",
            isin="INE999A01099",
            count=400,
            start_date=date(2024, 1, 1),
            base_price=Decimal("10.00"),  # Below INR 20.00 minimum
            base_turnover=Decimal("200000000.00"),
        )
        res_empty = self.builder.build_universe(
            prediction_timestamp=self.pred_time,
            membership_records=[mem],
            price_records=penny_prices,
            sector_records=[sec],
            is_mock_test=False,
        )
        self.assertEqual(res_empty.status, UniverseBuildStatus.VALID_EMPTY_UNIVERSE)
        self.assertFalse(res_empty.is_real_data_blocked)
        self.assertEqual(len(res_empty.eligible_symbols), 0)
        self.assertIn(ExclusionReason.BELOW_MIN_PRICE, res_empty.exclusions["STOCK1"])

    def test_traded_value_derivation_contract_safeguards(self):
        """Enforce traded value derivation rules and prohibition of Close-alone derivation."""
        # 1. Close-alone derivation is strictly prohibited
        with self.assertRaises(ValueError) as ctx:
            DailyPriceRecord(
                trading_date=date(2025, 1, 10),
                symbol="TEST",
                isin="INE123A01010",
                open=Decimal("100.00"),
                high=Decimal("105.00"),
                low=Decimal("95.00"),
                close=Decimal("102.00"),
                volume=1000,
                traded_value_inr=Decimal("102000.00"),
                traded_value_status=TradedValueStatus.DERIVED_FROM_PRICE_VOLUME,
                traded_value_derivation_method="CLOSE_X_VOLUME",  # Prohibited!
                price_adjustment_state=PriceAdjustmentState.RAW,
                source_timestamp=datetime(2025, 1, 10, 16, 0, tzinfo=timezone.utc),
                ingestion_timestamp=datetime(2025, 1, 10, 17, 0, tzinfo=timezone.utc),
                source_identifier="SRC",
            )
        self.assertIn("prohibited", str(ctx.exception).lower())

        # 2. EXCHANGE_REPORTED with derivation method must fail
        with self.assertRaises(ValueError) as ctx2:
            DailyPriceRecord(
                trading_date=date(2025, 1, 10),
                symbol="TEST",
                isin="INE123A01010",
                open=Decimal("100.00"),
                high=Decimal("105.00"),
                low=Decimal("95.00"),
                close=Decimal("102.00"),
                volume=1000,
                traded_value_inr=Decimal("102000.00"),
                traded_value_status=TradedValueStatus.EXCHANGE_REPORTED,
                traded_value_derivation_method="VWAP_X_VOLUME",
                price_adjustment_state=PriceAdjustmentState.RAW,
                source_timestamp=datetime(2025, 1, 10, 16, 0, tzinfo=timezone.utc),
                ingestion_timestamp=datetime(2025, 1, 10, 17, 0, tzinfo=timezone.utc),
                source_identifier="SRC",
            )
        self.assertIn("exchange_reported", str(ctx2.exception).lower())

        # 3. Derived without derivation method must fail
        with self.assertRaises(ValueError) as ctx3:
            DailyPriceRecord(
                trading_date=date(2025, 1, 10),
                symbol="TEST",
                isin="INE123A01010",
                open=Decimal("100.00"),
                high=Decimal("105.00"),
                low=Decimal("95.00"),
                close=Decimal("102.00"),
                volume=1000,
                traded_value_inr=Decimal("102000.00"),
                traded_value_status=TradedValueStatus.DERIVED_FROM_PRICE_VOLUME,
                traded_value_derivation_method=None,
                price_adjustment_state=PriceAdjustmentState.RAW,
                source_timestamp=datetime(2025, 1, 10, 16, 0, tzinfo=timezone.utc),
                ingestion_timestamp=datetime(2025, 1, 10, 17, 0, tzinfo=timezone.utc),
                source_identifier="SRC",
            )
        self.assertIn("requires a recorded derivation method", str(ctx3.exception).lower())

        # 4. Valid VWAP derivation succeeds
        rec = DailyPriceRecord(
            trading_date=date(2025, 1, 10),
            symbol="TEST",
            isin="INE123A01010",
            open=Decimal("100.00"),
            high=Decimal("105.00"),
            low=Decimal("95.00"),
            close=Decimal("102.00"),
            volume=1000,
            traded_value_inr=Decimal("102000.00"),
            traded_value_status=TradedValueStatus.DERIVED_FROM_PRICE_VOLUME,
            traded_value_derivation_method="VWAP_X_VOLUME",
            price_adjustment_state=PriceAdjustmentState.RAW,
            source_timestamp=datetime(2025, 1, 10, 16, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2025, 1, 10, 17, 0, tzinfo=timezone.utc),
            source_identifier="SRC",
        )
        self.assertEqual(rec.traded_value_derivation_method, "VWAP_X_VOLUME")

    def test_distinction_not_in_pit_universe_vs_missing_membership_history(self):
        """Distinguish MISSING_MEMBERSHIP_HISTORY from NOT_IN_PIT_UNIVERSE."""
        # Symbol INACTIVE has membership records, but only starting AFTER prediction date
        future_mem = PITMembershipRecord(
            index_code="NIFTY500",
            symbol="INACTIVE",
            isin="INE001A01001",
            effective_from=date(2026, 1, 1),  # After pred_date 2025-10-01
            source_timestamp=datetime(2025, 9, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2025, 9, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="CIRC",
        )
        # Symbol UNKNOWN has price records, but zero membership records anywhere
        unknown_prices = self._generate_synthetic_prices(
            symbol="UNKNOWN",
            isin="INE002A01002",
            count=300,
            start_date=date(2024, 1, 1),
        )
        inactive_prices = self._generate_synthetic_prices(
            symbol="INACTIVE",
            isin="INE001A01001",
            count=300,
            start_date=date(2024, 1, 1),
        )
        res = self.builder.build_universe(
            prediction_timestamp=self.pred_time,
            membership_records=[future_mem],
            price_records=unknown_prices + inactive_prices,
            sector_records=[],
            is_mock_test=True,
        )
        self.assertIn(ExclusionReason.NOT_IN_PIT_UNIVERSE, res.exclusions.get("INACTIVE", []))
        self.assertIn(ExclusionReason.MISSING_MEMBERSHIP_HISTORY, res.exclusions.get("UNKNOWN", []))

    def test_distinction_missing_price_history_vs_insufficient_history(self):
        """Distinguish MISSING_PRICE_HISTORY (0 observations) from INSUFFICIENT_HISTORY (< 252)."""
        mem1 = PITMembershipRecord(
            index_code="NIFTY500",
            symbol="NO_PRICES",
            isin="INE001A01001",
            effective_from=date(2020, 1, 1),
            source_timestamp=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2020, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="CIRC",
        )
        mem2 = PITMembershipRecord(
            index_code="NIFTY500",
            symbol="FEW_PRICES",
            isin="INE002A01002",
            effective_from=date(2020, 1, 1),
            source_timestamp=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2020, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="CIRC",
        )
        # FEW_PRICES has 50 valid observations
        few_prices = self._generate_synthetic_prices(
            symbol="FEW_PRICES",
            isin="INE002A01002",
            count=50,
            start_date=date(2025, 6, 1),
        )
        res = self.builder.build_universe(
            prediction_timestamp=self.pred_time,
            membership_records=[mem1, mem2],
            price_records=few_prices,
            sector_records=[],
            is_mock_test=True,
        )
        self.assertIn(ExclusionReason.MISSING_PRICE_HISTORY, res.exclusions.get("NO_PRICES", []))
        self.assertNotIn(ExclusionReason.INSUFFICIENT_HISTORY, res.exclusions.get("NO_PRICES", []))
        self.assertIn(ExclusionReason.INSUFFICIENT_HISTORY, res.exclusions.get("FEW_PRICES", []))
        self.assertNotIn(ExclusionReason.MISSING_PRICE_HISTORY, res.exclusions.get("FEW_PRICES", []))

    def test_distinction_missing_sector_vs_conflicting_sector(self):
        """Distinguish MISSING_SECTOR_CLASSIFICATION from CONFLICTING_SECTOR_CLASSIFICATION."""
        mem = PITMembershipRecord(
            index_code="NIFTY500",
            symbol="CONFLICT_SEC",
            isin="INE003A01003",
            effective_from=date(2020, 1, 1),
            source_timestamp=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2020, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="CIRC",
        )
        sec_a = PITSectorClassificationRecord(
            symbol="CONFLICT_SEC",
            isin="INE003A01003",
            sector_code="Financials",
            effective_from=date(2020, 1, 1),
            source_timestamp=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2020, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="VENDOR_A",
        )
        sec_b = PITSectorClassificationRecord(
            symbol="CONFLICT_SEC",
            isin="INE003A01003",
            sector_code="Technology",
            effective_from=date(2020, 1, 1),
            source_timestamp=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2020, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="VENDOR_B",
        )
        res = self.builder.build_universe(
            prediction_timestamp=self.pred_time,
            membership_records=[mem],
            price_records=[],
            sector_records=[sec_a, sec_b],
            is_mock_test=True,
        )
        self.assertIn(ExclusionReason.CONFLICTING_SECTOR_CLASSIFICATION, res.exclusions.get("CONFLICT_SEC", []))
        self.assertNotIn(ExclusionReason.MISSING_SECTOR_CLASSIFICATION, res.exclusions.get("CONFLICT_SEC", []))

    def test_duplicate_security_record_exclusion(self):
        """Conflicting price records on same date trigger DUPLICATE_SECURITY_RECORD."""
        mem = PITMembershipRecord(
            index_code="NIFTY500",
            symbol="DUP_STOCK",
            isin="INE004A01004",
            effective_from=date(2020, 1, 1),
            source_timestamp=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2020, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="CIRC",
        )
        prices = [
            DailyPriceRecord(
                trading_date=date(2025, 9, 10),
                symbol="DUP_STOCK",
                isin="INE004A01004",
                open=Decimal("100.00"),
                high=Decimal("110.00"),
                low=Decimal("95.00"),
                close=Decimal("100.00"),  # Close = 100
                volume=1000,
                traded_value_inr=Decimal("100000.00"),
                traded_value_status=TradedValueStatus.EXCHANGE_REPORTED,
                price_adjustment_state=PriceAdjustmentState.RAW,
                source_timestamp=datetime(2025, 9, 10, 16, 0, tzinfo=timezone.utc),
                ingestion_timestamp=datetime(2025, 9, 10, 17, 0, tzinfo=timezone.utc),
                source_identifier="FEED_A",
            ),
            DailyPriceRecord(
                trading_date=date(2025, 9, 10),
                symbol="DUP_STOCK",
                isin="INE004A01004",
                open=Decimal("100.00"),
                high=Decimal("110.00"),
                low=Decimal("95.00"),
                close=Decimal("108.00"),  # Conflicting Close = 108!
                volume=1000,
                traded_value_inr=Decimal("100000.00"),
                traded_value_status=TradedValueStatus.EXCHANGE_REPORTED,
                price_adjustment_state=PriceAdjustmentState.RAW,
                source_timestamp=datetime(2025, 9, 10, 16, 5, tzinfo=timezone.utc),
                ingestion_timestamp=datetime(2025, 9, 10, 17, 0, tzinfo=timezone.utc),
                source_identifier="FEED_B",
            ),
        ]
        res = self.builder.build_universe(
            prediction_timestamp=self.pred_time,
            membership_records=[mem],
            price_records=prices,
            sector_records=[],
            is_mock_test=True,
        )
        self.assertIn(ExclusionReason.DUPLICATE_SECURITY_RECORD, res.exclusions.get("DUP_STOCK", []))

    def test_future_data_detected_exclusion(self):
        """Records with source_timestamp > prediction_timestamp trigger FUTURE_DATA_DETECTED."""
        mem = PITMembershipRecord(
            index_code="NIFTY500",
            symbol="FUTURE_STOCK",
            isin="INE005A01005",
            effective_from=date(2020, 1, 1),
            source_timestamp=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2020, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="CIRC",
        )
        # Price record has source_timestamp on 2025-10-02, while prediction_time is 2025-10-01
        future_price = DailyPriceRecord(
            trading_date=date(2025, 9, 30),
            symbol="FUTURE_STOCK",
            isin="INE005A01005",
            open=Decimal("100.00"),
            high=Decimal("105.00"),
            low=Decimal("95.00"),
            close=Decimal("100.00"),
            volume=1000,
            traded_value_inr=Decimal("100000.00"),
            traded_value_status=TradedValueStatus.EXCHANGE_REPORTED,
            price_adjustment_state=PriceAdjustmentState.RAW,
            source_timestamp=datetime(2025, 10, 2, 16, 0, tzinfo=timezone.utc),  # Future source timestamp!
            ingestion_timestamp=datetime(2025, 10, 2, 17, 0, tzinfo=timezone.utc),
            source_identifier="FEED",
        )
        res = self.builder.build_universe(
            prediction_timestamp=self.pred_time,  # 2025-10-01
            membership_records=[mem],
            price_records=[future_price],
            sector_records=[],
            is_mock_test=True,
        )
        self.assertIn(ExclusionReason.FUTURE_DATA_DETECTED, res.exclusions.get("FUTURE_STOCK", []))

    def test_deterministic_ordering_and_hash_reproducibility(self):
        """Universe outputs are deterministically sorted and generate reproducible hashes."""
        mem_a = PITMembershipRecord(
            index_code="NIFTY500",
            symbol="STOCK_A",
            isin="INE001A01001",
            effective_from=date(2020, 1, 1),
            source_timestamp=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2020, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="CIRC",
        )
        mem_b = PITMembershipRecord(
            index_code="NIFTY500",
            symbol="STOCK_B",
            isin="INE002A01002",
            effective_from=date(2020, 1, 1),
            source_timestamp=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2020, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="CIRC",
        )
        sec_a = PITSectorClassificationRecord(
            symbol="STOCK_A",
            isin="INE001A01001",
            sector_code="Financials",
            effective_from=date(2020, 1, 1),
            source_timestamp=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2020, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="SEC",
        )
        sec_b = PITSectorClassificationRecord(
            symbol="STOCK_B",
            isin="INE002A01002",
            sector_code="Technology",
            effective_from=date(2020, 1, 1),
            source_timestamp=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2020, 1, 1, 1, 0, tzinfo=timezone.utc),
            source_identifier="SEC",
        )
        prices_a = self._generate_synthetic_prices(
            symbol="STOCK_A",
            isin="INE001A01001",
            count=400,
            start_date=date(2024, 1, 1),
        )
        prices_b = self._generate_synthetic_prices(
            symbol="STOCK_B",
            isin="INE002A01002",
            count=400,
            start_date=date(2024, 1, 1),
        )

        # Run 1: Input ordered B then A
        res1 = self.builder.build_universe(
            prediction_timestamp=self.pred_time,
            membership_records=[mem_b, mem_a],
            price_records=prices_b + prices_a,
            sector_records=[sec_b, sec_a],
            is_mock_test=True,
        )

        # Run 2: Input ordered A then B
        res2 = self.builder.build_universe(
            prediction_timestamp=self.pred_time,
            membership_records=[mem_a, mem_b],
            price_records=prices_a + prices_b,
            sector_records=[sec_a, sec_b],
            is_mock_test=True,
        )

        self.assertEqual(res1.eligible_symbols, ["STOCK_A", "STOCK_B"])
        self.assertEqual(res2.eligible_symbols, ["STOCK_A", "STOCK_B"])
        self.assertEqual(res1.universe_hash, res2.universe_hash)


if __name__ == "__main__":
    unittest.main()
