"""CI Test Suite: Phase 7 Configuration Schema & Governance Validation."""

import copy
import os
import sys
import unittest
from pathlib import Path
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from phase7.governance.schemas import (
    validate_phase7_config,
    load_and_validate_phase7_config,
    Phase7ConfigValidationError,
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = BASE_DIR / "config" / "phase7.yaml"


class TestPhase7ConfigSchema(unittest.TestCase):

    def setUp(self):
        self.assertTrue(CONFIG_PATH.is_file(), f"Phase 7 config missing at {CONFIG_PATH}")
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            self.valid_config = yaml.safe_load(f)

    def test_canonical_config_passes_validation(self):
        """Verify the repository's config/phase7.yaml passes all schema rules."""
        result = load_and_validate_phase7_config(CONFIG_PATH)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["metadata"]["runtime_python_version"], "3.12")
        self.assertEqual(result["targets"]["primary"]["horizon_trading_days"], 20)

    def test_missing_required_section_raises_error(self):
        """Ensure omitting a required top-level section triggers validation failure."""
        bad_config = copy.deepcopy(self.valid_config)
        del bad_config["targets"]
        with self.assertRaises(Phase7ConfigValidationError) as ctx:
            validate_phase7_config(bad_config)
        self.assertIn("Missing required top-level section: 'targets'", str(ctx.exception))

    def test_forbidden_universe_provider_fails(self):
        """Static legacy features.universe cannot be specified as universe provider."""
        bad_config = copy.deepcopy(self.valid_config)
        bad_config["universe"]["universe_provider"] = "features.universe"
        with self.assertRaises(Phase7ConfigValidationError) as ctx:
            validate_phase7_config(bad_config)
        self.assertIn("forbidden", str(ctx.exception).lower())

    def test_non_integer_basis_points_fail(self):
        """Max stock weight and transaction cost bps must be strict integers."""
        bad_config = copy.deepcopy(self.valid_config)
        bad_config["portfolio"]["max_initial_stock_weight_bps"] = 5.0  # float instead of int
        with self.assertRaises(Phase7ConfigValidationError) as ctx:
            validate_phase7_config(bad_config)
        self.assertIn("must be integer", str(ctx.exception).lower())

    def test_negative_or_zero_cost_scenarios_fail(self):
        """Transaction costs cannot be zero or negative in configuration."""
        bad_config = copy.deepcopy(self.valid_config)
        bad_config["transaction_costs_bps"]["base_scenario_bps"] = 0
        with self.assertRaises(Phase7ConfigValidationError) as ctx:
            validate_phase7_config(bad_config)
        self.assertIn("must be a positive integer", str(ctx.exception).lower())

    def test_same_day_execution_rejected(self):
        """Execution lag must be >= 1 trading day (t+1 next-session execution)."""
        bad_config = copy.deepcopy(self.valid_config)
        bad_config["targets"]["primary"]["execution_lag_trading_days"] = 0
        with self.assertRaises(Phase7ConfigValidationError) as ctx:
            validate_phase7_config(bad_config)
        self.assertIn("execution_lag_trading_days >= 1", str(ctx.exception))

    def test_forbidden_vault_reference_fails(self):
        """Any attempt to point Phase 7 data to Phase 6 vault triggers immediate failure."""
        bad_config = copy.deepcopy(self.valid_config)
        bad_config["universe"]["external_source"] = "C:\\Users\\r_chh\\gaurvideep_vault\\data.csv"
        with self.assertRaises(Phase7ConfigValidationError) as ctx:
            validate_phase7_config(bad_config)
        self.assertIn("Forbidden Phase 6 vault reference", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
