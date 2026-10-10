"""Unit tests for PilotGuard boundaries and authorization gating."""

import pytest
from phase7.sources.pilot_guard import (
    PILOT_ALLOWED_SYMBOLS,
    PILOT_END_DATE,
    PILOT_START_DATE,
    PilotGuard,
)


def test_pilot_unauthorized_execution_blocked():
    """Verify that pilot execution raises PermissionError without exact authorization phrase."""
    guard = PilotGuard(authorized_phrase="AUTHORIZE FIVE STOCK PILOT")
    assert not guard.is_authorized

    with pytest.raises(PermissionError, match="Live pilot execution is strictly PROHIBITED"):
        guard.verify_execution_permitted()

    empty_guard = PilotGuard()
    with pytest.raises(PermissionError, match="Live pilot execution is strictly PROHIBITED"):
        empty_guard.verify_execution_permitted()


def test_pilot_authorized_execution_allows_valid_params():
    """Verify that exact phrase validates pilot boundaries."""
    exact_phrase = "AUTHORIZE MILESTONE 4.9: FIVE-STOCK NSE LIVE PILOT"
    guard = PilotGuard(authorized_phrase=exact_phrase)
    assert guard.is_authorized
    guard.verify_execution_permitted()  # Succeeded without exception

    # Valid pilot symbols
    for sym in ("RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"):
        guard.validate_pilot_request(sym, PILOT_START_DATE, PILOT_END_DATE)


def test_pilot_rejects_unapproved_symbols():
    """Verify that any symbol outside the 5 approved tickers is rejected."""
    guard = PilotGuard(authorized_phrase="AUTHORIZE MILESTONE 4.9: FIVE-STOCK NSE LIVE PILOT")

    with pytest.raises(ValueError, match="not in approved pilot allowlist"):
        guard.validate_pilot_request("SBIN", PILOT_START_DATE, PILOT_END_DATE)

    with pytest.raises(ValueError, match="not in approved pilot allowlist"):
        guard.validate_pilot_request("WIPRO", PILOT_START_DATE, PILOT_END_DATE)


def test_pilot_rejects_non_frozen_dates():
    """Verify that dates outside Jan 2024 (2024-01-01 to 2024-01-31) are rejected."""
    guard = PilotGuard(authorized_phrase="AUTHORIZE MILESTONE 4.9: FIVE-STOCK NSE LIVE PILOT")

    with pytest.raises(ValueError, match="Pilot date range must be exactly"):
        guard.validate_pilot_request("RELIANCE", "2024-01-01", "2024-02-15")

    with pytest.raises(ValueError, match="Pilot date range must be exactly"):
        guard.validate_pilot_request("RELIANCE", "2023-01-01", "2023-01-31")
