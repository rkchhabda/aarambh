"""Phase 7 official listing date evidence persistence engine.

Strictly manages filesystem layout, atomic writes, cryptographic verification,
and immutable provenance records outside Git repository.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from phase7.sources.listing_evidence_authorization import validate_staging_root

EVIDENCE_SUBDIRECTORIES = [
    "authorization",
    "raw",
    "extracted",
    "manifests",
    "audit",
    "logs",
]


def ensure_evidence_directories(staging_root: Union[Path, str], repo_root: Optional[Path] = None) -> Dict[str, Path]:
    """Validate external root and ensure all required subdirectories exist."""
    valid_staging = validate_staging_root(staging_root, repo_root=repo_root)
    dir_map: Dict[str, Path] = {}
    for sub in EVIDENCE_SUBDIRECTORIES:
        p = valid_staging / sub
        p.mkdir(parents=True, exist_ok=True)
        dir_map[sub] = p
    return dir_map


from phase7.sources.rejections import sanitize_payload


def sanitize_evidence_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize evidence dictionary, strictly stripping session credentials and authorization markers."""
    clean = sanitize_payload(data)
    if isinstance(clean, dict):
        clean_copy = dict(clean)
        clean_copy.pop("nonce", None)
        clean_copy.pop("authorization_hash", None)
        return clean_copy
    return clean


def persist_raw_source_document(
    staging_root: Union[Path, str],
    filename: str,
    content_bytes: bytes,
    source_url: str,
    mime_type: str,
    source_document_date: Optional[str] = None,
    publisher: Optional[str] = None,
    repo_root: Optional[Path] = None,
) -> Tuple[Path, str]:
    """Persist a raw downloaded official document (PDF or HTML) atomically outside Git.

    Validates:
    - Content is non-empty
    - PDF header if PDF
    - No overwrite if file exists with different checksum
    - Computes SHA-256
    """
    if not content_bytes:
        raise ValueError("Cannot persist empty source document bytes.")

    dirs = ensure_evidence_directories(staging_root, repo_root=repo_root)
    raw_dir = dirs["raw"]

    sha256 = hashlib.sha256(content_bytes).hexdigest()

    # Validate PDF magic header
    if filename.lower().endswith(".pdf") or "pdf" in mime_type.lower():
        if not content_bytes.startswith(b"%PDF-"):
            raise ValueError(f"File '{filename}' expected to be PDF but missing '%PDF-' header.")

    target_path = raw_dir / filename
    if target_path.exists():
        existing_sha = hashlib.sha256(target_path.read_bytes()).hexdigest()
        if existing_sha != sha256:
            raise FileExistsError(
                f"Raw evidence file '{target_path}' already exists with different checksum: {existing_sha} != {sha256}"
            )
        return target_path, sha256

    temp_path = target_path.with_suffix(f".tmp.{sha256[:8]}")
    temp_path.write_bytes(content_bytes)
    os.replace(temp_path, target_path)

    return target_path, sha256


def persist_extracted_evidence_record(
    staging_root: Union[Path, str],
    filename: str,
    record_dict: Dict[str, Any],
    repo_root: Optional[Path] = None,
) -> Path:
    """Persist sanitized extracted evidence record to extracted/ directory."""
    dirs = ensure_evidence_directories(staging_root, repo_root=repo_root)
    extracted_dir = dirs["extracted"]

    sanitized = sanitize_evidence_data(record_dict)

    target_path = extracted_dir / filename
    temp_path = target_path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(sanitized, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temp_path, target_path)

    return target_path


def persist_evidence_manifest(
    staging_root: Union[Path, str],
    manifest_dict: Dict[str, Any],
    repo_root: Optional[Path] = None,
) -> Tuple[Path, str]:
    """Persist finalized evidence manifest to manifests/ directory."""
    dirs = ensure_evidence_directories(staging_root, repo_root=repo_root)
    manifest_dir = dirs["manifests"]

    sanitized = sanitize_evidence_data(manifest_dict)
    raw_json = json.dumps(sanitized, indent=2, sort_keys=True)
    manifest_hash = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()

    now_utc_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest_name = f"evidence_manifest_{now_utc_str}_{manifest_hash[:8]}.json"

    target_path = manifest_dir / manifest_name
    temp_path = target_path.with_suffix(".tmp")
    temp_path.write_text(raw_json, encoding="utf-8")
    os.replace(temp_path, target_path)

    return target_path, manifest_hash


def persist_retrospective_classification_record(
    staging_root: Union[Path, str],
    symbol: str,
    classification_data: Dict[str, Any],
    repo_root: Optional[Path] = None,
) -> Path:
    """Persist retrospective classification record to audit/ directory."""
    dirs = ensure_evidence_directories(staging_root, repo_root=repo_root)
    audit_dir = dirs["audit"]

    sanitized = sanitize_evidence_data(classification_data)

    target_path = audit_dir / f"retrospective_classification_{symbol}.json"
    temp_path = target_path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(sanitized, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temp_path, target_path)

    return target_path
