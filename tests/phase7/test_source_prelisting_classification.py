"""Tests for Phase 7 pre-listing interval outcome classification rules."""

import pytest

from phase7.sources.batch_contract import (
    BatchSymbolOutcome,
    BatchSymbolStatus,
)
from phase7.sources.listing_evidence import (
    ListingDateStatus,
    ListingEvidenceRecord,
    ListingSourceType,
    ListingVerificationStatus,
    classify_historical_period_outcome,
)


def _build_evidence(listing_date: str = "2024-09-03", symbol: str = "PREMIERENE") -> ListingEvidenceRecord:
    return ListingEvidenceRecord(
        symbol=symbol,
        security_name="Premier Energies Limited",
        exchange="NSE",
        listing_date=listing_date,
        listing_date_status=ListingDateStatus.SOURCE_REPORTED,
        source_type=ListingSourceType.NSE_SECURITY_MASTER,
        source_identifier="NSE_SEC_MASTER_20240903",
        source_document_date="2024-09-03",
        retrieval_timestamp="2026-10-10T12:00:00Z",
        evidence_file_reference="listing_evidence/PREMIERENE_listing_record.json",
        evidence_sha256="a" * 64,
        source_row_hash="b" * 64,
        verification_status=ListingVerificationStatus.VERIFIED_SINGLE_SOURCE,
        reviewer_status="GOVERNED_SYSTEM",
        notes="Verified from official master",
        isin="INE0K8D01017",
    )


def test_listing_date_after_requested_end_classifies_verified_prelisting():
    ev = _build_evidence(listing_date="2024-09-03")
    outcome = classify_historical_period_outcome(
        symbol="PREMIERENE",
        requested_start_date="2024-01-01",
        requested_end_date="2024-03-31",
        raw_row_count=0,
        listing_evidence=ev,
    )
    assert outcome == BatchSymbolOutcome.NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED.value


def test_listing_date_equal_to_requested_end_is_not_prelisting():
    ev = _build_evidence(listing_date="2024-03-31")
    outcome = classify_historical_period_outcome(
        symbol="PREMIERENE",
        requested_start_date="2024-01-01",
        requested_end_date="2024-03-31",
        raw_row_count=0,
        listing_evidence=ev,
    )
    assert outcome == BatchSymbolOutcome.EMPTY_RESPONSE_UNEXPLAINED.value


def test_listing_date_before_requested_start_is_not_prelisting():
    ev = _build_evidence(listing_date="2023-12-15")
    outcome = classify_historical_period_outcome(
        symbol="PREMIERENE",
        requested_start_date="2024-01-01",
        requested_end_date="2024-03-31",
        raw_row_count=0,
        listing_evidence=ev,
    )
    assert outcome == BatchSymbolOutcome.EMPTY_RESPONSE_UNEXPLAINED.value


def test_empty_response_alone_cannot_establish_listing_status():
    outcome = classify_historical_period_outcome(
        symbol="PREMIERENE",
        requested_start_date="2024-01-01",
        requested_end_date="2024-03-31",
        raw_row_count=0,
        listing_evidence=None,
    )
    assert outcome == BatchSymbolOutcome.EMPTY_RESPONSE_UNEXPLAINED.value


def test_unverified_evidence_cannot_establish_listing_status():
    ev = ListingEvidenceRecord(
        symbol="PREMIERENE",
        security_name="Premier Energies Limited",
        exchange="NSE",
        listing_date="2024-09-03",
        listing_date_status=ListingDateStatus.UNVERIFIED,
        source_type=ListingSourceType.NSE_SECURITY_MASTER,
        source_identifier="NSE_UNVERIFIED",
        source_document_date=None,
        retrieval_timestamp="2026-10-10T12:00:00Z",
        evidence_file_reference="evidence.json",
        evidence_sha256="c" * 64,
        source_row_hash="d" * 64,
        verification_status=ListingVerificationStatus.UNVERIFIED,
        reviewer_status="PENDING",
    )
    outcome = classify_historical_period_outcome(
        symbol="PREMIERENE",
        requested_start_date="2024-01-01",
        requested_end_date="2024-03-31",
        raw_row_count=0,
        listing_evidence=ev,
    )
    assert outcome == BatchSymbolOutcome.EMPTY_RESPONSE_UNEXPLAINED.value


def test_exact_symbol_matching_enforced():
    ev = _build_evidence(symbol="DIFFERENT_SYM")
    outcome = classify_historical_period_outcome(
        symbol="PREMIERENE",
        requested_start_date="2024-01-01",
        requested_end_date="2024-03-31",
        raw_row_count=0,
        listing_evidence=ev,
    )
    assert outcome == BatchSymbolOutcome.EMPTY_RESPONSE_UNEXPLAINED.value


def test_data_available_when_rows_exist():
    ev = _build_evidence(listing_date="2024-09-03")
    outcome = classify_historical_period_outcome(
        symbol="PREMIERENE",
        requested_start_date="2024-01-01",
        requested_end_date="2024-03-31",
        raw_row_count=22,
        listing_evidence=ev,
    )
    assert outcome == BatchSymbolOutcome.DATA_AVAILABLE.value


def test_verified_prelisting_is_distinct_from_succeeded_and_failure():
    prelisting_outcome = BatchSymbolOutcome.NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED.value
    # Distinct from SUCCEEDED
    assert prelisting_outcome != BatchSymbolStatus.SUCCEEDED.value
    # Distinct from FAILED
    assert prelisting_outcome != BatchSymbolStatus.FAILED.value
    # Distinct from SOURCE_ERROR
    assert prelisting_outcome != BatchSymbolOutcome.SOURCE_ERROR.value
