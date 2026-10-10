"""Unit tests for symbol, date, cutoff, and path validation guards."""

from pathlib import Path
import pytest
from phase7.sources.pilot_guard import (
    DEVELOPMENT_CUTOFF_DATE,
    validate_date_range,
    validate_staging_path,
    validate_symbol,
)


def test_symbol_normalization_and_validation():
    """Verify symbol normalization and character allowlisting."""
    assert validate_symbol("reliance") == "RELIANCE"
    assert validate_symbol("  tcs  ") == "TCS"
    assert validate_symbol("M&M") == "M&M"
    assert validate_symbol("BAJAJ-AUTO") == "BAJAJ-AUTO"

    # Rejection of whitespace-only and empty
    with pytest.raises(ValueError, match="non-empty string"):
        validate_symbol("")
    with pytest.raises(ValueError, match="whitespace-only"):
        validate_symbol("   ")

    # Rejection of path separators and URL query fragments
    with pytest.raises(ValueError, match="forbidden path"):
        validate_symbol("../../etc/passwd")
    with pytest.raises(ValueError, match="forbidden path"):
        validate_symbol("TCS/../")
    with pytest.raises(ValueError, match="forbidden path"):
        validate_symbol("INFY?quote=1")
    with pytest.raises(ValueError, match="forbidden path"):
        validate_symbol("HDFC#anchor")
    with pytest.raises(ValueError, match="forbidden path"):
        validate_symbol("ICICI:EQ")

    # Rejection of excessively long symbols
    with pytest.raises(ValueError, match="exceeds maximum length"):
        validate_symbol("A" * 35)


def test_date_range_validation():
    """Verify ISO parsing, sequence, and development cutoff enforcement."""
    # Valid date range
    validate_date_range("2024-01-01", "2024-01-31")
    validate_date_range("2015-01-01", "2025-09-16")

    # Invalid date formats
    with pytest.raises(ValueError, match="Invalid date format"):
        validate_date_range("01-01-2024", "31-01-2024")
    with pytest.raises(ValueError, match="Invalid date format"):
        validate_date_range("2024/01/01", "2024/01/31")

    # Reversed date range
    with pytest.raises(ValueError, match="start_date '2024-02-01' is after end_date '2024-01-01'"):
        validate_date_range("2024-02-01", "2024-01-01")

    # Future date exceeding cutoff (2025-09-16)
    with pytest.raises(ValueError, match="exceeds Phase 7 development cutoff"):
        validate_date_range("2024-01-01", "2025-09-17")
    with pytest.raises(ValueError, match="exceeds Phase 7 development cutoff"):
        validate_date_range("2025-09-10", "2026-01-01")


def test_staging_path_validation(tmp_path):
    """Verify repository containment rejection."""
    repo = tmp_path / "repo"
    repo.mkdir()
    internal_data = repo / "data"
    internal_data.mkdir()

    external_staging = tmp_path / "external_staging"
    external_staging.mkdir()

    # Valid external path
    valid = validate_staging_path(external_staging, repo)
    assert valid == external_staging.resolve()

    # Rejection of repository paths
    with pytest.raises(ValueError, match="cannot be located within the Git repository"):
        validate_staging_path(repo, repo)

    with pytest.raises(ValueError, match="cannot be located within the Git repository"):
        validate_staging_path(internal_data, repo)
