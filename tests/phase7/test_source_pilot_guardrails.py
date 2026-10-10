"""Tests for Phase 7 live pilot guardrails, symbol/date constraints, and authorization."""

from pathlib import Path
import pytest

from phase7.sources.authorization import (
    create_pilot_authorization,
)
from phase7.sources.pilot import (
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


def test_live_execution_requires_authorization_marker(tmp_path):
    """Verify live pilot execution fails closed without valid authorization marker."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()

    outside_staging = tmp_path / "external_staging"
    outside_staging.mkdir()

    # Dry run / non-live passes without authorization marker
    validate_pilot_cli_args(
        symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        staging_root_str=str(outside_staging),
        authorization_file_str="",
        execute_live=False,
        repo_root=repo_root,
    )

    # Live execution with missing authorization file -> raises ValueError
    with pytest.raises(ValueError, match="Live execution requires a valid --authorization-file"):
        validate_pilot_cli_args(
            symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
            start_date="2024-01-01",
            end_date="2024-01-31",
            interval="1d",
            staging_root_str=str(outside_staging),
            authorization_file_str="",
            execute_live=True,
            repo_root=repo_root,
        )

    # Create valid external marker
    marker_path = create_pilot_authorization(staging_root=outside_staging, repo_root=repo_root)

    # Live execution with valid authorization marker -> passes CLI validation
    validate_pilot_cli_args(
        symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        staging_root_str=str(outside_staging),
        authorization_file_str=str(marker_path),
        execute_live=True,
        repo_root=repo_root,
    )
