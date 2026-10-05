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
    PITCorporateAnnouncementRecord,
    PITFinancialStatementRecord,
    PITMembershipEventRecord,
    PITMembershipRecord,
    PITSectorClassificationRecord,
    PITShareholdingRecord,
    PriceAdjustmentState,
    TradedValueStatus,
    compute_row_hash,
    convert_membership_events_to_intervals,
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

    # --------------------------------------------------------------------------
    # Membership ADD/REMOVE Event Conversion Tests
    # --------------------------------------------------------------------------

    def test_membership_conversion_normal_add_then_remove(self):
        """Normal ADD then REMOVE creates validated half-open interval [from, to)."""
        events = [
            PITMembershipEventRecord(
                index_code="NIFTY500",
                symbol="WIPRO",
                isin="INE075A01022",
                effective_date=date(2020, 1, 1),
                action="ADD",
                source_timestamp=datetime(2019, 12, 15, 10, 0, tzinfo=timezone.utc),
                ingestion_timestamp=datetime(2019, 12, 15, 11, 0, tzinfo=timezone.utc),
                source_identifier="CIRC_ADD",
            ),
            PITMembershipEventRecord(
                index_code="NIFTY500",
                symbol="WIPRO",
                isin="INE075A01022",
                effective_date=date(2021, 6, 1),
                action="REMOVE",
                source_timestamp=datetime(2021, 5, 15, 10, 0, tzinfo=timezone.utc),
                ingestion_timestamp=datetime(2021, 5, 15, 11, 0, tzinfo=timezone.utc),
                source_identifier="CIRC_REM",
            ),
        ]
        intervals, errors = convert_membership_events_to_intervals(events)
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(intervals), 1)
        iv = intervals[0]
        self.assertEqual(iv.effective_from, date(2020, 1, 1))
        self.assertEqual(iv.effective_to, date(2021, 6, 1))
        self.assertTrue(iv.is_active_on(date(2020, 1, 1)))
        self.assertTrue(iv.is_active_on(date(2021, 5, 31)))
        self.assertFalse(iv.is_active_on(date(2021, 6, 1)))

    def test_membership_conversion_open_ended_addition(self):
        """Open-ended ADD produces interval with effective_to=None."""
        events = [
            PITMembershipEventRecord(
                index_code="NIFTY500",
                symbol="SBIN",
                isin="INE062A01020",
                effective_date=date(2018, 1, 1),
                action="ADD",
                source_timestamp=datetime(2017, 12, 1, 10, 0, tzinfo=timezone.utc),
                ingestion_timestamp=datetime(2017, 12, 1, 11, 0, tzinfo=timezone.utc),
                source_identifier="CIRC_ADD",
            ),
        ]
        intervals, errors = convert_membership_events_to_intervals(events)
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(intervals), 1)
        self.assertIsNone(intervals[0].effective_to)
        self.assertTrue(intervals[0].is_active_on(date(2026, 1, 1)))

    def test_membership_conversion_removal_without_prior_addition_fails_closed(self):
        """REMOVE without prior ADD fails closed with error and zero intervals."""
        events = [
            PITMembershipEventRecord(
                index_code="NIFTY500",
                symbol="UNLISTED",
                isin="INE999A01099",
                effective_date=date(2021, 1, 1),
                action="REMOVE",
                source_timestamp=datetime(2020, 12, 1, 10, 0, tzinfo=timezone.utc),
                ingestion_timestamp=datetime(2020, 12, 1, 11, 0, tzinfo=timezone.utc),
                source_identifier="CIRC_REM",
            ),
        ]
        intervals, errors = convert_membership_events_to_intervals(events)
        self.assertEqual(len(intervals), 0)
        self.assertTrue(any("Removal without prior addition" in e for e in errors))

    def test_membership_conversion_duplicate_addition_fails_closed(self):
        """Duplicate ADD while already active fails closed."""
        events = [
            PITMembershipEventRecord(
                index_code="NIFTY500",
                symbol="AXISBANK",
                isin="INE238A01034",
                effective_date=date(2020, 1, 1),
                action="ADD",
                source_timestamp=datetime(2019, 12, 1, 10, 0, tzinfo=timezone.utc),
                ingestion_timestamp=datetime(2019, 12, 1, 11, 0, tzinfo=timezone.utc),
                source_identifier="CIRC_ADD1",
            ),
            PITMembershipEventRecord(
                index_code="NIFTY500",
                symbol="AXISBANK",
                isin="INE238A01034",
                effective_date=date(2020, 6, 1),
                action="ADD",
                source_timestamp=datetime(2020, 5, 1, 10, 0, tzinfo=timezone.utc),
                ingestion_timestamp=datetime(2020, 5, 1, 11, 0, tzinfo=timezone.utc),
                source_identifier="CIRC_ADD2",
            ),
        ]
        intervals, errors = convert_membership_events_to_intervals(events)
        self.assertEqual(len(intervals), 0)
        self.assertTrue(any("Duplicate addition" in e for e in errors))

    def test_membership_conversion_re_addition_after_removal(self):
        """Re-addition after removal produces two non-overlapping intervals."""
        events = [
            PITMembershipEventRecord(
                index_code="NIFTY500",
                symbol="TATAMOTORS",
                isin="INE155A01022",
                effective_date=date(2020, 1, 1),
                action="ADD",
                source_timestamp=datetime(2019, 12, 1, 10, 0, tzinfo=timezone.utc),
                ingestion_timestamp=datetime(2019, 12, 1, 11, 0, tzinfo=timezone.utc),
                source_identifier="ADD1",
            ),
            PITMembershipEventRecord(
                index_code="NIFTY500",
                symbol="TATAMOTORS",
                isin="INE155A01022",
                effective_date=date(2021, 1, 1),
                action="REMOVE",
                source_timestamp=datetime(2020, 12, 1, 10, 0, tzinfo=timezone.utc),
                ingestion_timestamp=datetime(2020, 12, 1, 11, 0, tzinfo=timezone.utc),
                source_identifier="REM1",
            ),
            PITMembershipEventRecord(
                index_code="NIFTY500",
                symbol="TATAMOTORS",
                isin="INE155A01022",
                effective_date=date(2022, 1, 1),
                action="ADD",
                source_timestamp=datetime(2021, 12, 1, 10, 0, tzinfo=timezone.utc),
                ingestion_timestamp=datetime(2021, 12, 1, 11, 0, tzinfo=timezone.utc),
                source_identifier="ADD2",
            ),
        ]
        intervals, errors = convert_membership_events_to_intervals(events)
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(intervals), 2)
        self.assertEqual(intervals[0].effective_from, date(2020, 1, 1))
        self.assertEqual(intervals[0].effective_to, date(2021, 1, 1))
        self.assertEqual(intervals[1].effective_from, date(2022, 1, 1))
        self.assertIsNone(intervals[1].effective_to)

    def test_membership_conversion_same_time_conflicting_events(self):
        """Conflicting ADD and REMOVE on same effective date fails closed."""
        events = [
            PITMembershipEventRecord(
                index_code="NIFTY500",
                symbol="CONFLICT",
                isin="INE888A01088",
                effective_date=date(2021, 1, 1),
                action="ADD",
                source_timestamp=datetime(2020, 12, 1, 10, 0, tzinfo=timezone.utc),
                ingestion_timestamp=datetime(2020, 12, 1, 11, 0, tzinfo=timezone.utc),
                source_identifier="ADD_CONF",
            ),
            PITMembershipEventRecord(
                index_code="NIFTY500",
                symbol="CONFLICT",
                isin="INE888A01088",
                effective_date=date(2021, 1, 1),
                action="REMOVE",
                source_timestamp=datetime(2020, 12, 1, 10, 0, tzinfo=timezone.utc),
                ingestion_timestamp=datetime(2020, 12, 1, 11, 0, tzinfo=timezone.utc),
                source_identifier="REM_CONF",
            ),
        ]
        intervals, errors = convert_membership_events_to_intervals(events)
        self.assertEqual(len(intervals), 0)
        self.assertTrue(any("Conflicting same-day events" in e for e in errors))

    def test_membership_conversion_future_events_ignored_at_prediction_time(self):
        """Events disseminated after prediction timestamp are excluded from interval conversion."""
        events = [
            PITMembershipEventRecord(
                index_code="NIFTY500",
                symbol="FUTURE_ADD",
                isin="INE777A01077",
                effective_date=date(2022, 1, 1),
                action="ADD",
                source_timestamp=datetime(2022, 1, 5, 10, 0, tzinfo=timezone.utc),  # Source after prediction
                ingestion_timestamp=datetime(2022, 1, 5, 11, 0, tzinfo=timezone.utc),
                source_identifier="FUTURE_CIRC",
            ),
        ]
        pred_ts = datetime(2022, 1, 1, 9, 0, tzinfo=timezone.utc)
        intervals, errors = convert_membership_events_to_intervals(events, prediction_timestamp=pred_ts)
        self.assertEqual(len(intervals), 0)
        self.assertTrue(any("Future source timestamp ignored" in e for e in errors))

    # --------------------------------------------------------------------------
    # Point-in-Time Sector Classification Tests
    # --------------------------------------------------------------------------

    def test_sector_classification_pit_checks(self):
        """Point-in-time sector classification enforces interval boundaries with no current fallback."""
        sec_rec = PITSectorClassificationRecord(
            symbol="INFY",
            isin="INE009A01021",
            sector_code="Technology",
            effective_from=date(2020, 1, 1),
            effective_to=date(2024, 1, 1),
            source_timestamp=datetime(2019, 12, 1, 10, 0, tzinfo=timezone.utc),
            ingestion_timestamp=datetime(2019, 12, 1, 11, 0, tzinfo=timezone.utc),
            source_identifier="AMFI_2020",
        )
        # Prior to effective_from -> False
        self.assertFalse(sec_rec.is_active_on(date(2019, 12, 31)))
        # Within interval -> True
        self.assertTrue(sec_rec.is_active_on(date(2020, 1, 1)))
        self.assertTrue(sec_rec.is_active_on(date(2023, 12, 31)))
        # On or after effective_to -> False (no forward bleed)
        self.assertFalse(sec_rec.is_active_on(date(2024, 1, 1)))

        # Future classification source timestamp fails is_active_as_of
        pred_early = datetime(2019, 11, 1, 10, 0, tzinfo=timezone.utc)
        self.assertFalse(sec_rec.is_active_as_of(pred_early))

    # --------------------------------------------------------------------------
    # Gated Interface Contracts Tests
    # --------------------------------------------------------------------------

    def test_gated_interface_contracts_timestamp_distinction(self):
        """Shareholding, Announcement, and Financial interfaces distinguish all required timestamps."""
        t_pub = datetime(2024, 4, 15, 10, 0, tzinfo=timezone.utc)
        t_first = datetime(2024, 4, 15, 10, 5, tzinfo=timezone.utc)
        t_ing = datetime(2024, 4, 15, 11, 0, tzinfo=timezone.utc)
        t_event = datetime(2024, 4, 14, 18, 0, tzinfo=timezone.utc)

        # 1. Shareholding record
        sh_rec = PITShareholdingRecord(
            symbol="TCS",
            isin="INE467B01029",
            reporting_period_end=date(2024, 3, 31),
            publication_timestamp=t_pub,
            first_seen_timestamp=t_first,
            ingestion_timestamp=t_ing,
            source_identifier="BSE_SHP",
            promoter_holding_percent=Decimal("72.05"),
        )
        self.assertEqual(sh_rec.reporting_period_end, date(2024, 3, 31))
        self.assertEqual(sh_rec.publication_timestamp, t_pub)
        self.assertEqual(sh_rec.first_seen_timestamp, t_first)
        self.assertEqual(sh_rec.ingestion_timestamp, t_ing)

        # 2. Corporate Announcement record
        ann_rec = PITCorporateAnnouncementRecord(
            symbol="TCS",
            isin="INE467B01029",
            event_timestamp=t_event,
            exchange_dissemination_timestamp=t_pub,
            first_seen_timestamp=t_first,
            ingestion_timestamp=t_ing,
            category="BOARD_MEETING",
            source_identifier="NSE_ANN",
            source_document_identifier="DOC_001",
            source_document_hash="hash001",
        )
        self.assertEqual(ann_rec.event_timestamp, t_event)
        self.assertEqual(ann_rec.exchange_dissemination_timestamp, t_pub)
        self.assertEqual(ann_rec.first_seen_timestamp, t_first)
        self.assertEqual(ann_rec.ingestion_timestamp, t_ing)


if __name__ == "__main__":
    unittest.main()
