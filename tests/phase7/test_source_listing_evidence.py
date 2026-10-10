"""Tests for Phase 7 governed listing date evidence contract and validation."""

import json
from pathlib import Path
import tempfile
import pytest

from phase7.sources.listing_evidence import (
    ListingDateStatus,
    ListingEvidenceRecord,
    ListingSourcePriority,
    ListingSourceType,
    ListingVerificationStatus,
    load_listing_evidence,
    save_listing_evidence,
    validate_listing_evidence,
)


def _build_valid_evidence(**overrides) -> ListingEvidenceRecord:
    defaults = {
        "symbol": "PREMIERENE",
        "security_name": "Premier Energies Limited",
        "exchange": "NSE",
        "listing_date": "2024-09-03",
        "listing_date_status": ListingDateStatus.SOURCE_REPORTED,
        "source_type": ListingSourceType.NSE_SECURITY_MASTER,
        "source_identifier": "NSE_SEC_MASTER_20240903",
        "source_document_date": "2024-09-03",
        "retrieval_timestamp": "2026-10-10T12:00:00Z",
        "evidence_file_reference": "listing_evidence/PREMIERENE_listing_record.json",
        "evidence_sha256": "a" * 64,
        "source_row_hash": "b" * 64,
        "verification_status": ListingVerificationStatus.VERIFIED_SINGLE_SOURCE,
        "reviewer_status": "GOVERNED_SYSTEM",
        "notes": "Verified from official exchange master",
        "isin": "INE0K8D01017",
    }
    defaults.update(overrides)
    return ListingEvidenceRecord(**defaults)


def test_official_nse_source_accepted():
    record = _build_valid_evidence(source_type=ListingSourceType.NSE_SECURITY_MASTER)
    validate_listing_evidence(record)
    assert record.supports_prelisting_classification() is True


def test_sebi_filing_source_accepted():
    record = _build_valid_evidence(
        source_type=ListingSourceType.SEBI_PROSPECTUS,
        source_identifier="SEBI_PROSPECTUS_FINAL_20240828",
    )
    validate_listing_evidence(record)
    assert record.supports_prelisting_classification() is True


def test_unapproved_source_rejected():
    with pytest.raises(ValueError, match="Unapproved listing source type rejected"):
        record = _build_valid_evidence(
            source_type=ListingSourceType.DISALLOWED_UNGOVERNED,
        )
        validate_listing_evidence(record)


def test_disallowed_source_keywords_rejected():
    for keyword in ["wikipedia", "screener", "news", "blog", "ai_generated", "google_search"]:
        with pytest.raises(ValueError, match="Disallowed evidence provenance detected"):
            record = _build_valid_evidence(
                notes=f"Retrieved via {keyword} query",
            )
            validate_listing_evidence(record)


def test_listing_evidence_requires_checksum():
    with pytest.raises(ValueError, match="Listing evidence requires valid 64-char SHA-256 evidence_sha256"):
        record = _build_valid_evidence(evidence_sha256="")
        validate_listing_evidence(record)

    with pytest.raises(ValueError, match="Listing evidence requires valid 64-char SHA-256 evidence_sha256"):
        record = _build_valid_evidence(evidence_sha256="short_hash")
        validate_listing_evidence(record)


def test_listing_evidence_requires_source_identifier():
    with pytest.raises(ValueError, match="Listing evidence requires non-empty source_identifier"):
        record = _build_valid_evidence(source_identifier="")
        validate_listing_evidence(record)


def test_invalid_date_format_rejected():
    with pytest.raises(ValueError, match="Invalid listing_date format"):
        record = _build_valid_evidence(listing_date="03-09-2024")
        validate_listing_evidence(record)

    with pytest.raises(ValueError, match="Invalid calendar date"):
        record = _build_valid_evidence(listing_date="2024-02-31")
        validate_listing_evidence(record)


def test_conflicting_dates_produce_conflict_status():
    record = _build_valid_evidence(
        listing_date_status=ListingDateStatus.CONFLICTING,
        verification_status=ListingVerificationStatus.CONFLICT,
    )
    validate_listing_evidence(record)
    assert record.supports_prelisting_classification() is False

    with pytest.raises(ValueError, match="Conflicting listing date status must have CONFLICT verification status"):
        invalid_conflict = _build_valid_evidence(
            listing_date_status=ListingDateStatus.CONFLICTING,
            verification_status=ListingVerificationStatus.VERIFIED_SINGLE_SOURCE,
        )
        validate_listing_evidence(invalid_conflict)


def test_missing_listing_date_remains_unverified():
    record = _build_valid_evidence(
        listing_date=None,
        listing_date_status=ListingDateStatus.NOT_PROVIDED,
        verification_status=ListingVerificationStatus.UNVERIFIED,
    )
    validate_listing_evidence(record)
    assert record.supports_prelisting_classification() is False


def test_save_and_load_listing_evidence():
    with tempfile.TemporaryDirectory() as tmp_dir:
        target_path = Path(tmp_dir) / "PREMIERENE_evidence.json"
        record = _build_valid_evidence()
        saved = save_listing_evidence(record, target_path)
        assert saved.exists()

        loaded = load_listing_evidence(saved)
        assert loaded.symbol == record.symbol
        assert loaded.listing_date == record.listing_date
        assert loaded.evidence_sha256 == record.evidence_sha256
        assert loaded.verification_status == record.verification_status
