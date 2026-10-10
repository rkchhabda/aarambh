"""Phase 7 batch checkpointing and resume validation engine.

Tracks symbol-level execution states and strictly enforces resume integrity invariants.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from phase7.sources.batch_contract import (
    BatchContract,
    BatchStatus,
    BatchSymbolStatus,
)


class InvalidResumeCheckpointError(ValueError):
    """Raised when an existing batch checkpoint fails strict resume validation."""
    pass


@dataclass
class SymbolCheckpoint:
    symbol: str
    status: BatchSymbolStatus
    request_id: Optional[str] = None
    raw_file_path: Optional[str] = None
    normalized_file_path: Optional[str] = None
    manifest_file_path: Optional[str] = None
    raw_checksum: Optional[str] = None
    normalized_checksum: Optional[str] = None
    manifest_checksum: Optional[str] = None
    source_rows: int = 0
    normalized_rows: int = 0
    rejected_rows: int = 0
    error_message: Optional[str] = None
    last_updated: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class BatchCheckpoint:
    batch_id: str
    total_symbols: int
    completed_symbols: int
    pending_symbols: int
    failed_symbols: int
    source_rows: int
    normalized_rows: int
    rejected_rows: int
    raw_checksums: Dict[str, str]
    normalized_checksums: Dict[str, str]
    manifest_checksums: Dict[str, str]
    symbol_states: Dict[str, SymbolCheckpoint]
    start_timestamp: str
    last_checkpoint_timestamp: str
    stop_reason: Optional[str]
    final_status: BatchStatus

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "total_symbols": self.total_symbols,
            "completed_symbols": self.completed_symbols,
            "pending_symbols": self.pending_symbols,
            "failed_symbols": self.failed_symbols,
            "source_rows": self.source_rows,
            "normalized_rows": self.normalized_rows,
            "rejected_rows": self.rejected_rows,
            "raw_checksums": self.raw_checksums,
            "normalized_checksums": self.normalized_checksums,
            "manifest_checksums": self.manifest_checksums,
            "symbol_states": {
                sym: sc.to_dict() for sym, sc in self.symbol_states.items()
            },
            "start_timestamp": self.start_timestamp,
            "last_checkpoint_timestamp": self.last_checkpoint_timestamp,
            "stop_reason": self.stop_reason,
            "final_status": self.final_status.value,
        }


def create_initial_batch_checkpoint(
    batch_id: str,
    ordered_symbols: List[str],
) -> BatchCheckpoint:
    """Initialize a new clean batch checkpoint."""
    now_ts = datetime.now(timezone.utc).isoformat()
    symbol_states = {
        sym: SymbolCheckpoint(
            symbol=sym,
            status=BatchSymbolStatus.NOT_STARTED,
            last_updated=now_ts,
        )
        for sym in ordered_symbols
    }

    return BatchCheckpoint(
        batch_id=batch_id,
        total_symbols=len(ordered_symbols),
        completed_symbols=0,
        pending_symbols=len(ordered_symbols),
        failed_symbols=0,
        source_rows=0,
        normalized_rows=0,
        rejected_rows=0,
        raw_checksums={},
        normalized_checksums={},
        manifest_checksums={},
        symbol_states=symbol_states,
        start_timestamp=now_ts,
        last_checkpoint_timestamp=now_ts,
        stop_reason=None,
        final_status=BatchStatus.INITIALIZED,
    )


def save_checkpoint(
    checkpoint: BatchCheckpoint,
    checkpoint_file: Path,
) -> None:
    """Persist batch checkpoint atomically."""
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
    temp_file = checkpoint_file.with_suffix(".tmp")
    now_ts = datetime.now(timezone.utc).isoformat()
    checkpoint.last_checkpoint_timestamp = now_ts

    payload = json.dumps(checkpoint.to_dict(), indent=2)
    temp_file.write_text(payload, encoding="utf-8")
    temp_file.replace(checkpoint_file)


def load_checkpoint(checkpoint_file: Path) -> BatchCheckpoint:
    """Load existing batch checkpoint from disk."""
    if not checkpoint_file.exists():
        raise FileNotFoundError(f"Checkpoint file not found: {checkpoint_file}")

    data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
    symbol_states = {}
    for sym, s_data in data["symbol_states"].items():
        symbol_states[sym] = SymbolCheckpoint(
            symbol=s_data["symbol"],
            status=BatchSymbolStatus(s_data["status"]),
            request_id=s_data.get("request_id"),
            raw_file_path=s_data.get("raw_file_path"),
            normalized_file_path=s_data.get("normalized_file_path"),
            manifest_file_path=s_data.get("manifest_file_path"),
            raw_checksum=s_data.get("raw_checksum"),
            normalized_checksum=s_data.get("normalized_checksum"),
            manifest_checksum=s_data.get("manifest_checksum"),
            source_rows=s_data.get("source_rows", 0),
            normalized_rows=s_data.get("normalized_rows", 0),
            rejected_rows=s_data.get("rejected_rows", 0),
            error_message=s_data.get("error_message"),
            last_updated=s_data.get("last_updated", ""),
        )

    return BatchCheckpoint(
        batch_id=data["batch_id"],
        total_symbols=data["total_symbols"],
        completed_symbols=data["completed_symbols"],
        pending_symbols=data["pending_symbols"],
        failed_symbols=data["failed_symbols"],
        source_rows=data["source_rows"],
        normalized_rows=data["normalized_rows"],
        rejected_rows=data["rejected_rows"],
        raw_checksums=data["raw_checksums"],
        normalized_checksums=data["normalized_checksums"],
        manifest_checksums=data["manifest_checksums"],
        symbol_states=symbol_states,
        start_timestamp=data["start_timestamp"],
        last_checkpoint_timestamp=data["last_checkpoint_timestamp"],
        stop_reason=data.get("stop_reason"),
        final_status=BatchStatus(data["final_status"]),
    )


def validate_resume_checkpoint(
    checkpoint: BatchCheckpoint,
    contract: BatchContract,
    governed_symbols: List[str],
) -> Set[str]:
    """Strictly validate existing checkpoint for resume eligibility across all 10 criteria.
    
    Returns set of verified completed symbols that can be trusted.
    Raises InvalidResumeCheckpointError if any corruption or invariant breach is found.
    """
    if checkpoint.total_symbols != len(governed_symbols):
        raise InvalidResumeCheckpointError(
            f"Checkpoint total symbols mismatch: {checkpoint.total_symbols} != {len(governed_symbols)}"
        )

    governed_set = set(governed_symbols)
    trusted_completed: Set[str] = set()

    for sym, sc in checkpoint.symbol_states.items():
        # Condition 8: Symbol belongs to the governed selection
        if sym not in governed_set:
            raise InvalidResumeCheckpointError(
                f"Symbol {sym} does not belong to governed batch selection"
            )

        if sc.status == BatchSymbolStatus.SUCCEEDED:
            # Condition 1: Final manifest exists
            if not sc.manifest_file_path or not Path(sc.manifest_file_path).exists():
                raise InvalidResumeCheckpointError(
                    f"Completed symbol {sym} missing manifest file: {sc.manifest_file_path}"
                )

            manifest_content = Path(sc.manifest_file_path).read_text(encoding="utf-8")
            manifest_hash = hashlib.sha256(manifest_content.encode("utf-8")).hexdigest()
            if sc.manifest_checksum and sc.manifest_checksum != manifest_hash:
                raise InvalidResumeCheckpointError(
                    f"Manifest checksum mismatch for {sym}: {manifest_hash} != {sc.manifest_checksum}"
                )

            man_data = json.loads(manifest_content)

            # Condition 2: Status is SUCCEEDED
            if man_data.get("status") not in ("SUCCEEDED", "SUCCESS"):
                raise InvalidResumeCheckpointError(
                    f"Manifest status for {sym} is not SUCCEEDED: {man_data.get('status')}"
                )

            # Condition 3 & 4: Raw file exists and raw checksum matches
            if not sc.raw_file_path or not Path(sc.raw_file_path).exists():
                raise InvalidResumeCheckpointError(
                    f"Completed symbol {sym} missing raw file: {sc.raw_file_path}"
                )
            raw_bytes = Path(sc.raw_file_path).read_bytes()
            computed_raw_hash = hashlib.sha256(raw_bytes).hexdigest()
            if computed_raw_hash != sc.raw_checksum or computed_raw_hash != man_data.get("raw_checksum"):
                raise InvalidResumeCheckpointError(
                    f"Raw checksum mismatch for {sym}: {computed_raw_hash} != {sc.raw_checksum}"
                )

            # Condition 5 & 6: Normalized file exists and normalized checksum matches
            if not sc.normalized_file_path or not Path(sc.normalized_file_path).exists():
                raise InvalidResumeCheckpointError(
                    f"Completed symbol {sym} missing normalized file: {sc.normalized_file_path}"
                )
            norm_bytes = Path(sc.normalized_file_path).read_bytes()
            computed_norm_hash = hashlib.sha256(norm_bytes).hexdigest()
            if computed_norm_hash != sc.normalized_checksum or computed_norm_hash != man_data.get("normalized_checksum"):
                raise InvalidResumeCheckpointError(
                    f"Normalized checksum mismatch for {sym}: {computed_norm_hash} != {sc.normalized_checksum}"
                )

            # Condition 7: Conservation holds (source = normalized + rejected)
            src_cnt = man_data.get("source_row_count", 0)
            norm_cnt = man_data.get("normalized_row_count", 0)
            rej_cnt = man_data.get("rejected_row_count", 0)
            if src_cnt != norm_cnt + rej_cnt:
                raise InvalidResumeCheckpointError(
                    f"Row conservation breached for {sym}: {src_cnt} != {norm_cnt} + {rej_cnt}"
                )

            # Condition 9: Dates and interval match batch contract
            if man_data.get("start_date") and man_data.get("start_date") != contract.start_date:
                raise InvalidResumeCheckpointError(
                    f"Start date mismatch for {sym}: {man_data.get('start_date')} != {contract.start_date}"
                )
            if man_data.get("end_date") and man_data.get("end_date") != contract.end_date:
                raise InvalidResumeCheckpointError(
                    f"End date mismatch for {sym}: {man_data.get('end_date')} != {contract.end_date}"
                )
            if man_data.get("interval") and man_data.get("interval") != contract.interval:
                raise InvalidResumeCheckpointError(
                    f"Interval mismatch for {sym}: {man_data.get('interval')} != {contract.interval}"
                )

            # Condition 10: Schema version matches
            if man_data.get("schema_mapping_version") and man_data.get("schema_mapping_version") != contract.schema_mapping_version:
                raise InvalidResumeCheckpointError(
                    f"Schema mapping mismatch for {sym}: {man_data.get('schema_mapping_version')} != {contract.schema_mapping_version}"
                )

            trusted_completed.add(sym)

    return trusted_completed
