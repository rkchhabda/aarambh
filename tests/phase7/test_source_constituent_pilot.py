"""Unit tests for Phase 7 constituent snapshot pilot execution workflow.

Tests:
- End-to-end execution with fake client returning 500 valid stocks + 1 index header
- Atomic marker consumption before client creation
- Verification of exit code 0 on full success
- Clean client closure in finally block
- Error exit codes: ARGUMENT_ERROR (2), AUTHORIZATION_ERROR (3), RETRIEVAL_ERROR (5), SCHEMA_ERROR (6)
- Panel-version identifier generation
"""

import json
from pathlib import Path
import pytest

from phase7.sources.constituent_authorization import (
    create_snapshot_authorization,
)
from phase7.sources.constituent_pilot import (
    run_snapshot_pilot,
)
from phase7.sources.contracts import (
    SnapshotPilotExitCode,
    SnapshotPilotOutcome,
)


class FakeNSEClient:
    def __init__(self, data_list=None, should_fail_conn=False, should_timeout=False):
        self.data_list = data_list or []
        self.should_fail_conn = should_fail_conn
        self.should_timeout = should_timeout
        self.is_closed = False
        self.call_count = 0

    def listEquityStocksByIndex(self, index: str = "NIFTY 50"):
        self.call_count += 1
        if self.should_fail_conn:
            raise ConnectionError("Simulated upstream connection failure")
        if self.should_timeout:
            raise TimeoutError("Simulated upstream timeout")
        return {
            "name": index,
            "timestamp": "10-Oct-2026 15:30:00",
            "data": self.data_list,
        }

    def exit(self):
        self.is_closed = True


@pytest.fixture
def mock_pilot_staging(tmp_path):
    root = tmp_path / "mock_staging_pilot"
    root.mkdir()
    return root


def create_fake_500_payload():
    """Create a realistic 501-item payload (1 index header + 500 stocks)."""
    items = [{"symbol": "NIFTY 500", "identifier": "NIFTY 500", "lastPrice": 22500.0}]
    for i in range(500):
        sym = f"STOCK{i:03d}"
        items.append({
            "symbol": sym,
            "identifier": f"{sym}EQN",
            "series": "EQ",
            "lastPrice": 100.0 + i,
            "meta": {
                "symbol": sym,
                "companyName": f"Company {sym} Ltd",
                "industry": "Finance",
                "isin": f"INE{i:09d}0",
                "activeSeries": ["EQ"],
            }
        })
    return items


def test_snapshot_pilot_full_success(mock_pilot_staging):
    """Pilot executes end-to-end, consumes marker, normalizes 500 stocks, and exits 0."""
    # Step 1: Create authorization marker
    marker_path, _ = create_snapshot_authorization(
        staging_root=mock_pilot_staging,
        expires_minutes=30,
        repo_root=mock_pilot_staging.parent / "fake_repo",
    )
    assert marker_path.exists()

    fake_client = FakeNSEClient(data_list=create_fake_500_payload())

    def fake_factory(download_folder, server=True, timeout=15):
        return fake_client

    # Step 2: Execute pilot
    exit_code = run_snapshot_pilot(
        index_name="NIFTY 500",
        staging_root=mock_pilot_staging,
        authorization_file=marker_path,
        execute_live=True,
        client_factory=fake_factory,
    )

    assert exit_code == SnapshotPilotExitCode.SUCCESS.value
    # Marker was consumed
    assert not marker_path.exists()
    consumed_markers = list((mock_pilot_staging / "authorization").glob("snapshot_authorization.consumed.*.json"))
    assert len(consumed_markers) == 1

    # Client was called and closed
    assert fake_client.call_count == 1
    assert fake_client.is_closed is True

    # Artifacts exist
    raw_files = list((mock_pilot_staging / "raw" / "constituents").glob("NIFTY_500_snapshot_*.json"))
    assert len(raw_files) == 1

    norm_files = list((mock_pilot_staging / "normalized" / "constituents").glob("NIFTY_500_normalized_*.jsonl"))
    assert len(norm_files) == 1

    manifest_files = list((mock_pilot_staging / "manifests").glob("manifest_NIFTY_500_*.json"))
    assert len(manifest_files) == 1

    manifest_data = json.loads(manifest_files[0].read_text(encoding="utf-8"))
    assert manifest_data["status"] == "SUCCEEDED"
    assert manifest_data["source_row_count"] == 501
    assert manifest_data["normalized_row_count"] == 500
    assert manifest_data["rejected_row_count"] == 1
    assert manifest_data["unique_symbols"] == 500
    assert manifest_data["panel_version_id"].startswith("CURRENT_NIFTY500_")


def test_snapshot_pilot_argument_error(mock_pilot_staging):
    """Unauthorized index name returns ARGUMENT_ERROR (2)."""
    marker_path, _ = create_snapshot_authorization(
        staging_root=mock_pilot_staging,
        repo_root=mock_pilot_staging.parent / "fake_repo",
    )
    exit_code = run_snapshot_pilot(
        index_name="NIFTY 50",  # Unauthorized
        staging_root=mock_pilot_staging,
        authorization_file=marker_path,
        execute_live=True,
    )
    assert exit_code == SnapshotPilotExitCode.ARGUMENT_ERROR.value
    # Marker not consumed on argument error
    assert marker_path.exists()


def test_snapshot_pilot_missing_authorization(mock_pilot_staging):
    """Missing authorization marker returns AUTHORIZATION_ERROR (3)."""
    non_existent_marker = mock_pilot_staging / "authorization" / "missing.json"
    exit_code = run_snapshot_pilot(
        index_name="NIFTY 500",
        staging_root=mock_pilot_staging,
        authorization_file=non_existent_marker,
        execute_live=True,
    )
    assert exit_code == SnapshotPilotExitCode.AUTHORIZATION_ERROR.value


def test_snapshot_pilot_upstream_connection_error(mock_pilot_staging):
    """ConnectionError from client returns RETRIEVAL_ERROR (5) and closes client."""
    marker_path, _ = create_snapshot_authorization(
        staging_root=mock_pilot_staging,
        repo_root=mock_pilot_staging.parent / "fake_repo",
    )
    fake_client = FakeNSEClient(should_fail_conn=True)

    exit_code = run_snapshot_pilot(
        index_name="NIFTY 500",
        staging_root=mock_pilot_staging,
        authorization_file=marker_path,
        execute_live=True,
        client_factory=lambda **kw: fake_client,
    )
    assert exit_code == SnapshotPilotExitCode.RETRIEVAL_ERROR.value
    assert fake_client.is_closed is True


def test_snapshot_pilot_implausible_count_fails(mock_pilot_staging):
    """Small/suspicious count (e.g. 50 stocks) returns SCHEMA_NORMALIZATION_ERROR (6)."""
    marker_path, _ = create_snapshot_authorization(
        staging_root=mock_pilot_staging,
        repo_root=mock_pilot_staging.parent / "fake_repo",
    )
    small_items = [{"symbol": f"STOCK{i}"} for i in range(50)]
    fake_client = FakeNSEClient(data_list=small_items)

    exit_code = run_snapshot_pilot(
        index_name="NIFTY 500",
        staging_root=mock_pilot_staging,
        authorization_file=marker_path,
        execute_live=True,
        client_factory=lambda **kw: fake_client,
    )
    assert exit_code == SnapshotPilotExitCode.SCHEMA_NORMALIZATION_ERROR.value
    assert fake_client.is_closed is True
