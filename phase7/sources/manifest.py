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
) -> RequestManifest:
    """Build an immutable RequestManifest instance with cryptographic checksums."""
    raw_bytes = json.dumps(raw_payload, sort_keys=True, default=str).encode("utf-8")
    raw_checksum = compute_sha256_bytes(raw_bytes)
    normalized_checksum = compute_sha256_records(normalized_records)

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
        row_count=len(normalized_records),
        raw_checksum=raw_checksum,
        normalized_checksum=normalized_checksum,
        failure_reason=failure_reason,
        retry_count=retry_count,
        is_partial=is_partial,
    )


def write_manifest(manifest: RequestManifest, output_dir: Path) -> Path:
    """Persist the RequestManifest to an immutable JSON file."""
    path = Path(output_dir) / f"manifest_{manifest.symbol}_{manifest.start_date}_{manifest.end_date}.json"
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
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    return path
