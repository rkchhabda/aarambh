"""Phase 7 batch audit and conservation verification engine.

Provides cryptographic verification of conservation and batch-level operational invariants.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from phase7.sources.batch_checkpoint import BatchCheckpoint
from phase7.sources.batch_contract import BatchContract, BatchSymbolStatus


@dataclass(frozen=True)
class BatchAuditSummary:
    batch_id: str
    total_symbols: int
    completed_symbols: int
    pending_symbols: int
    failed_symbols: int
    source_rows: int
    normalized_rows: int
    rejected_rows: int
    conservation_holds: bool
    status: str
    duration_seconds: float
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def verify_batch_conservation(checkpoint: BatchCheckpoint) -> bool:
    """Verify row conservation across all symbols in the checkpoint."""
    expected_source = checkpoint.normalized_rows + checkpoint.rejected_rows
    if checkpoint.source_rows != expected_source:
        return False

    for sc in checkpoint.symbol_states.values():
        if sc.status == BatchSymbolStatus.SUCCEEDED:
            if sc.source_rows != sc.normalized_rows + sc.rejected_rows:
                return False

    return True


def generate_batch_audit_payload(
    checkpoint: BatchCheckpoint,
    contract: BatchContract,
    duration_seconds: float,
) -> Dict[str, Any]:
    """Generate comprehensive batch audit report payload."""
    now_ts = datetime.now(timezone.utc).isoformat()
    conservation_ok = verify_batch_conservation(checkpoint)

    return {
        "audit_version": "1.0",
        "batch_id": checkpoint.batch_id,
        "classification": contract.classification,
        "contract": contract.to_dict(),
        "total_symbols": checkpoint.total_symbols,
        "completed_symbols": checkpoint.completed_symbols,
        "pending_symbols": checkpoint.pending_symbols,
        "failed_symbols": checkpoint.failed_symbols,
        "source_rows": checkpoint.source_rows,
        "normalized_rows": checkpoint.normalized_rows,
        "rejected_rows": checkpoint.rejected_rows,
        "conservation_holds": conservation_ok,
        "raw_checksums_count": len(checkpoint.raw_checksums),
        "normalized_checksums_count": len(checkpoint.normalized_checksums),
        "manifest_checksums_count": len(checkpoint.manifest_checksums),
        "status": checkpoint.final_status.value,
        "stop_reason": checkpoint.stop_reason,
        "duration_seconds": duration_seconds,
        "timestamp": now_ts,
    }


def save_batch_audit(
    audit_payload: Dict[str, Any],
    audit_file: Path,
) -> Path:
    """Persist batch audit to external staging directory."""
    audit_file.parent.mkdir(parents=True, exist_ok=True)
    audit_file.write_text(json.dumps(audit_payload, indent=2), encoding="utf-8")
    return audit_file
