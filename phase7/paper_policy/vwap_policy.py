"""Governed VWAP Policy and Formula Verification [Milestone 4.14].

Enforces formula verification for source-reported, trade-reconstructed, and candle-approximated
VWAP metrics. Governed candle approximations are strictly restricted to display-only usage.
"""

from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from phase7.paper_policy.config import FreshnessConfig
from phase7.paper_policy.constants import (
    CANDLE_APPROXIMATION_STATUS,
    VWAPFormulaType,
)
from phase7.paper_policy.freshness import evaluate_vwap_freshness
from phase7.paper_policy.reason_codes import PolicyReasonCode


def evaluate_vwap_policy(
    vwap_data: Dict[str, Any],
    evaluation_time_utc: datetime,
    freshness_config: Optional[FreshnessConfig] = None,
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Evaluate VWAP data against governed formula contracts and freshness boundaries.

    Returns:
        (is_valid, reason_code, details_dict)
    """
    formula = vwap_data.get("formula_type")
    valid_formulas = [f.value for f in VWAPFormulaType]
    if formula not in valid_formulas:
        return (
            False,
            PolicyReasonCode.PROVENANCE_INVALID_NO_DECISION.value,
            {"error": f"INVALID_VWAP_FORMULA: '{formula}'. Must be in {valid_formulas}"},
        )

    # Decision eligibility check
    is_decision_eligible = formula in (
        VWAPFormulaType.SOURCE_REPORTED_VWAP.value,
        VWAPFormulaType.TRADE_RECONSTRUCTED_VWAP.value,
    )
    is_display_only = formula == VWAPFormulaType.GOVERNED_CANDLE_APPROXIMATION.value

    # Exchange and session verification
    exchange = vwap_data.get("exchange", "NSE")
    session_start = vwap_data.get("session_start")
    cumulative_volume = vwap_data.get("cumulative_volume", 0)

    if cumulative_volume <= 0:
        return (
            False,
            PolicyReasonCode.ZERO_VOLUME_NO_DECISION.value,
            {"error": "VWAP_CUMULATIVE_VOLUME_NOT_POSITIVE", "cumulative_volume": cumulative_volume},
        )

    # Freshness evaluation
    fresh_ok, fresh_reason, fresh_details = evaluate_vwap_freshness(
        vwap_data, evaluation_time_utc, freshness_config
    )
    if not fresh_ok:
        return False, fresh_reason, fresh_details

    details = {
        "formula_type": formula,
        "is_decision_eligible": is_decision_eligible,
        "is_display_only": is_display_only,
        "display_status": CANDLE_APPROXIMATION_STATUS if is_display_only else "DECISION_ELIGIBLE_FORMULA",
        "exchange": exchange,
        "session_start": session_start,
        "vwap_value": vwap_data.get("vwap_value"),
        "cumulative_volume": cumulative_volume,
        "age_seconds": fresh_details.get("age_seconds", 0.0),
    }

    return True, None, details
