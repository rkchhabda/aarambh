"""Fail-closed crash recovery inspection and resume planning engine for Phase 7.

Strictly enforces:
- Explicit new authorization required for every resume run
- Refusal to reuse or replay consumed markers
- Deep integrity validation of previously completed evidence
- Prevention of duplicate downloads or evidence overwrites
- Immediate fail-closed halt if previously completed evidence is corrupted or altered
- Rejection of resume if batch contract, selection, or symbol ordering differs
"""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from phase7.operations.atomic_io import (
    AtomicIOError,
    validate_safe_staging_path,
)
from phase7.operations.integrity import (
    validate_manifest_integrity,
    validate_batch_contract_match,
    verify_sha256,
)


class RecoveryError(AtomicIOError):
    """Base exception for crash recovery and resume violations."""
    pass


class ResumeAuthorizationError(RecoveryError):
    """Raised when resume authorization marker is missing, consumed, or invalid."""
    pass


class CorruptedPriorEvidenceError(RecoveryError):
    """Raised when previously completed evidence fails verification upon resume."""
    pass


class ResumeContractMismatchError(RecoveryError):
    """Raised when resume parameters differ from original halted batch contract."""
    pass


@dataclass(frozen=True)
class ResumePlan:
    """Deterministic plan for resuming a halted batch."""
    can_resume: bool
    halted_run_id: str
    completed_symbols: Tuple[str, ...]
    remaining_symbols: Tuple[str, ...]
    corrupted_symbols: Tuple[str, ...]
    reasons: Tuple[str, ...]
    new_marker_id: Optional[str] = None


def inspect_run_state(
    run_dir: Union[Path, str],
    repo_root: Optional[Union[Path, str]] = None,
) -> Dict[str, Any]:
    """Inspect the filesystem state of a run directory without modifying any files."""
    r_dir = validate_safe_staging_path(run_dir, repo_root=repo_root)
    if not r_dir.exists():
        return {
            "exists": False,
            "manifests": {},
            "checkpoint": None,
            "has_lock": False,
        }

    checkpoint_file = r_dir / "checkpoint.json"
    checkpoint_data = None
    if checkpoint_file.exists():
        try:
            checkpoint_data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
        except Exception:
            checkpoint_data = {"corrupted": True}

    manifests = {}
    manifests_dir = r_dir / "manifests"
    if manifests_dir.exists():
        for mf in manifests_dir.glob("*.json"):
            try:
                manifests[mf.stem] = json.loads(mf.read_text(encoding="utf-8"))
            except Exception:
                manifests[mf.stem] = {"corrupted": True}

    return {
        "exists": True,
        "run_dir": str(r_dir),
        "manifests": manifests,
        "checkpoint": checkpoint_data,
        "has_lock": (r_dir / ".process_lock").exists(),
    }


def validate_resume_prerequisites(
    run_dir: Union[Path, str],
    contract_path: Union[Path, str],
    new_marker_path: Optional[Union[Path, str]],
    expected_symbols: List[str],
    repo_root: Optional[Union[Path, str]] = None,
) -> ResumePlan:
    """Validate all fail-closed criteria for resuming a batch."""
    reasons: List[str] = []
    corrupted: List[str] = []
    completed: List[str] = []
    remaining: List[str] = []

    r_dir = validate_safe_staging_path(run_dir, repo_root=repo_root)
    c_path = Path(contract_path)

    # 1. New authorization marker is strictly mandatory
    if not new_marker_path or not Path(new_marker_path).exists():
        reasons.append("Resume requires an explicit, active new authorization marker.")
        return ResumePlan(
            can_resume=False,
            halted_run_id=r_dir.name,
            completed_symbols=(),
            remaining_symbols=tuple(expected_symbols),
            corrupted_symbols=(),
            reasons=tuple(reasons),
        )

    # Validate marker is not consumed
    marker_p = Path(new_marker_path)
    try:
        marker_data = json.loads(marker_p.read_text(encoding="utf-8"))
        if marker_data.get("status") == "CONSUMED":
            reasons.append("Resume rejected: marker is already CONSUMED. Replay prohibited.")
            return ResumePlan(
                can_resume=False,
                halted_run_id=r_dir.name,
                completed_symbols=(),
                remaining_symbols=tuple(expected_symbols),
                corrupted_symbols=(),
                reasons=tuple(reasons),
            )
        marker_id = marker_data.get("marker_id")
    except Exception as exc:
        reasons.append(f"Resume rejected: failed to read marker: {exc}")
        return ResumePlan(
            can_resume=False,
            halted_run_id=r_dir.name,
            completed_symbols=(),
            remaining_symbols=tuple(expected_symbols),
            corrupted_symbols=(),
            reasons=tuple(reasons),
        )

    # 2. Contract verification
    if not c_path.exists():
        reasons.append(f"Contract file missing: '{c_path}'")
        return ResumePlan(
            can_resume=False,
            halted_run_id=r_dir.name,
            completed_symbols=(),
            remaining_symbols=tuple(expected_symbols),
            corrupted_symbols=(),
            reasons=tuple(reasons),
        )

    try:
        contract = json.loads(c_path.read_text(encoding="utf-8"))
        run_contract_file = r_dir / "batch_contract.json"
        if run_contract_file.exists():
            run_contract = json.loads(run_contract_file.read_text(encoding="utf-8"))
            mismatches = validate_batch_contract_match(contract, run_contract)
            if mismatches:
                reasons.extend(mismatches)
                return ResumePlan(
                    can_resume=False,
                    halted_run_id=r_dir.name,
                    completed_symbols=(),
                    remaining_symbols=tuple(expected_symbols),
                    corrupted_symbols=(),
                    reasons=tuple(reasons),
                )
    except Exception as exc:
        reasons.append(f"Contract read or match error: {exc}")
        return ResumePlan(
            can_resume=False,
            halted_run_id=r_dir.name,
            completed_symbols=(),
            remaining_symbols=tuple(expected_symbols),
            corrupted_symbols=(),
            reasons=tuple(reasons),
        )

    # 3. Check existing evidence and manifests
    manifests_dir = r_dir / "manifests"
    for sym in expected_symbols:
        mf_path = manifests_dir / f"manifest_{sym}.json"
        if mf_path.exists():
            try:
                m_data = json.loads(mf_path.read_text(encoding="utf-8"))
                errors = validate_manifest_integrity(m_data, base_staging_dir=r_dir)
                if errors:
                    corrupted.append(sym)
                    reasons.extend([f"Symbol '{sym}': {e}" for e in errors])
                elif m_data.get("status") == "SUCCEEDED":
                    completed.append(sym)
                else:
                    # Incomplete or non-succeeded
                    remaining.append(sym)
            except Exception as exc:
                corrupted.append(sym)
                reasons.append(f"Failed to read manifest for '{sym}': {exc}")
        else:
            remaining.append(sym)

    # If any completed evidence is corrupted, resume CANNOT proceed (fail-closed)
    if corrupted:
        reasons.append(f"Found {len(corrupted)} corrupted symbols in run directory. Halting.")
        return ResumePlan(
            can_resume=False,
            halted_run_id=r_dir.name,
            completed_symbols=tuple(completed),
            remaining_symbols=tuple(remaining),
            corrupted_symbols=tuple(corrupted),
            reasons=tuple(reasons),
            new_marker_id=marker_id,
        )

    return ResumePlan(
        can_resume=True,
        halted_run_id=r_dir.name,
        completed_symbols=tuple(completed),
        remaining_symbols=tuple(remaining),
        corrupted_symbols=(),
        reasons=(),
        new_marker_id=marker_id,
    )
