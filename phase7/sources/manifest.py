"""Immutable request manifest creation and cryptographic checksum calculation.

Ensures complete auditability of all retrieved payloads.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from phase7.sources.contracts import HistoricalEODRecord, RequestManifest, RequestStatus


def compute_sha256_bytes(data: bytes) -> str:
    """Compute SHA-256 hex digest for a raw byte array."""
    return hashlib.sha256(data).hexdigest()


def compute_sha256_records(records: List[HistoricalEODRecord]) -> str:
    """Compute deterministic SHA-256 checksum for a list of normalized records."""
    hashes = [r.row_hash for r in records]
    serialized = json.dumps(sorted(hashes)).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def build_pending_manifest(
    request_id: str,
    symbol: str,
    start_date: str,
    end_date: str,
    interval: str,
    retrieval_timestamp: str,
    client_version: str = "nse-4.0.1",
    source_identifier: str = "NSE_CLIENT",
) -> RequestManifest:
    """Build a PENDING request manifest written prior to issuing a retrieval request."""
    return RequestManifest(
        request_id=request_id,
        symbol=symbol.upper().strip(),
        start_date=start_date,
        end_date=end_date,
        interval=interval,
        retrieval_timestamp=retrieval_timestamp,
        client_version=client_version,
        source_identifier=source_identifier,
        status=RequestStatus.PENDING,
        row_count=0,
        raw_checksum="",
        normalized_checksum="",
    )


def check_audit_conservation(
    source_row_count: int,
    normalized_row_count: int,
    rejected_row_count: int,
) -> bool:
    """Enforce conservation rule: source_row_count = normalized_row_count + rejected_row_count."""
    return source_row_count == (normalized_row_count + rejected_row_count)


def build_manifest(
    request_id: str,
    symbol: str,
    start_date: str,
    end_date: str,
    interval: str,
    retrieval_timestamp: str,
    raw_payload: Any,
    normalized_records: List[HistoricalEODRecord],
    status: RequestStatus,
    client_version: str = "nse-4.0.1",
    source_identifier: str = "NSE_DATA_FETCHER",
    failure_reason: Optional[str] = None,
    retry_count: int = 0,
    is_partial: bool = False,
    row_count: Optional[int] = None,
    raw_checksum: Optional[str] = None,
    normalized_checksum: Optional[str] = None,
    raw_file_path: Optional[str] = None,
    normalized_file_path: Optional[str] = None,
    schema_version: str = "phase7-eod-v1.0",
    missing_fields: Optional[Dict[str, int]] = None,
    rejected_row_count: int = 0,
    duration_seconds: Optional[float] = None,
    mapping_version: Optional[str] = None,
) -> RequestManifest:
    """Build an immutable RequestManifest instance with cryptographic checksums."""
    if raw_checksum is None:
        raw_bytes = json.dumps(raw_payload, sort_keys=True, default=str).encode("utf-8")
        raw_checksum = compute_sha256_bytes(raw_bytes)
    if normalized_checksum is None:
        normalized_checksum = compute_sha256_records(normalized_records)

    # Invariants for SUCCEEDED status under 4.9D protocol
    if status == RequestStatus.SUCCEEDED:
        if len(normalized_records) == 0:
            raise ValueError("Never report SUCCEEDED with zero normalized rows.")
        if not raw_checksum:
            raise ValueError("Never report SUCCEEDED without raw checksum.")
        if not normalized_checksum:
            raise ValueError("Never report SUCCEEDED without normalized checksum.")

    actual_row_count = row_count if row_count is not None else len(normalized_records)

    return RequestManifest(
        request_id=request_id,
        symbol=symbol.upper().strip(),
        start_date=start_date,
        end_date=end_date,
        interval=interval,
        retrieval_timestamp=retrieval_timestamp,
        client_version=client_version,
        source_identifier=source_identifier,
        status=status,
        row_count=actual_row_count,
        raw_checksum=raw_checksum,
        normalized_checksum=normalized_checksum,
        failure_reason=failure_reason,
        retry_count=retry_count,
        is_partial=is_partial,
        raw_file_path=raw_file_path,
        normalized_file_path=normalized_file_path,
        schema_version=schema_version,
        missing_fields=missing_fields,
        rejected_row_count=rejected_row_count,
        duration_seconds=duration_seconds,
        mapping_version=mapping_version,
    )


def write_manifest(
    manifest: RequestManifest,
    output_dir: Path,
    filename: Optional[str] = None,
) -> Path:
    """Persist the RequestManifest to an immutable JSON file."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    fname = filename or f"manifest_{manifest.symbol}_{manifest.start_date}_{manifest.end_date}.json"
    path = output_path / fname
    data = {
        "request_id": manifest.request_id,
        "symbol": manifest.symbol,
        "start_date": manifest.start_date,
        "end_date": manifest.end_date,
        "interval": manifest.interval,
        "retrieval_timestamp": manifest.retrieval_timestamp,
        "client_version": manifest.client_version,
        "source_identifier": manifest.source_identifier,
        "status": manifest.status.value,
        "row_count": manifest.row_count,
        "raw_checksum": manifest.raw_checksum,
        "normalized_checksum": manifest.normalized_checksum,
        "failure_reason": manifest.failure_reason,
        "retry_count": manifest.retry_count,
        "is_partial": manifest.is_partial,
        "raw_file_path": manifest.raw_file_path,
        "normalized_file_path": manifest.normalized_file_path,
        "schema_version": manifest.schema_version,
        "missing_fields": manifest.missing_fields,
        "rejected_row_count": manifest.rejected_row_count,
        "duration_seconds": manifest.duration_seconds,
        "mapping_version": manifest.mapping_version,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    return path
