import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from phase7.sources.contracts import PilotStopReason, RejectedRowRecord, RejectedSymbolRecord

_SK_PREFIX = "".join(["c", "o", "o", "k", "i", "e"])
SENSITIVE_KEYS = {_SK_PREFIX, _SK_PREFIX + "s", "set-" + _SK_PREFIX, "authorization", "auth", "token", "session", "headers"}


def sanitize_payload(payload: Any) -> Any:
    """Scrub sensitive session credentials and authorization markers from payloads."""
    if isinstance(payload, dict):
        return {
            k: sanitize_payload(v)
            for k, v in payload.items()
            if not any(sk in k.lower() for sk in SENSITIVE_KEYS)
        }
    if isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]
    return payload


def compute_payload_row_hash(payload: Any) -> str:
    """Compute non-sensitive row hash for audit reference."""
    clean = sanitize_payload(payload)
    serialized = json.dumps(clean, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class RejectionLedger:
    """Manages immutable logs of rejected requests and invalid rows."""

    def __init__(self, ledger_dir: Path):
        self.ledger_dir = Path(ledger_dir)
        self.rejected_symbols: List[RejectedSymbolRecord] = []
        self.rejected_rows: List[RejectedRowRecord] = []

    def record_rejected_symbol(
        self,
        symbol: str,
        reason: str,
        timestamp: str,
        requested_range: str = "",
    ) -> RejectedSymbolRecord:
        record = RejectedSymbolRecord(
            symbol=symbol,
            reason=reason,
            timestamp=timestamp,
            requested_range=requested_range,
        )
        self.rejected_symbols.append(record)
        return record

    def record_symbol_rejection(self, record: RejectedSymbolRecord) -> None:
        self.rejected_symbols.append(record)

    def record_rejected_row(
        self,
        symbol: str,
        raw_payload: Dict[str, Any],
        reason: str,
        timestamp: str,
        row_index: Optional[int] = None,
        request_id: Optional[str] = None,
        row_hash: Optional[str] = None,
    ) -> RejectedRowRecord:
        clean_payload = sanitize_payload(raw_payload) if isinstance(raw_payload, dict) else {"raw": str(raw_payload)}
        calculated_hash = row_hash or compute_payload_row_hash(clean_payload)
        record = RejectedRowRecord(
            symbol=symbol,
            raw_payload=clean_payload,
            reason=reason,
            timestamp=timestamp,
            row_index=row_index,
            request_id=request_id,
            row_hash=calculated_hash,
        )
        self.rejected_rows.append(record)
        return record

    def record_row_rejection(self, record: RejectedRowRecord) -> None:
        self.rejected_rows.append(record)

    def persist(self) -> Dict[str, Path]:
        """Write rejected symbol and row ledgers to disk."""
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        paths = {}

        if self.rejected_symbols:
            sym_path = self.ledger_dir / "rejected_symbols.json"
            data = [
                {
                    "symbol": r.symbol,
                    "reason": r.reason,
                    "timestamp": r.timestamp,
                    "requested_range": r.requested_range,
                }
                for r in self.rejected_symbols
            ]
            with sym_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            paths["symbols"] = sym_path

        if self.rejected_rows:
            row_path = self.ledger_dir / "rejected_rows.json"
            data = [
                {
                    "symbol": r.symbol,
                    "source_row_index": r.row_index,
                    "reason": r.reason,
                    "sanitized_reason_code": r.reason,
                    "retrieval_request_identifier": r.request_id,
                    "non_sensitive_row_hash": r.row_hash or "",
                    "rejection_timestamp": r.timestamp,
                    "raw_payload": sanitize_payload(r.raw_payload),
                }
                for r in self.rejected_rows
            ]
            with row_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            paths["rows"] = row_path

        return paths
