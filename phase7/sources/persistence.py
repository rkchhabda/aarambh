"""External immutable persistence engine for Phase 7 historical market data.

Strictly enforces:
- Path resolution strictly outside the Git repository.
- Exclusive creation / atomic temporary-file-and-rename writes.
- Absolute prohibition against overwriting existing raw or normalized files.
- Scrubbing and zero-persistence of session credentials, authorization markers, or tokens.
- Cryptographic SHA-256 calculation over canonical bytes.
- Canonical JSONL output for normalized records.
"""

from dataclasses import asdict
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from phase7.sources.authorization import find_repo_root
from phase7.sources.contracts import HistoricalEODRecord, RequestManifest, RequestStatus
from phase7.sources.rejections import sanitize_payload


def validate_persistence_path_outside_git(path: Path, repo_root: Optional[Path] = None) -> Path:
    """Refuse any resolved target path that resides inside the Git repository."""
    resolved_path = Path(path).resolve()
    repo = (repo_root or find_repo_root()).resolve()

    if resolved_path == repo or repo in resolved_path.parents:
        raise PermissionError(
            f"REFUSED_IN_REPO_PERSISTENCE: Target path '{resolved_path}' resides inside Git repository '{repo}'."
        )
    return resolved_path


def format_iso_to_compact_utc(iso_ts: str) -> str:
    """Format ISO-8601 UTC timestamp to compact format YYYYMMDDTHHMMSSZ."""
    try:
        # Replace Z with +00:00 for fromisoformat if needed
        clean_ts = iso_ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_ts)
        return dt.strftime("%Y%m%dT%H%M%SZ")
    except Exception:
        # Fallback sanitize alphanumeric characters
        return "".join(c for c in iso_ts if c.isalnum() or c in ("T", "Z"))[:16]


def compute_canonical_sha256(data: bytes) -> str:
    """Compute deterministic SHA-256 hex digest."""
    return hashlib.sha256(data).hexdigest()


def _atomic_write_bytes(target_path: Path, content: bytes, allow_replace_pending: bool = False) -> Path:
    """Atomically write bytes using a temporary file, strictly refusing overwrite unless finalizing PENDING manifest."""
    if target_path.exists() and not allow_replace_pending:
        raise FileExistsError(
            f"PERSISTENCE_OVERWRITE_REFUSED: File already exists: '{target_path}'."
        )

    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = target_path.parent
    fd, temp_file_path = tempfile.mkstemp(
        dir=str(temp_dir),
        prefix=f".tmp_{target_path.stem}_",
        suffix=".tmp",
    )
    temp_path = Path(temp_file_path)

    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        if target_path.exists():
            if not allow_replace_pending:
                raise FileExistsError(
                    f"PERSISTENCE_OVERWRITE_REFUSED: Target file was created concurrently: '{target_path}'."
                )
            try:
                existing_data = json.loads(target_path.read_text(encoding="utf-8"))
                if existing_data.get("status") != "PENDING":
                    raise FileExistsError(
                        f"PERSISTENCE_OVERWRITE_REFUSED: Manifest is already finalized with status '{existing_data.get('status')}': '{target_path}'."
                    )
            except Exception as read_err:
                if isinstance(read_err, FileExistsError):
                    raise
                raise FileExistsError(
                    f"PERSISTENCE_OVERWRITE_REFUSED: Existing manifest file cannot be read: '{target_path}'."
                ) from read_err

        os.replace(temp_path, target_path)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass

    return target_path


def persist_raw_payload(
    payload: Any,
    staging_root: Path,
    symbol: str,
    start_date: str,
    end_date: str,
    interval: str,
    retrieval_timestamp: str,
    repo_root: Optional[Path] = None,
) -> Tuple[Path, str]:
    """Persist raw response payload to external staging directory.

    Path format:
        <staging_root>/raw/historical/<symbol>_<start>_<end>_<interval>_<ts>_<hash[:8]>.json
    """
    clean_symbol = symbol.upper().strip()
    clean_staging = validate_persistence_path_outside_git(staging_root, repo_root=repo_root)
    raw_dir = clean_staging / "raw" / "historical"
    validate_persistence_path_outside_git(raw_dir, repo_root=repo_root)

    # Sanitize payload: strip session credentials, auth, tokens, headers
    sanitized = sanitize_payload(payload)
    canonical_bytes = json.dumps(sanitized, sort_keys=True, default=str).encode("utf-8")
    payload_hash = compute_canonical_sha256(canonical_bytes)
    compact_ts = format_iso_to_compact_utc(retrieval_timestamp)
    hash_abbr = payload_hash[:8]

    filename = f"{clean_symbol}_{start_date}_{end_date}_{interval}_{compact_ts}_{hash_abbr}.json"
    target_path = raw_dir / filename
    validate_persistence_path_outside_git(target_path, repo_root=repo_root)

    persisted_path = _atomic_write_bytes(target_path, canonical_bytes)
    return persisted_path, payload_hash


def persist_normalized_records(
    records: List[HistoricalEODRecord],
    staging_root: Path,
    symbol: str,
    start_date: str,
    end_date: str,
    interval: str,
    retrieval_timestamp: str,
    repo_root: Optional[Path] = None,
) -> Tuple[Path, str, int, Dict[str, int]]:
    """Persist normalized records in canonical JSONL format to external staging directory.

    Path format:
        <staging_root>/normalized/historical/<symbol>_<start>_<end>_<interval>_<ts>_<hash[:8]>.jsonl
    """
    clean_symbol = symbol.upper().strip()
    clean_staging = validate_persistence_path_outside_git(staging_root, repo_root=repo_root)
    norm_dir = clean_staging / "normalized" / "historical"
    validate_persistence_path_outside_git(norm_dir, repo_root=repo_root)

    missing_fields: Dict[str, int] = {
        "isin": 0,
        "previous_close": 0,
        "last_price": 0,
        "vwap": 0,
        "turnover": 0,
        "number_of_trades": 0,
        "deliverable_quantity": 0,
        "delivery_percentage": 0,
    }

    lines = []
    for r in records:
        if r.isin is None:
            missing_fields["isin"] += 1
        if r.previous_close is None:
            missing_fields["previous_close"] += 1
        if r.last_price is None:
            missing_fields["last_price"] += 1
        if r.vwap is None:
            missing_fields["vwap"] += 1
        if r.total_traded_value_inr is None:
            missing_fields["turnover"] += 1
        if r.number_of_trades is None:
            missing_fields["number_of_trades"] += 1
        if r.deliverable_quantity is None:
            missing_fields["deliverable_quantity"] += 1
        if r.delivery_percentage is None:
            missing_fields["delivery_percentage"] += 1

        rec_dict = asdict(r)
        # Convert enums to string values
        rec_dict["adjustment_state"] = r.adjustment_state.value
        rec_dict["traded_value_status"] = r.traded_value_status.value
        line_bytes = json.dumps(rec_dict, sort_keys=True, default=str)
        lines.append(line_bytes)

    jsonl_content = "\n".join(lines) + ("\n" if lines else "")
    content_bytes = jsonl_content.encode("utf-8")
    norm_hash = compute_canonical_sha256(content_bytes)

    compact_ts = format_iso_to_compact_utc(retrieval_timestamp)
    hash_abbr = norm_hash[:8]

    filename = f"{clean_symbol}_{start_date}_{end_date}_{interval}_{compact_ts}_{hash_abbr}.jsonl"
    target_path = norm_dir / filename
    validate_persistence_path_outside_git(target_path, repo_root=repo_root)

    persisted_path = _atomic_write_bytes(target_path, content_bytes)
    return persisted_path, norm_hash, len(records), missing_fields


def persist_request_manifest(
    manifest: RequestManifest,
    staging_root: Path,
    repo_root: Optional[Path] = None,
) -> Path:
    """Persist immutable finalized request manifest to external staging manifests directory."""
    clean_staging = validate_persistence_path_outside_git(staging_root, repo_root=repo_root)
    manifests_dir = clean_staging / "manifests"
    validate_persistence_path_outside_git(manifests_dir, repo_root=repo_root)
    manifests_dir.mkdir(parents=True, exist_ok=True)

    filename = f"manifest_{manifest.symbol}_{manifest.request_id}.json"
    target_path = manifests_dir / filename
    validate_persistence_path_outside_git(target_path, repo_root=repo_root)

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
    }
    content_bytes = json.dumps(data, indent=2, sort_keys=True).encode("utf-8")
    allow_replace_pending = (manifest.status != RequestStatus.PENDING)
    persisted_path = _atomic_write_bytes(target_path, content_bytes, allow_replace_pending=allow_replace_pending)
    return persisted_path
