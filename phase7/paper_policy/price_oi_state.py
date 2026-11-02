"""Governed Price/Open-Interest State Classification Policy [Milestone 4.14].

Classifies derivative contract state into LONG_BUILDUP, SHORT_COVERING,
SHORT_BUILDUP, LONG_UNWINDING, NEUTRAL_PRICE, NEUTRAL_OI, or INDETERMINATE.
Labels output strictly as PRICE_OI_STATE. INSTITUTIONAL_POSITIONING is prohibited.
"""

from typing import Any, Dict, Optional, Tuple

from phase7.paper_policy.config import PriceOIConfig
from phase7.paper_policy.constants import (
    GOVERNED_PRICE_OI_LABEL,
    PROHIBITED_PRICE_OI_LABEL,
    PriceOIState,
)
from phase7.paper_policy.reason_codes import PolicyReasonCode


def classify_price_oi_state(
    prev_price: float,
    curr_price: float,
    prev_oi: int,
    curr_oi: int,
    contract_info: Optional[Dict[str, Any]] = None,
    config: Optional[PriceOIConfig] = None,
) -> Tuple[PriceOIState, Optional[str], Dict[str, Any]]:
    """Classify Price and OI state changes.

    Returns:
        (state_enum, reason_code, details_dict)
    """
    cfg = config or PriceOIConfig()
    info = contract_info or {}

    # 1. Contract continuity and boundary validations
    if info.get("symbol_mismatch", False):
        return (
            PriceOIState.INSUFFICIENT_DATA,
            PolicyReasonCode.WRONG_SYMBOL_NO_DECISION.value,
            {"error": "UNDERLYING_SYMBOL_MISMATCH"},
        )
    if info.get("contract_mismatch", False):
        return (
            PriceOIState.INSUFFICIENT_DATA,
            PolicyReasonCode.CONTRACT_MISMATCH_NO_DECISION.value,
            {"error": "CONTRACT_SPECIFICATION_MISMATCH"},
        )
    if info.get("expiry_mismatch", False):
        return (
            PriceOIState.INSUFFICIENT_DATA,
            PolicyReasonCode.MIXED_EXPIRY_REJECTED.value,
            {"error": "EXPIRY_DATE_MISMATCH"},
        )
    if info.get("rollover_mismatch", False):
        return (
            PriceOIState.INSUFFICIENT_DATA,
            PolicyReasonCode.ROLLOVER_MISMATCH_NO_DECISION.value,
            {"error": "ROLLOVER_STATE_MISMATCH"},
        )
    if info.get("corporate_action_unresolved", False):
        return (
            PriceOIState.INSUFFICIENT_DATA,
            PolicyReasonCode.CORPORATE_ACTION_UNRESOLVED_NO_DECISION.value,
            {"error": "CORPORATE_ACTION_UNRESOLVED"},
        )

    # 2. Price and OI baseline validation
    if prev_price <= 0 or curr_price <= 0:
        return (
            PriceOIState.INSUFFICIENT_DATA,
            PolicyReasonCode.ZERO_VOLUME_NO_DECISION.value,
            {"error": "INVALID_PRICE_BASELINE", "prev_price": prev_price, "curr_price": curr_price},
        )
    if prev_oi <= 0:
        return (
            PriceOIState.INSUFFICIENT_DATA,
            PolicyReasonCode.ZERO_PRIOR_OI_NO_DECISION.value,
            {"error": "ZERO_OR_NEGATIVE_PRIOR_OI", "prev_oi": prev_oi},
        )

    price_change_pct = ((curr_price - prev_price) / prev_price) * 100.0
    oi_change_pct = ((curr_oi - prev_oi) / float(prev_oi)) * 100.0

    abs_price = abs(price_change_pct)
    abs_oi = abs(oi_change_pct)

    # 3. Neutral Band Evaluation
    is_price_neutral = abs_price <= cfg.price_neutral_band_pct
    is_oi_neutral = abs_oi <= cfg.oi_neutral_band_pct

    details = {
        "label": GOVERNED_PRICE_OI_LABEL,
        "price_change_pct": round(price_change_pct, 4),
        "oi_change_pct": round(oi_change_pct, 4),
        "prev_price": prev_price,
        "curr_price": curr_price,
        "prev_oi": prev_oi,
        "curr_oi": curr_oi,
    }

    if is_price_neutral and is_oi_neutral:
        return PriceOIState.INDETERMINATE, None, {**details, "state": PriceOIState.INDETERMINATE.value, "reason": "BOTH_NEUTRAL"}
    if is_price_neutral:
        return PriceOIState.NEUTRAL_PRICE, None, {**details, "state": PriceOIState.NEUTRAL_PRICE.value}
    if is_oi_neutral:
        return PriceOIState.NEUTRAL_OI, None, {**details, "state": PriceOIState.NEUTRAL_OI.value}

    # 4. State classification against thresholds
    p_thresh = cfg.price_state_threshold_pct
    oi_thresh = cfg.oi_state_threshold_pct

    if price_change_pct >= p_thresh and oi_change_pct >= oi_thresh:
        state = PriceOIState.LONG_BUILDUP
    elif price_change_pct >= p_thresh and oi_change_pct <= -oi_thresh:
        state = PriceOIState.SHORT_COVERING
    elif price_change_pct <= -p_thresh and oi_change_pct >= oi_thresh:
        state = PriceOIState.SHORT_BUILDUP
    elif price_change_pct <= -p_thresh and oi_change_pct <= -oi_thresh:
        state = PriceOIState.LONG_UNWINDING
    else:
        state = PriceOIState.INDETERMINATE

    details["state"] = state.value
    return state, None, details
