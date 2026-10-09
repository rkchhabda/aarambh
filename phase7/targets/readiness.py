"""Real-data readiness gate and blocker enforcement for Phase 7 target engine.

Governs:
1. Enforcement of BLK-01 (Nifty 500 PIT Membership) and BLK-02 (OHLCV Traded Value) as mandatory blockers.
2. Enforcement of BLK-04 (PIT Sector Classification) as a mandatory blocker for sector-relative targets.
3. Preservation of multiple simultaneous blocker statuses.
4. Fail-closed rejection of missing dataset versions.
5. Strict prohibition against treating empty real-data generated output as success.
6. Clean separation: synthetic testing readiness does not imply real-data readiness.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

from phase7.data.contracts import compute_row_hash


class TargetReadinessStatus(str, Enum):
    """Lifecycle and gate readiness status for target engine evaluation."""
    READY_FOR_SYNTHETIC_TESTING = "READY_FOR_SYNTHETIC_TESTING"
    TARGET_ENGINE_READY_REAL_DATA_BLOCKED = "TARGET_ENGINE_READY_REAL_DATA_BLOCKED"
    BLOCKED_BLK_01_MEMBERSHIP = "BLOCKED_BLK_01_MEMBERSHIP"
    BLOCKED_BLK_02_OHLCV_LIQUIDITY = "BLOCKED_BLK_02_OHLCV_LIQUIDITY"
    BLOCKED_BLK_04_SECTOR_HISTORY = "BLOCKED_BLK_04_SECTOR_HISTORY"
    DATA_VALIDATION_FAILURE = "DATA_VALIDATION_FAILURE"


@dataclass(frozen=True)
class TargetReadinessResult:
    """Immutable audit record representing the real-data gate readiness state."""
    overall_status: TargetReadinessStatus
    is_synthetic_ready: bool
    is_real_data_blocked: bool
    active_blockers: Tuple[str, ...]
    blocker_statuses: Tuple[TargetReadinessStatus, ...]
    target_name: str
    dataset_version: Optional[str]
    evaluated_records_count: int
    audit_notes: Tuple[str, ...]
    readiness_hash: str = ""

    def __post_init__(self) -> None:
        clean_dict = {k: v for k, v in self.__dict__.items() if k != "readiness_hash"}
        computed = compute_row_hash(clean_dict)
        if self.readiness_hash and self.readiness_hash != computed:
            raise ValueError(f"Supplied readiness_hash '{self.readiness_hash}' does not match computed '{computed}'")
        if not self.readiness_hash:
            object.__setattr__(self, "readiness_hash", computed)


def evaluate_target_readiness(
    target_name: str,
    dataset_version: Optional[str],
    blk_01_resolved: bool = False,
    blk_02_resolved: bool = False,
    blk_04_resolved: bool = False,
    is_real_data_evaluation: bool = False,
    generated_targets_count: Optional[int] = None,
) -> TargetReadinessResult:
    """Evaluate target engine readiness against governance gates and active real-data blockers.

    Args:
        target_name: Target specification name (e.g. target_20d_sector_relative).
        dataset_version: Underlying dataset version identifier (required).
        blk_01_resolved: Whether BLK-01 (PIT constituent membership) has been resolved with genuine data.
        blk_02_resolved: Whether BLK-02 (OHLCV & daily traded value) has been resolved with genuine data.
        blk_04_resolved: Whether BLK-04 (PIT sector history) has been resolved with genuine data.
        is_real_data_evaluation: True if evaluating real historical target pipeline.
        generated_targets_count: Count of generated target records produced (if evaluated).

    Returns:
        TargetReadinessResult capturing all active blockers and overall gate status.
    """
    notes: List[str] = []
    blockers: List[str] = []
    b_statuses: List[TargetReadinessStatus] = []

    # 1. Dataset version validation (fails closed)
    if not dataset_version or not dataset_version.strip():
        notes.append("Dataset version is missing or empty; fails closed.")
        return TargetReadinessResult(
            overall_status=TargetReadinessStatus.DATA_VALIDATION_FAILURE,
            is_synthetic_ready=False,
            is_real_data_blocked=True,
            active_blockers=tuple(blockers),
            blocker_statuses=tuple(b_statuses),
            target_name=target_name,
            dataset_version=dataset_version,
            evaluated_records_count=generated_targets_count or 0,
            audit_notes=tuple(notes),
        )

    # 2. Real-data output check: empty generated output CANNOT be reported as success
    if is_real_data_evaluation and generated_targets_count is not None and generated_targets_count <= 0:
        notes.append("Empty generated target output in real-data evaluation cannot be reported as success.")
        return TargetReadinessResult(
            overall_status=TargetReadinessStatus.DATA_VALIDATION_FAILURE,
            is_synthetic_ready=False,
            is_real_data_blocked=True,
            active_blockers=("EMPTY_REAL_DATA_OUTPUT",),
            blocker_statuses=(TargetReadinessStatus.DATA_VALIDATION_FAILURE,),
            target_name=target_name,
            dataset_version=dataset_version,
            evaluated_records_count=0,
            audit_notes=tuple(notes),
        )

    # 3. Check individual blockers
    if not blk_01_resolved:
        blockers.append("BLK-01")
        b_statuses.append(TargetReadinessStatus.BLOCKED_BLK_01_MEMBERSHIP)
        notes.append("BLK-01: Historical Nifty 500 point-in-time constituent membership is unresolved.")

    if not blk_02_resolved:
        blockers.append("BLK-02")
        b_statuses.append(TargetReadinessStatus.BLOCKED_BLK_02_OHLCV_LIQUIDITY)
        notes.append("BLK-02: Complete OHLCV and traded value history is unresolved.")

    # BLK-04 blocks sector-relative targets specifically
    is_sector_target = "sector" in target_name.lower()
    if not blk_04_resolved and is_sector_target:
        blockers.append("BLK-04")
        b_statuses.append(TargetReadinessStatus.BLOCKED_BLK_04_SECTOR_HISTORY)
        notes.append("BLK-04: Historical point-in-time sector classification history is unresolved.")

    # 4. Resolve overall status
    if blockers:
        overall = TargetReadinessStatus.TARGET_ENGINE_READY_REAL_DATA_BLOCKED
        real_blocked = True
        notes.append("Target engine interfaces are verified; real data execution is blocked.")
    else:
        overall = TargetReadinessStatus.READY_FOR_SYNTHETIC_TESTING
        real_blocked = False
        notes.append("All prerequisite data sources resolved.")

    return TargetReadinessResult(
        overall_status=overall,
        is_synthetic_ready=True,
        is_real_data_blocked=real_blocked,
        active_blockers=tuple(blockers),
        blocker_statuses=tuple(b_statuses),
        target_name=target_name,
        dataset_version=dataset_version,
        evaluated_records_count=generated_targets_count or 0,
        audit_notes=tuple(notes),
    )
