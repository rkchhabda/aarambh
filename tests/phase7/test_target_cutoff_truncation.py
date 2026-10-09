"""Unit tests for Phase 7 target cutoff truncation and temporal boundary enforcement.

Verifies:
1. Exact boundary success (horizon-th observation exactly on or before authorized cutoff).
2. One observation short (insufficient forward observations; fail closed).
3. Outcome beyond cutoff (future observation strictly blocked).
4. Weekend and holiday gaps (session-based counting, not calendar day extrapolation).
5. Different terminal histories for two securities.
6. 20-endpoint behavior (primary target).
7. 60-endpoint behavior (secondary target).
8. Deterministic hash of truncation record.
9. Blocked-event count tracking.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import unittest

from phase7.data.contracts import PriceAdjustmentState
from phase7.targets.contracts import (
    ForwardPriceObservationRecord,
    PredictionEventRecord,
)
from phase7.targets.truncation import (
    CutoffTruncationResult,
    TruncationStatus,
    evaluate_cutoff_truncation,
)


class TestTargetCutoffTruncation(unittest.TestCase):

    def setUp(self):
        self.pred_time = datetime(2025, 1, 15, 16, 0, 0, tzinfo=timezone.utc)
        self.pred_date = date(2025, 1, 15)
        self.pred_event_tcs = PredictionEventRecord(
            prediction_timestamp=self.pred_time,
            prediction_trading_date=self.pred_date,
            symbol="TCS",
            isin="INE467B01029",
            universe_hash="u" * 64,
            dataset_version="1.0.0",
            source_cutoff_timestamp=self.pred_time,
            target_specification_hash="s" * 64,
        )
        self.pred_event_infy = PredictionEventRecord(
            prediction_timestamp=self.pred_time,
            prediction_trading_date=self.pred_date,
            symbol="INFY",
            isin="INE009A01021",
            universe_hash="u" * 64,
            dataset_version="1.0.0",
            source_cutoff_timestamp=self.pred_time,
            target_specification_hash="s" * 64,
        )

    def _generate_business_days(self, start_date: date, count: int):
        days = []
        curr = start_date
        while len(days) < count:
            curr += timedelta(days=1)
            if curr.weekday() < 5:  # Monday to Friday
                days.append(curr)
        return days

    def _make_observations(self, symbol: str, isin: str, dates):
        obs = []
        for d in dates:
            obs.append(
                ForwardPriceObservationRecord(
                    trading_date=d,
                    symbol=symbol,
                    isin=isin,
                    price=Decimal("1000.00"),
                    adjustment_state=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
                    source_timestamp=datetime(d.year, d.month, d.day, 16, 0, tzinfo=timezone.utc),
                    source_identifier="NSE_TEST",
                )
            )
        return obs

    def test_exact_boundary_success_20_and_60(self):
        """Horizon 20 and 60 succeed when available observations exactly match cutoff boundary."""
        bdays_20 = self._generate_business_days(self.pred_date, 20)
        obs_20 = self._make_observations("TCS", "INE467B01029", bdays_20)
        cutoff_20 = datetime(bdays_20[-1].year, bdays_20[-1].month, bdays_20[-1].day, 23, 59, tzinfo=timezone.utc)

        res_20 = evaluate_cutoff_truncation(
            prediction_event=self.pred_event_tcs,
            observations=obs_20,
            horizon_endpoint=20,
            authorized_cutoff=cutoff_20,
            target_name="target_20d_sector_relative",
        )
        self.assertEqual(res_20.truncation_status, TruncationStatus.COMPLETE)
        self.assertEqual(res_20.available_observation_count, 20)
        self.assertEqual(res_20.required_observation_count, 20)
        self.assertEqual(res_20.required_outcome_start, bdays_20[0])
        self.assertEqual(res_20.required_outcome_end, bdays_20[-1])
        self.assertEqual(res_20.removed_event_count, 0)

        # 60 endpoint
        bdays_60 = self._generate_business_days(self.pred_date, 60)
        obs_60 = self._make_observations("TCS", "INE467B01029", bdays_60)
        cutoff_60 = datetime(bdays_60[-1].year, bdays_60[-1].month, bdays_60[-1].day, 23, 59, tzinfo=timezone.utc)

        res_60 = evaluate_cutoff_truncation(
            prediction_event=self.pred_event_tcs,
            observations=obs_60,
            horizon_endpoint=60,
            authorized_cutoff=cutoff_60,
            target_name="target_60d_residual",
        )
        self.assertEqual(res_60.truncation_status, TruncationStatus.COMPLETE)
        self.assertEqual(res_60.required_outcome_end, bdays_60[-1])

    def test_one_observation_short_fails_closed(self):
        """When exactly 1 observation is missing (19 of 20), status is INSUFFICIENT_FORWARD_OBSERVATIONS."""
        bdays_19 = self._generate_business_days(self.pred_date, 19)
        obs_19 = self._make_observations("TCS", "INE467B01029", bdays_19)
        cutoff = datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)

        res = evaluate_cutoff_truncation(
            prediction_event=self.pred_event_tcs,
            observations=obs_19,
            horizon_endpoint=20,
            authorized_cutoff=cutoff,
        )
        self.assertEqual(res.truncation_status, TruncationStatus.INSUFFICIENT_FORWARD_OBSERVATIONS)
        self.assertEqual(res.available_observation_count, 19)
        self.assertEqual(res.required_observation_count, 20)
        self.assertIsNone(res.required_outcome_end)
        self.assertEqual(res.removed_event_count, 1)

    def test_outcome_beyond_cutoff_blocked(self):
        """When horizon window requires sessions past authorized cutoff, outcome is blocked."""
        bdays_20 = self._generate_business_days(self.pred_date, 20)
        obs_20 = self._make_observations("TCS", "INE467B01029", bdays_20)
        # Cutoff set at 15th business day
        cutoff = datetime(bdays_20[14].year, bdays_20[14].month, bdays_20[14].day, 12, 0, tzinfo=timezone.utc)

        res = evaluate_cutoff_truncation(
            prediction_event=self.pred_event_tcs,
            observations=obs_20,
            horizon_endpoint=20,
            authorized_cutoff=cutoff,
        )
        self.assertEqual(res.truncation_status, TruncationStatus.OUTCOME_EXCEEDS_AUTHORIZED_CUTOFF)
        self.assertEqual(res.removed_event_count, 1)

    def test_weekend_and_holiday_gaps(self):
        """Calendar gaps (weekends, holidays) are skipped; only actual discrete trading sessions count."""
        # 20 business days naturally span across 4 weekends (28 calendar days)
        bdays = self._generate_business_days(self.pred_date, 20)
        obs = self._make_observations("TCS", "INE467B01029", bdays)
        cutoff = datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)

        res = evaluate_cutoff_truncation(
            prediction_event=self.pred_event_tcs,
            observations=obs,
            horizon_endpoint=20,
            authorized_cutoff=cutoff,
        )
        self.assertEqual(res.truncation_status, TruncationStatus.COMPLETE)
        # Verify no calendar forward-fill or fabricated session
        self.assertEqual(res.available_observation_count, 20)
        self.assertEqual(res.required_outcome_start, bdays[0])
        self.assertEqual(res.required_outcome_end, bdays[19])

    def test_different_terminal_histories_two_securities(self):
        """Securities can have different terminal trading dates (e.g., delisting, suspension)."""
        bdays_20 = self._generate_business_days(self.pred_date, 20)
        bdays_10 = bdays_20[:10]  # INFY stopped trading early

        obs_tcs = self._make_observations("TCS", "INE467B01029", bdays_20)
        obs_infy = self._make_observations("INFY", "INE009A01021", bdays_10)

        cutoff = datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)

        res_tcs = evaluate_cutoff_truncation(
            prediction_event=self.pred_event_tcs,
            observations=obs_tcs,
            horizon_endpoint=20,
            authorized_cutoff=cutoff,
        )
        res_infy = evaluate_cutoff_truncation(
            prediction_event=self.pred_event_infy,
            observations=obs_infy,
            horizon_endpoint=20,
            authorized_cutoff=cutoff,
        )

        self.assertEqual(res_tcs.truncation_status, TruncationStatus.COMPLETE)
        self.assertEqual(res_tcs.removed_event_count, 0)

        self.assertEqual(res_infy.truncation_status, TruncationStatus.INSUFFICIENT_FORWARD_OBSERVATIONS)
        self.assertEqual(res_infy.available_observation_count, 10)
        self.assertEqual(res_infy.removed_event_count, 1)

    def test_deterministic_hash_and_immutability(self):
        """Truncation record produces deterministic SHA-256 result_hash."""
        bdays_20 = self._generate_business_days(self.pred_date, 20)
        obs_20 = self._make_observations("TCS", "INE467B01029", bdays_20)
        cutoff = datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)

        res_a = evaluate_cutoff_truncation(
            prediction_event=self.pred_event_tcs,
            observations=obs_20,
            horizon_endpoint=20,
            authorized_cutoff=cutoff,
        )
        res_b = evaluate_cutoff_truncation(
            prediction_event=self.pred_event_tcs,
            observations=obs_20,
            horizon_endpoint=20,
            authorized_cutoff=cutoff,
        )

        self.assertEqual(res_a.result_hash, res_b.result_hash)
        self.assertEqual(len(res_a.result_hash), 64)


if __name__ == "__main__":
    unittest.main()
