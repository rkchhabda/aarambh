"""Return calculation interfaces and adjustment state validation for Phase 7 targets.

Implements:
1. Strict Decimal discrete return calculation: (exit_price / entry_price) - 1.
2. Price adjustment state validation (raw, split-adjusted, total-return-adjusted).
3. Non-mixing rules preventing contamination of return types.
4. Precision checks enforcing finite, positive price boundaries.
"""

from decimal import Decimal
from typing import Optional, Tuple

from phase7.data.contracts import PriceAdjustmentState
from phase7.targets.contracts import TargetReasonCode


def calculate_discrete_return(entry_price: Decimal, exit_price: Decimal) -> Decimal:
    """Calculate discrete percentage return between entry and exit prices.

    Formula:
        return = (exit_price / entry_price) - 1

    Args:
        entry_price: Positive finite entry price.
        exit_price: Positive finite exit price.

    Returns:
        Decimal return value.

    Raises:
        ValueError: If either price is non-positive or non-finite.
    """
    if not isinstance(entry_price, Decimal) or not isinstance(exit_price, Decimal):
        raise TypeError("entry_price and exit_price must be Decimal instances.")
    if not entry_price.is_finite() or entry_price <= Decimal("0"):
        raise ValueError(f"entry_price must be positive and finite, got {entry_price}")
    if not exit_price.is_finite() or exit_price <= Decimal("0"):
        raise ValueError(f"exit_price must be positive and finite, got {exit_price}")

    return (exit_price / entry_price) - Decimal("1")


def validate_adjustment_compatibility(
    entry_state: PriceAdjustmentState,
    exit_state: PriceAdjustmentState,
    required_state: Optional[PriceAdjustmentState] = None,
) -> Tuple[bool, Optional[TargetReasonCode], str]:
    """Validate that entry and exit prices share compatible adjustment states.

    Rules:
    1. Neither state may be UNKNOWN (fails closed).
    2. entry_state and exit_state must match exactly.
    3. TOTAL_RETURN_ADJUSTED and SPLIT_ADJUSTED must not be mixed.
    4. If required_state is specified, both states must equal required_state.

    Returns:
        (is_compatible, reason_code, message)
    """
    if entry_state == PriceAdjustmentState.UNKNOWN or exit_state == PriceAdjustmentState.UNKNOWN:
        return (
            False,
            TargetReasonCode.INVALID_ADJUSTMENT_STATE,
            f"Adjustment state UNKNOWN fails closed (entry={entry_state.value}, exit={exit_state.value}).",
        )

    if entry_state != exit_state:
        return (
            False,
            TargetReasonCode.INVALID_ADJUSTMENT_STATE,
            f"Mismatched adjustment states between entry ({entry_state.value}) and exit ({exit_state.value}). Mixing states is prohibited.",
        )

    if required_state is not None and entry_state != required_state:
        return (
            False,
            TargetReasonCode.INVALID_ADJUSTMENT_STATE,
            f"Observed adjustment state {entry_state.value} does not satisfy target specification requirement {required_state.value}.",
        )

    return (True, None, "Adjustment states compatible.")
