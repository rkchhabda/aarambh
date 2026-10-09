"""Unit tests for Phase 7 forward target window overlap detection.

Verifies:
1. Non-overlapping windows (zero overlap, distinct solo group IDs).
2. Partially overlapping windows (boundary touch and partial overlap detected).
3. Identical windows (classified as overlapping).
4. Chained overlaps (transitive connected component grouping).
5. Different securities (strict isolation: securities never grouped together).
6. Deterministic group identifiers regardless of input order.
7. Input-order independence for overlap counts and groups.
8. Preservation of all input target records.
9. Accurate overlap count calculation.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import random
import unittest

from phase7.targets.contracts import (
    TargetResultRecord,
    TargetStatus,
)
from phase7.targets.overlap import (
    detect_target_overlaps,
    windows_overlap,
)


class TestTargetOverlap(unittest.TestCase):

    def _make_target(
        self,
        symbol: str,
        isin: str,
        pred_date: date,
        entry_date: date,
        exit_date: date,
        val: str = "0.05",
    ) -> TargetResultRecord:
        pred_dt = datetime(pred_date.year, pred_date.month, pred_date.day, 16, 0, tzinfo=timezone.utc)
        return TargetResultRecord(
            target_name="target_20d_sector_relative",
            target_version="1.0.0",
            prediction_timestamp=pred_dt,
            symbol=symbol,
            isin=isin,
            horizon_trading_days=20,
            entry_date=entry_date,
            exit_date=exit_date,
            stock_total_return=Decimal(val),
            benchmark_total_return=Decimal("0.02"),
            beta_used=None,
            target_value=Decimal(val) - Decimal("0.02"),
            target_status=TargetStatus.VALID,
            universe_hash="u" * 64,
        )

    def test_non_overlapping_windows(self):
        """Windows where entry_b > exit_a do not overlap and receive solo group IDs."""
        t1 = self._make_target("TCS", "INE467B01029", date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 25))
        t2 = self._make_target("TCS", "INE467B01029", date(2025, 1, 25), date(2025, 1, 26), date(2025, 2, 15))

        overlaps = detect_target_overlaps([t1, t2])
        self.assertEqual(len(overlaps), 2)
        self.assertEqual(overlaps[0].overlap_count, 0)
        self.assertEqual(overlaps[1].overlap_count, 0)
        self.assertTrue(overlaps[0].overlap_group_id.startswith("solo_"))
        self.assertTrue(overlaps[1].overlap_group_id.startswith("solo_"))
        self.assertNotEqual(overlaps[0].overlap_group_id, overlaps[1].overlap_group_id)

    def test_partially_overlapping_and_boundary_touching_windows(self):
        """Windows sharing dates or touching on boundary are classified as overlapping."""
        # Partial overlap: [Jan 2, Jan 25] and [Jan 15, Feb 5]
        t1 = self._make_target("TCS", "INE467B01029", date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 25))
        t2 = self._make_target("TCS", "INE467B01029", date(2025, 1, 14), date(2025, 1, 15), date(2025, 2, 5))

        overlaps = detect_target_overlaps([t1, t2])
        self.assertEqual(len(overlaps), 2)
        self.assertEqual(overlaps[0].overlap_count, 1)
        self.assertEqual(overlaps[1].overlap_count, 1)
        self.assertEqual(overlaps[0].overlap_group_id, overlaps[1].overlap_group_id)
        self.assertTrue(overlaps[0].overlap_group_id.startswith("grp_"))

        # Boundary touching: [Jan 2, Jan 25] and [Jan 25, Feb 15]
        t3 = self._make_target("TCS", "INE467B01029", date(2025, 1, 24), date(2025, 1, 25), date(2025, 2, 15))
        self.assertTrue(windows_overlap(date(2025, 1, 2), date(2025, 1, 25), date(2025, 1, 25), date(2025, 2, 15)))

    def test_identical_windows_are_overlapping(self):
        """Two predictions with identical holding windows overlap each other."""
        t1 = self._make_target("TCS", "INE467B01029", date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 25), val="0.05")
        t2 = self._make_target("TCS", "INE467B01029", date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 25), val="0.06")

        overlaps = detect_target_overlaps([t1, t2])
        self.assertEqual(len(overlaps), 2)
        self.assertEqual(overlaps[0].overlap_count, 1)
        self.assertEqual(overlaps[1].overlap_count, 1)
        self.assertEqual(overlaps[0].overlap_group_id, overlaps[1].overlap_group_id)

    def test_chained_overlaps_form_connected_component_group(self):
        """Window A overlaps B, B overlaps C, but A does not overlap C -> all 3 belong to one chained group."""
        # A: Jan 2 - Jan 20
        # B: Jan 15 - Feb 5 (overlaps A and C)
        # C: Jan 30 - Feb 20 (overlaps B, does not overlap A)
        t_a = self._make_target("TCS", "INE467B01029", date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 20))
        t_b = self._make_target("TCS", "INE467B01029", date(2025, 1, 14), date(2025, 1, 15), date(2025, 2, 5))
        t_c = self._make_target("TCS", "INE467B01029", date(2025, 1, 29), date(2025, 1, 30), date(2025, 2, 20))

        overlaps = detect_target_overlaps([t_a, t_b, t_c])
        self.assertEqual(len(overlaps), 3)

        # Pairwise counts
        self.assertEqual(overlaps[0].overlap_count, 1)  # A overlaps B
        self.assertEqual(overlaps[1].overlap_count, 2)  # B overlaps A and C
        self.assertEqual(overlaps[2].overlap_count, 1)  # C overlaps B

        # Connected component group ID is identical across all 3
        self.assertEqual(overlaps[0].overlap_group_id, overlaps[1].overlap_group_id)
        self.assertEqual(overlaps[1].overlap_group_id, overlaps[2].overlap_group_id)

    def test_different_securities_never_grouped_together(self):
        """Windows on identical dates for different securities are never grouped together."""
        t_tcs = self._make_target("TCS", "INE467B01029", date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 25))
        t_infy = self._make_target("INFY", "INE009A01021", date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 25))

        overlaps = detect_target_overlaps([t_tcs, t_infy])
        self.assertEqual(len(overlaps), 2)
        self.assertEqual(overlaps[0].overlap_count, 0)
        self.assertEqual(overlaps[1].overlap_count, 0)
        self.assertNotEqual(overlaps[0].overlap_group_id, overlaps[1].overlap_group_id)

    def test_input_order_independence_and_preservation(self):
        """Shuffling input targets preserves exact order of outputs and group IDs."""
        t_a = self._make_target("TCS", "INE467B01029", date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 20))
        t_b = self._make_target("TCS", "INE467B01029", date(2025, 1, 14), date(2025, 1, 15), date(2025, 2, 5))
        t_c = self._make_target("TCS", "INE467B01029", date(2025, 1, 29), date(2025, 1, 30), date(2025, 2, 20))

        forward_run = detect_target_overlaps([t_a, t_b, t_c])
        reverse_run = detect_target_overlaps([t_c, t_b, t_a])

        # Reverse run preserves reverse order
        self.assertEqual(reverse_run[0].outcome_start, date(2025, 1, 30))
        self.assertEqual(reverse_run[1].outcome_start, date(2025, 1, 15))
        self.assertEqual(reverse_run[2].outcome_start, date(2025, 1, 2))

        # Group IDs remain identical regardless of input order
        self.assertEqual(forward_run[0].overlap_group_id, reverse_run[2].overlap_group_id)
        self.assertEqual(forward_run[1].overlap_group_id, reverse_run[1].overlap_group_id)


if __name__ == "__main__":
    unittest.main()
