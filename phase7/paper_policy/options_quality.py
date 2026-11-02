"""Governed Options Wall Quality and Liquidity Verification [Milestone 4.14].

Evaluates option chain strike quality, call/put resistance/support walls,
and liquidity confidence. Produces conflict metadata only; never overrides targets.
"""

from typing import Any, Dict, List, Optional, Tuple

from phase7.paper_policy.config import OptionsQualityConfig
from phase7.paper_policy.constants import OptionsWallConfidence
from phase7.paper_policy.reason_codes import PolicyReasonCode


def evaluate_strike_liquidity(
    strike_data: Dict[str, Any],
    spot_price: float,
    config: Optional[OptionsQualityConfig] = None,
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Evaluate an individual strike for liquidity quality within the strike window.

    Returns:
        (is_liquid, reason_code, details)
    """
    cfg = config or OptionsQualityConfig()
    strike = strike_data.get("strike_price", 0.0)
    if spot_price <= 0 or strike <= 0:
        return False, PolicyReasonCode.OPTIONS_INSUFFICIENT_LIQUIDITY_NO_DECISION.value, {"error": "INVALID_STRIKE_OR_SPOT"}

    distance_pct = abs(strike - spot_price) / spot_price * 100.0
    if distance_pct > cfg.strike_window_pct:
        return (
            False,
            PolicyReasonCode.OPTIONS_INSUFFICIENT_LIQUIDITY_NO_DECISION.value,
            {"error": "OUTSIDE_STRIKE_WINDOW", "distance_pct": distance_pct, "max_allowed": cfg.strike_window_pct},
        )

    oi = strike_data.get("open_interest", 0)
    vol = strike_data.get("volume", 0)
    trades = strike_data.get("trade_count", 0)
    bid = strike_data.get("bid_price", 0.0)
    ask = strike_data.get("ask_price", 0.0)

    if oi < cfg.minimum_open_interest or vol < cfg.minimum_volume or trades < cfg.minimum_trade_count:
        return (
            False,
            PolicyReasonCode.OPTIONS_INSUFFICIENT_LIQUIDITY_NO_DECISION.value,
            {"error": "MINIMUM_LIQUIDITY_NOT_MET", "oi": oi, "vol": vol, "trades": trades},
        )

    # Spread check
    mid = (bid + ask) / 2.0 if (bid > 0 and ask > 0) else 0.0
    if mid > 0:
        spread_pct = (ask - bid) / mid * 100.0
        if spread_pct > cfg.maximum_bid_ask_spread_pct:
            return (
                False,
                PolicyReasonCode.OPTIONS_INSUFFICIENT_LIQUIDITY_NO_DECISION.value,
                {"error": "SPREAD_EXCEEDS_MAXIMUM", "spread_pct": spread_pct, "max_allowed": cfg.maximum_bid_ask_spread_pct},
            )

    return True, None, {"strike": strike, "distance_pct": round(distance_pct, 2), "oi": oi, "vol": vol}


def evaluate_options_wall(
    strikes: List[Dict[str, Any]],
    spot_price: float,
    config: Optional[OptionsQualityConfig] = None,
) -> Tuple[OptionsWallConfidence, Dict[str, Any]]:
    """Identify call/put options walls and assign governed confidence state.

    Returns:
        (confidence_state, wall_metadata)
    """
    cfg = config or OptionsQualityConfig()
    if not strikes or spot_price <= 0:
        return OptionsWallConfidence.INDETERMINATE, {"error": "NO_STRIKES_OR_INVALID_SPOT"}

    valid_calls: List[Dict[str, Any]] = []
    valid_puts: List[Dict[str, Any]] = []

    for s in strikes:
        is_liq, _, det = evaluate_strike_liquidity(s, spot_price, cfg)
        if is_liq:
            opt_type = s.get("option_type", "").upper()
            if opt_type == "CE":
                valid_calls.append(s)
            elif opt_type == "PE":
                valid_puts.append(s)

    if not valid_calls and not valid_puts:
        return OptionsWallConfidence.INSUFFICIENT_LIQUIDITY, {
            "valid_call_strikes": 0,
            "valid_put_strikes": 0,
            "call_wall": None,
            "put_wall": None,
        }

    # Find highest OI strike for call wall and put wall
    call_wall = max(valid_calls, key=lambda x: x.get("open_interest", 0)) if valid_calls else None
    put_wall = max(valid_puts, key=lambda x: x.get("open_interest", 0)) if valid_puts else None

    # Determine confidence
    total_valid = len(valid_calls) + len(valid_puts)
    call_oi = call_wall.get("open_interest", 0) if call_wall else 0
    put_oi = put_wall.get("open_interest", 0) if put_wall else 0

    if total_valid >= 6 and call_oi >= cfg.minimum_open_interest * 2 and put_oi >= cfg.minimum_open_interest * 2:
        confidence = OptionsWallConfidence.HIGH_CONFIDENCE
    elif total_valid >= 2 and (call_oi >= cfg.minimum_open_interest or put_oi >= cfg.minimum_open_interest):
        confidence = OptionsWallConfidence.MEDIUM_CONFIDENCE
    elif total_valid > 0:
        confidence = OptionsWallConfidence.LOW_CONFIDENCE
    else:
        confidence = OptionsWallConfidence.INSUFFICIENT_LIQUIDITY

    metadata = {
        "confidence": confidence.value,
        "call_wall_strike": call_wall.get("strike_price") if call_wall else None,
        "call_wall_oi": call_oi,
        "put_wall_strike": put_wall.get("strike_price") if put_wall else None,
        "put_wall_oi": put_oi,
        "valid_call_count": len(valid_calls),
        "valid_put_count": len(valid_puts),
        "conflict_metadata_only": True,
    }
    return confidence, metadata
