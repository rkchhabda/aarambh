"""Tests for Phase 7 official listing date evidence semantic classifications and decision rules."""

import pytest

from phase7.sources.listing_evidence import (
    DateSemanticClassification,
    DateStatementRecord,
    ListingDateStatus,
    ListingEvidenceRecord,
    ListingSourcePriority,
    ListingSourceType,
    ListingVerificationStatus,
    RetrospectiveOutcome,
    classify_date_statement_text,
    classify_historical_period_outcome,
    classify_retrospective_listing_outcome,
    validate_listing_evidence,
)


def _build_valid_record(**overrides) -> ListingEvidenceRecord:
    defaults = {
        "symbol": "PREMIERENE",
        "security_name": "Premier Energies Limited",
        "exchange": "NSE",
        "listing_date": "2024-09-03",
        "listing_date_status": ListingDateStatus.SOURCE_REPORTED,
        "source_type": ListingSourceType.NSE_OFFICIAL_CIRCULAR,
        "source_identifier": "ADV_INE0BS701011_02SEP2024.pdf",
        "source_document_date": "2024-09-02",
        "retrieval_timestamp": "2026-10-10T12:00:00Z",
        "evidence_file_reference": "raw/ADV_INE0BS701011_02SEP2024.pdf",
        "evidence_sha256": "a" * 64,
        "source_row_hash": "b" * 64,
        "verification_status": ListingVerificationStatus.VERIFIED_SINGLE_SOURCE,
        "reviewer_status": "GOVERNED_SYSTEM",
        "notes": "Official circular verified",
        "isin": "INE0BS701011",
        "expected_trading_date": "2024-09-03",
        "confirmed_trading_date": "2024-09-03",
    }
    defaults.update(overrides)
    return ListingEvidenceRecord(**defaults)


def test_classify_date_statement_semantics():
    # Expected commencement
    assert (
        classify_date_statement_text("Trading is expected to commence on September 3, 2024")
        == DateSemanticClassification.EXPECTED_TRADING_COMMENCEMENT_DATE
    )
    assert (
        classify_date_statement_text("Indicative timetable: expected date of listing September 03, 2024")
        == DateSemanticClassification.EXPECTED_TRADING_COMMENCEMENT_DATE
    )

    # Confirmed commencement
    assert (
        classify_date_statement_text("Trading members are informed that equity shares shall be admitted to dealings on September 03, 2024")
        == DateSemanticClassification.CONFIRMED_TRADING_COMMENCEMENT_DATE
    )
    assert (
        classify_date_statement_text("Listing and trading of equity shares effective from September 03, 2024")
        == DateSemanticClassification.CONFIRMED_TRADING_COMMENCEMENT_DATE
    )

    # Prospectus date
    assert (
        classify_date_statement_text("Prospectus dated August 28, 2024 filed with ROC")
        == DateSemanticClassification.PROSPECTUS_DATE
    )

    # Allotment date
    assert (
        classify_date_statement_text("Basis of allotment finalised on August 30, 2024")
        == DateSemanticClassification.ALLOTMENT_DATE
    )

    # Offer open/close
    assert (
        classify_date_statement_text("Bid/Offer opens on August 27, 2024")
        == DateSemanticClassification.OFFER_OPEN_DATE
    )
    assert (
        classify_date_statement_text("Bid/Offer closes on August 29, 2024")
        == DateSemanticClassification.OFFER_CLOSE_DATE
    )

    # Unclassified
    assert (
        classify_date_statement_text("Annual general meeting notice date")
        == DateSemanticClassification.UNCLASSIFIED_DATE
    )


def test_expected_date_not_recorded_as_confirmed_actual_date():
    # Record with only expected trading date
    record = _build_valid_record(
        confirmed_trading_date=None,
        expected_trading_date="2024-09-03",
    )
    validate_listing_evidence(record)
    assert record.confirmed_trading_date is None
    assert record.expected_trading_date == "2024-09-03"

    # Only expected trading date yields provisionally confirmed outcome
    outcome = classify_retrospective_listing_outcome(
        symbol="PREMIERENE",
        requested_start_date="2024-01-01",
        requested_end_date="2024-03-31",
        raw_row_count=0,
        listing_evidence=record,
    )
    assert outcome == RetrospectiveOutcome.PRELISTING_AFTER_PERIOD_PROVISIONALLY_CONFIRMED


def test_confirmed_listing_notice_supports_verified_outcome():
    record = _build_valid_record(
        confirmed_trading_date="2024-09-03",
        expected_trading_date="2024-09-03",
    )
    outcome = classify_retrospective_listing_outcome(
        symbol="PREMIERENE",
        requested_start_date="2024-01-01",
        requested_end_date="2024-03-31",
        raw_row_count=0,
        listing_evidence=record,
    )
    assert outcome == RetrospectiveOutcome.NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED


def test_prospectus_date_not_treated_as_listing_date():
    stmt = DateStatementRecord(
        statement_text="Prospectus dated August 28, 2024",
        extracted_date="2024-08-28",
        semantic_classification=DateSemanticClassification.PROSPECTUS_DATE,
    )
    assert stmt.semantic_classification != DateSemanticClassification.CONFIRMED_TRADING_COMMENCEMENT_DATE
    assert stmt.semantic_classification != DateSemanticClassification.EXPECTED_TRADING_COMMENCEMENT_DATE


def test_offer_open_date_not_treated_as_listing_date():
    stmt = DateStatementRecord(
        statement_text="Offer opens on August 27, 2024",
        extracted_date="2024-08-27",
        semantic_classification=DateSemanticClassification.OFFER_OPEN_DATE,
    )
    assert stmt.semantic_classification != DateSemanticClassification.CONFIRMED_TRADING_COMMENCEMENT_DATE


def test_conflicting_official_dates_create_conflict():
    record = _build_valid_record(
        listing_date="2024-09-03",
        listing_date_status=ListingDateStatus.CONFLICTING,
        verification_status=ListingVerificationStatus.CONFLICT,
    )
    validate_listing_evidence(record)

    outcome = classify_retrospective_listing_outcome(
        symbol="PREMIERENE",
        requested_start_date="2024-01-01",
        requested_end_date="2024-03-31",
        raw_row_count=0,
        listing_evidence=record,
    )
    assert outcome == RetrospectiveOutcome.EMPTY_RESPONSE_UNEXPLAINED


def test_two_consistent_sources_produce_verified_multi_source():
    record = _build_valid_record(
        verification_status=ListingVerificationStatus.VERIFIED_MULTI_SOURCE,
        confirmed_trading_date="2024-09-03",
    )
    validate_listing_evidence(record)

    outcome = classify_retrospective_listing_outcome(
        symbol="PREMIERENE",
        requested_start_date="2024-01-01",
        requested_end_date="2024-03-31",
        raw_row_count=0,
        listing_evidence=record,
    )
    assert outcome == RetrospectiveOutcome.NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED


def test_unofficial_source_rejected():
    with pytest.raises(ValueError, match="Unapproved listing source type rejected"):
        validate_listing_evidence(_build_valid_record(source_type=ListingSourceType.DISALLOWED_UNGOVERNED))


def test_search_snippet_rejected_as_evidence():
    with pytest.raises(ValueError, match="Disallowed evidence provenance detected"):
        validate_listing_evidence(_build_valid_record(notes="Found via google_search snippet on web"))


def test_empty_historical_response_does_not_prove_listing_status():
    outcome = classify_retrospective_listing_outcome(
        symbol="PREMIERENE",
        requested_start_date="2024-01-01",
        requested_end_date="2024-03-31",
        raw_row_count=0,
        listing_evidence=None,
    )
    assert outcome == RetrospectiveOutcome.EMPTY_RESPONSE_UNEXPLAINED


def test_listing_date_on_or_before_requested_end_does_not_support_prelisting():
    record = _build_valid_record(
        listing_date="2024-03-15",
        confirmed_trading_date="2024-03-15",
        expected_trading_date="2024-03-15",
    )
    outcome = classify_retrospective_listing_outcome(
        symbol="PREMIERENE",
        requested_start_date="2024-01-01",
        requested_end_date="2024-03-31",
        raw_row_count=0,
        listing_evidence=record,
    )
    assert outcome == RetrospectiveOutcome.EMPTY_RESPONSE_UNEXPLAINED
