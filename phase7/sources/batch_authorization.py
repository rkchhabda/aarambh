"""Phase 7 batch pilot authorization and single-use marker engine.

Governs single-use authorization markers specifically scoped to the 20-stock batch.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import uuid

from phase7.sources.batch_contract import (
    REQUIRED_AUTHORIZATION_SCOPE,
    REQUIRED_END_DATE,
    REQUIRED_INTERVAL,
    REQUIRED_PANEL_VERSION,
    REQUIRED_SNAPSHOT_CHECKSUM,
    REQUIRED_START_DATE,
    REQUIRED_SYMBOL_COUNT,
    BatchContract,
)

MARKER_FILENAME = "batch_authorization.json"
CONSUMED_PREFIX = "batch_authorization.consumed."


@dataclass(frozen=True)
class BatchAuthorizationRecord:
    authorization_version: str
    milestone: str
    scope: str
    source_panel_version: str
    source_snapshot_checksum: str
    selection_checksum: str
    ordered_symbols_hash: str
    symbol_count: int
    start_date: str
    end_date: str
    interval: str
    staging_root_hash: str
    maximum_concurrency: int
    minimum_request_spacing_seconds: float
    maximum_retries: int
    issued_timestamp: str
    expires_timestamp: str
    single_use: bool
    nonce: str
    authorization_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_batch_authorization_hash(
    milestone: str,
    scope: str,
    source_panel_version: str,
    source_snapshot_checksum: str,
    selection_checksum: str,
    ordered_symbols_hash: str,
    symbol_count: int,
    start_date: str,
    end_date: str,
    interval: str,
    staging_root_hash: str,
    maximum_concurrency: int,
    minimum_request_spacing_seconds: float,
    maximum_retries: int,
    issued_timestamp: str,
    expires_timestamp: str,
    nonce: str,
) -> str:
    """Compute cryptographic authorization hash over all bound governance fields."""
    components = [
        milestone,
        scope,
        source_panel_version,
        source_snapshot_checksum,
        selection_checksum,
        ordered_symbols_hash,
        str(symbol_count),
        start_date,
        end_date,
        interval,
        staging_root_hash,
        str(maximum_concurrency),
        str(minimum_request_spacing_seconds),
        str(maximum_retries),
        issued_timestamp,
        expires_timestamp,
        nonce,
    ]
    payload = "|".join(components).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def create_batch_authorization_marker(
    staging_root: Path,
    selection_checksum: str,
    ordered_symbols_hash: str,
    expires_minutes: int = 30,
    milestone: str = "4.10C",
    scope: str = REQUIRED_AUTHORIZATION_SCOPE,
    panel_version: str = REQUIRED_PANEL_VERSION,
    snapshot_checksum: str = REQUIRED_SNAPSHOT_CHECKSUM,
    start_date: str = REQUIRED_START_DATE,
    end_date: str = REQUIRED_END_DATE,
    interval: str = REQUIRED_INTERVAL,
    symbol_count: int = REQUIRED_SYMBOL_COUNT,
    maximum_concurrency: int = 1,
    minimum_spacing: float = 2.0,
    maximum_retries: int = 0,
) -> Tuple[BatchAuthorizationRecord, Path]:
    """Create a single-use batch authorization marker."""
    staging_root_hash = hashlib.sha256(str(staging_root.resolve()).encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    issued_ts = now.isoformat()
    expires_ts = (now + timedelta(minutes=expires_minutes)).isoformat()
    nonce = str(uuid.uuid4())

    auth_hash = compute_batch_authorization_hash(
        milestone=milestone,
        scope=scope,
        source_panel_version=panel_version,
        source_snapshot_checksum=snapshot_checksum,
        selection_checksum=selection_checksum,
        ordered_symbols_hash=ordered_symbols_hash,
        symbol_count=symbol_count,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
        staging_root_hash=staging_root_hash,
        maximum_concurrency=maximum_concurrency,
        minimum_request_spacing_seconds=minimum_spacing,
        maximum_retries=maximum_retries,
        issued_timestamp=issued_ts,
        expires_timestamp=expires_ts,
        nonce=nonce,
    )

    record = BatchAuthorizationRecord(
        authorization_version="1.0",
        milestone=milestone,
        scope=scope,
        source_panel_version=panel_version,
        source_snapshot_checksum=snapshot_checksum,
        selection_checksum=selection_checksum,
        ordered_symbols_hash=ordered_symbols_hash,
        symbol_count=symbol_count,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
        staging_root_hash=staging_root_hash,
        maximum_concurrency=maximum_concurrency,
        minimum_request_spacing_seconds=minimum_spacing,
        maximum_retries=maximum_retries,
        issued_timestamp=issued_ts,
        expires_timestamp=expires_ts,
        single_use=True,
        nonce=nonce,
        authorization_hash=auth_hash,
    )

    auth_dir = staging_root / "authorization"
    auth_dir.mkdir(parents=True, exist_ok=True)
    marker_path = auth_dir / MARKER_FILENAME

    if marker_path.exists():
        raise RuntimeError(f"Active authorization marker already exists: {marker_path}")

    marker_path.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")
    return record, marker_path


def validate_batch_authorization(
    marker_path: Path,
    contract: BatchContract,
    staging_root: Path,
) -> BatchAuthorizationRecord:
    """Validate active authorization marker against the batch contract and invariants."""
    if not marker_path.exists():
        raise FileNotFoundError(f"Authorization marker not found: {marker_path}")

    try:
        data = json.loads(marker_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Corrupt authorization marker payload: {exc}") from exc

    if not data.get("single_use", False):
        raise ValueError("Authorization marker must declare single_use=True")

    if data.get("scope") != REQUIRED_AUTHORIZATION_SCOPE:
        raise ValueError(
            f"Scope mismatch: {data.get('scope')} != {REQUIRED_AUTHORIZATION_SCOPE}"
        )

    if data.get("milestone") != "4.10C":
        raise ValueError(
            f"Milestone mismatch: {data.get('milestone')} != 4.10C"
        )

    if data.get("source_panel_version") != contract.source_panel_version:
        raise ValueError(
            f"Panel version mismatch: {data.get('source_panel_version')} != {contract.source_panel_version}"
        )

    if data.get("source_snapshot_checksum") != contract.source_snapshot_checksum:
        raise ValueError(
            f"Snapshot checksum mismatch: {data.get('source_snapshot_checksum')} != {contract.source_snapshot_checksum}"
        )

    if data.get("selection_checksum") != contract.selection_checksum:
        raise ValueError(
            f"Selection checksum mismatch: {data.get('selection_checksum')} != {contract.selection_checksum}"
        )

    if data.get("ordered_symbols_hash") != contract.ordered_symbols_hash:
        raise ValueError(
            f"Ordered symbols hash mismatch: {data.get('ordered_symbols_hash')} != {contract.ordered_symbols_hash}"
        )

    if data.get("symbol_count") != contract.symbol_count:
        raise ValueError(
            f"Symbol count mismatch: {data.get('symbol_count')} != {contract.symbol_count}"
        )

    if data.get("start_date") != contract.start_date:
        raise ValueError(
            f"Start date mismatch: {data.get('start_date')} != {contract.start_date}"
        )

    if data.get("end_date") != contract.end_date:
        raise ValueError(
            f"End date mismatch: {data.get('end_date')} != {contract.end_date}"
        )

    if data.get("interval") != contract.interval:
        raise ValueError(
            f"Interval mismatch: {data.get('interval')} != {contract.interval}"
        )

    expected_staging_hash = hashlib.sha256(str(staging_root.resolve()).encode("utf-8")).hexdigest()
    if data.get("staging_root_hash") != expected_staging_hash:
        raise ValueError(
            f"Staging root hash mismatch: {data.get('staging_root_hash')} != {expected_staging_hash}"
        )

    # Expiry verification
    expires_str = data.get("expires_timestamp")
    if not expires_str:
        raise ValueError("Missing expires_timestamp in authorization marker")

    expires_dt = datetime.fromisoformat(expires_str)
    now_dt = datetime.now(timezone.utc)
    if now_dt >= expires_dt:
        raise ValueError(f"Authorization marker expired at {expires_dt} (now {now_dt})")

    # Re-verify authorization hash
    recomputed_hash = compute_batch_authorization_hash(
        milestone=data["milestone"],
        scope=data["scope"],
        source_panel_version=data["source_panel_version"],
        source_snapshot_checksum=data["source_snapshot_checksum"],
        selection_checksum=data["selection_checksum"],
        ordered_symbols_hash=data["ordered_symbols_hash"],
        symbol_count=data["symbol_count"],
        start_date=data["start_date"],
        end_date=data["end_date"],
        interval=data["interval"],
        staging_root_hash=data["staging_root_hash"],
        maximum_concurrency=data["maximum_concurrency"],
        minimum_request_spacing_seconds=data["minimum_request_spacing_seconds"],
        maximum_retries=data["maximum_retries"],
        issued_timestamp=data["issued_timestamp"],
        expires_timestamp=data["expires_timestamp"],
        nonce=data["nonce"],
    )

    if recomputed_hash != data.get("authorization_hash"):
        raise ValueError("Cryptographic authorization hash tampering detected")

    return BatchAuthorizationRecord(**data)


def consume_batch_authorization_marker(
    marker_path: Path,
    contract: BatchContract,
    staging_root: Path,
) -> Path:
    """Atomically consume the single-use batch authorization marker."""
    record = validate_batch_authorization(marker_path, contract, staging_root)

    now_tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    consumed_name = f"{CONSUMED_PREFIX}{now_tag}.json"
    consumed_path = marker_path.parent / consumed_name

    # Atomic rename prevents reuse
    try:
        os.replace(marker_path, consumed_path)
    except Exception as exc:
        raise RuntimeError(f"Atomic marker consumption failed: {exc}") from exc

    return consumed_path
