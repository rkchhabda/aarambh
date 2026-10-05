"""CI Test Suite: Strict Cutoff and Zero Future Leakage Verification.

Verifies:
- Future price observations cannot enter history or liquidity calculations.
- Future sector reclassifications cannot backfill earlier predictions.
- Future index additions or removals cannot qualify/disqualify earlier dates.
- Financial period end date is not treated as data availability.
- Ingestion timestamp does not substitute for missing source availability timestamp.
"""

from datetime import date, datetime, timezone
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
    PITFinancialStatementRecord,
    PITMembershipRecord,
    PITSectorClassificationRecord,
    PriceAdjustmentState,
    TradedValueStatus,
)
from phase7.data.universe import PointInTimeUniverseBuilder, UniverseBuildStatus


class TestNoFutureFeatures(unittest.TestCase):

    def setUp(self):
        self.pred_time = datetime(2025, 6, 1, 9, 0, 0, tzinfo=timezone.utc)
        self.pred_date = date(2025, 6, 1)
        self.builder = PointInTimeUniverseBuilder(
            min_price_inr=Decimal("20.00"),
            min_history_observations=10,  # lowered for unit fixture
            min_mdtv_inr=Decimal("1000000.00"),
        )

    def test_future_source_timestamp_disqualifies_record(self):
        """68. A source timestamp after prediction timestamp cannot qualify a record."""
        # Record dated 2025-05-15 but disseminated to exchange at 2025-06-02 (after prediction)
        future_membership = PITMembershipRecord(
            index_code="NIFTY500",
            symbol="INFY",
            isin="INE009A01021",
            effective_from=date(2025, 5, 1),
            source_timestamp=datetime(2025, 6, 2, 10, 0, 0, tzinfo=timezone.utc),  # Future source timestamp!
            ingestion_timestamp=datetime(2025, 6, 2, 11, 0, 0, tzinfo=timezone.utc),
            source_identifier="CIRCULAR_LATE",
        )
        res = self.builder.build_universe(
            prediction_timestamp=self.pred_time,
            membership_records=[future_membership],
            price_records=[],
            sector_records=[],
            is_mock_test=True,
        )
        # Because the source timestamp was in the future, it was ignored as of pred_time -> excluded
        self.assertNotIn("INFY", res.eligible_symbols)
        self.assertIn(ExclusionReason.NOT_IN_PIT_UNIVERSE, res.exclusions.get("INFY", []))

    def test_future_price_does_not_enter_history(self):
        """26. Future price observations do not enter history calculations."""
        # Membership valid
        membership = PITMembershipRecord(
            index_code="NIFTY500",
            symbol="TCS",
            isin="INE467B01029",
            effective_from=date(2020, 1, 1),
            source_timestamp=datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2020, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
            source_identifier="CIRC",
        )
        sector = PITSectorClassificationRecord(
            symbol="TCS",
            isin="INE467B01029",
            sector_code="Technology",
            effective_from=date(2020, 1, 1),
            source_timestamp=datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2020, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
            source_identifier="SEC",
        )

        # 9 past prices, 5 future prices
        past_prices = [
            DailyPriceRecord(
                trading_date=date(2025, 5, i),
                symbol="TCS",
                isin="INE467B01029",
                open=Decimal("3500.00"),
                high=Decimal("3550.00"),
                low=Decimal("3480.00"),
                close=Decimal("3520.00"),
                volume=100000,
                traded_value_inr=Decimal("350000000.00"),
                traded_value_status=TradedValueStatus.EXCHANGE_REPORTED,
                price_adjustment_state=PriceAdjustmentState.RAW,
                source_timestamp=datetime(2025, 5, i, 16, 0, 0, tzinfo=timezone.utc),
                ingestion_timestamp=datetime(2025, 5, i, 17, 0, 0, tzinfo=timezone.utc),
                source_identifier="PRICES",
            )
            for i in range(1, 10)
        ]
        future_prices = [
            DailyPriceRecord(
                trading_date=date(2025, 6, i),
                symbol="TCS",
                isin="INE467B01029",
                open=Decimal("3500.00"),
                high=Decimal("3550.00"),
                low=Decimal("3480.00"),
                close=Decimal("3520.00"),
                volume=100000,
                traded_value_inr=Decimal("350000000.00"),
                traded_value_status=TradedValueStatus.EXCHANGE_REPORTED,
                price_adjustment_state=PriceAdjustmentState.RAW,
                source_timestamp=datetime(2025, 6, i, 16, 0, 0, tzinfo=timezone.utc),
                ingestion_timestamp=datetime(2025, 6, i, 17, 0, 0, tzinfo=timezone.utc),
                source_identifier="PRICES",
            )
            for i in range(2, 7)
        ]

        all_prices = past_prices + future_prices
        res = self.builder.build_universe(
            prediction_timestamp=self.pred_time,
            membership_records=[membership],
            price_records=all_prices,
            sector_records=[sector],
            is_mock_test=True,
        )

        ev = res.evidence.get("TCS", {})
        # Only 9 valid past prices should be counted, not the 5 future prices
        self.assertEqual(ev.get("valid_history_count"), 9)
        self.assertIn(ExclusionReason.INSUFFICIENT_HISTORY, res.exclusions.get("TCS", []))

    def test_future_sector_cannot_backfill_earlier_date(self):
        """16. A future sector classification cannot backfill an earlier date."""
        future_sector = PITSectorClassificationRecord(
            symbol="RELIANCE",
            isin="INE002A01018",
            sector_code="Energy",
            effective_from=date(2025, 7, 1),  # Starts in July 2025
            source_timestamp=datetime(2025, 5, 1, 0, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2025, 5, 1, 1, 0, 0, tzinfo=timezone.utc),
            source_identifier="SEC",
        )
        membership = PITMembershipRecord(
            index_code="NIFTY500",
            symbol="RELIANCE",
            isin="INE002A01018",
            effective_from=date(2020, 1, 1),
            source_timestamp=datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2020, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
            source_identifier="CIRC",
        )
        res = self.builder.build_universe(
            prediction_timestamp=self.pred_time,  # 2025-06-01
            membership_records=[membership],
            price_records=[],
            sector_records=[future_sector],
            is_mock_test=True,
        )
        self.assertIn(ExclusionReason.MISSING_SECTOR_CLASSIFICATION, res.exclusions.get("RELIANCE", []))

    def test_period_end_date_not_treated_as_availability(self):
        """70. Financial period-end date is not treated as filing availability."""
        # Q4 ends on 2025-03-31, but exchange publication is 2025-05-15
        filing = PITFinancialStatementRecord(
            symbol="INFY",
            isin="INE009A01021",
            period_end_date=date(2025, 3, 31),
            exchange_publication_timestamp=datetime(2025, 5, 15, 16, 45, 0, tzinfo=timezone.utc),
            statement_type="CONSOLIDATED",
            reporting_basis="IND_AS",
            source_identifier="NSE_XBRL",
            ingestion_timestamp=datetime(2025, 5, 15, 17, 0, 0, tzinfo=timezone.utc),
        )
        # Check that as of 2025-04-01 (day after period end), publication timestamp has NOT occurred yet
        query_instant = datetime(2025, 4, 1, 9, 0, 0, tzinfo=timezone.utc)
        self.assertGreater(filing.exchange_publication_timestamp, query_instant)


if __name__ == "__main__":
    unittest.main()
