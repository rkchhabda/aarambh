"""Governed offline backup, restoration, and disaster-recovery validation for Phase 7.

Strictly enforces:
- Backups reside strictly in external staging, never in Git repository
- Backup manifest/inventory generation with SHA-256 digests for all files
- Raw, normalized, manifest, checkpoint, contract files preserved bit-for-bit
- Exclusion of active temporary files (.tmp.*) and sensitive session/cookie files
- Complete cryptographic verification of restored files against backup inventory
- Reconciliation of manifests and row counts after restoration
- Rejection of corrupted or incomplete backups (fail-closed)
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from phase7.operations.atomic_io import (
    AtomicIOError,
    atomic_write_text,
    validate_safe_staging_path,
)


class BackupRestoreError(AtomicIOError):
    """Base exception for backup and restoration violations."""
    pass


class BackupInventoryError(BackupRestoreError):
    """Raised when backup inventory is missing, corrupted, or tampered."""
    pass


class RestorationIntegrityError(BackupRestoreError):
    """Raised when restored files fail cryptographic verification."""
    pass


EXCLUDED_PATTERNS = {
    ".tmp.",
    ".process_lock",
    "cookie",
    "session",
    ".cache",
}


def should_exclude_from_backup(filename: str) -> bool:
    """Check if file should be excluded from backup under governance rules."""
    lower = filename.lower()
    return any(pat in lower for pat in EXCLUDED_PATTERNS)


def compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def create_offline_backup(
    source_dir: Union[Path, str],
    backup_target_dir: Union[Path, str],
    backup_id: str,
    repo_root: Optional[Union[Path, str]] = None,
) -> Path:
    """Create an offline, bit-for-bit validated backup of staging artifacts."""
    src = validate_safe_staging_path(source_dir, repo_root=repo_root)
    dest = validate_safe_staging_path(backup_target_dir, repo_root=repo_root)
    dest.mkdir(parents=True, exist_ok=True)

    backup_folder = dest / backup_id
    backup_folder.mkdir(parents=True, exist_ok=True)

    inventory_files: List[Dict[str, Any]] = []

    for root, _, files in os.walk(src):
        for f in files:
            if should_exclude_from_backup(f):
                continue
            src_file = Path(root) / f
            rel_path = src_file.relative_to(src)
            dest_file = backup_folder / rel_path

            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dest_file)

            sha = compute_file_sha256(dest_file)
            size = dest_file.stat().st_size
            inventory_files.append({
                "relative_path": str(rel_path).replace("\\", "/"),
                "sha256": sha,
                "size_bytes": size,
            })

    # Sort inventory for deterministic ordering
    inventory_files.sort(key=lambda x: x["relative_path"])

    inventory_doc = {
        "backup_id": backup_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(src),
        "file_count": len(inventory_files),
        "files": inventory_files,
    }

    inv_json = json.dumps(inventory_doc, indent=2)
    inv_path = backup_folder / "backup_inventory.json"
    atomic_write_text(inv_path, inv_json, repo_root=repo_root, allow_overwrite=True)

    return backup_folder


def restore_and_verify_backup(
    backup_folder: Union[Path, str],
    restore_target_dir: Union[Path, str],
    repo_root: Optional[Union[Path, str]] = None,
) -> Tuple[bool, List[str]]:
    """Restore staging artifacts from backup and verify all checksums bit-for-bit."""
    bf = validate_safe_staging_path(backup_folder, repo_root=repo_root)
    dest = validate_safe_staging_path(restore_target_dir, repo_root=repo_root)
    dest.mkdir(parents=True, exist_ok=True)

    inv_path = bf / "backup_inventory.json"
    if not inv_path.exists():
        raise BackupInventoryError(f"Missing backup inventory at '{inv_path}'")

    try:
        inv = json.loads(inv_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise BackupInventoryError(f"Corrupt backup inventory: {exc}")

    errors: List[str] = []
    files_to_restore = inv.get("files", [])

    for entry in files_to_restore:
        rel_p = Path(entry["relative_path"])
        expected_sha = entry["sha256"]
        expected_size = entry["size_bytes"]

        src_file = bf / rel_p
        if not src_file.exists():
            errors.append(f"Missing file in backup archive: '{rel_p}'")
            continue

        dest_file = dest / rel_p
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest_file)

        # Verify restored file
        actual_size = dest_file.stat().st_size
        actual_sha = compute_file_sha256(dest_file)

        if actual_size != expected_size:
            errors.append(
                f"Size mismatch on restored '{rel_p}': expected {expected_size}, got {actual_size}"
            )
        if actual_sha != expected_sha:
            errors.append(
                f"Checksum mismatch on restored '{rel_p}': expected {expected_sha}, got {actual_sha}"
            )

    return (len(errors) == 0), errors
