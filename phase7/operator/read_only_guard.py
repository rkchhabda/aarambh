"""Read-only evidence guard for Phase 7 Offline Operator Application.

Milestone 4.12: Strictly prohibits any mutation, repair, fallback generation,
or state transitions on preserved Phase 7 evidence.
"""

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union


class ReadOnlyViolationError(RuntimeError):
    """Raised whenever an attempt to mutate or repair preserved evidence is detected."""
    pass


PRESERVED_DIR_NAMES: Set[str] = {
    "pilot_4_9",
    "snapshot_4_10a",
    "batch_4_10c",
    "production_readiness_4_11",
}


class ReadOnlyEvidenceGuard:
    """Enforces strict read-only immutability across preserved evidence directories."""

    def __init__(self, staging_root: Optional[Path] = None) -> None:
        self.staging_root = Path(staging_root) if staging_root else Path(r"C:\Users\r_chh\gaurvideep_phase7_staging\nse500")

    def is_preserved_path(self, target_path: Union[str, Path]) -> bool:
        """Return True if path falls within any preserved evidence domain."""
        try:
            resolved = Path(target_path).resolve()
            parts = resolved.parts
            return any(p in PRESERVED_DIR_NAMES for p in parts)
        except Exception:
            return False

    def assert_immutable(self, target_path: Union[str, Path], operation: str = "MUTATION") -> None:
        """Raise ReadOnlyViolationError if target_path is within preserved evidence."""
        if self.is_preserved_path(target_path):
            raise ReadOnlyViolationError(
                f"READ_ONLY_VIOLATION: Operation '{operation}' strictly prohibited on preserved evidence: {target_path}"
            )

    def refuse_manifest_repair(self, manifest_path: Union[str, Path]) -> None:
        """Strictly prohibit automatic repair of corrupt or missing manifests."""
        self.assert_immutable(manifest_path, "MANIFEST_REPAIR")
        raise ReadOnlyViolationError(
            f"READ_ONLY_VIOLATION: Manifest repair strictly prohibited: {manifest_path}. Governed fail-closed status must be retained."
        )

    def refuse_checkpoint_repair(self, checkpoint_path: Union[str, Path]) -> None:
        """Strictly prohibit automatic repair of checkpoints."""
        self.assert_immutable(checkpoint_path, "CHECKPOINT_REPAIR")
        raise ReadOnlyViolationError(
            f"READ_ONLY_VIOLATION: Checkpoint repair strictly prohibited: {checkpoint_path}. Manual audit required."
        )

    def refuse_marker_restoration(self, marker_path: Union[str, Path]) -> None:
        """Strictly prohibit restoration of consumed authorization markers."""
        self.assert_immutable(marker_path, "MARKER_RESTORATION")
        raise ReadOnlyViolationError(
            f"READ_ONLY_VIOLATION: Restoration of consumed authorization marker prohibited: {marker_path}."
        )

    def refuse_marker_consumption(self, marker_path: Union[str, Path]) -> None:
        """Strictly prohibit consuming authorization markers inside operator app."""
        self.assert_immutable(marker_path, "MARKER_CONSUMPTION")
        raise ReadOnlyViolationError(
            f"READ_ONLY_VIOLATION: Marker consumption prohibited inside read-only operator application: {marker_path}."
        )

    def refuse_automatic_resume(self, batch_id: str) -> None:
        """Strictly prohibit automatic resume of halted historical batch."""
        raise ReadOnlyViolationError(
            f"READ_ONLY_VIOLATION: Automatic batch resume prohibited for '{batch_id}'. External acquisition is deferred by Owner."
        )

    def refuse_fallback_generation(self, symbol: str) -> None:
        """Strictly prohibit generating fallback synthetic data in place of missing real evidence."""
        raise ReadOnlyViolationError(
            f"READ_ONLY_VIOLATION: Fallback data generation strictly prohibited for symbol '{symbol}'."
        )

    @staticmethod
    def inspect_file_health(file_path: Union[str, Path], expected_sha256: Optional[str] = None) -> Dict[str, Any]:
        """Inspect evidence file health without modifying it."""
        p = Path(file_path)
        if not p.exists():
            return {
                "path": str(p),
                "status": "EVIDENCE_MISSING",
                "valid": False,
                "size_bytes": 0,
                "actual_sha256": None,
                "expected_sha256": expected_sha256,
            }

        try:
            data = p.read_bytes()
            size = len(data)
            if size == 0:
                return {
                    "path": str(p),
                    "status": "EVIDENCE_EMPTY",
                    "valid": False,
                    "size_bytes": 0,
                    "actual_sha256": hashlib.sha256(b"").hexdigest(),
                    "expected_sha256": expected_sha256,
                }

            actual_sha = hashlib.sha256(data).hexdigest()
            if expected_sha256 and actual_sha.lower() != expected_sha256.lower():
                return {
                    "path": str(p),
                    "status": "CHECKSUM_MISMATCH_CORRUPT",
                    "valid": False,
                    "size_bytes": size,
                    "actual_sha256": actual_sha,
                    "expected_sha256": expected_sha256,
                }

            return {
                "path": str(p),
                "status": "PRESERVED_VALID",
                "valid": True,
                "size_bytes": size,
                "actual_sha256": actual_sha,
                "expected_sha256": expected_sha256,
            }
        except Exception as e:
            return {
                "path": str(p),
                "status": f"READ_ERROR_{type(e).__name__}",
                "valid": False,
                "size_bytes": 0,
                "actual_sha256": None,
                "expected_sha256": expected_sha256,
            }
