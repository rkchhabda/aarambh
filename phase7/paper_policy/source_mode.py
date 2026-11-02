"""Governed Source Mode Policy and Isolation [Milestone 4.14].

Enforces strict isolation between synthetic test fixtures, governed recorded
fixtures, and live market sources. Relabeling synthetic data as live is
structurally prohibited and rejected fail-closed.
"""

from typing import Any, Dict, Optional, Tuple

from phase7.paper_policy.constants import (
    LIVE_SOURCE_STATUS,
    PERMITTED_SOURCE_MODES,
    SourceMode,
)
from phase7.paper_policy.reason_codes import PolicyReasonCode


class SourceModeError(ValueError):
    """Raised when an invalid or prohibited source mode transition is attempted."""


def is_source_mode_permitted(mode: str) -> bool:
    """Return True if the source mode is approved for offline policy evaluation."""
    return mode in PERMITTED_SOURCE_MODES


def validate_source_mode(mode: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Validate source mode against governed policy.

    Returns:
        (is_valid, reason_code, status_message)
    """
    if mode == SourceMode.LIVE_SOURCE.value:
        return (
            False,
            PolicyReasonCode.EXTERNAL_ACQUISITION_BLOCKED.value,
            LIVE_SOURCE_STATUS,
        )
    if mode not in [m.value for m in SourceMode]:
        return (
            False,
            PolicyReasonCode.SOURCE_MODE_BLOCKED_NO_DECISION.value,
            f"UNKNOWN_SOURCE_MODE: '{mode}'",
        )
    if not is_source_mode_permitted(mode):
        return (
            False,
            PolicyReasonCode.SOURCE_MODE_BLOCKED_NO_DECISION.value,
            f"SOURCE_MODE_NOT_PERMITTED: '{mode}'",
        )
    return True, None, "SOURCE_MODE_PERMITTED"


def verify_immutable_source_label(payload: Dict[str, Any]) -> str:
    """Verify and return the permanent source mode label from a record.

    Raises SourceModeError if missing, invalid, or if an attempt to disguise
    synthetic data as live is detected.
    """
    mode = payload.get("source_mode")
    if not mode:
        raise SourceModeError("Missing mandatory 'source_mode' label in record")

    if mode not in [m.value for m in SourceMode]:
        raise SourceModeError(f"Invalid 'source_mode' value: '{mode}'")

    # Anti-masquerade check: flags or attributes attempting to claim live status
    # while carrying synthetic markers
    is_synthetic_flag = payload.get("is_synthetic", False)
    if is_synthetic_flag and mode == SourceMode.LIVE_SOURCE.value:
        raise SourceModeError("PROHIBITED_RELABELING: Synthetic record cannot be labeled as LIVE_SOURCE")

    return str(mode)
