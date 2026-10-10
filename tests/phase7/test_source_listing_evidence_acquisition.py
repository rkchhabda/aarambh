"""Tests for Phase 7 official listing date evidence acquisition runner and network boundaries."""

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest

from phase7.sources.listing_evidence_acquisition import (
    APPROVED_EVIDENCE_DOMAINS,
    MAX_RESPONSE_BYTES,
    MAXIMUM_REQUEST_COUNT,
    ListingEvidenceAcquisitionError,
    detect_captcha,
    execute_listing_evidence_pilot,
    extract_html_text,
    extract_pdf_text,
    validate_source_url,
)
from phase7.sources.listing_evidence_authorization import (
    create_listing_evidence_authorization,
)


def _setup_external_staging(tmp_path_factory) -> Path:
    staging = tmp_path_factory.mktemp("listing_evidence_acq_staging")
    return staging.resolve()


def test_approved_domains_accepted():
    for d in APPROVED_EVIDENCE_DOMAINS:
        url = f"https://{d}/official_notice.pdf"
        validated = validate_source_url(url)
        assert validated == url


def test_http_url_rejected():
    with pytest.raises(ListingEvidenceAcquisitionError, match="Disallowed scheme 'http'"):
        validate_source_url("http://nsearchives.nseindia.com/doc.pdf")


def test_unapproved_domain_rejected():
    disallowed_urls = [
        "https://en.wikipedia.org/wiki/Premier_Energies",
        "https://screener.in/company/PREMIERENE/",
        "https://moneycontrol.com/news/premier-energies",
        "https://google.com/search?q=premier+energies+listing+date",
    ]
    for url in disallowed_urls:
        with pytest.raises(ListingEvidenceAcquisitionError, match="Unapproved domain"):
            validate_source_url(url)


def test_invalid_pdf_header_rejected():
    fake_data = b"NOT_A_PDF_DOCUMENT_CONTENT"
    with pytest.raises(ValueError, match="Invalid PDF header"):
        extract_pdf_text(fake_data)


def test_captcha_detection():
    assert detect_captcha("Please solve this CAPTCHA to proceed") is True
    assert detect_captcha("Attention Required! | Cloudflare cf-browser-verification") is True
    assert detect_captcha("Normal exchange listing notice for Premier Energies") is False


def test_html_text_extraction():
    html_sample = "<html><body><h1>Premier Energies Limited</h1><p>Prospectus dated August 28, 2024</p></body></html>"
    extracted = extract_html_text(html_sample)
    assert "Premier Energies Limited" in extracted
    assert "August 28, 2024" in extracted


def test_oversized_response_rejected(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    marker_path, _ = create_listing_evidence_authorization(staging_root=staging)

    # 51 MB payload exceeds 50 MB ceiling
    oversized_bytes = b"%PDF-" + b"0" * (MAX_RESPONSE_BYTES + 1024)
    target_url = "https://nsearchives.nseindia.com/corporate/oversized.pdf"
    mock_responses = {
        target_url: (200, oversized_bytes, "application/pdf")
    }

    with pytest.raises(ListingEvidenceAcquisitionError, match="Oversized response"):
        execute_listing_evidence_pilot(
            staging_root=staging,
            authorization_file=marker_path,
            source_urls=[target_url],
            mock_responses=mock_responses,
        )


def test_empty_response_rejected(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    marker_path, _ = create_listing_evidence_authorization(staging_root=staging)

    target_url = "https://nsearchives.nseindia.com/corporate/empty.pdf"
    mock_responses = {
        target_url: (200, b"", "application/pdf")
    }

    with pytest.raises(ListingEvidenceAcquisitionError, match="Empty response received"):
        execute_listing_evidence_pilot(
            staging_root=staging,
            authorization_file=marker_path,
            source_urls=[target_url],
            mock_responses=mock_responses,
        )


def test_request_count_above_ceiling_rejected(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    marker_path, _ = create_listing_evidence_authorization(staging_root=staging)

    # 6 URLs exceeds 5 request ceiling
    urls = [f"https://nseindia.com/doc_{i}.pdf" for i in range(6)]

    with pytest.raises(ListingEvidenceAcquisitionError, match="exceeds maximum ceiling"):
        execute_listing_evidence_pilot(
            staging_root=staging,
            authorization_file=marker_path,
            source_urls=urls,
            mock_responses={},
        )


def test_marker_consumed_before_first_request(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    marker_path, _ = create_listing_evidence_authorization(staging_root=staging)

    target_url = "https://nsearchives.nseindia.com/corporate/ADV_INE0BS701011_02SEP2024.pdf"
    # Even if request raises an error, marker was consumed prior to network execution
    mock_responses = {
        target_url: (403, b"Forbidden", "text/plain")
    }

    with pytest.raises(ListingEvidenceAcquisitionError, match="HTTP denial"):
        execute_listing_evidence_pilot(
            staging_root=staging,
            authorization_file=marker_path,
            source_urls=[target_url],
            mock_responses=mock_responses,
        )

    # Marker must NOT exist in active state
    assert not marker_path.exists()
    # Consumed marker must exist
    consumed_files = list((staging / "authorization").glob("listing_evidence_authorization.consumed.*.json"))
    assert len(consumed_files) == 1


def test_mock_end_to_end_acquisition_success(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    marker_path, _ = create_listing_evidence_authorization(staging_root=staging)

    # Synthetic official NSE listing circular PDF bytes
    synthetic_pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Length 200 >> stream\n"
        b"BT\n"
        b"/F1 12 Tf\n"
        b"(National Stock Exchange of India Limited) Tj\n"
        b"(Circular: Listing and trading of equity shares of Premier Energies Limited) Tj\n"
        b"(Trading members are informed that Premier Energies Limited shall be admitted to dealings on September 03, 2024) Tj\n"
        b"(ISIN: INE0BS701011 Symbol: PREMIERENE) Tj\n"
        b"(Date of Circular: September 02, 2024) Tj\n"
        b"ET\n"
        b"endstream\n"
        b"endobj\n"
        b"%%EOF\n"
    )

    target_url = "https://nsearchives.nseindia.com/corporate/ADV_INE0BS701011_02SEP2024.pdf"
    mock_responses = {
        target_url: (200, synthetic_pdf, "application/pdf")
    }

    exit_code = execute_listing_evidence_pilot(
        staging_root=staging,
        authorization_file=marker_path,
        source_urls=[target_url],
        mock_responses=mock_responses,
    )

    assert exit_code == 0

    # Verify artifacts outside Git
    raw_files = list((staging / "raw").glob("*.pdf"))
    assert len(raw_files) == 1

    extracted_file = staging / "extracted" / "PREMIERENE_listing_evidence.json"
    assert extracted_file.exists()
    extracted_data = json.loads(extracted_file.read_text(encoding="utf-8"))
    assert extracted_data["symbol"] == "PREMIERENE"
    assert extracted_data["listing_date"] == "2024-09-03"
    assert extracted_data["listing_date_status"] == "SOURCE_REPORTED"

    manifest_files = list((staging / "manifests").glob("evidence_manifest_*.json"))
    assert len(manifest_files) == 1

    audit_file = staging / "audit" / "retrospective_classification_PREMIERENE.json"
    assert audit_file.exists()
    audit_data = json.loads(audit_file.read_text(encoding="utf-8"))
    assert audit_data["retrospective_outcome"] == "NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED"
