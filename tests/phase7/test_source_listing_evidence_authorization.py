"""Tests for Phase 7 official listing date evidence authorization marker management."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import pytest

from phase7.sources.listing_evidence_authorization import (
    ACTIVE_MARKER_FILENAME,
    APPROVED_EVIDENCE_DOMAINS,
    EVIDENCE_AUTHORIZATION_VERSION,
    EVIDENCE_MILESTONE,
    EVIDENCE_REQUIRED_EXCHANGE,
    EVIDENCE_REQUIRED_REQUESTED_END,
    EVIDENCE_REQUIRED_SECURITY_NAME,
    EVIDENCE_REQUIRED_SYMBOL,
    EVIDENCE_SCOPE,
    MAXIMUM_REQUEST_COUNT,
    ListingEvidenceAuthorizationRecord,
    compute_listing_evidence_authorization_hash,
    compute_staging_root_hash,
    consume_listing_evidence_authorization,
    create_listing_evidence_authorization,
    find_repo_root,
    load_and_validate_listing_evidence_authorization,
    validate_listing_evidence_marker_path,
    validate_staging_root,
)


def _setup_external_staging(tmp_path_factory) -> Path:
    staging = tmp_path_factory.mktemp("listing_evidence_auth_staging")
    return staging.resolve()


def test_create_and_validate_evidence_authorization(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    marker_path, record = create_listing_evidence_authorization(staging_root=staging)

    assert marker_path.exists()
    assert marker_path.name == ACTIVE_MARKER_FILENAME
    assert record.milestone == EVIDENCE_MILESTONE
    assert record.scope == EVIDENCE_SCOPE
    assert record.symbol == EVIDENCE_REQUIRED_SYMBOL
    assert record.security_name == EVIDENCE_REQUIRED_SECURITY_NAME
    assert record.exchange == EVIDENCE_REQUIRED_EXCHANGE
    assert record.requested_period_end == EVIDENCE_REQUIRED_REQUESTED_END
    assert record.maximum_request_count == MAXIMUM_REQUEST_COUNT
    assert record.single_use is True

    # Validate loading and verification
    loaded = load_and_validate_listing_evidence_authorization(
        marker_path=marker_path,
        staging_root=staging,
    )
    assert loaded.authorization_hash == record.authorization_hash
    assert loaded.nonce == record.nonce


def test_symbol_binding_is_exact(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    with pytest.raises(ValueError, match="Unauthorized symbol for evidence pilot"):
        create_listing_evidence_authorization(staging_root=staging, symbol="RELIANCE")


def test_security_name_binding_is_exact(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    with pytest.raises(ValueError, match="Unauthorized security_name"):
        create_listing_evidence_authorization(staging_root=staging, security_name="Other Ltd")


def test_exchange_binding_is_exact(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    with pytest.raises(ValueError, match="Unauthorized exchange"):
        create_listing_evidence_authorization(staging_root=staging, exchange="BSE")


def test_requested_end_binding_is_exact(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    with pytest.raises(ValueError, match="Unauthorized requested_end"):
        create_listing_evidence_authorization(staging_root=staging, requested_end="2024-06-30")


def test_duplicate_active_marker_rejected(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    create_listing_evidence_authorization(staging_root=staging)
    with pytest.raises(FileExistsError, match="Active authorization marker already exists"):
        create_listing_evidence_authorization(staging_root=staging)


def test_staging_root_inside_git_rejected():
    repo = find_repo_root()
    inside_dir = repo / "phase7_forbidden_staging"
    with pytest.raises(ValueError, match="must be strictly external"):
        validate_staging_root(inside_dir, repo_root=repo)


def test_relative_staging_root_rejected():
    with pytest.raises(ValueError, match="Staging root path must be absolute"):
        validate_staging_root("relative/path/staging")


def test_expired_authorization_rejected(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    marker_path, _ = create_listing_evidence_authorization(
        staging_root=staging,
        expires_minutes=-5,  # Already expired
    )
    with pytest.raises(PermissionError, match="Authorization marker expired"):
        load_and_validate_listing_evidence_authorization(
            marker_path=marker_path,
            staging_root=staging,
        )


def test_tampered_authorization_hash_rejected(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    marker_path, _ = create_listing_evidence_authorization(staging_root=staging)

    # Tamper with payload
    data = json.loads(marker_path.read_text(encoding="utf-8"))
    data["maximum_request_count"] = 100  # Attempt to increase ceiling
    marker_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="Maximum request count exceeds ceiling|Authorization marker hash mismatch"):
        load_and_validate_listing_evidence_authorization(
            marker_path=marker_path,
            staging_root=staging,
        )


def test_single_use_consumption_atomic(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    marker_path, _ = create_listing_evidence_authorization(staging_root=staging)

    consumed_path = consume_listing_evidence_authorization(marker_path)
    assert consumed_path.exists()
    assert "listing_evidence_authorization.consumed." in consumed_path.name
    assert not marker_path.exists()

    # Re-consumption must fail
    with pytest.raises(FileNotFoundError, match="Cannot consume non-existent authorization marker"):
        consume_listing_evidence_authorization(marker_path)


def test_marker_does_not_authorize_market_price_or_batch_resume(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    _, record = create_listing_evidence_authorization(staging_root=staging)
    d = record.to_dict()

    assert "historical_price" not in d["scope"].lower()
    assert "resume" not in d["scope"].lower()
    assert d["scope"] == "OFFICIAL_LISTING_DATE_EVIDENCE_PILOT"
