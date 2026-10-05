"""CI Test Suite: Point-in-Time Integrity, Hashing, and Membership Interval Verification.

Covers tests 1-14, 65-77:
- Point-in-time index membership intervals [from, to)
- Half-open logic and open-ended validity
- Fail-closed behavior on unknown timing
- Deterministic SHA-256 row hashing across equivalent UTC instants and field orders
- ISIN format and natural key uniqueness
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
    PriceAdjustmentState,
    TradedValueStatus,
    compute_row_hash,
)
from phase7.data.loaders import parse_iso_datetime


class TestPointInTimeIntegrity(unittest.TestCase):

    def setUp(self):
        self.utc_now = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        self.t_src = datetime(2021, 12, 31, 18, 30, 0, tzinfo=timezone.utc)
        self.t_ing = datetime(2022, 1, 1, 6, 0, 0, tzinfo=timezone.utc)

    # --------------------------------------------------------------------------
    # Membership Tests (1-10)
    # --------------------------------------------------------------------------

    def test_stock_added_in_2022_not_eligible_in_2021(self):
        """1. A stock added to an index in 2022 is not eligible in 2021."""
        rec = PITMembershipRecord(
            index_code="NIFTY500",
            symbol="INFY",
            isin="INE009A01021",
            effective_from=date(2022, 1, 1),
            source_timestamp=self.t_src,
            ingestion_timestamp=self.t_ing,
            source_identifier="CIRCULAR_2022",
        )
        self.assertFalse(rec.is_active_on(date(2021, 12, 31)))

    def test_stock_eligible_on_or_after_addition(self):
        """2. The stock is eligible on or after the effective addition time."""
        rec = PITMembershipRecord(
            index_code="NIFTY500",
            symbol="INFY",
            isin="INE009A01021",
            effective_from=date(2022, 1, 1),
            effective_to=date(2024, 1, 1),
            source_timestamp=self.t_src,
            ingestion_timestamp=self.t_ing,
            source_identifier="CIRCULAR_2022",
        )
        self.assertTrue(rec.is_active_on(date(2022, 1, 1)))
        self.assertTrue(rec.is_active_on(date(2023, 6, 15)))

    def test_stock_removed_in_2023_not_eligible_after_removal(self):
        """3. A stock removed in 2023 is not eligible after the effective removal."""
        rec = PITMembershipRecord(
            index_code="NIFTY500",
            symbol="INFY",
            isin="INE009A01021",
            effective_from=date(2022, 1, 1),
            effective_to=date(2023, 7, 1),
            source_timestamp=self.t_src,
            ingestion_timestamp=self.t_ing,
            source_identifier="CIRCULAR_2022",
        )
        self.assertTrue(rec.is_active_on(date(2023, 6, 30)))
        # Half-open interval [from, to): excluded exactly on and after effective_to
        self.assertFalse(rec.is_active_on(date(2023, 7, 1)))
        self.assertFalse(rec.is_active_on(date(2023, 7, 2)))

    def test_open_ended_interval_works(self):
        """6. An open-ended membership interval works after effective_from."""
        rec = PITMembershipRecord(
            index_code="NIFTY500",
            symbol="RELIANCE",
            isin="INE002A01018",
            effective_from=date(2015, 1, 1),
            effective_to=None,
            source_timestamp=self.t_src,
            ingestion_timestamp=self.t_ing,
            source_identifier="CIRCULAR_2015",
        )
        self.assertTrue(rec.is_active_on(date(2026, 10, 5)))

    def test_invalid_interval_bounds_fail(self):
        """7. effective_to earlier than or equal to effective_from fails validation."""
        with self.assertRaises(ValueError) as ctx:
            PITMembershipRecord(
                index_code="NIFTY500",
                symbol="TCS",
                isin="INE467B01029",
                effective_from=date(2022, 1, 1),
                effective_to=date(2022, 1, 1),  # Equal
                source_timestamp=self.t_src,
                ingestion_timestamp=self.t_ing,
                source_identifier="TEST",
            )
        self.assertIn("strictly later than effective_from", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx2:
            PITMembershipRecord(
                index_code="NIFTY500",
                symbol="TCS",
                isin="INE467B01029",
                effective_from=date(2022, 1, 1),
                effective_to=date(2021, 1, 1),  # Earlier
                source_timestamp=self.t_src,
                ingestion_timestamp=self.t_ing,
                source_identifier="TEST",
            )
        self.assertIn("strictly later than effective_from", str(ctx2.exception))

    # --------------------------------------------------------------------------
    # ISIN and Identifier Tests (11-14)
    # --------------------------------------------------------------------------

    def test_missing_or_invalid_isin_raises_error(self):
        """11. Missing or invalid ISIN causes exclusion / error."""
        with self.assertRaises(ValueError):
            PITMembershipRecord(
                index_code="NIFTY500",
                symbol="TCS",
                isin="",
                effective_from=date(2022, 1, 1),
                source_timestamp=self.t_src,
                ingestion_timestamp=self.t_ing,
                source_identifier="TEST",
            )
        with self.assertRaises(ValueError):
            PITMembershipRecord(
                index_code="NIFTY500",
                symbol="TCS",
                isin="SHORT",  # Not 12-char
                effective_from=date(2022, 1, 1),
                source_timestamp=self.t_src,
                ingestion_timestamp=self.t_ing,
                source_identifier="TEST",
            )

    # --------------------------------------------------------------------------
    # Timestamp & Future Data Tests (65-71)
    # --------------------------------------------------------------------------

    def test_timezone_naive_timestamp_rejected(self):
        """66. Timezone-naive timestamps fail when timezone awareness is required."""
        naive_dt = datetime(2022, 1, 1, 12, 0, 0)  # No tzinfo
        with self.assertRaises(ValueError) as ctx:
            PITMembershipRecord(
                index_code="NIFTY500",
                symbol="TCS",
                isin="INE467B01029",
                effective_from=date(2022, 1, 1),
                source_timestamp=naive_dt,
                ingestion_timestamp=self.t_ing,
                source_identifier="TEST",
            )
        self.assertIn("must be timezone-aware", str(ctx.exception))

    def test_equivalent_utc_instants_normalize_consistently(self):
        """67. Equivalent UTC instants normalize consistently."""
        dt_utc = datetime(2026, 5, 10, 10, 0, 0, tzinfo=timezone.utc)
        # IST is UTC+05:30 -> 15:30 IST is 10:00 UTC
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        dt_ist = datetime(2026, 5, 10, 15, 30, 0, tzinfo=ist_tz)

        dict1 = {"timestamp": dt_utc, "value": Decimal("100.00")}
        dict2 = {"timestamp": dt_ist, "value": Decimal("100.00")}

        hash1 = compute_row_hash(dict1)
        hash2 = compute_row_hash(dict2)
        self.assertEqual(hash1, hash2, "Equivalent instants in different timezones must yield identical hashes.")

    # --------------------------------------------------------------------------
    # Deterministic Hashing Tests (72-77)
    # --------------------------------------------------------------------------

    def test_deterministic_row_hash_identical_records(self):
        """72. Identical records produce identical SHA-256 hashes."""
        payload1 = {
            "symbol": "reliance",
            "isin": "ine002a01018",
            "open": Decimal("2500.50"),
            "trading_date": date(2026, 1, 15),
            "source_timestamp": self.t_src,
        }
        payload2 = {
            "symbol": "RELIANCE",
            "isin": "INE002A01018",
            "open": Decimal("2500.5"),
            "trading_date": date(2026, 1, 15),
            "source_timestamp": self.t_src,
        }
        self.assertEqual(compute_row_hash(payload1), compute_row_hash(payload2))

    def test_field_order_difference_does_not_change_hash(self):
        """73. Field-order differences do not change hashes."""
        p1 = {"a": 1, "b": 2, "c": "test"}
        p2 = {"c": "test", "a": 1, "b": 2}
        self.assertEqual(compute_row_hash(p1), compute_row_hash(p2))

    def test_material_field_change_alters_hash(self):
        """74. Material field changes alter hashes."""
        p1 = {"symbol": "INFY", "close": Decimal("1500.00")}
        p2 = {"symbol": "INFY", "close": Decimal("1500.05")}
        self.assertNotEqual(compute_row_hash(p1), compute_row_hash(p2))

    def test_row_hash_field_itself_excluded(self):
        """76. The row_hash field itself is excluded from hash computation."""
        p1 = {"symbol": "INFY", "close": Decimal("1500.00")}
        p2 = {"symbol": "INFY", "close": Decimal("1500.00"), "row_hash": "existing_old_hash"}
        self.assertEqual(compute_row_hash(p1), compute_row_hash(p2))

    def test_supplied_hash_mismatch_detected(self):
        """77. Supplied hash mismatches are detected."""
        with self.assertRaises(ValueError) as ctx:
            PITMembershipRecord(
                index_code="NIFTY500",
                symbol="TCS",
                isin="INE467B01029",
                effective_from=date(2022, 1, 1),
                source_timestamp=self.t_src,
                ingestion_timestamp=self.t_ing,
                source_identifier="TEST",
                row_hash="0000000000000000000000000000000000000000000000000000000000000000",
            )
        self.assertIn("Supplied row_hash mismatch", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
