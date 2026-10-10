"""Phase 7 governed listing date evidence contract and verification engine.

Provides strict cryptographic provenance, source hierarchy validation, date-semantic
classification, and governed pre-listing outcome classifications.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple


class DateSemanticClassification(str, Enum):
    EXPECTED_TRADING_COMMENCEMENT_DATE = "EXPECTED_TRADING_COMMENCEMENT_DATE"
    CONFIRMED_TRADING_COMMENCEMENT_DATE = "CONFIRMED_TRADING_COMMENCEMENT_DATE"
    LISTING_APPROVAL_DATE = "LISTING_APPROVAL_DATE"
    PROSPECTUS_DATE = "PROSPECTUS_DATE"
    OFFER_OPEN_DATE = "OFFER_OPEN_DATE"
    OFFER_CLOSE_DATE = "OFFER_CLOSE_DATE"
    ALLOTMENT_DATE = "ALLOTMENT_DATE"
    UNCLASSIFIED_DATE = "UNCLASSIFIED_DATE"


class RetrospectiveOutcome(str, Enum):
    NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED = "NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED"
    PRELISTING_AFTER_PERIOD_PROVISIONALLY_CONFIRMED = "PRELISTING_AFTER_PERIOD_PROVISIONALLY_CONFIRMED"
    EMPTY_RESPONSE_UNEXPLAINED = "EMPTY_RESPONSE_UNEXPLAINED"


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
class DateStatementRecord:
    statement_text: str
    extracted_date: str
    semantic_classification: DateSemanticClassification
    page_or_section: Optional[str] = None
    statement_hash: str = ""

    def __post_init__(self):
        if not self.statement_hash and self.statement_text:
            h = hashlib.sha256(self.statement_text.strip().encode("utf-8")).hexdigest()
            object.__setattr__(self, "statement_hash", h)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statement_text": self.statement_text,
            "extracted_date": self.extracted_date,
            "semantic_classification": self.semantic_classification.value,
            "page_or_section": self.page_or_section,
            "statement_hash": self.statement_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DateStatementRecord":
        return cls(
            statement_text=data["statement_text"],
            extracted_date=data["extracted_date"],
            semantic_classification=DateSemanticClassification(data["semantic_classification"]),
            page_or_section=data.get("page_or_section"),
            statement_hash=data.get("statement_hash", ""),
        )


def classify_date_statement_text(statement_text: str) -> DateSemanticClassification:
    """Classify date statement text into strictly governed semantic categories.

    Distinguishes expected vs confirmed dates and ancillary offer dates.
    """
    lower = statement_text.lower()

    # Expected commencement patterns
    expected_keywords = [
        "expected to commence",
        "tentative",
        "indicative timetable",
        "expected date of",
        "expected listing date",
        "proposed date",
        "commencing on or about",
    ]
    for kw in expected_keywords:
        if kw in lower:
            return DateSemanticClassification.EXPECTED_TRADING_COMMENCEMENT_DATE

    # Confirmed trading commencement patterns
    confirmed_keywords = [
        "trading members are informed",
        "admitted to dealings",
        "trading shall be admitted",
        "shall be admitted to dealings",
        "trading shall commence",
        "trading commenced on",
        "effective from",
        "listing and trading of equity shares",
    ]
    for kw in confirmed_keywords:
        if kw in lower:
            return DateSemanticClassification.CONFIRMED_TRADING_COMMENCEMENT_DATE

    # Ancillary offer dates
    if "prospectus dated" in lower or "red herring prospectus" in lower or "rhp dated" in lower:
        return DateSemanticClassification.PROSPECTUS_DATE

    if "basis of allotment" in lower or "allotment on" in lower:
        return DateSemanticClassification.ALLOTMENT_DATE

    if "bid/offer opens" in lower or "offer opens on" in lower or "issue opens" in lower:
        return DateSemanticClassification.OFFER_OPEN_DATE

    if "bid/offer closes" in lower or "offer closes on" in lower or "issue closes" in lower:
        return DateSemanticClassification.OFFER_CLOSE_DATE

    if "in-principle approval" in lower or "listing approval" in lower:
        return DateSemanticClassification.LISTING_APPROVAL_DATE

    return DateSemanticClassification.UNCLASSIFIED_DATE


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
    cin: Optional[str] = None
    date_statements: List[DateStatementRecord] = field(default_factory=list)
    expected_trading_date: Optional[str] = None
    confirmed_trading_date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["listing_date_status"] = self.listing_date_status.value
        d["source_type"] = self.source_type.value
        d["verification_status"] = self.verification_status.value
        d["date_statements"] = [stmt.to_dict() for stmt in self.date_statements]
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
    for date_val, date_name in [
        (record.listing_date, "listing_date"),
        (record.expected_trading_date, "expected_trading_date"),
        (record.confirmed_trading_date, "confirmed_trading_date"),
        (record.source_document_date, "source_document_date"),
    ]:
        if date_val is not None:
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_val):
                raise ValueError(f"Invalid {date_name} format (must be YYYY-MM-DD): {date_val}")
            try:
                datetime.strptime(date_val, "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError(f"Invalid calendar date for {date_name}: {date_val}") from exc

    # Invariant: Do not conflate expected with confirmed actual trading date
    if record.expected_trading_date and record.confirmed_trading_date:
        if record.expected_trading_date == record.confirmed_trading_date and not record.date_statements:
            pass  # Allowed only if both statements exist independently

    # Validate date statements
    for stmt in record.date_statements:
        if not stmt.statement_hash or len(stmt.statement_hash) != 64:
            raise ValueError(f"Date statement requires valid 64-char SHA-256 statement_hash: '{stmt.statement_hash}'")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", stmt.extracted_date):
            raise ValueError(f"Date statement extracted_date must be YYYY-MM-DD: '{stmt.extracted_date}'")

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
    raw_statements = data.get("date_statements", [])
    statements = [DateStatementRecord.from_dict(s) for s in raw_statements]

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
        cin=data.get("cin"),
        date_statements=statements,
        expected_trading_date=data.get("expected_trading_date"),
        confirmed_trading_date=data.get("confirmed_trading_date"),
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
    """Classify historical acquisition outcome for a security in a requested date window.

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


def classify_retrospective_listing_outcome(
    symbol: str,
    requested_start_date: str,
    requested_end_date: str,
    raw_row_count: int,
    listing_evidence: Optional[ListingEvidenceRecord] = None,
) -> RetrospectiveOutcome:
    """Classify the retrospective listing outcome distinguishing confirmed vs provisional evidence.

    Governed Invariants:
    1. Confirmed actual trading date > requested_end_date -> NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED
    2. Official listing notice establishing trading date > requested_end_date -> NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED
    3. Only expected trading commencement date > requested_end_date -> PRELISTING_AFTER_PERIOD_PROVISIONALLY_CONFIRMED
    4. Otherwise -> EMPTY_RESPONSE_UNEXPLAINED
    """
    if raw_row_count > 0:
        return RetrospectiveOutcome.EMPTY_RESPONSE_UNEXPLAINED

    if listing_evidence is None:
        return RetrospectiveOutcome.EMPTY_RESPONSE_UNEXPLAINED

    if listing_evidence.symbol != symbol:
        return RetrospectiveOutcome.EMPTY_RESPONSE_UNEXPLAINED

    if listing_evidence.verification_status not in (
        ListingVerificationStatus.VERIFIED_SINGLE_SOURCE,
        ListingVerificationStatus.VERIFIED_MULTI_SOURCE,
    ):
        return RetrospectiveOutcome.EMPTY_RESPONSE_UNEXPLAINED

    # Invariant: If listing date or confirmed trading date is on or before requested_end_date,
    # the security was listed during or prior to the requested period.
    if listing_evidence.listing_date and listing_evidence.listing_date <= requested_end_date:
        return RetrospectiveOutcome.EMPTY_RESPONSE_UNEXPLAINED
    if listing_evidence.confirmed_trading_date and listing_evidence.confirmed_trading_date <= requested_end_date:
        return RetrospectiveOutcome.EMPTY_RESPONSE_UNEXPLAINED

    # Check for confirmed actual trading date
    if listing_evidence.confirmed_trading_date and listing_evidence.confirmed_trading_date > requested_end_date:
        return RetrospectiveOutcome.NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED

    # Check if primary listing date is verified and supported by official circular / master
    if (
        listing_evidence.listing_date
        and listing_evidence.listing_date > requested_end_date
        and listing_evidence.source_type
        in (
            ListingSourceType.NSE_OFFICIAL_CIRCULAR,
            ListingSourceType.NSE_SECURITY_MASTER,
            ListingSourceType.NSE_EXCHANGE_RECORD,
        )
        and not listing_evidence.expected_trading_date
    ):
        return RetrospectiveOutcome.NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED

    # Check for two consistent official documents establishing trading could not commence before period end
    if (
        listing_evidence.verification_status == ListingVerificationStatus.VERIFIED_MULTI_SOURCE
        and listing_evidence.listing_date
        and listing_evidence.listing_date > requested_end_date
    ):
        return RetrospectiveOutcome.NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED

    # If only an expected trading date is available after the period end
    if listing_evidence.expected_trading_date and listing_evidence.expected_trading_date > requested_end_date:
        return RetrospectiveOutcome.PRELISTING_AFTER_PERIOD_PROVISIONALLY_CONFIRMED

    # Fallback if listing_date is present > requested_end_date
    if listing_evidence.listing_date and listing_evidence.listing_date > requested_end_date:
        if listing_evidence.confirmed_trading_date:
            return RetrospectiveOutcome.NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED
        return RetrospectiveOutcome.PRELISTING_AFTER_PERIOD_PROVISIONALLY_CONFIRMED

    return RetrospectiveOutcome.EMPTY_RESPONSE_UNEXPLAINED
