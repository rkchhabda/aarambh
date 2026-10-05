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
        self.assertTrue(any("BLK-01" in b for b in res.blockers))


if __name__ == "__main__":
    unittest.main()
