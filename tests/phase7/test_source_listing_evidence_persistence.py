"""Tests for Phase 7 official listing date evidence persistence and external staging isolation."""

import hashlib
import json
from pathlib import Path
import pytest

from phase7.sources.listing_evidence_persistence import (
    EVIDENCE_SUBDIRECTORIES,
    ensure_evidence_directories,
    persist_evidence_manifest,
    persist_extracted_evidence_record,
    persist_raw_source_document,
    persist_retrospective_classification_record,
    sanitize_evidence_data,
)


def _setup_external_staging(tmp_path_factory) -> Path:
    staging = tmp_path_factory.mktemp("listing_evidence_persist_staging")
    return staging.resolve()


def test_ensure_evidence_directories(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    dirs = ensure_evidence_directories(staging)

    for sub in EVIDENCE_SUBDIRECTORIES:
        assert sub in dirs
        assert dirs[sub].exists()
        assert dirs[sub].is_dir()


def test_persist_raw_source_document_pdf(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    content = b"%PDF-1.4\nsynthetic official notice\n%%EOF"
    target_path, sha256 = persist_raw_source_document(
        staging_root=staging,
        filename="ADV_TEST.pdf",
        content_bytes=content,
        source_url="https://nsearchives.nseindia.com/corporate/ADV_TEST.pdf",
        mime_type="application/pdf",
        publisher="NSE",
    )

    assert target_path.exists()
    assert sha256 == hashlib.sha256(content).hexdigest()
    assert target_path.read_bytes() == content


def test_persist_empty_raw_document_rejected(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    with pytest.raises(ValueError, match="Cannot persist empty source document bytes"):
        persist_raw_source_document(
            staging_root=staging,
            filename="empty.pdf",
            content_bytes=b"",
            source_url="https://nsearchives.nseindia.com/corporate/empty.pdf",
            mime_type="application/pdf",
        )


def test_persist_invalid_pdf_header_rejected(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    with pytest.raises(ValueError, match="missing '%PDF-' header"):
        persist_raw_source_document(
            staging_root=staging,
            filename="invalid.pdf",
            content_bytes=b"NOT_A_VALID_PDF",
            source_url="https://nsearchives.nseindia.com/corporate/invalid.pdf",
            mime_type="application/pdf",
        )


def test_no_overwrite_different_hash_rejected(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    content1 = b"%PDF-1.4\nfirst document content\n%%EOF"
    content2 = b"%PDF-1.4\nsecond different document\n%%EOF"

    persist_raw_source_document(
        staging_root=staging,
        filename="notice.pdf",
        content_bytes=content1,
        source_url="https://nsearchives.nseindia.com/corporate/notice.pdf",
        mime_type="application/pdf",
    )

    with pytest.raises(FileExistsError, match="already exists with different checksum"):
        persist_raw_source_document(
            staging_root=staging,
            filename="notice.pdf",
            content_bytes=content2,
            source_url="https://nsearchives.nseindia.com/corporate/notice.pdf",
            mime_type="application/pdf",
        )


def test_sanitize_evidence_data_strips_cookies_and_secrets():
    dirty_data = {
        "symbol": "PREMIERENE",
        "listing_date": "2024-09-03",
        "cookie": "session_secret_12345",
        "set-cookie": "tracking_id=abc",
        "authorization": "Bearer secret_token",
        "headers": {"User-Agent": "test", "Cookie": "xyz"},
        "nested": {
            "token": "secret_abc",
            "clean_field": "valid_value",
        },
    }

    clean = sanitize_evidence_data(dirty_data)
    assert "cookie" not in clean
    assert "set-cookie" not in clean
    assert "authorization" not in clean
    assert "headers" not in clean
    assert clean["symbol"] == "PREMIERENE"
    assert clean["listing_date"] == "2024-09-03"
    assert "token" not in clean["nested"]
    assert clean["nested"]["clean_field"] == "valid_value"


def test_persist_extracted_evidence_record(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    data = {
        "symbol": "PREMIERENE",
        "security_name": "Premier Energies Limited",
        "listing_date": "2024-09-03",
        "cookie": "should_be_stripped",
    }
    extracted_path = persist_extracted_evidence_record(
        staging_root=staging,
        filename="PREMIERENE_extracted.json",
        record_dict=data,
    )

    assert extracted_path.exists()
    saved = json.loads(extracted_path.read_text(encoding="utf-8"))
    assert saved["symbol"] == "PREMIERENE"
    assert "cookie" not in saved


def test_persist_evidence_manifest(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    manifest_data = {
        "milestone": "4.10C-2",
        "symbol": "PREMIERENE",
        "request_count": 2,
    }
    manifest_path, manifest_hash = persist_evidence_manifest(
        staging_root=staging,
        manifest_dict=manifest_data,
    )

    assert manifest_path.exists()
    assert len(manifest_hash) == 64
    assert manifest_path.parent.name == "manifests"


def test_persist_retrospective_classification_record(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    retro_data = {
        "symbol": "PREMIERENE",
        "retrospective_outcome": "NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED",
    }
    retro_path = persist_retrospective_classification_record(
        staging_root=staging,
        symbol="PREMIERENE",
        classification_data=retro_data,
    )

    assert retro_path.exists()
    assert retro_path.parent.name == "audit"
    assert retro_path.name == "retrospective_classification_PREMIERENE.json"
