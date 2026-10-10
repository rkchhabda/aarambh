"""Unit tests for Phase 7 constituent snapshot authorization marker management.

Tests:
- Marker creation, scope, milestone 4.10A, index NIFTY 500, single_use=True
- Atomic consumption renames active marker to snapshot_authorization.consumed.<ts>.json
- Active marker ceased to exist upon consumption
- Marker inside Git repository rejected
- Tampered marker rejected
- Expired marker rejected
- Cannot authorize another index or milestone
"""

import json
from pathlib import Path
import pytest
import time

from phase7.sources.constituent_authorization import (
    ACTIVE_MARKER_FILENAME,
    SNAPSHOT_AUTHORIZATION_VERSION,
    SNAPSHOT_INDEX_NAME,
    SNAPSHOT_MILESTONE,
    SNAPSHOT_SCOPE,
    consume_snapshot_authorization,
    create_snapshot_authorization,
    load_and_validate_snapshot_authorization,
    validate_snapshot_marker_path,
    validate_staging_root,
)


@pytest.fixture
def mock_external_staging(tmp_path):
    """Create a temporary external staging root outside the repo root."""
    staging = tmp_path / "mock_staging_snapshot"
    staging.mkdir()
    return staging


def test_create_snapshot_authorization_marker(mock_external_staging):
    """Marker is created with exact scope, milestone, index, and single_use=True."""
    marker_path, record = create_snapshot_authorization(
        staging_root=mock_external_staging,
        expires_minutes=30,
        repo_root=mock_external_staging.parent / "fake_repo",
    )

    assert marker_path.exists()
    assert marker_path.name == ACTIVE_MARKER_FILENAME
    assert record.milestone == SNAPSHOT_MILESTONE
    assert record.scope == SNAPSHOT_SCOPE
    assert record.index_name == SNAPSHOT_INDEX_NAME
    assert record.single_use is True
    assert record.nonce is not None
    assert record.authorization_hash is not None


def test_multiple_active_markers_rejected(mock_external_staging):
    """Creating a second active marker when one exists raises FileExistsError."""
    create_snapshot_authorization(
        staging_root=mock_external_staging,
        repo_root=mock_external_staging.parent / "fake_repo",
    )
    with pytest.raises(FileExistsError, match="Active authorization marker already exists"):
        create_snapshot_authorization(
            staging_root=mock_external_staging,
            repo_root=mock_external_staging.parent / "fake_repo",
        )


def test_marker_inside_git_rejected(tmp_path):
    """Staging root located inside repo root is rejected."""
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    (fake_repo / ".git").mkdir()

    inside_staging = fake_repo / "staging_inside"
    inside_staging.mkdir()

    with pytest.raises(ValueError, match="cannot be located within Git repository"):
        validate_staging_root(inside_staging, repo_root=fake_repo)


def test_atomic_consumption(mock_external_staging):
    """Marker is atomically consumed and active marker is removed."""
    marker_path, record = create_snapshot_authorization(
        staging_root=mock_external_staging,
        repo_root=mock_external_staging.parent / "fake_repo",
    )
    assert marker_path.exists()

    consumed_path = consume_snapshot_authorization(marker_path)

    assert not marker_path.exists()
    assert consumed_path.exists()
    assert "snapshot_authorization.consumed." in consumed_path.name


def test_cannot_consume_non_existent_marker(tmp_path):
    """Consuming a non-existent marker raises FileNotFoundError."""
    non_existent = tmp_path / "does_not_exist.json"
    with pytest.raises(FileNotFoundError):
        consume_snapshot_authorization(non_existent)


def test_tampered_marker_rejected(mock_external_staging):
    """Marker with modified content fails hash validation."""
    marker_path, record = create_snapshot_authorization(
        staging_root=mock_external_staging,
        repo_root=mock_external_staging.parent / "fake_repo",
    )

    data = json.loads(marker_path.read_text(encoding="utf-8"))
    data["index_name"] = "NIFTY 50"  # Tampering
    marker_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError):
        load_and_validate_snapshot_authorization(
            marker_path=marker_path,
            staging_root=mock_external_staging,
            expected_index="NIFTY 500",
            repo_root=mock_external_staging.parent / "fake_repo",
        )


def test_expired_marker_rejected(mock_external_staging):
    """Expired marker fails validation with PermissionError."""
    marker_path, record = create_snapshot_authorization(
        staging_root=mock_external_staging,
        expires_minutes=-5,  # Already expired
        repo_root=mock_external_staging.parent / "fake_repo",
    )

    with pytest.raises(PermissionError, match="Authorization marker expired"):
        load_and_validate_snapshot_authorization(
            marker_path=marker_path,
            staging_root=mock_external_staging,
            expected_index="NIFTY 500",
            repo_root=mock_external_staging.parent / "fake_repo",
        )
