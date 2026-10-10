"""Phase 7 governed listing date evidence contract and verification engine.

Provides strict cryptographic provenance, source hierarchy validation, and
governed pre-listing outcome classifications.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple


class ListingDateStatus(str, Enum):
    SOURCE_REPORTED = "SOURCE_REPORTED"
    NOT_PROVIDED = "NOT_PROVIDED"
    CONFLICTING = "CONFLICTING"
    INVALID = "INVALID"
    UNVERIFIED = "UNVERIFIED"


class ListingVerificationStatus(str, Enum):
    VERIFIED_SINGLE_SOURCE = "VERIFIED_SINGLE_SOURCE"
    VERIFIED_MULTI_SOURCE = "VERIFIED_MULTI_SOURCE"
    UNVERIFIED = "UNVERIFIED"
    CONFLICT = "CONFLICT"
    REJECTED = "REJECTED"


class ListingSourcePriority(int, Enum):
    PRIORITY_1 = 1  # Official NSE security master, circular, notice, or official exchange record
    PRIORITY_2 = 2  # SEBI-hosted prospectus or final offer document with confirmed schedule
    PRIORITY_3 = 3  # Another exchange record where NSE listing date is explicitly stated
    DISALLOWED = 99  # News, blogs, screeners, wikipedia, brokerage, snippets, AI, manual dates


class ListingSourceType(str, Enum):
    NSE_SECURITY_MASTER = "NSE_SECURITY_MASTER"
    NSE_OFFICIAL_CIRCULAR = "NSE_OFFICIAL_CIRCULAR"
    NSE_EXCHANGE_RECORD = "NSE_EXCHANGE_RECORD"
    SEBI_PROSPECTUS = "SEBI_PROSPECTUS"
    ISSUER_EXCHANGE_FILING = "ISSUER_EXCHANGE_FILING"
    OTHER_EXCHANGE_EXPLICIT = "OTHER_EXCHANGE_EXPLICIT"
    DISALLOWED_UNGOVERNED = "DISALLOWED_UNGOVERNED"


APPROVED_SOURCE_PRIORITIES = {
    ListingSourceType.NSE_SECURITY_MASTER: ListingSourcePriority.PRIORITY_1,
    ListingSourceType.NSE_OFFICIAL_CIRCULAR: ListingSourcePriority.PRIORITY_1,
    ListingSourceType.NSE_EXCHANGE_RECORD: ListingSourcePriority.PRIORITY_1,
    ListingSourceType.SEBI_PROSPECTUS: ListingSourcePriority.PRIORITY_2,
    ListingSourceType.ISSUER_EXCHANGE_FILING: ListingSourcePriority.PRIORITY_2,
    ListingSourceType.OTHER_EXCHANGE_EXPLICIT: ListingSourcePriority.PRIORITY_3,
}

DISALLOWED_SOURCE_KEYWORDS = [
    "news",
    "blog",
    "screener",
    "wikipedia",
    "brokerage",
    "snippet",
    "ai_generated",
    "manual_typed",
    "chatgpt",
    "perplexity",
    "google_search",
]


@dataclass(frozen=True)
class ListingEvidenceRecord:
    symbol: str
    security_name: str
    exchange: str
    listing_date: Optional[str]
    listing_date_status: ListingDateStatus
    source_type: ListingSourceType
    source_identifier: str
    source_document_date: Optional[str]
    retrieval_timestamp: str
    evidence_file_reference: str
    evidence_sha256: str
    source_row_hash: str
    verification_status: ListingVerificationStatus
    reviewer_status: str
    notes: str = ""
    isin: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["listing_date_status"] = self.listing_date_status.value
        d["source_type"] = self.source_type.value
        d["verification_status"] = self.verification_status.value
        return d

    def supports_prelisting_classification(self) -> bool:
        """Only VERIFIED_SINGLE_SOURCE and VERIFIED_MULTI_SOURCE may support pre-listing classification."""
        if self.verification_status not in (
            ListingVerificationStatus.VERIFIED_SINGLE_SOURCE,
            ListingVerificationStatus.VERIFIED_MULTI_SOURCE,
        ):
            return False
        if self.listing_date_status != ListingDateStatus.SOURCE_REPORTED:
            return False
        if not self.listing_date:
            return False
        return True


def validate_listing_evidence(record: ListingEvidenceRecord) -> None:
    """Validate a listing evidence record against strict governance rules."""
    if not record.symbol or not record.symbol.strip():
        raise ValueError("Listing evidence requires non-empty symbol")

    if not record.source_identifier or not record.source_identifier.strip():
        raise ValueError("Listing evidence requires non-empty source_identifier")

    if not record.evidence_sha256 or len(record.evidence_sha256) != 64:
        raise ValueError(
            f"Listing evidence requires valid 64-char SHA-256 evidence_sha256, got: '{record.evidence_sha256}'"
        )

    # Check source priority / approval
    if record.source_type not in APPROVED_SOURCE_PRIORITIES:
        raise ValueError(f"Unapproved listing source type rejected: {record.source_type}")

    # Check for disallowed provenance notes/identifiers
    combined_meta = f"{record.source_identifier} {record.notes} {record.evidence_file_reference}".lower()
    for kw in DISALLOWED_SOURCE_KEYWORDS:
        if kw in combined_meta:
            raise ValueError(f"Disallowed evidence provenance detected: '{kw}'")

    # Validate date format if present
    if record.listing_date is not None:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", record.listing_date):
            raise ValueError(f"Invalid listing_date format (must be YYYY-MM-DD): {record.listing_date}")
        try:
            datetime.strptime(record.listing_date, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(f"Invalid calendar date for listing_date: {record.listing_date}") from exc

    # Invariants for conflicting date status
    if record.listing_date_status == ListingDateStatus.CONFLICTING:
        if record.verification_status != ListingVerificationStatus.CONFLICT:
            raise ValueError("Conflicting listing date status must have CONFLICT verification status")

    # Invariants for verification status
    if record.verification_status in (
        ListingVerificationStatus.VERIFIED_SINGLE_SOURCE,
        ListingVerificationStatus.VERIFIED_MULTI_SOURCE,
    ):
        if record.listing_date is None:
            raise ValueError("Verified listing status requires non-null listing_date")
        if record.listing_date_status != ListingDateStatus.SOURCE_REPORTED:
            raise ValueError(
                f"Verified listing status requires SOURCE_REPORTED date status, got: {record.listing_date_status}"
            )


def save_listing_evidence(record: ListingEvidenceRecord, target_file: Path) -> Path:
    """Persist listing evidence atomically to disk outside Git."""
    validate_listing_evidence(record)
    target_file.parent.mkdir(parents=True, exist_ok=True)
    temp_file = target_file.with_suffix(".tmp")
    temp_file.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")
    temp_file.replace(target_file)
    return target_file


def load_listing_evidence(source_file: Path) -> ListingEvidenceRecord:
    """Load and validate listing evidence from disk."""
    if not source_file.exists():
        raise FileNotFoundError(f"Listing evidence file not found: {source_file}")

    data = json.loads(source_file.read_text(encoding="utf-8"))
    record = ListingEvidenceRecord(
        symbol=data["symbol"],
        security_name=data["security_name"],
        exchange=data["exchange"],
        listing_date=data.get("listing_date"),
        listing_date_status=ListingDateStatus(data["listing_date_status"]),
        source_type=ListingSourceType(data["source_type"]),
        source_identifier=data["source_identifier"],
        source_document_date=data.get("source_document_date"),
        retrieval_timestamp=data["retrieval_timestamp"],
        evidence_file_reference=data["evidence_file_reference"],
        evidence_sha256=data["evidence_sha256"],
        source_row_hash=data["source_row_hash"],
        verification_status=ListingVerificationStatus(data["verification_status"]),
        reviewer_status=data["reviewer_status"],
        notes=data.get("notes", ""),
        isin=data.get("isin"),
    )
    validate_listing_evidence(record)
    return record


def classify_historical_period_outcome(
    symbol: str,
    requested_start_date: str,
    requested_end_date: str,
    raw_row_count: int,
    listing_evidence: Optional[ListingEvidenceRecord] = None,
) -> str:
    """Classify the historical acquisition outcome for a security in a requested date window.

    Governed Invariants:
    1. raw_row_count > 0 -> DATA_AVAILABLE
    2. raw_row_count == 0 and verified listing_date > requested_end_date -> NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED
    3. raw_row_count == 0 without verified listing date proving listing_date > requested_end_date -> EMPTY_RESPONSE_UNEXPLAINED
    4. An empty response alone NEVER establishes listing date or pre-listing status.
    5. Listing date equal to or prior to requested_end_date with 0 rows -> EMPTY_RESPONSE_UNEXPLAINED
    """
    from phase7.sources.batch_contract import BatchSymbolOutcome

    if raw_row_count > 0:
        return BatchSymbolOutcome.DATA_AVAILABLE.value

    # Empty response branch
    if listing_evidence is None:
        return BatchSymbolOutcome.EMPTY_RESPONSE_UNEXPLAINED.value

    # Validate exact symbol matching
    if listing_evidence.symbol != symbol:
        return BatchSymbolOutcome.EMPTY_RESPONSE_UNEXPLAINED.value

    # Check whether evidence supports pre-listing classification
    if not listing_evidence.supports_prelisting_classification():
        return BatchSymbolOutcome.EMPTY_RESPONSE_UNEXPLAINED.value

    assert listing_evidence.listing_date is not None
    # Strict date comparison: listing_date > requested_end_date
    if listing_evidence.listing_date > requested_end_date:
        return BatchSymbolOutcome.NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED.value

    # Security was listed on or before the requested end date; zero rows is unexplained
    return BatchSymbolOutcome.EMPTY_RESPONSE_UNEXPLAINED.value
