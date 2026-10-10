"""Tests for Phase 7 live pilot guardrails, symbol/date constraints, and authorization."""

from pathlib import Path
import pytest

from phase7.sources.pilot import (
    REQUIRED_PILOT_PHRASE,
    validate_pilot_cli_args,
)
from phase7.sources.pilot_guard import (
    APPROVED_PILOT_SYMBOLS,
    PILOT_END_DATE,
    PILOT_START_DATE,
    validate_pilot_parameters,
    validate_staging_path,
)


def test_pilot_symbols_exactly_approved():
    """Verify pilot symbols set is exactly the approved 5 stocks."""
    assert APPROVED_PILOT_SYMBOLS == {"RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"}

    # Allowed set passes
    validate_pilot_parameters(
        ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"],
        PILOT_START_DATE,
        PILOT_END_DATE,
    )

    # Any unapproved symbol is strictly rejected
    with pytest.raises(ValueError, match="not in approved pilot allowlist"):
        validate_pilot_parameters(["SBIN"], PILOT_START_DATE, PILOT_END_DATE)


def test_pilot_dates_exactly_january_2024():
    """Verify pilot date window is strictly 2024-01-01 to 2024-01-31."""
    symbols = ["RELIANCE"]

    # Wrong start date rejected
    with pytest.raises(ValueError, match="Pilot date range must be exactly"):
        validate_pilot_parameters(symbols, "2023-12-31", PILOT_END_DATE)

    # Wrong end date rejected
    with pytest.raises(ValueError, match="Pilot date range must be exactly"):
        validate_pilot_parameters(symbols, PILOT_START_DATE, "2024-02-01")


def test_external_staging_path_required(tmp_path):
    """Verify staging root inside repository is strictly rejected."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Inside repo -> rejected
    inside_staging = repo_root / "data" / "staging"
    inside_staging.mkdir(parents=True)
    with pytest.raises(ValueError, match="must be strictly external"):
        validate_staging_path(inside_staging, repo_root)

    # Outside repo -> accepted
    outside_staging = tmp_path / "external_staging"
    outside_staging.mkdir()
    validated = validate_staging_path(outside_staging, repo_root)
    assert validated == outside_staging.resolve()


def test_live_execution_requires_exact_authorization_phrase(tmp_path):
    """Verify live pilot execution fails closed without exact authorization phrase."""
    outside_staging = tmp_path / "external_staging"
    outside_staging.mkdir()

    # Dry run / non-live passes without phrase
    validate_pilot_cli_args(
        symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        start_date="2024-01-01",
        end_date="2024-01-31",
        staging_root_str=str(outside_staging),
        execute_live=False,
        owner_authorization="",
        repo_root=tmp_path / "repo",
    )

    # Live execution with missing or wrong phrase -> raises PermissionError
    with pytest.raises(PermissionError, match="authorization phrase must match exactly"):
        validate_pilot_cli_args(
            symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
            start_date="2024-01-01",
            end_date="2024-01-31",
            staging_root_str=str(outside_staging),
            execute_live=True,
            owner_authorization="PLEASE RUN PILOT",
            repo_root=tmp_path / "repo",
        )

    # Live execution with exact phrase -> passes validation
    validate_pilot_cli_args(
        symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        start_date="2024-01-01",
        end_date="2024-01-31",
        staging_root_str=str(outside_staging),
        execute_live=True,
        owner_authorization=REQUIRED_PILOT_PHRASE,
        repo_root=tmp_path / "repo",
    )
