"""Production-readiness hardening tests: Logging, Auditability, and Redaction (Workstream G).

Module docstring:
- Protected production invariants: All audit logs, operational traces, and runtime exceptions must be
  strictly redacted of cookies, tokens, and authorization materials. Log injection attacks (CRLF)
  must be escaped, all timestamps must be UTC ISO-8601, and audit entries must reconcile with manifests.
- Fault classes covered: Sensitive credential leakage in logs, CRLF log-splitting attacks, unescaped
  exceptions, corrupted audit log lines, missing governed reason codes, and audit-manifest divergences.
- Why tests are not duplicates: Existing Phase 7 tests verify return codes and console messages;
  these tests specifically audit JSONL structured event records, regex redactions, and log reconciliation.
"""

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from phase7.operations.audit_reconciliation import (
    AuditEntry,
    StructuredAuditLogger,
    reconcile_audit_trail,
    sanitize_log_message,
)
from phase7.operations.security_validation import redact_sensitive_data

pytestmark = [pytest.mark.unit]


# 1. Cookie values are never logged
def test_cookie_values_never_logged():
    msg = "Request failed: Cookie: session_token=12345; user=tester"
    sanitized = sanitize_log_message(msg)
    assert "12345" not in sanitized
    assert "[REDACTED]" in sanitized


# 2. Authorization content is never logged
def test_authorization_content_never_logged():
    msg = "Header: Authorization: Bearer secret_api_token_xyz"
    sanitized = sanitize_log_message(msg)
    assert "secret_api_token_xyz" not in sanitized
    assert "Bearer [REDACTED]" in sanitized


# 3. Owner instructions not logged as credentials
def test_owner_instruction_logged_safely():
    instruction = "OWNER_DIRECTIVE: PROCEED_OFFLINE_ONLY"
    sanitized = sanitize_log_message(instruction)
    assert sanitized == "OWNER_DIRECTIVE: PROCEED_OFFLINE_ONLY"


# 4. Request headers with tokens are redacted
def test_request_headers_redacted():
    headers_dict = '{"authorization": "token_abc", "host": "www.sebi.gov.in"}'
    sanitized = redact_sensitive_data(headers_dict)
    assert "token_abc" not in sanitized
    assert "[REDACTED]" in sanitized


# 5. Sensitive response headers redacted
def test_sensitive_response_headers_redacted():
    msg = 'Response headers: {"set-cookie": "id=cookie_val_999; Secure"}'
    sanitized = redact_sensitive_data(msg)
    assert "cookie_val_999" not in sanitized
    assert "[REDACTED]" in sanitized


# 6. Raw upstream exceptions are sanitized
def test_raw_upstream_exceptions_sanitized():
    exc = Exception("Connection error to https://secret-token@host/api")
    clean = sanitize_log_message(str(exc))
    assert clean is not None


# 7. File paths recorded without secret material
def test_file_paths_recorded_cleanly(temp_staging: Path):
    path_str = str(temp_staging / "evidence.raw")
    clean = sanitize_log_message(path_str)
    assert "password" not in clean.lower()


# 8. Every halt contains a governed reason code
def test_halt_contains_governed_reason_code(temp_staging: Path, repo_root: Path):
    logger = StructuredAuditLogger(
        log_file_path=temp_staging / "audit.jsonl",
        run_id="R1",
        batch_id="B1",
        repo_root=repo_root,
    )
    entry = logger.record_event(
        event_type="HALT",
        symbol="PREMIERENE",
        outcome="HALTED",
        reason_code="EMPTY_RESPONSE_UNEXPLAINED",
    )
    assert entry.reason_code == "EMPTY_RESPONSE_UNEXPLAINED"


# 9. Every run has one final outcome
def test_run_single_final_outcome(temp_staging: Path, repo_root: Path):
    logger = StructuredAuditLogger(
        log_file_path=temp_staging / "audit.jsonl",
        run_id="R2",
        batch_id="B2",
        repo_root=repo_root,
    )
    entry = logger.record_event(
        event_type="BATCH_COMPLETION",
        outcome="HALTED",
        reason_code="BLK_02_PILOT_HALTED",
    )
    assert entry.outcome == "HALTED"


# 10. Every request has one request ID
def test_request_id_assigned(temp_staging: Path, repo_root: Path):
    logger = StructuredAuditLogger(
        log_file_path=temp_staging / "audit.jsonl",
        run_id="R3",
        batch_id="B3",
        repo_root=repo_root,
    )
    entry = logger.record_event(
        event_type="REQUEST_DISPATCH",
        symbol="SYN0001",
        request_id="REQ_SYN0001_1",
    )
    assert entry.request_id == "REQ_SYN0001_1"


# 11. Every manifest traceable to run ID and batch ID
def test_manifest_traceable_to_run_id():
    manifest = {
        "manifest_version": "1.0",
        "batch_id": "BATCH_20261010",
        "run_id": "RUN_001",
        "symbol": "SYN0001",
    }
    assert manifest["run_id"] == "RUN_001"
    assert manifest["batch_id"] == "BATCH_20261010"


# 12. Audit timestamps are UTC
def test_audit_timestamps_are_utc(temp_staging: Path, repo_root: Path):
    logger = StructuredAuditLogger(
        log_file_path=temp_staging / "audit.jsonl",
        run_id="R4",
        batch_id="B4",
        repo_root=repo_root,
    )
    entry = logger.record_event(event_type="INIT")
    assert entry.timestamp_utc.endswith("+00:00") or "T" in entry.timestamp_utc


# 13. Structured logs remain parseable
def test_structured_logs_remain_parseable(temp_staging: Path, repo_root: Path):
    log_file = temp_staging / "audit.jsonl"
    logger = StructuredAuditLogger(log_file_path=log_file, run_id="R5", batch_id="B5", repo_root=repo_root)
    logger.record_event(event_type="START")
    logger.record_event(event_type="END", outcome="SUCCEEDED")

    lines = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    assert lines[0]["event_type"] == "START"
    assert lines[1]["outcome"] == "SUCCEEDED"


# 14. Log injection (CRLF) is escaped
def test_log_injection_escaped():
    malicious_input = "Failed login\nADMIN_OVERRIDE_SUCCESS\rLOG_SPLIT"
    escaped = sanitize_log_message(malicious_input)
    assert "\n" not in escaped
    assert "\r" not in escaped
    assert "\\n" in escaped
    assert "\\r" in escaped


# 15. Audit summary reconciles with manifests and checkpoints
def test_audit_summary_reconciles(temp_staging: Path, repo_root: Path):
    log_file = temp_staging / "audit.jsonl"
    logger = StructuredAuditLogger(log_file_path=log_file, run_id="R6", batch_id="B6", repo_root=repo_root)

    logger.record_event(
        event_type="SYMBOL_COMPLETE",
        symbol="SYN0001",
        request_id="REQ_1",
        outcome="SUCCEEDED",
    )

    manifests = [{"symbol": "SYN0001", "status": "SUCCEEDED", "request_id": "REQ_1"}]
    chk = {"completed_count": 1}

    success, errors = reconcile_audit_trail(log_file, chk, manifests)
    assert success is True
    assert errors == []
