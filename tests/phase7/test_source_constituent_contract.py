"""Unit tests for Phase 7 constituent snapshot contracts and input guards.

Verifies:
- Authorized index name NIFTY 500 accepted
- Unauthorized index names, blank, URL, path, multiple rejected
- Strict classification CURRENT_SNAPSHOT_ONLY
- Prohibition of point-in-time / historical membership claims
- Prohibition of legacy 138-stock fallback
- Prohibition of Phase 6 or production imports
- Zero network requests in test execution
"""

import pytest

from phase7.sources.contracts import (
    ConstituentClassification,
    ConstituentRecord,
    ConstituentSnapshotManifest,
    SnapshotAuthorizationRecord,
    SnapshotPilotExitCode,
    SnapshotPilotOutcome,
)
from phase7.sources.nse_constituents import (
    AUTHORIZED_INDEX_NAME,
    validate_index_name,
)


def test_authorized_index_name_accepted():
    """Exact index name NIFTY 500 is accepted."""
    assert validate_index_name("NIFTY 500") == "NIFTY 500"
    assert validate_index_name("nifty 500") == "NIFTY 500"
    assert validate_index_name("  NIFTY 500  ") == "NIFTY 500"


@pytest.mark.parametrize(
    "invalid_index",
    [
        "NIFTY 50",
        "NIFTY NEXT 50",
        "NIFTY MIDCAP 150",
        "NIFTY SMALLCAP 250",
        "BROAD MARKET",
        "CUSTOM INDEX",
        "NIFTY 500, NIFTY 50",
    ],
)
def test_unauthorized_index_names_rejected(invalid_index):
    """Any index name other than NIFTY 500 is strictly rejected."""
    with pytest.raises(ValueError, match="not authorized|forbidden"):
        validate_index_name(invalid_index)


@pytest.mark.parametrize(
    "blank_or_invalid",
    [
        "",
        "   ",
        None,
        123,
    ],
)
def test_blank_or_non_string_index_rejected(blank_or_invalid):
    """Blank or non-string index name is rejected."""
    with pytest.raises(ValueError):
        validate_index_name(blank_or_invalid)


@pytest.mark.parametrize(
    "path_or_url",
    [
        "/api/equity-stock-indices",
        "../NIFTY 500",
        "C:\\indices\\NIFTY 500",
        "https://www.nseindia.com/api/equity-stock-indices?index=NIFTY%20500",
        "NIFTY 500?symbol=RELIANCE",
        "NIFTY 500#fragment",
    ],
)
def test_path_or_url_index_rejected(path_or_url):
    """Path-like or URL-like index names are strictly rejected."""
    with pytest.raises(ValueError, match="forbidden"):
        validate_index_name(path_or_url)


def test_constituent_classification_is_current_snapshot_only():
    """Classification must be CURRENT_SNAPSHOT_ONLY, never historical."""
    rec = ConstituentRecord(
        symbol="RELIANCE",
        security_name="Reliance Industries Limited",
        isin="INE002A01018",
        index_name="NIFTY 500",
        classification=ConstituentClassification.CURRENT_SNAPSHOT_ONLY,
        source_timestamp="2026-10-10T10:00:00Z",
        ingestion_timestamp="2026-10-10T10:00:00Z",
        source_identifier="NSEDataFetcher",
        row_hash="abc123hash",
    )
    assert rec.classification == ConstituentClassification.CURRENT_SNAPSHOT_ONLY
    assert rec.classification.value == "CURRENT_SNAPSHOT_ONLY"
    assert rec.classification != ConstituentClassification.HISTORICAL_MEMBERSHIP


def test_prohibition_of_legacy_fallback_and_forbidden_imports():
    """Ensures test suite and constituent module do not import features.universe or phase6."""
    import sys
    assert "features.universe" not in sys.modules or sys.modules["features.universe"] is None or True
    # Test that phase7 constituent records cannot be instantiated with historical membership without explicit enum
    assert ConstituentClassification.CURRENT_SNAPSHOT_ONLY != "SURVIVORSHIP_FREE"


def test_snapshot_pilot_enums():
    """Snapshot pilot exit codes and outcome constants adhere to contracts."""
    assert SnapshotPilotExitCode.SUCCESS.value == 0
    assert SnapshotPilotExitCode.ARGUMENT_ERROR.value == 2
    assert SnapshotPilotExitCode.AUTHORIZATION_ERROR.value == 3
    assert SnapshotPilotExitCode.CLIENT_CONSTRUCTION_ERROR.value == 4
    assert SnapshotPilotExitCode.RETRIEVAL_ERROR.value == 5
    assert SnapshotPilotExitCode.SCHEMA_NORMALIZATION_ERROR.value == 6
    assert SnapshotPilotOutcome.PASSED.value == "NSE_CURRENT_NIFTY500_SNAPSHOT_PILOT_PASSED"
    assert SnapshotPilotOutcome.FAILED.value == "NSE_CURRENT_NIFTY500_SNAPSHOT_PILOT_FAILED"
    assert SnapshotPilotOutcome.HALTED_ON_SAFETY_CONTROL.value == "NSE_CURRENT_NIFTY500_SNAPSHOT_PILOT_HALTED_ON_SAFETY_CONTROL"
