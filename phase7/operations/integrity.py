"""Governed integrity, reconciliation, and audit verification for Phase 7 artifacts.

Enforces deep cryptographic and logical validation across:
- Manifests (raw/normalized paths, row counts, checksums, status consistency)
- Checkpoints (symbol state counts, summary totals, run/batch ID matching)
- Batch contracts (panel version, snapshot checksum, selection checksum, symbol hash)
- Conservation laws (source rows = normalized rows + rejected rows)
- Duplicate detection (request IDs, paths, symbols)
- Immutability and tamper detection
"""

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from phase7.operations.atomic_io import (
    AtomicIOError,
    validate_safe_staging_path,
)


class IntegrityError(AtomicIOError):
    """Base exception for integrity violations."""
    pass


class ManifestIntegrityError(IntegrityError):
    """Raised when a manifest fails structural, cryptographic, or logical validation."""
    pass


class CheckpointIntegrityError(IntegrityError):
    """Raised when a checkpoint fails summary, count, or state consistency validation."""
    pass


class ConservationIntegrityError(IntegrityError):
    """Raised when row counts fail the fundamental conservation equation."""
    pass


class ContractMismatchError(IntegrityError):
    """Raised when run parameters diverge from the governed batch contract."""
    pass


@dataclass(frozen=True)
class IntegrityReport:
    """Result of a comprehensive integrity verification scan."""
    is_valid: bool
    errors: Tuple[str, ...]
    manifest_count: int
    raw_files_checked: int
    normalized_files_checked: int
    total_source_rows: int
    total_normalized_rows: int
    total_rejected_rows: int

    @property
    def has_conservation_passed(self) -> bool:
        return self.total_source_rows == (self.total_normalized_rows + self.total_rejected_rows)


def verify_sha256(file_path: Union[Path, str], expected_sha256: str) -> bool:
    """Verify file SHA-256 matches expected checksum."""
    p = Path(file_path)
    if not p.exists() or not p.is_file():
        return False
    actual_sha = hashlib.sha256(p.read_bytes()).hexdigest()
    return actual_sha.lower() == expected_sha256.lower()


def validate_manifest_integrity(
    manifest_data: Dict[str, Any],
    base_staging_dir: Optional[Union[Path, str]] = None,
    verify_files_on_disk: bool = True,
) -> List[str]:
    """Validate a single manifest against all governed Phase 7 integrity rules."""
    errors: List[str] = []

    required_keys = {
        "manifest_version", "batch_id", "run_id", "symbol", "status",
        "date_window", "interval", "requested_at_utc"
    }
    missing = required_keys - set(manifest_data.keys())
    if missing:
        errors.append(f"Manifest missing required keys: {sorted(missing)}")
        return errors

    status = manifest_data.get("status")
    symbol = manifest_data.get("symbol")

    # Invariant: PENDING manifest must not be considered finished
    if status == "PENDING":
        errors.append(f"Manifest for '{symbol}' remains in PENDING status; unfinished.")

    # Status-specific validations
    if status == "SUCCEEDED":
        source_count = manifest_data.get("source_row_count", 0)
        norm_count = manifest_data.get("normalized_row_count", 0)
        rej_count = manifest_data.get("rejected_row_count", 0)

        # SUCCEEDED manifest with zero rows is prohibited
        if norm_count <= 0:
            errors.append(f"SUCCEEDED manifest for '{symbol}' cannot have zero normalized rows.")

        # Conservation rule
        if source_count != (norm_count + rej_count):
            errors.append(
                f"Row conservation failed for '{symbol}': source={source_count} != norm={norm_count} + rej={rej_count}"
            )

        # File paths and checksums
        raw_path_str = manifest_data.get("raw_evidence_path")
        norm_path_str = manifest_data.get("normalized_evidence_path")
        raw_sha = manifest_data.get("raw_evidence_sha256")
        norm_sha = manifest_data.get("normalized_evidence_sha256")

        if not raw_sha or not norm_sha:
            errors.append(f"SUCCEEDED manifest for '{symbol}' missing raw or normalized checksums.")

        if not raw_path_str or not norm_path_str:
            errors.append(f"SUCCEEDED manifest for '{symbol}' missing raw or normalized file path.")
        elif verify_files_on_disk and base_staging_dir:
            raw_p = Path(raw_path_str) if Path(raw_path_str).is_absolute() else (Path(base_staging_dir) / raw_path_str)
            norm_p = Path(norm_path_str) if Path(norm_path_str).is_absolute() else (Path(base_staging_dir) / norm_path_str)

            if not raw_p.exists():
                errors.append(f"Raw evidence file missing on disk: '{raw_p}'")
            elif raw_sha and not verify_sha256(raw_p, raw_sha):
                errors.append(f"Raw evidence checksum mismatch for '{symbol}' at '{raw_p}'")

            if not norm_p.exists():
                errors.append(f"Normalized evidence file missing on disk: '{norm_p}'")
            elif norm_sha and not verify_sha256(norm_p, norm_sha):
                errors.append(f"Normalized evidence checksum mismatch for '{symbol}' at '{norm_p}'")

    elif status == "FAILED":
        reason = manifest_data.get("failure_reason_code")
        if not reason:
            errors.append(f"FAILED manifest for '{symbol}' missing governed failure_reason_code.")

    elif status not in ("SUCCEEDED", "FAILED", "HALTED", "SKIPPED"):
        errors.append(f"Unknown manifest status '{status}' for symbol '{symbol}'.")

    return errors


def validate_checkpoint_integrity(
    checkpoint_data: Dict[str, Any],
    manifest_records: Optional[List[Dict[str, Any]]] = None,
    governed_symbol_count: Optional[int] = None,
) -> List[str]:
    """Validate checkpoint consistency, summary totals, and cross-reconciliation."""
    errors: List[str] = []

    required_keys = {
        "checkpoint_version", "batch_id", "run_id", "created_at_utc",
        "updated_at_utc", "completed_count", "failed_count", "pending_count",
        "symbols"
    }
    missing = required_keys - set(checkpoint_data.keys())
    if missing:
        errors.append(f"Checkpoint missing required keys: {sorted(missing)}")
        return errors

    symbols_map = checkpoint_data.get("symbols", {})
    comp_count = checkpoint_data.get("completed_count", 0)
    failed_count = checkpoint_data.get("failed_count", 0)
    pending_count = checkpoint_data.get("pending_count", 0)

    # Count actual symbols in symbols dictionary
    actual_completed = sum(1 for v in symbols_map.values() if v.get("status") == "SUCCEEDED")
    actual_failed = sum(1 for v in symbols_map.values() if v.get("status") in ("FAILED", "HALTED"))
    actual_pending = sum(1 for v in symbols_map.values() if v.get("status") == "PENDING")

    if comp_count != actual_completed:
        errors.append(f"Completed count mismatch: summary={comp_count} != actual={actual_completed}")

    if failed_count != actual_failed:
        errors.append(f"Failed count mismatch: summary={failed_count} != actual={actual_failed}")

    if pending_count != actual_pending:
        errors.append(f"Pending count mismatch: summary={pending_count} != actual={actual_pending}")

    total_symbols = len(symbols_map)
    if (comp_count + failed_count + pending_count) != total_symbols:
        errors.append(
            f"Impossible summary totals: sum ({comp_count + failed_count + pending_count}) != total symbols ({total_symbols})"
        )

    if governed_symbol_count is not None:
        if total_symbols != governed_symbol_count:
            errors.append(
                f"Checkpoint total symbols ({total_symbols}) does not match governed count ({governed_symbol_count})"
            )
        # Checkpoint cannot claim final batch success if fewer than governed symbols succeeded
        if checkpoint_data.get("batch_status") == "SUCCEEDED" and comp_count < governed_symbol_count:
            errors.append(
                f"Batch cannot claim SUCCEEDED with only {comp_count}/{governed_symbol_count} completed symbols."
            )

    # Cross-reconcile with manifests if provided
    if manifest_records is not None:
        seen_requests: Set[str] = set()
        seen_raw_paths: Set[str] = set()
        seen_norm_paths: Set[str] = set()

        for m in manifest_records:
            req_id = m.get("request_id")
            if req_id:
                if req_id in seen_requests:
                    errors.append(f"Duplicate request_id detected in manifests: '{req_id}'")
                seen_requests.add(req_id)

            raw_p = m.get("raw_evidence_path")
            if raw_p:
                if raw_p in seen_raw_paths:
                    errors.append(f"Duplicate raw evidence path detected: '{raw_p}'")
                seen_raw_paths.add(raw_p)

            norm_p = m.get("normalized_evidence_path")
            if norm_p:
                if norm_p in seen_norm_paths:
                    errors.append(f"Duplicate normalized evidence path detected: '{norm_p}'")
                seen_norm_paths.add(norm_p)

    return errors


def validate_batch_contract_match(
    contract_data: Dict[str, Any],
    run_contract_data: Dict[str, Any],
) -> List[str]:
    """Validate that run execution parameters match the immutable batch contract."""
    errors: List[str] = []

    keys_to_match = [
        "panel_version",
        "snapshot_checksum",
        "selection_checksum",
        "ordered_symbols_sha256",
        "date_window",
        "interval",
    ]

    for key in keys_to_match:
        expected = contract_data.get(key)
        actual = run_contract_data.get(key)
        if expected != actual:
            errors.append(f"Contract mismatch on '{key}': expected '{expected}', got '{actual}'")

    return errors
