"""Guardrails and pre-conditions for pilot execution and input validation.

Strictly locks pilot symbols, calendar dates, development cutoffs, and authorization boundaries.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Set

DEVELOPMENT_CUTOFF_DATE = "2025-09-16"
PILOT_ALLOWED_SYMBOLS: Set[str] = {
    "RELIANCE",
    "TCS",
    "HDFCBANK",
    "INFY",
    "ICICIBANK",
}
PILOT_START_DATE = "2024-01-01"
PILOT_END_DATE = "2024-01-31"
APPROVED_PILOT_SYMBOLS = PILOT_ALLOWED_SYMBOLS

SYMBOL_REGEX = re.compile(r"^[A-Z0-9_\-\.&]+$")


def validate_symbol(symbol: str) -> str:
    """Validate and normalize equity ticker symbol.

    Raises:
        ValueError: If symbol is empty, contains path separators, URLs, or invalid characters.
    """
    if not symbol or not isinstance(symbol, str):
        raise ValueError("Symbol must be a non-empty string.")

    cleaned = symbol.strip().upper()
    if not cleaned:
        raise ValueError("Symbol cannot be whitespace-only.")

    if len(cleaned) > 30:
        raise ValueError(f"Symbol '{cleaned}' exceeds maximum length of 30 characters.")

    # Reject path separators, control characters, URL query fragments
    if any(c in cleaned for c in ("/", "\\", ":", "?", "#", "\x00", "\n", "\r", "\t")):
        raise ValueError(f"Symbol '{cleaned}' contains forbidden path, URL, or control characters.")

    if not SYMBOL_REGEX.match(cleaned):
        raise ValueError(f"Symbol '{cleaned}' contains invalid characters (allowed: [A-Z0-9_-.&]).")

    return cleaned


def validate_date_range(start_date: str, end_date: str) -> tuple[str, str]:
    """Validate ISO YYYY-MM-DD date range against Phase 7 boundaries.

    Raises:
        ValueError: If dates are invalid, reversed, or violate research cutoff.
    """
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Invalid date format (must be YYYY-MM-DD): {exc}") from exc

    if start_dt > end_dt:
        raise ValueError(f"Invalid date range: start_date '{start_date}' is after end_date '{end_date}'.")

    cutoff_dt = datetime.strptime(DEVELOPMENT_CUTOFF_DATE, "%Y-%m-%d")
    if end_dt > cutoff_dt:
        raise ValueError(
            f"End date '{end_date}' exceeds Phase 7 development cutoff '{DEVELOPMENT_CUTOFF_DATE}'."
        )

    return start_date, end_date


def validate_staging_path(staging_root: Path, repo_root: Path) -> Path:
    """Ensure staging root is non-empty, exists or is creatable, and is outside repository tree."""
    s_path = Path(staging_root).resolve()
    r_path = Path(repo_root).resolve()

    if s_path == r_path or r_path in s_path.parents:
        raise ValueError(
            f"Staging path '{s_path}' must be strictly external and cannot be located within the Git repository '{r_path}'."
        )

    return s_path


class PilotGuard:
    """Enforces pre-flight boundaries for the 5-security pilot."""

    def __init__(self, is_authorized: bool = False):
        self.is_authorized = bool(is_authorized)

    def verify_execution_permitted(self) -> None:
        if not self.is_authorized:
            raise PermissionError(
                "Live pilot execution is strictly PROHIBITED without a valid single-use authorization marker."
            )

    def validate_pilot_request(self, symbol: str, start_date: str, end_date: str) -> None:
        norm_sym = validate_symbol(symbol)
        if norm_sym not in PILOT_ALLOWED_SYMBOLS:
            raise ValueError(
                f"Symbol '{norm_sym}' is not in approved pilot allowlist: {sorted(PILOT_ALLOWED_SYMBOLS)}"
            )

        validate_date_range(start_date, end_date)

        if start_date != PILOT_START_DATE or end_date != PILOT_END_DATE:
            raise ValueError(
                f"Pilot date range must be exactly '{PILOT_START_DATE}' to '{PILOT_END_DATE}', "
                f"got '{start_date}' to '{end_date}'."
            )


def validate_pilot_parameters(symbols: list[str], start_date: str, end_date: str) -> None:
    """Validate a list of symbols and date range for the 5-stock pilot."""
    guard = PilotGuard()
    if not symbols:
        raise ValueError("Pilot symbol list cannot be empty.")
    for s in symbols:
        guard.validate_pilot_request(s, start_date, end_date)
