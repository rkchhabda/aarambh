"""Persistence layer for Phase 7 NIFTY 500 constituent snapshot pilot.

Strictly enforces:
- External directory tree outside Git (<staging_root>/raw/constituents/, normalized/constituents/, manifests/)
- Atomic file writes using temporary files and os.replace
- Prohibition of overwriting existing evidence
- Deterministic SHA-256 calculation over raw bytes
- Zero credential / session leak into raw or normalized artifacts
"""

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

from phase7.sources.contracts import (
    ConstituentRecord,
    ConstituentSnapshotManifest,
    RejectedRowRecord,
)


def ensure_directory(path: Path) -> Path:
    """Create directory if missing and return resolved Path."""
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def compute_sha256(content: Union[str, bytes]) -> str:
    """Compute deterministic SHA-256 hex digest."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def compute_file_sha256(file_path: Union[Path, str]) -> str:
    """Compute deterministic SHA-256 hex digest for a file on disk."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def save_raw_snapshot(
    raw_payload: Any,
    staging_root: Union[Path, str],
    timestamp_str: Optional[str] = None,
) -> Tuple[Path, str]:
    """Persist immutable raw JSON payload of constituent snapshot externally."""
    target_dir = ensure_directory(Path(staging_root) / "raw" / "constituents")
    ts = timestamp_str or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    content_bytes = json.dumps(raw_payload, indent=2, sort_keys=True).encode("utf-8")
    checksum = compute_sha256(content_bytes)
    prefix = checksum[:8]

    target_file = target_dir / f"NIFTY_500_snapshot_{ts}_{prefix}.json"
    if target_file.exists():
        raise FileExistsError(f"Target raw file already exists at '{target_file}'. Overwrite is prohibited.")

    temp_file = target_file.with_suffix(f".tmp.{uuid.uuid4().hex}")
    temp_file.write_bytes(content_bytes)
    os.replace(temp_file, target_file)

    return target_file, checksum


def save_normalized_snapshot(
    records: List[ConstituentRecord],
    staging_root: Union[Path, str],
    timestamp_str: Optional[str] = None,
) -> Tuple[Path, str]:
    """Persist normalized constituent records as JSONL externally."""
    target_dir = ensure_directory(Path(staging_root) / "normalized" / "constituents")
    ts = timestamp_str or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [json.dumps(asdict(r), sort_keys=True) for r in records]
    content_str = "\n".join(lines) + ("\n" if lines else "")
    content_bytes = content_str.encode("utf-8")
    checksum = compute_sha256(content_bytes)
    prefix = checksum[:8]

    target_file = target_dir / f"NIFTY_500_normalized_{ts}_{prefix}.jsonl"
    if target_file.exists():
        raise FileExistsError(f"Target normalized file already exists at '{target_file}'. Overwrite is prohibited.")

    temp_file = target_file.with_suffix(f".tmp.{uuid.uuid4().hex}")
    temp_file.write_bytes(content_bytes)
    os.replace(temp_file, target_file)

    return target_file, checksum


def save_snapshot_manifest(
    manifest: ConstituentSnapshotManifest,
    staging_root: Union[Path, str],
) -> Path:
    """Persist immutable snapshot manifest JSON externally."""
    target_dir = ensure_directory(Path(staging_root) / "manifests")
    target_file = target_dir / f"manifest_NIFTY_500_{manifest.request_id}.json"

    data = asdict(manifest)
    content_bytes = json.dumps(data, indent=2, sort_keys=True).encode("utf-8")

    temp_file = target_file.with_suffix(f".tmp.{uuid.uuid4().hex}")
    temp_file.write_bytes(content_bytes)
    os.replace(temp_file, target_file)

    return target_file


def save_rejected_rows(
    rejected_rows: List[RejectedRowRecord],
    staging_root: Union[Path, str],
    timestamp_str: Optional[str] = None,
) -> Optional[Path]:
    """Persist rejected row audit records if any exist."""
    if not rejected_rows:
        return None

    target_dir = ensure_directory(Path(staging_root) / "rejected" / "constituents")
    ts = timestamp_str or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target_file = target_dir / f"NIFTY_500_rejected_{ts}.jsonl"

    lines = [json.dumps(asdict(r), sort_keys=True) for r in rejected_rows]
    content_bytes = ("\n".join(lines) + "\n").encode("utf-8")

    temp_file = target_file.with_suffix(f".tmp.{uuid.uuid4().hex}")
    temp_file.write_bytes(content_bytes)
    os.replace(temp_file, target_file)

    return target_file
