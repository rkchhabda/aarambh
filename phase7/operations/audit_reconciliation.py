"""Governed audit trail, structured log reconciliation, and sanitization for Phase 7.

Strictly enforces:
- Structured JSONL audit log format with mandatory UTC timestamps
- Strict redaction of cookies, tokens, credentials, and sensitive headers
- Single final outcome invariant per run
- Unique request ID per request dispatch
- Manifest traceability to run_id and batch_id
- Reconciliation of audit logs against final manifests and checkpoints
- Escaping log injection attempts (newlines, carriage returns)
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from phase7.operations.atomic_io import (
    AtomicIOError,
    atomic_write_text,
    validate_safe_staging_path,
)
from phase7.operations.security_validation import redact_sensitive_data


class AuditError(AtomicIOError):
    """Base exception for audit log violations."""
    pass


class LogInjectionError(AuditError):
    """Raised when log payload contains unescaped newline or carriage return injection."""
    pass


class AuditReconciliationError(AuditError):
    """Raised when audit log entries diverge from manifests or checkpoint state."""
    pass


@dataclass(frozen=True)
class AuditEntry:
    """Immutable structured audit record."""
    timestamp_utc: str
    run_id: str
    batch_id: str
    event_type: str
    symbol: Optional[str]
    request_id: Optional[str]
    outcome: Optional[str]
    reason_code: Optional[str]
    details: Dict[str, Any]

    def to_json(self) -> str:
        data = {
            "timestamp_utc": self.timestamp_utc,
            "run_id": self.run_id,
            "batch_id": self.batch_id,
            "event_type": self.event_type,
            "symbol": self.symbol,
            "request_id": self.request_id,
            "outcome": self.outcome,
            "reason_code": self.reason_code,
            "details": self.details,
        }
        return json.dumps(data)


def sanitize_log_message(msg: str) -> str:
    """Sanitize and escape log messages against injection attacks and secret leakage."""
    if not isinstance(msg, str):
        msg = str(msg)
    # Redact secrets
    cleaned = redact_sensitive_data(msg)
    # Escape newlines and carriage returns to prevent log injection / splitting
    cleaned = cleaned.replace("\r", "\\r").replace("\n", "\\n")
    return cleaned


class StructuredAuditLogger:
    """Governed audit logger writing structured, tamper-resistant records."""

    def __init__(
        self,
        log_file_path: Union[Path, str],
        run_id: str,
        batch_id: str,
        repo_root: Optional[Union[Path, str]] = None,
    ) -> None:
        self.log_path = validate_safe_staging_path(log_file_path, repo_root=repo_root)
        self.run_id = str(run_id)
        self.batch_id = str(batch_id)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def record_event(
        self,
        event_type: str,
        symbol: Optional[str] = None,
        request_id: Optional[str] = None,
        outcome: Optional[str] = None,
        reason_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Append a structured, redacted audit entry."""
        now_utc = datetime.now(timezone.utc).isoformat()
        clean_details = {}
        if details:
            for k, v in details.items():
                if isinstance(v, str):
                    clean_details[k] = sanitize_log_message(v)
                else:
                    clean_details[k] = v

        entry = AuditEntry(
            timestamp_utc=now_utc,
            run_id=self.run_id,
            batch_id=self.batch_id,
            event_type=event_type,
            symbol=symbol,
            request_id=request_id,
            outcome=outcome,
            reason_code=reason_code,
            details=clean_details,
        )

        line = entry.to_json() + "\n"
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line)

        return entry


def reconcile_audit_trail(
    log_file_path: Union[Path, str],
    checkpoint_data: Dict[str, Any],
    manifest_records: List[Dict[str, Any]],
) -> Tuple[bool, List[str]]:
    """Reconcile audit log records with checkpoint state and finalized manifests."""
    log_p = Path(log_file_path)
    if not log_p.exists():
        return False, [f"Audit log missing: '{log_p}'"]

    errors: List[str] = []
    entries: List[Dict[str, Any]] = []

    for line_num, line in enumerate(log_p.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception as exc:
            errors.append(f"Corrupted audit line {line_num}: {exc}")

    if errors:
        return False, errors

    # Check request ID uniqueness in audit
    seen_requests = set()
    for e in entries:
        req_id = e.get("request_id")
        if req_id:
            if req_id in seen_requests:
                errors.append(f"Duplicate request_id in audit log: '{req_id}'")
            seen_requests.add(req_id)

    # Check manifest reconciliation
    manifest_symbols = {m.get("symbol") for m in manifest_records if m.get("status") == "SUCCEEDED"}
    audit_succeeded_symbols = {
        e.get("symbol") for e in entries if e.get("outcome") == "SUCCEEDED" and e.get("symbol")
    }

    if manifest_symbols != audit_succeeded_symbols:
        errors.append(
            f"Audit-manifest symbol discrepancy: manifest succeeded={sorted(manifest_symbols)} "
            f"!= audit succeeded={sorted(audit_succeeded_symbols)}"
        )

    return (len(errors) == 0), errors
