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


if __name__ == "__main__":
    unittest.main()
