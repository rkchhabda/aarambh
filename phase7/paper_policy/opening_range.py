"""Governed Opening-Range Policy [Milestone 4.14].

Evaluates the 09:15 to 09:30 IST opening range interval with a mandatory 30-second
finalization buffer (earliest evaluation at 09:30:30 IST). Uses deterministic timestamps.
"""

from datetime import datetime, time
from typing import Any, Dict, Optional, Tuple

from phase7.paper_policy.config import OpeningRangeConfig
from phase7.paper_policy.constants import OpeningRangeOutcome
from phase7.paper_policy.reason_codes import PolicyReasonCode


def parse_time_str(t_str: str) -> time:
    """Parse HH:MM:SS string to time object."""
    parts = [int(p) for p in t_str.split(":")]
    if len(parts) == 3:
        return time(parts[0], parts[1], parts[2])
    elif len(parts) == 2:
        return time(parts[0], parts[1], 0)
    raise ValueError(f"Invalid time format: '{t_str}'")


def evaluate_opening_range(
    data: Dict[str, Any],
    evaluation_time_ist: Any,
    config: Optional[OpeningRangeConfig] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """Evaluate opening range data against governed finalization contracts.

    Returns:
        (is_ready, outcome_or_reason, details_dict)
    """
    cfg = config or OpeningRangeConfig()

    high = data.get("high")
    low = data.get("low")
    volume = data.get("volume", 0)
    finalized = data.get("finalized", True)

    # 1. Price and structure validity check
    if high is None or low is None or high <= 0 or low <= 0 or high < low:
        return (
            False,
            OpeningRangeOutcome.OPENING_RANGE_INVALID_NO_DECISION.value,
            {"error": "INVALID_HIGH_LOW_BOUNDS", "high": high, "low": low},
        )

    # 2. Positive volume check
    if cfg.require_positive_volume and volume <= 0:
        return (
            False,
            OpeningRangeOutcome.OPENING_RANGE_INVALID_NO_DECISION.value,
            {"error": "ZERO_OR_NEGATIVE_OPENING_VOLUME", "volume": volume},
        )

    # 3. Finalization timing check
    eval_t: time
    if isinstance(evaluation_time_ist, str):
        eval_t = parse_time_str(evaluation_time_ist)
    elif isinstance(evaluation_time_ist, datetime):
        eval_t = evaluation_time_ist.time()
    elif isinstance(evaluation_time_ist, time):
        eval_t = evaluation_time_ist
    else:
        return (
            False,
            OpeningRangeOutcome.OPENING_RANGE_INVALID_NO_DECISION.value,
            {"error": "INVALID_EVALUATION_TIME_TYPE"},
        )

    earliest_t = parse_time_str(cfg.earliest_evaluation)
    if eval_t < earliest_t or (cfg.require_finalized_interval and not finalized):
        return (
            False,
            OpeningRangeOutcome.OPENING_RANGE_INCOMPLETE_NO_DECISION.value,
            {
                "eval_time_ist": eval_t.strftime("%H:%M:%S"),
                "earliest_required": cfg.earliest_evaluation,
                "finalized": finalized,
            },
        )

    # Stale market day boundary check (e.g. past standard session close 15:30:00)
    session_close = time(15, 30, 0)
    if eval_t > session_close:
        return (
            False,
            OpeningRangeOutcome.OPENING_RANGE_STALE_NO_DECISION.value,
            {"eval_time_ist": eval_t.strftime("%H:%M:%S"), "session_close": "15:30:00"},
        )

    details = {
        "range_high": high,
        "range_low": low,
        "range_spread": round(high - low, 4),
        "range_spread_pct": round(((high - low) / low) * 100.0, 4),
        "volume": volume,
        "finalized": True,
        "outcome": OpeningRangeOutcome.OPENING_RANGE_READY.value,
    }
    return True, OpeningRangeOutcome.OPENING_RANGE_READY.value, details
