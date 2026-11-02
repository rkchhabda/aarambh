"""Governed Paper Risk and Allocation Policy [Milestone 4.14].

Computes theoretical paper-only risk sizing and caps for synthetic/recorded fixtures.
Outputs are strictly labeled PAPER_POSITION_ESTIMATE. Order execution or broker
terms are strictly prohibited and structurally rejected.
"""

from typing import Any, Dict, Optional, Tuple

from phase7.paper_policy.config import PaperRiskConfig
from phase7.paper_policy.constants import (
    GOVERNED_RISK_OUTPUT_LABEL,
    PROHIBITED_RISK_OUTPUT_LABELS,
    SourceMode,
)
from phase7.paper_policy.reason_codes import PolicyReasonCode


def evaluate_paper_risk(
    entry_price: float,
    stop_loss_price: float,
    take_profit_price: float,
    portfolio_capital: float,
    source_mode: str,
    open_observations_count: int = 0,
    current_sector_exposure_pct: float = 0.0,
    config: Optional[PaperRiskConfig] = None,
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Evaluate and compute paper position estimate within strict governance bounds.

    Returns:
        (is_eligible, reason_code, details_dict)
    """
    cfg = config or PaperRiskConfig()

    # 1. Source mode check: Paper risk estimates are only permissible in offline synthetic/fixture modes
    if source_mode == SourceMode.LIVE_SOURCE.value:
        return (
            False,
            PolicyReasonCode.EXTERNAL_ACQUISITION_BLOCKED.value,
            {"error": "RISK_CALCULATION_BLOCKED_FOR_LIVE_SOURCE"},
        )

    # 2. Capital and pricing validity
    if portfolio_capital <= 0 or entry_price <= 0 or stop_loss_price <= 0 or take_profit_price <= 0:
        return (
            False,
            PolicyReasonCode.RISK_LIMIT_EXCEEDED_NO_DECISION.value,
            {"error": "INVALID_PRICE_OR_CAPITAL_PARAMETERS"},
        )

    # 3. Stop loss and distance check
    stop_distance_pct = abs(entry_price - stop_loss_price) / entry_price * 100.0
    if stop_distance_pct < cfg.minimum_stop_distance_pct or stop_distance_pct > cfg.maximum_stop_distance_pct:
        return (
            False,
            PolicyReasonCode.RISK_LIMIT_EXCEEDED_NO_DECISION.value,
            {
                "error": "STOP_DISTANCE_OUT_OF_BOUNDS",
                "stop_distance_pct": round(stop_distance_pct, 4),
                "min_allowed": cfg.minimum_stop_distance_pct,
                "max_allowed": cfg.maximum_stop_distance_pct,
            },
        )

    # 4. Reward-to-Risk ratio check
    reward_distance = abs(take_profit_price - entry_price)
    risk_distance = abs(entry_price - stop_loss_price)
    if risk_distance <= 0:
        return (
            False,
            PolicyReasonCode.RISK_LIMIT_EXCEEDED_NO_DECISION.value,
            {"error": "ZERO_RISK_DISTANCE"},
        )

    rr_ratio = reward_distance / risk_distance
    if rr_ratio < cfg.minimum_reward_risk_ratio:
        return (
            False,
            PolicyReasonCode.RISK_LIMIT_EXCEEDED_NO_DECISION.value,
            {
                "error": "REWARD_RISK_RATIO_BELOW_MINIMUM",
                "rr_ratio": round(rr_ratio, 4),
                "min_required": cfg.minimum_reward_risk_ratio,
            },
        )

    # 5. Open observations cap check
    if open_observations_count >= cfg.maximum_open_observations:
        return (
            False,
            PolicyReasonCode.RISK_LIMIT_EXCEEDED_NO_DECISION.value,
            {
                "error": "MAX_OPEN_OBSERVATIONS_EXCEEDED",
                "open_count": open_observations_count,
                "max_allowed": cfg.maximum_open_observations,
            },
        )

    # 6. Sector exposure cap check
    if current_sector_exposure_pct >= cfg.maximum_sector_exposure_pct:
        return (
            False,
            PolicyReasonCode.RISK_LIMIT_EXCEEDED_NO_DECISION.value,
            {
                "error": "SECTOR_EXPOSURE_CAP_EXCEEDED",
                "current_sector_pct": current_sector_exposure_pct,
                "max_allowed": cfg.maximum_sector_exposure_pct,
            },
        )

    # 7. Paper position estimate computation
    capital_at_risk = portfolio_capital * (cfg.risk_per_observation_pct / 100.0)
    raw_position_value = capital_at_risk / (stop_distance_pct / 100.0)
    max_position_value = portfolio_capital * (cfg.maximum_position_pct / 100.0)
    capped_position_value = min(raw_position_value, max_position_value)
    capped_position_pct = (capped_position_value / portfolio_capital) * 100.0

    output = {
        "output_type": GOVERNED_RISK_OUTPUT_LABEL,
        "entry_price": entry_price,
        "stop_loss_price": stop_loss_price,
        "take_profit_price": take_profit_price,
        "stop_distance_pct": round(stop_distance_pct, 4),
        "reward_risk_ratio": round(rr_ratio, 4),
        "capital_at_risk": round(capital_at_risk, 2),
        "paper_position_value": round(capped_position_value, 2),
        "paper_position_pct": round(capped_position_pct, 4),
        "portfolio_capital": portfolio_capital,
        "disclaimer": "THEORETICAL_PAPER_ONLY_NOT_AN_ORDER_OR_RECOMMENDATION",
    }

    # Safeguard assertion against prohibited order terms
    for key in output.keys():
        if key in PROHIBITED_RISK_OUTPUT_LABELS:
            raise RuntimeError(f"PROHIBITED_RISK_TERM_DETECTED: '{key}'")

    return True, None, output
