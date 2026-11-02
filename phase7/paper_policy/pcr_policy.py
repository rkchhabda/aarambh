"""Governed Put-Call Ratio (PCR) Policy [Milestone 4.14].

Calculates Open-Interest and Volume Put-Call Ratios across governed option contracts.
Enforces single-expiry, single business-date, strike-window filtering, and zero-denominator rejection.
"""

from typing import Any, Dict, List, Optional, Tuple

from phase7.paper_policy.config import OptionsQualityConfig
from phase7.paper_policy.reason_codes import PolicyReasonCode


def calculate_pcr(
    contracts: List[Dict[str, Any]],
    spot_price: float,
    target_expiry: Optional[str] = None,
    target_business_date: Optional[str] = None,
    config: Optional[OptionsQualityConfig] = None,
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Calculate OI and Volume Put-Call Ratios for governed contracts.

    Returns:
        (is_valid, reason_code, details_dict)
    """
    cfg = config or OptionsQualityConfig()
    if not contracts or spot_price <= 0:
        return (
            False,
            PolicyReasonCode.OPTIONS_INSUFFICIENT_LIQUIDITY_NO_DECISION.value,
            {"error": "NO_CONTRACTS_OR_INVALID_SPOT"},
        )

    # 1. Single-expiry and single-date verification
    expiries = {c.get("expiry_date") for c in contracts if c.get("expiry_date")}
    if len(expiries) > 1 and not target_expiry:
        return (
            False,
            PolicyReasonCode.MIXED_EXPIRY_REJECTED.value,
            {"error": "MULTIPLE_EXPIRIES_DETECTED", "expiries": list(expiries)},
        )

    active_expiry = target_expiry or (next(iter(expiries)) if expiries else None)

    biz_dates = {c.get("business_date") for c in contracts if c.get("business_date")}
    if len(biz_dates) > 1 and not target_business_date:
        return (
            False,
            PolicyReasonCode.WRONG_BUSINESS_DATE_NO_DECISION.value,
            {"error": "MULTIPLE_BUSINESS_DATES_DETECTED", "dates": list(biz_dates)},
        )

    active_date = target_business_date or (next(iter(biz_dates)) if biz_dates else None)

    total_put_oi = 0
    total_call_oi = 0
    total_put_vol = 0
    total_call_vol = 0

    included_count = 0
    excluded_count = 0

    for c in contracts:
        # Expiry match check
        if active_expiry and c.get("expiry_date") != active_expiry:
            excluded_count += 1
            continue

        # Business date match check
        if active_date and c.get("business_date") != active_date:
            excluded_count += 1
            continue

        strike = c.get("strike_price", 0.0)
        dist_pct = abs(strike - spot_price) / spot_price * 100.0 if spot_price > 0 else 999.0
        if dist_pct > cfg.strike_window_pct:
            excluded_count += 1
            continue

        opt_type = c.get("option_type", "").upper()
        oi = c.get("open_interest", 0)
        vol = c.get("volume", 0)

        if oi <= 0 and vol <= 0:
            excluded_count += 1
            continue

        if opt_type == "PE":
            if oi > 0:
                total_put_oi += oi
            if vol > 0:
                total_put_vol += vol
            included_count += 1
        elif opt_type == "CE":
            if oi > 0:
                total_call_oi += oi
            if vol > 0:
                total_call_vol += vol
            included_count += 1
        else:
            excluded_count += 1

    # Zero denominator protection
    if total_call_oi <= 0:
        return (
            False,
            PolicyReasonCode.PCR_ZERO_DENOMINATOR_NO_DECISION.value,
            {
                "error": "CALL_OI_DENOMINATOR_ZERO",
                "total_put_oi": total_put_oi,
                "total_call_oi": total_call_oi,
                "included_count": included_count,
                "excluded_count": excluded_count,
            },
        )

    oi_pcr = round(total_put_oi / float(total_call_oi), 4)
    vol_pcr = round(total_put_vol / float(total_call_vol), 4) if total_call_vol > 0 else None

    details = {
        "oi_pcr": oi_pcr,
        "volume_pcr": vol_pcr,
        "total_put_oi": total_put_oi,
        "total_call_oi": total_call_oi,
        "total_put_vol": total_put_vol,
        "total_call_vol": total_call_vol,
        "included_contracts": included_count,
        "excluded_contracts": excluded_count,
        "expiry": active_expiry,
        "business_date": active_date,
    }
    return True, None, details
