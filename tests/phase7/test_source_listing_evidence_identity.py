"""Tests for Phase 7 official listing date evidence issuer identity matching and repository safeguards."""

import hashlib
import json
from pathlib import Path
import pytest
import sys

from phase7.sources.listing_evidence import (
    ListingDateStatus,
    ListingEvidenceRecord,
    ListingSourceType,
    ListingVerificationStatus,
    RetrospectiveOutcome,
    classify_retrospective_listing_outcome,
    validate_listing_evidence,
)
from phase7.sources.listing_evidence_acquisition import analyze_document_content


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
        "notes": "Verified from official exchange master",
        "isin": "INE0BS701011",
        "cin": "U40106TG1995PLC019749",
    }
    defaults.update(overrides)
    return ListingEvidenceRecord(**defaults)


def test_symbol_exact_matching():
    rec = _build_valid_record(symbol="OTHER_SYMBOL")
    outcome = classify_retrospective_listing_outcome(
        symbol="PREMIERENE",
        requested_start_date="2024-01-01",
        requested_end_date="2024-03-31",
        raw_row_count=0,
        listing_evidence=rec,
    )
    assert outcome == RetrospectiveOutcome.EMPTY_RESPONSE_UNEXPLAINED


def test_isin_accepted_when_source_reported():
    text = "Circular: Premier Energies Limited. ISIN: INE0BS701011. Symbol: PREMIERENE."
    analysis = analyze_document_content(
        content_text=text,
        source_url="https://nsearchives.nseindia.com/corporate/notice.pdf",
        symbol="PREMIERENE",
        security_name="Premier Energies Limited",
        exchange="NSE",
    )
    assert analysis["isin"] == "INE0BS701011"
    assert analysis["name_matched"] is True
    assert analysis["symbol_matched"] is True


def test_isin_not_inferred_when_absent():
    text = "Circular: Premier Energies Limited listed on NSE on September 03, 2024."
    analysis = analyze_document_content(
        content_text=text,
        source_url="https://nsearchives.nseindia.com/corporate/notice.pdf",
        symbol="PREMIERENE",
        security_name="Premier Energies Limited",
        exchange="NSE",
    )
    assert analysis["isin"] is None  # Not inferred


def test_mismatched_issuer_identity_handling():
    text = "Circular: Tata Motors Limited listed on NSE on January 01, 2020."
    analysis = analyze_document_content(
        content_text=text,
        source_url="https://nsearchives.nseindia.com/corporate/notice.pdf",
        symbol="PREMIERENE",
        security_name="Premier Energies Limited",
        exchange="NSE",
    )
    assert analysis["name_matched"] is False
    assert analysis["symbol_matched"] is False


def test_original_halted_run_and_selection_immutable():
    staging_base = Path(r"C:\Users\r_chh\gaurvideep_phase7_staging\nse500\batch_4_10c")
    if staging_base.exists():
        # Check selection checksum file
        selection_file = staging_base / "selection" / "deterministic_20stock_selection_CURRENT_NIFTY500_09Oct2026_8F4C439F.json"
        if selection_file.exists():
            data = json.loads(selection_file.read_text(encoding="utf-8"))
            expected_checksum = "60dd03580442b1f874f364206da5d9bf252a4abf1ff93801d4b58e93fdee7b1d"
            assert data["selection_checksum"] == expected_checksum
            expected_ordered_hash = "26e4be7c9cfd366b630b0b714f0afd65a223ffae91edad6e231060e6b95c4ee3"
            assert data["ordered_symbols_hash"] == expected_ordered_hash

        # Check historical consumed marker remains consumed
        auth_dir = staging_base / "authorization"
        if auth_dir.exists():
            active_markers = list(auth_dir.glob("batch_authorization.json"))
            assert len(active_markers) == 0  # No active batch markers
            consumed_markers = list(auth_dir.glob("batch_authorization.consumed.*.json"))
            assert len(consumed_markers) >= 1  # Consumed marker intact


def test_no_phase6_or_production_imports():
    import ast
    sources_dir = Path(__file__).resolve().parent.parent.parent / "phase7" / "sources"
    evidence_files = [
        "listing_evidence.py",
        "listing_evidence_authorization.py",
        "listing_evidence_persistence.py",
        "listing_evidence_acquisition.py",
    ]
    disallowed_prefixes = ("service", "features", "config", "scripts.phase6")

    for fname in evidence_files:
        py_path = sources_dir / fname
        assert py_path.exists(), f"Source file {py_path} does not exist"
        tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for prefix in disallowed_prefixes:
                        assert not alias.name.startswith(prefix), f"Forbidden import '{alias.name}' in {fname}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for prefix in disallowed_prefixes:
                        assert not node.module.startswith(prefix), f"Forbidden from-import '{node.module}' in {fname}"
