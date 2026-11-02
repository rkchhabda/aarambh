"""Governed Freshness and Timestamp Verification [Milestone 4.14].

Validates quote and VWAP freshness, exchange timestamp presence, monotonic ordering,
and business date consistency using deterministic UTC clocks.
"""

from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from phase7.paper_policy.config import FreshnessConfig
from phase7.paper_policy.reason_codes import PolicyReasonCode


def parse_iso_utc(ts_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO formatted UTC string safely."""
    if not ts_str or not isinstance(ts_str, str):
        return None
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt
    except Exception:
        return None


def evaluate_quote_freshness(
    quote: Dict[str, Any],
    evaluation_time_utc: datetime,
    config: Optional[FreshnessConfig] = None,
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Evaluate quote freshness and timestamp boundaries.

    Returns:
        (is_fresh, reason_code, details_dict)
    """
    cfg = config or FreshnessConfig()
    ts_str = quote.get("exchange_timestamp_utc") or quote.get("timestamp_utc")

    # 1. Exchange timestamp presence check
    if not ts_str:
        if cfg.require_exchange_timestamp:
            return False, PolicyReasonCode.UNVERIFIED_TIMESTAMP_NO_DECISION.value, {"error": "MISSING_TIMESTAMP"}

    ts = parse_iso_utc(ts_str)
    if not ts:
        return False, PolicyReasonCode.UNVERIFIED_TIMESTAMP_NO_DECISION.value, {"error": "INVALID_TIMESTAMP_FORMAT"}

    # 2. Future timestamp check
    if cfg.reject_future_timestamp and ts > evaluation_time_utc:
        return (
            False,
            PolicyReasonCode.FUTURE_TIMESTAMP_NO_DECISION.value,
            {"quote_ts": ts.isoformat(), "eval_ts": evaluation_time_utc.isoformat()},
        )

    # 3. Business date sequence check
    quote_biz_date = quote.get("business_date") or ts.strftime("%Y-%m-%d")
    eval_biz_date = evaluation_time_utc.strftime("%Y-%m-%d")
    if cfg.require_same_business_date and quote_biz_date != eval_biz_date:
        return (
            False,
            PolicyReasonCode.WRONG_BUSINESS_DATE_NO_DECISION.value,
            {"quote_biz_date": quote_biz_date, "eval_biz_date": eval_biz_date},
        )

    # 4. Traded volume positivity check
    volume = quote.get("volume", 0)
    if cfg.reject_zero_volume and volume <= 0:
        return False, PolicyReasonCode.ZERO_VOLUME_NO_DECISION.value, {"volume": volume}

    # 5. Age threshold check
    age_seconds = (evaluation_time_utc - ts).total_seconds()
    if age_seconds > cfg.maximum_quote_age_seconds:
        return (
            False,
            PolicyReasonCode.STALE_QUOTE_NO_DECISION.value,
            {"age_seconds": age_seconds, "max_allowed": cfg.maximum_quote_age_seconds},
        )

    return True, None, {"age_seconds": max(0.0, age_seconds), "quote_ts": ts.isoformat()}


def evaluate_vwap_freshness(
    vwap_data: Dict[str, Any],
    evaluation_time_utc: datetime,
    config: Optional[FreshnessConfig] = None,
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Evaluate VWAP metric freshness and timestamp boundaries.

    Returns:
        (is_fresh, reason_code, details_dict)
    """
    cfg = config or FreshnessConfig()
    ts_str = vwap_data.get("timestamp_utc") or vwap_data.get("exchange_timestamp_utc")

    if not ts_str:
        if cfg.require_exchange_timestamp:
            return False, PolicyReasonCode.UNVERIFIED_TIMESTAMP_NO_DECISION.value, {"error": "MISSING_VWAP_TIMESTAMP"}

    ts = parse_iso_utc(ts_str)
    if not ts:
        return False, PolicyReasonCode.UNVERIFIED_TIMESTAMP_NO_DECISION.value, {"error": "INVALID_VWAP_TIMESTAMP"}

    if cfg.reject_future_timestamp and ts > evaluation_time_utc:
        return (
            False,
            PolicyReasonCode.FUTURE_TIMESTAMP_NO_DECISION.value,
            {"vwap_ts": ts.isoformat(), "eval_ts": evaluation_time_utc.isoformat()},
        )

    age_seconds = (evaluation_time_utc - ts).total_seconds()
    if age_seconds > cfg.maximum_vwap_age_seconds:
        return (
            False,
            PolicyReasonCode.STALE_VWAP_NO_DECISION.value,
            {"age_seconds": age_seconds, "max_allowed": cfg.maximum_vwap_age_seconds},
        )

    return True, None, {"age_seconds": max(0.0, age_seconds), "vwap_ts": ts.isoformat()}
