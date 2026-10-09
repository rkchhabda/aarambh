"""CI Test Suite: Validation Module Isolation and Boundary Defense.

Verifies:
1. Validation modules (phase7/validation/) do not import feature engineering, models, portfolio, or Phase 6 scripts.
2. Validation modules do not import production service routes (service/).
3. Validation code contains zero references to Phase 6 sealed vaults or archives.
4. Validation code does not write to data/ directory.
5. phase7.validation exports only explicit canonical symbols without wildcard leaks.
"""

import os
from pathlib import Path
import unittest

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class TestValidationIsolation(unittest.TestCase):

    def test_validation_modules_have_no_forbidden_imports(self):
        """Active phase7/validation/ modules must not import features, models, portfolio, Phase 6 scripts, or service routes."""
        val_dir = BASE_DIR / "phase7" / "validation"
        self.assertTrue(val_dir.is_dir(), f"phase7/validation directory missing at {val_dir}")

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
        for root, _, files in os.walk(val_dir):
            for f in files:
                if not f.endswith(".py"):
                    continue
                fpath = Path(root) / f
                content = fpath.read_text(encoding="utf-8", errors="ignore")
                for imp in forbidden_imports:
                    if f"import {imp}" in content or f"from {imp}" in content:
                        violations.append(f"{fpath.relative_to(BASE_DIR)} imports {imp}")

        self.assertEqual(violations, [], f"Forbidden imports detected in phase7/validation/:\n" + "\n".join(violations))

    def test_validation_modules_have_no_phase6_vault_references(self):
        """Active phase7/validation/ modules must contain zero references to Phase 6 vault paths or archives."""
        val_dir = BASE_DIR / "phase7" / "validation"
        forbidden_vault_patterns = [
            "gaurvideep_vault",
            "window_a_sealed",
            "window_b_sealed",
            "vault_secret",
            "vault_password",
        ]

        violations = []
        for root, _, files in os.walk(val_dir):
            for f in files:
                if not f.endswith(".py"):
                    continue
                fpath = Path(root) / f
                content = fpath.read_text(encoding="utf-8", errors="ignore").lower()
                for pat in forbidden_vault_patterns:
                    if pat in content:
                        violations.append(f"{fpath.relative_to(BASE_DIR)} contains vault reference '{pat}'")

        self.assertEqual(violations, [], f"Forbidden Phase 6 vault references in phase7/validation/:\n" + "\n".join(violations))

    def test_no_wildcard_export_leaks_and_clean_validation_namespace(self):
        """phase7.validation exports only explicit canonical symbols; no wildcard leaks."""
        import phase7.validation as pv
        self.assertTrue(hasattr(pv, "__all__"))
        forbidden_tokens = ["feature", "model", "vault", "train_model", "alpha", "sharpe", "weight", "portfolio"]
        for sym in pv.__all__:
            for tok in forbidden_tokens:
                self.assertNotIn(tok, sym.lower(), f"Validation export '{sym}' contains forbidden token '{tok}'!")

    def test_validation_code_does_not_write_to_data_directory(self):
        """Validation modules must not contain hardcoded write operations into data/."""
        val_dir = BASE_DIR / "phase7" / "validation"
        write_patterns = [
            ".to_csv('data/",
            '.to_csv("data/',
            ".to_parquet('data/",
            '.to_parquet("data/',
            "open('data/",
            'open("data/',
        ]
        violations = []
        for root, _, files in os.walk(val_dir):
            for f in files:
                if not f.endswith(".py"):
                    continue
                fpath = Path(root) / f
                content = fpath.read_text(encoding="utf-8", errors="ignore")
                for wp in write_patterns:
                    if wp in content:
                        violations.append(f"{fpath.relative_to(BASE_DIR)} contains write pattern '{wp}'")

        self.assertEqual(violations, [], f"Data directory write calls detected:\n" + "\n".join(violations))
