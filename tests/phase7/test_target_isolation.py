"""CI Test Suite: Target Module Isolation and Boundary Defense.

Verifies:
1. Target modules (phase7/targets/) do not import feature engineering modules.
2. Target modules do not import Phase 6 scripts (scripts/phase6/).
3. Target modules do not import production service routes (service/).
4. Target code contains zero references to Phase 6 sealed vaults or archives.
5. Target calculation outputs are physically segregated from feature matrices.
"""

import os
from pathlib import Path
import unittest

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class TestTargetIsolation(unittest.TestCase):

    def test_target_modules_have_no_forbidden_imports(self):
        """Active phase7/targets/ modules must not import features, Phase 6 scripts, or service routes."""
        targets_dir = BASE_DIR / "phase7" / "targets"
        self.assertTrue(targets_dir.is_dir(), f"phase7/targets directory missing at {targets_dir}")

        forbidden_imports = [
            "features.indicators",
            "features.universe",
            "scripts.phase6",
            "service.app",
            "service.routes_signals",
            "phase7.features",
            "phase7.models",
            "phase7.portfolio",
            "phase7.backtest",
            "models",
            "portfolio",
            "backtest",
        ]

        violations = []
        for root, _, files in os.walk(targets_dir):
            for f in files:
                if not f.endswith(".py"):
                    continue
                fpath = Path(root) / f
                content = fpath.read_text(encoding="utf-8", errors="ignore")
                for imp in forbidden_imports:
                    if f"import {imp}" in content or f"from {imp}" in content:
                        violations.append(f"{fpath.relative_to(BASE_DIR)} imports {imp}")

        self.assertEqual(violations, [], f"Forbidden imports detected in phase7/targets/:\n" + "\n".join(violations))

    def test_target_modules_have_no_phase6_vault_references(self):
        """Active phase7/targets/ modules must contain zero references to Phase 6 vault paths or archives."""
        targets_dir = BASE_DIR / "phase7" / "targets"
        forbidden_vault_patterns = [
            "gaurvideep_vault",
            "window_a_sealed",
            "window_b_sealed",
            "vault_secret",
            "vault_password",
        ]

        violations = []
        for root, _, files in os.walk(targets_dir):
            for f in files:
                if not f.endswith(".py"):
                    continue
                fpath = Path(root) / f
                content = fpath.read_text(encoding="utf-8", errors="ignore").lower()
                for pat in forbidden_vault_patterns:
                    if pat in content:
                        violations.append(f"{fpath.relative_to(BASE_DIR)} contains vault reference '{pat}'")

        self.assertEqual(violations, [], f"Forbidden Phase 6 vault references in phase7/targets/:\n" + "\n".join(violations))

    def test_target_classes_do_not_expose_feature_generation_methods(self):
        """Target classes must calculate only forward labels and expose zero feature methods."""
        from phase7.targets.contracts import TargetResultRecord
        forbidden_method_substrings = [
            "compute_feature",
            "generate_feature",
            "calculate_rsi",
            "calculate_macd",
            "rolling_momentum",
        ]
        for attr in dir(TargetResultRecord):
            for substr in forbidden_method_substrings:
                self.assertNotIn(substr, attr.lower(), f"Forbidden feature method '{attr}' found in TargetResultRecord!")

    def test_no_wildcard_export_leaks_and_clean_target_namespace(self):
        """phase7.targets exports only explicit canonical symbols; no wildcard leaks."""
        import phase7.targets as pt
        self.assertTrue(hasattr(pt, "__all__"))
        forbidden_tokens = ["feature", "model", "vault", "train", "alpha", "sharpe", "weight", "portfolio"]
        for sym in pt.__all__:
            for tok in forbidden_tokens:
                self.assertNotIn(tok, sym.lower(), f"Target export '{sym}' contains forbidden token '{tok}'!")

    def test_target_functions_do_not_mutate_immutable_inputs(self):
        """Target functions must not mutate frozen input records."""
        from datetime import date, datetime, timezone
        from decimal import Decimal
        from phase7.data.contracts import PriceAdjustmentState
        from phase7.targets.alignment import align_forward_observations
        from phase7.targets.contracts import ForwardPriceObservationRecord, PredictionEventRecord

        t_pred = datetime(2025, 1, 15, 16, 0, tzinfo=timezone.utc)
        pred = PredictionEventRecord(
            prediction_timestamp=t_pred,
            prediction_trading_date=date(2025, 1, 15),
            symbol="TCS",
            isin="INE467B01029",
            universe_hash="u" * 64,
            dataset_version="1.0.0",
            source_cutoff_timestamp=t_pred,
            target_specification_hash="s" * 64,
        )
        obs = [
            ForwardPriceObservationRecord(
                trading_date=date(2025, 1, 16),
                symbol="TCS",
                isin="INE467B01029",
                price=Decimal("100.00"),
                adjustment_state=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
                source_timestamp=t_pred,
                source_identifier="TEST",
            )
        ]
        pred_hash_before = pred.row_hash
        obs_hash_before = obs[0].row_hash

        align_forward_observations(pred, obs, horizon_trading_days=1)

        self.assertEqual(pred.row_hash, pred_hash_before)
        self.assertEqual(obs[0].row_hash, obs_hash_before)

    def test_target_code_does_not_write_to_data_directory(self):
        """Target code must be purely functional and never execute writes to repository data/ directories."""
        targets_dir = BASE_DIR / "phase7" / "targets"
        forbidden_write_patterns = [
            'open("data/',
            "open('data/",
            '.to_csv("data/',
            ".to_csv('data/",
            '.to_parquet("data/',
            ".to_parquet('data/",
        ]
        violations = []
        for root, _, files in os.walk(targets_dir):
            for f in files:
                if not f.endswith(".py"):
                    continue
                fpath = Path(root) / f
                content = fpath.read_text(encoding="utf-8", errors="ignore")
                for pat in forbidden_write_patterns:
                    if pat in content:
                        violations.append(f"{fpath.relative_to(BASE_DIR)} contains write pattern '{pat}'")

        self.assertEqual(violations, [])

    def test_feature_cutoff_and_outcome_timestamps_remain_distinct(self):
        """Prediction source cutoff timestamp must precede or match prediction instant, never forward outcomes."""
        from datetime import date, datetime, timedelta, timezone
        from decimal import Decimal
        from phase7.data.contracts import PriceAdjustmentState
        from phase7.targets.alignment import align_forward_observations
        from phase7.targets.contracts import ForwardPriceObservationRecord, PredictionEventRecord

        t_cutoff = datetime(2025, 1, 15, 15, 30, tzinfo=timezone.utc)
        t_pred = datetime(2025, 1, 15, 16, 0, tzinfo=timezone.utc)
        d_pred = date(2025, 1, 15)

        pred = PredictionEventRecord(
            prediction_timestamp=t_pred,
            prediction_trading_date=d_pred,
            symbol="TCS",
            isin="INE467B01029",
            universe_hash="u" * 64,
            dataset_version="1.0.0",
            source_cutoff_timestamp=t_cutoff,
            target_specification_hash="s" * 64,
        )

        obs = [
            ForwardPriceObservationRecord(
                trading_date=d_pred + timedelta(days=1),
                symbol="TCS",
                isin="INE467B01029",
                price=Decimal("100.00"),
                adjustment_state=PriceAdjustmentState.TOTAL_RETURN_ADJUSTED,
                source_timestamp=t_pred + timedelta(days=1),
                source_identifier="TEST",
            )
        ]

        res = align_forward_observations(pred, obs, horizon_trading_days=1)
        self.assertTrue(res.entry_record.trading_date > pred.prediction_trading_date)
        self.assertTrue(res.entry_record.source_timestamp > pred.source_cutoff_timestamp)


if __name__ == "__main__":
    unittest.main()
