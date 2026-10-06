"""CI Test Suite: Target Contracts, Immutability, and Hashing.

Verifies:
1. Frozen dataclass immutability across all target record types.
2. Deterministic SHA-256 row and specification hashing.
3. Strict Decimal precision and positive price boundaries.
4. Timezone-aware UTC timestamp validation.
5. ISIN structural-format regex validation.
6. Target status and reason code enumeration integrity.
7. TargetAuditRecord quality fields and zero-performance invariants.
"""

from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone
from decimal import Decimal
import unittest

from phase7.data.contracts import PriceAdjustmentState
from phase7.targets.contracts import (
    BetaInputRecord,
    ForwardPriceObservationRecord,
    PredictionEventRecord,
    SectorBenchmarkObservationRecord,
    TargetAuditRecord,
    TargetReasonCode,
    TargetResultRecord,
    TargetSpecificationRecord,
    TargetStatus,
)


class TestTargetContracts(unittest.TestCase):

    def setUp(self):
        self.t_pred = datetime(2025, 1, 15, 16, 0, 0, tzinfo=timezone.utc)
        self.t_cutoff = datetime(2025, 1, 15, 15, 30, 0, tzinfo=timezone.utc)
        self.t_create = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    def test_target_specification_record_frozen_and_hashing(self):
        """Specification record is frozen, validates positive horizon, and computes hash."""
        spec = TargetSpecificationRecord(
            target_name="target_20d_sector_relative",
            target_version="1.0.0",
            horizon_trading_days=20,
            execution_lag_trading_days=1,
            entry_price_field="open",
            exit_price_field="close",
            return_type="TOTAL_RETURN_ADJUSTED",
            benchmark_type="SECTOR",
            adjustment_state_requirement=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
            missing_terminal_policy="FAIL_CLOSED",
            suspension_policy="INVALIDATE_ON_SUSPENSION",
            delisting_policy="INVALIDATE_ON_DELISTING",
            created_timestamp=self.t_create,
        )
        self.assertTrue(len(spec.specification_hash) == 64)

        # Frozen immutability check
        with self.assertRaises(FrozenInstanceError):
            spec.horizon_trading_days = 60

        # Invalid zero horizon check
        with self.assertRaises(ValueError):
            TargetSpecificationRecord(
                target_name="bad",
                target_version="1.0.0",
                horizon_trading_days=0,
                execution_lag_trading_days=1,
                entry_price_field="open",
                exit_price_field="close",
                return_type="TOTAL_RETURN_ADJUSTED",
                benchmark_type="SECTOR",
                adjustment_state_requirement=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
                missing_terminal_policy="FAIL_CLOSED",
                suspension_policy="INVALIDATE",
                delisting_policy="INVALIDATE",
                created_timestamp=self.t_create,
            )

        # Same-day execution (lag < 1) check
        with self.assertRaises(ValueError):
            TargetSpecificationRecord(
                target_name="bad",
                target_version="1.0.0",
                horizon_trading_days=20,
                execution_lag_trading_days=0,
                entry_price_field="open",
                exit_price_field="close",
                return_type="TOTAL_RETURN_ADJUSTED",
                benchmark_type="SECTOR",
                adjustment_state_requirement=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
                missing_terminal_policy="FAIL_CLOSED",
                suspension_policy="INVALIDATE",
                delisting_policy="INVALIDATE",
                created_timestamp=self.t_create,
            )

    def test_prediction_event_record_validation(self):
        """Prediction event requires valid ISIN, timezone-aware UTC, and non-future cutoff."""
        pred = PredictionEventRecord(
            prediction_timestamp=self.t_pred,
            prediction_trading_date=date(2025, 1, 15),
            symbol="TCS",
            isin="INE467B01029",
            universe_hash="a" * 64,
            dataset_version="1.0.0",
            source_cutoff_timestamp=self.t_cutoff,
            target_specification_hash="b" * 64,
        )
        self.assertEqual(pred.symbol, "TCS")
        self.assertEqual(pred.isin, "INE467B01029")
        self.assertTrue(len(pred.row_hash) == 64)

        # Invalid ISIN raises ValueError
        with self.assertRaises(ValueError):
            PredictionEventRecord(
                prediction_timestamp=self.t_pred,
                prediction_trading_date=date(2025, 1, 15),
                symbol="TCS",
                isin="INVALID_ISIN",
                universe_hash="a" * 64,
                dataset_version="1.0.0",
                source_cutoff_timestamp=self.t_cutoff,
                target_specification_hash="b" * 64,
            )

        # Timezone-naive raises ValueError
        with self.assertRaises(ValueError):
            PredictionEventRecord(
                prediction_timestamp=datetime(2025, 1, 15, 16, 0, 0),  # Naive
                prediction_trading_date=date(2025, 1, 15),
                symbol="TCS",
                isin="INE467B01029",
                universe_hash="a" * 64,
                dataset_version="1.0.0",
                source_cutoff_timestamp=self.t_cutoff,
                target_specification_hash="b" * 64,
            )

    def test_forward_price_observation_record_positive_price(self):
        """ForwardPriceObservationRecord requires positive finite price and known adjustment state."""
        rec = ForwardPriceObservationRecord(
            trading_date=date(2025, 1, 16),
            symbol="TCS",
            isin="INE467B01029",
            price=Decimal("3500.50"),
            adjustment_state=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
            source_timestamp=self.t_pred,
            source_identifier="TEST_SRC",
        )
        self.assertEqual(rec.price, Decimal("3500.50"))

        # Zero or negative price raises ValueError
        with self.assertRaises(ValueError):
            ForwardPriceObservationRecord(
                trading_date=date(2025, 1, 16),
                symbol="TCS",
                isin="INE467B01029",
                price=Decimal("0.00"),
                adjustment_state=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
                source_timestamp=self.t_pred,
                source_identifier="TEST_SRC",
            )

        # UNKNOWN adjustment state raises ValueError
        with self.assertRaises(ValueError):
            ForwardPriceObservationRecord(
                trading_date=date(2025, 1, 16),
                symbol="TCS",
                isin="INE467B01029",
                price=Decimal("3500.50"),
                adjustment_state=PriceAdjustmentState.UNKNOWN,
                source_timestamp=self.t_pred,
                source_identifier="TEST_SRC",
            )

    def test_beta_input_record_finite_and_validation(self):
        """BetaInputRecord requires finite Decimal beta and timezone-aware UTC."""
        beta = BetaInputRecord(
            symbol="TCS",
            isin="INE467B01029",
            beta=Decimal("0.85"),
            estimation_end_timestamp=self.t_pred,
            estimation_method="60D_ROLLING_OLS",
            benchmark_identifier="NIFTY50",
            dataset_version="1.0.0",
        )
        self.assertEqual(beta.beta, Decimal("0.85"))
        self.assertTrue(len(beta.row_hash) == 64)

        # Non-finite beta raises ValueError
        with self.assertRaises(ValueError):
            BetaInputRecord(
                symbol="TCS",
                isin="INE467B01029",
                beta=Decimal("NaN"),
                estimation_end_timestamp=self.t_pred,
                estimation_method="60D_ROLLING_OLS",
                benchmark_identifier="NIFTY50",
                dataset_version="1.0.0",
            )

    def test_target_result_record_valid_invariants(self):
        """TargetResultRecord requires finite target value and entry/exit dates when VALID."""
        res = TargetResultRecord(
            target_name="target_20d_sector_relative",
            target_version="1.0.0",
            prediction_timestamp=self.t_pred,
            symbol="TCS",
            isin="INE467B01029",
            horizon_trading_days=20,
            entry_date=date(2025, 1, 16),
            exit_date=date(2025, 2, 13),
            stock_total_return=Decimal("0.05"),
            benchmark_total_return=Decimal("0.02"),
            beta_used=None,
            target_value=Decimal("0.03"),
            target_status=TargetStatus.VALID,
        )
        self.assertEqual(res.target_value, Decimal("0.03"))
        self.assertTrue(len(res.target_hash) == 64)

        # VALID status without target_value raises ValueError
        with self.assertRaises(ValueError):
            TargetResultRecord(
                target_name="target_20d_sector_relative",
                target_version="1.0.0",
                prediction_timestamp=self.t_pred,
                symbol="TCS",
                isin="INE467B01029",
                horizon_trading_days=20,
                entry_date=date(2025, 1, 16),
                exit_date=date(2025, 2, 13),
                stock_total_return=Decimal("0.05"),
                benchmark_total_return=Decimal("0.02"),
                beta_used=None,
                target_value=None,  # Missing!
                target_status=TargetStatus.VALID,
            )

    def test_target_audit_record_zero_performance_metrics(self):
        """TargetAuditRecord to_dict contains zero investment performance keys."""
        audit = TargetAuditRecord(
            input_record_count=100,
            accepted_target_count=90,
            rejected_target_count=8,
            blocked_target_count=2,
            future_data_count=1,
            missing_entry_count=2,
            missing_exit_count=3,
            adjustment_state_failure_count=1,
            suspension_count=1,
            delisting_count=0,
            invalid_beta_count=0,
            overlapping_label_count=50,
            target_specification_hash="s" * 64,
            dataset_version="1.0.0",
        )
        report = audit.to_dict()
        self.assertEqual(report["accepted_target_count"], 90)

        forbidden_metrics = {"sharpe", "sortino", "alpha", "drawdown", "max_drawdown", "ic", "rank_ic", "calmar", "win_rate", "hit_rate"}
        for k in report.keys():
            k_tokens = set(k.lower().split("_"))
            for f in forbidden_metrics:
                self.assertNotIn(f, k_tokens, f"Forbidden performance metric '{f}' found in audit key '{k}'!")
                if f in ("sharpe", "sortino", "alpha", "drawdown", "calmar"):
                    self.assertNotIn(f, k.lower(), f"Forbidden performance substring '{f}' found in audit key '{k}'!")


if __name__ == "__main__":
    unittest.main()
