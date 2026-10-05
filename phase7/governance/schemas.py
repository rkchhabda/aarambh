"""Schema validation and governance enforcement for Phase 7 configuration.

Validates config/phase7.yaml against strict research preregistration rules:
1. All required sections must be present.
2. Basis points must be represented as positive integers.
3. Target horizons, purge days, and embargo days must meet preregistered thresholds.
4. Universe must mandate point-in-time construction and prohibit static legacy modules.
5. Vault and archive fields must strictly prohibit Phase 6 external vault references.
6. Prohibited deep learning / black-box architectures must be explicitly banned.
"""

from pathlib import Path
from typing import Any, Dict, List
import yaml


class Phase7ConfigValidationError(ValueError):
    """Raised when Phase 7 configuration violates schema or governance rules."""
    pass


REQUIRED_TOP_LEVEL_SECTIONS = [
    "metadata",
    "universe",
    "targets",
    "validation",
    "feature_families",
    "model_families",
    "portfolio",
    "transaction_costs_bps",
    "success_criteria",
    "governance",
]

FORBIDDEN_VAULT_STRINGS = [
    "window_a_sealed.7z",
    "window_b_sealed.7z",
    "gaurvideep_vault",
]

FORBIDDEN_UNIVERSE_MODULES = [
    "features.universe",
    "features.universe.TICKERS",
]

PROHIBITED_ARCHITECTURES = [
    "lstm",
    "transformer",
    "reinforcement_learning",
    "deep_neural_network",
]


def _check_no_forbidden_vault_references(node: Any, path: str = "config") -> None:
    """Recursively verify that no configuration node references Phase 6 vaults."""
    if isinstance(node, str):
        for forbidden in FORBIDDEN_VAULT_STRINGS:
            # We allow listing them in prohibited_vault_paths / prohibited_vault_archives
            if "prohibited" in path.lower():
                continue
            if forbidden in node:
                raise Phase7ConfigValidationError(
                    f"[GOVERNANCE VIOLATION] Forbidden Phase 6 vault reference '{forbidden}' found at {path}: '{node}'"
                )
    elif isinstance(node, dict):
        for k, v in node.items():
            _check_no_forbidden_vault_references(v, f"{path}.{k}")
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            _check_no_forbidden_vault_references(item, f"{path}[{idx}]")


def validate_phase7_config(config_dict: Dict[str, Any]) -> bool:
    """Validate a parsed Phase 7 configuration dictionary against schema rules.

    Args:
        config_dict: Parsed dictionary from phase7.yaml.

    Returns:
        True if all schema and governance checks pass.

    Raises:
        Phase7ConfigValidationError: If any rule is violated.
    """
    if not isinstance(config_dict, dict):
        raise Phase7ConfigValidationError("Configuration root must be a YAML dictionary.")

    # 1. Required top-level sections
    for section in REQUIRED_TOP_LEVEL_SECTIONS:
        if section not in config_dict:
            raise Phase7ConfigValidationError(f"Missing required top-level section: '{section}'")

    meta = config_dict["metadata"]
    if meta.get("runtime_python_version") != "3.12":
        raise Phase7ConfigValidationError(
            f"Metadata runtime_python_version must be '3.12', got '{meta.get('runtime_python_version')}'"
        )
    if meta.get("status") != "PREREGISTERED":
        raise Phase7ConfigValidationError(
            f"Metadata status must be 'PREREGISTERED', got '{meta.get('status')}'"
        )

    # 2. Universe rules
    uni = config_dict["universe"]
    if not uni.get("point_in_time_required"):
        raise Phase7ConfigValidationError("Universe must mandate 'point_in_time_required: true'")
    if not uni.get("fail_closed_on_unknown_timing"):
        raise Phase7ConfigValidationError("Universe must mandate 'fail_closed_on_unknown_timing: true'")
    if uni.get("universe_provider") in FORBIDDEN_UNIVERSE_MODULES:
        raise Phase7ConfigValidationError(
            f"Universe provider '{uni.get('universe_provider')}' is forbidden (static survivorship risk)."
        )
    if not isinstance(uni.get("min_closing_price_inr"), (int, float)) or uni["min_closing_price_inr"] < 20:
        raise Phase7ConfigValidationError("min_closing_price_inr must be >= 20")
    if not isinstance(uni.get("min_trading_history_days"), int) or uni["min_trading_history_days"] < 252:
        raise Phase7ConfigValidationError("min_trading_history_days must be >= 252")
    if not isinstance(uni.get("min_median_daily_traded_value_60d_crore"), (int, float)) or uni["min_median_daily_traded_value_60d_crore"] < 10:
        raise Phase7ConfigValidationError("min_median_daily_traded_value_60d_crore must be >= 10")

    # 3. Targets
    targets = config_dict["targets"]
    if "primary" not in targets or "secondary" not in targets:
        raise Phase7ConfigValidationError("Both 'primary' and 'secondary' targets must be defined.")

    pri = targets["primary"]
    if pri.get("horizon_trading_days") != 20:
        raise Phase7ConfigValidationError("Primary target horizon must be exactly 20 trading days.")
    if pri.get("execution_lag_trading_days", 0) < 1:
        raise Phase7ConfigValidationError("Primary target must enforce execution_lag_trading_days >= 1 (t+1 execution).")
    if pri.get("prediction_type") != "cross_sectional_rank":
        raise Phase7ConfigValidationError("Primary prediction_type must be 'cross_sectional_rank'.")

    sec = targets["secondary"]
    if sec.get("horizon_trading_days") != 60:
        raise Phase7ConfigValidationError("Secondary target horizon must be exactly 60 trading days.")
    if sec.get("execution_lag_trading_days", 0) < 1:
        raise Phase7ConfigValidationError("Secondary target must enforce execution_lag_trading_days >= 1 (t+1 execution).")

    # 4. Validation
    val = config_dict["validation"]
    if val.get("min_expanding_windows", 0) < 10:
        raise Phase7ConfigValidationError("Validation must specify min_expanding_windows >= 10.")
    if val.get("primary_target_purge_days", 0) < 20:
        raise Phase7ConfigValidationError("Primary target purge days must be >= 20.")
    if val.get("primary_target_embargo_days", 0) < 5:
        raise Phase7ConfigValidationError("Primary target embargo days must be >= 5.")
    if val.get("secondary_target_purge_days", 0) < 60:
        raise Phase7ConfigValidationError("Secondary target purge days must be >= 60.")
    if val.get("secondary_target_embargo_days", 0) < 10:
        raise Phase7ConfigValidationError("Secondary target embargo days must be >= 10.")
    if not val.get("fold_local_preprocessing"):
        raise Phase7ConfigValidationError("Validation must mandate fold_local_preprocessing: true.")

    # 5. Portfolio & Integer Basis Points
    port = config_dict["portfolio"]
    if port.get("type") != "long_only":
        raise Phase7ConfigValidationError("Portfolio type must be 'long_only'.")
    if port.get("selection_target_count") != 20:
        raise Phase7ConfigValidationError("Portfolio selection_target_count must be 20.")

    stock_bps = port.get("max_initial_stock_weight_bps")
    if not isinstance(stock_bps, int) or stock_bps > 500 or stock_bps <= 0:
        raise Phase7ConfigValidationError("max_initial_stock_weight_bps must be integer <= 500 (5.00%).")

    sector_bps = port.get("max_sector_weight_bps")
    if not isinstance(sector_bps, int) or sector_bps > 2500 or sector_bps <= 0:
        raise Phase7ConfigValidationError("max_sector_weight_bps must be integer <= 2500 (25.00%).")

    if port.get("leverage_allowed") is not False:
        raise Phase7ConfigValidationError("Portfolio leverage_allowed must be false.")
    if port.get("short_selling_allowed") is not False:
        raise Phase7ConfigValidationError("Portfolio short_selling_allowed must be false.")

    # 6. Transaction costs
    costs = config_dict["transaction_costs_bps"]
    for scenario in ["base_scenario_bps", "conservative_scenario_bps", "stress_scenario_bps"]:
        val_bps = costs.get(scenario)
        if not isinstance(val_bps, int) or val_bps <= 0:
            raise Phase7ConfigValidationError(f"Transaction cost scenario '{scenario}' must be a positive integer.")
    if costs["base_scenario_bps"] != 25 or costs["conservative_scenario_bps"] != 50 or costs["stress_scenario_bps"] != 75:
        raise Phase7ConfigValidationError("Cost scenarios must be exactly 25, 50, and 75 bps.")

    # 7. Model Families & Prohibited Architectures
    mf = config_dict["model_families"]
    prohibited = mf.get("prohibited_architectures", [])
    for p in PROHIBITED_ARCHITECTURES:
        if p not in prohibited:
            raise Phase7ConfigValidationError(f"Prohibited architecture '{p}' must be listed in prohibited_architectures.")

    # 8. Governance & Vault safety
    _check_no_forbidden_vault_references(config_dict)

    gov = config_dict["governance"]
    if not gov.get("phase6_immutability_enforced"):
        raise Phase7ConfigValidationError("Governance must enforce phase6_immutability_enforced: true.")
    if gov.get("max_total_registered_trials", 0) > 100:
        raise Phase7ConfigValidationError("max_total_registered_trials cannot exceed 100.")

    return True


def load_and_validate_phase7_config(config_path: Path) -> Dict[str, Any]:
    """Load phase7.yaml from disk and validate it."""
    if not config_path.is_file():
        raise FileNotFoundError(f"Phase 7 config file not found at: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    validate_phase7_config(data)
    return data
