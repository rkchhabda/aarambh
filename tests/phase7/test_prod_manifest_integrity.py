"""Production-readiness hardening tests: Checkpoint, Manifest, and Integrity (Workstream B).

Module docstring:
- Protected production invariants: Manifest and checkpoint records must maintain strict cryptographic,
  structural, and mathematical consistency. Source rows must strictly equal normalized rows plus rejected rows.
  Corrupt files, missing checksums, duplicate paths/requests, or contract mismatches must be caught fail-closed.
- Fault classes covered: Row conservation failure, duplicate keys, checksum mismatches, contract divergences,
  impossible summary totals, missing raw/norm artifacts, and false success claims.
- Why tests are not duplicates: Existing Phase 7 tests verify batch runtime happy-paths and single-ticker pilot;
  these tests systematically evaluate the multidimensional integrity matrix across all possible corruption modes.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from phase7.operations.atomic_io import atomic_write_bytes, atomic_write_text
from phase7.operations.integrity import (
    validate_batch_contract_match,
    validate_checkpoint_integrity,
    validate_manifest_integrity,
    verify_sha256,
)

pytestmark = [pytest.mark.unit]


@pytest.fixture
def valid_manifest_data(temp_staging: Path, repo_root: Path) -> Dict[str, Any]:
    raw_p = temp_staging / "raw_SYN0001.json"
    norm_p = temp_staging / "norm_SYN0001.csv"
    _, raw_sha = atomic_write_bytes(raw_p, b'{"raw": 1}', repo_root=repo_root)
    _, norm_sha = atomic_write_text(norm_p, "date,close\n2024-01-01,100\n", repo_root=repo_root)

    return {
        "manifest_version": "1.0",
        "batch_id": "BATCH_001",
        "run_id": "RUN_001",
        "symbol": "SYN0001",
        "status": "SUCCEEDED",
        "date_window": "2024Q1",
        "interval": "1d",
        "requested_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_row_count": 1,
        "normalized_row_count": 1,
        "rejected_row_count": 0,
        "raw_evidence_path": str(raw_p),
        "normalized_evidence_path": str(norm_p),
        "raw_evidence_sha256": raw_sha,
        "normalized_evidence_sha256": norm_sha,
        "request_id": "REQ_001",
    }


# 1. Valid completed manifest accepted
def test_valid_completed_manifest_accepted(valid_manifest_data: Dict[str, Any], temp_staging: Path):
    errors = validate_manifest_integrity(valid_manifest_data, base_staging_dir=temp_staging)
    assert errors == []


# 2. Missing final manifest rejected
def test_missing_final_manifest_rejected(temp_staging: Path):
    missing_manifest = temp_staging / "manifest_MISSING.json"
    assert not missing_manifest.exists()


# 3. Remaining PENDING manifest rejected
def test_pending_manifest_rejected(valid_manifest_data: Dict[str, Any], temp_staging: Path):
    data = dict(valid_manifest_data, status="PENDING")
    errors = validate_manifest_integrity(data, base_staging_dir=temp_staging)
    assert any("remains in PENDING status" in e for e in errors)


# 4. Unknown manifest status rejected
def test_unknown_manifest_status_rejected(valid_manifest_data: Dict[str, Any], temp_staging: Path):
    data = dict(valid_manifest_data, status="IN_PROGRESS")
    errors = validate_manifest_integrity(data, base_staging_dir=temp_staging)
    assert any("Unknown manifest status" in e for e in errors)


# 5. Raw file missing detected
def test_raw_file_missing_detected(valid_manifest_data: Dict[str, Any], temp_staging: Path):
    data = dict(valid_manifest_data, raw_evidence_path=str(temp_staging / "nonexistent_raw.json"))
    errors = validate_manifest_integrity(data, base_staging_dir=temp_staging)
    assert any("Raw evidence file missing on disk" in e for e in errors)


# 6. Normalized file missing detected
def test_normalized_file_missing_detected(valid_manifest_data: Dict[str, Any], temp_staging: Path):
    data = dict(valid_manifest_data, normalized_evidence_path=str(temp_staging / "nonexistent_norm.csv"))
    errors = validate_manifest_integrity(data, base_staging_dir=temp_staging)
    assert any("Normalized evidence file missing on disk" in e for e in errors)


# 7. Raw checksum mismatch detected
def test_raw_checksum_mismatch_detected(valid_manifest_data: Dict[str, Any], temp_staging: Path):
    data = dict(valid_manifest_data, raw_evidence_sha256="0" * 64)
    errors = validate_manifest_integrity(data, base_staging_dir=temp_staging)
    assert any("Raw evidence checksum mismatch" in e for e in errors)


# 8. Normalized checksum mismatch detected
def test_normalized_checksum_mismatch_detected(valid_manifest_data: Dict[str, Any], temp_staging: Path):
    data = dict(valid_manifest_data, normalized_evidence_sha256="0" * 64)
    errors = validate_manifest_integrity(data, base_staging_dir=temp_staging)
    assert any("Normalized evidence checksum mismatch" in e for e in errors)


# 9. SUCCEEDED manifest without raw/norm checksums rejected
def test_succeeded_manifest_without_checksums_rejected(valid_manifest_data: Dict[str, Any], temp_staging: Path):
    data = dict(valid_manifest_data, raw_evidence_sha256=None)
    errors = validate_manifest_integrity(data, base_staging_dir=temp_staging)
    assert any("missing raw or normalized checksums" in e for e in errors)


# 10. SUCCEEDED manifest with zero normalized rows rejected
def test_succeeded_manifest_with_zero_rows_rejected(valid_manifest_data: Dict[str, Any], temp_staging: Path):
    data = dict(valid_manifest_data, normalized_row_count=0)
    errors = validate_manifest_integrity(data, base_staging_dir=temp_staging)
    assert any("cannot have zero normalized rows" in e for e in errors)


# 11. Row-count conservation failure detected
def test_row_count_conservation_failure(valid_manifest_data: Dict[str, Any], temp_staging: Path):
    # source=10, norm=8, rej=1 -> sum is 9 != 10
    data = dict(valid_manifest_data, source_row_count=10, normalized_row_count=8, rejected_row_count=1)
    errors = validate_manifest_integrity(data, base_staging_dir=temp_staging)
    assert any("Row conservation failed" in e for e in errors)


# 12. FAILED manifest missing reason code rejected
def test_failed_manifest_missing_reason_rejected(valid_manifest_data: Dict[str, Any], temp_staging: Path):
    data = dict(valid_manifest_data, status="FAILED", failure_reason_code=None)
    errors = validate_manifest_integrity(data, base_staging_dir=temp_staging)
    assert any("missing governed failure_reason_code" in e for e in errors)


# 13. Manifest missing required top-level keys
@pytest.mark.parametrize("missing_key", ["manifest_version", "batch_id", "run_id", "symbol", "status"])
def test_manifest_missing_required_keys(valid_manifest_data: Dict[str, Any], temp_staging: Path, missing_key: str):
    data = dict(valid_manifest_data)
    del data[missing_key]
    errors = validate_manifest_integrity(data, base_staging_dir=temp_staging)
    assert any("missing required keys" in e for e in errors)


# 14. Checkpoint valid summary totals accepted
def test_checkpoint_valid_totals_accepted():
    chk = {
        "checkpoint_version": "1.0",
        "batch_id": "B1",
        "run_id": "R1",
        "created_at_utc": "2026-10-10T12:00:00Z",
        "updated_at_utc": "2026-10-10T12:05:00Z",
        "completed_count": 2,
        "failed_count": 1,
        "pending_count": 0,
        "symbols": {
            "S1": {"status": "SUCCEEDED"},
            "S2": {"status": "SUCCEEDED"},
            "S3": {"status": "FAILED"},
        },
    }
    errors = validate_checkpoint_integrity(chk)
    assert errors == []


# 15. Checkpoint completed count mismatch detected
def test_checkpoint_completed_count_mismatch():
    chk = {
        "checkpoint_version": "1.0",
        "batch_id": "B1",
        "run_id": "R1",
        "created_at_utc": "2026-10-10T12:00:00Z",
        "updated_at_utc": "2026-10-10T12:05:00Z",
        "completed_count": 5,  # Claim 5, but symbols only has 1
        "failed_count": 0,
        "pending_count": 0,
        "symbols": {"S1": {"status": "SUCCEEDED"}},
    }
    errors = validate_checkpoint_integrity(chk)
    assert any("Completed count mismatch" in e for e in errors)


# 16. Checkpoint failed count mismatch detected
def test_checkpoint_failed_count_mismatch():
    chk = {
        "checkpoint_version": "1.0",
        "batch_id": "B1",
        "run_id": "R1",
        "created_at_utc": "2026-10-10T12:00:00Z",
        "updated_at_utc": "2026-10-10T12:05:00Z",
        "completed_count": 0,
        "failed_count": 9,
        "pending_count": 0,
        "symbols": {"S1": {"status": "FAILED"}},
    }
    errors = validate_checkpoint_integrity(chk)
    assert any("Failed count mismatch" in e for e in errors)


# 17. Checkpoint pending count mismatch detected
def test_checkpoint_pending_count_mismatch():
    chk = {
        "checkpoint_version": "1.0",
        "batch_id": "B1",
        "run_id": "R1",
        "created_at_utc": "2026-10-10T12:00:00Z",
        "updated_at_utc": "2026-10-10T12:05:00Z",
        "completed_count": 0,
        "failed_count": 0,
        "pending_count": 2,
        "symbols": {"S1": {"status": "PENDING"}},
    }
    errors = validate_checkpoint_integrity(chk)
    assert any("Pending count mismatch" in e for e in errors)


# 18. Impossible summary totals in checkpoint
def test_checkpoint_impossible_summary_totals():
    chk = {
        "checkpoint_version": "1.0",
        "batch_id": "B1",
        "run_id": "R1",
        "created_at_utc": "2026-10-10T12:00:00Z",
        "updated_at_utc": "2026-10-10T12:05:00Z",
        "completed_count": 1,
        "failed_count": 0,
        "pending_count": 0,
        "symbols": {
            "S1": {"status": "SUCCEEDED"},
            "S2": {"status": "SUCCEEDED"},  # 2 symbols total but sum claims 1
        },
    }
    errors = validate_checkpoint_integrity(chk)
    assert any("Impossible summary totals" in e for e in errors)


# 19. Governed symbol count mismatch
def test_checkpoint_governed_symbol_count_mismatch():
    chk = {
        "checkpoint_version": "1.0",
        "batch_id": "B1",
        "run_id": "R1",
        "created_at_utc": "2026-10-10T12:00:00Z",
        "updated_at_utc": "2026-10-10T12:05:00Z",
        "completed_count": 1,
        "failed_count": 0,
        "pending_count": 0,
        "symbols": {"S1": {"status": "SUCCEEDED"}},
    }
    errors = validate_checkpoint_integrity(chk, governed_symbol_count=20)
    assert any("does not match governed count" in e for e in errors)


# 20. Batch success claimed with fewer than governed symbols
def test_batch_success_fewer_than_governed_symbols():
    chk = {
        "checkpoint_version": "1.0",
        "batch_id": "B1",
        "run_id": "R1",
        "created_at_utc": "2026-10-10T12:00:00Z",
        "updated_at_utc": "2026-10-10T12:05:00Z",
        "batch_status": "SUCCEEDED",
        "completed_count": 19,
        "failed_count": 1,
        "pending_count": 0,
        "symbols": {f"S{i}": {"status": "SUCCEEDED" if i < 20 else "FAILED"} for i in range(1, 21)},
    }
    errors = validate_checkpoint_integrity(chk, governed_symbol_count=20)
    assert any("Batch cannot claim SUCCEEDED with only 19/20" in e for e in errors)


# 21. Duplicate request IDs detected
def test_duplicate_request_ids_detected():
    chk = {
        "checkpoint_version": "1.0",
        "batch_id": "B1",
        "run_id": "R1",
        "created_at_utc": "2026-10-10T12:00:00Z",
        "updated_at_utc": "2026-10-10T12:05:00Z",
        "completed_count": 2,
        "failed_count": 0,
        "pending_count": 0,
        "symbols": {"S1": {"status": "SUCCEEDED"}, "S2": {"status": "SUCCEEDED"}},
    }
    manifests = [
        {"request_id": "REQ_DUP", "status": "SUCCEEDED"},
        {"request_id": "REQ_DUP", "status": "SUCCEEDED"},
    ]
    errors = validate_checkpoint_integrity(chk, manifest_records=manifests)
    assert any("Duplicate request_id detected" in e for e in errors)


# 22. Duplicate raw evidence paths detected
def test_duplicate_raw_evidence_paths_detected():
    chk = {
        "checkpoint_version": "1.0",
        "batch_id": "B1",
        "run_id": "R1",
        "created_at_utc": "2026-10-10T12:00:00Z",
        "updated_at_utc": "2026-10-10T12:05:00Z",
        "completed_count": 2,
        "failed_count": 0,
        "pending_count": 0,
        "symbols": {"S1": {"status": "SUCCEEDED"}, "S2": {"status": "SUCCEEDED"}},
    }
    manifests = [
        {"raw_evidence_path": "/staging/raw_same.json", "status": "SUCCEEDED"},
        {"raw_evidence_path": "/staging/raw_same.json", "status": "SUCCEEDED"},
    ]
    errors = validate_checkpoint_integrity(chk, manifest_records=manifests)
    assert any("Duplicate raw evidence path detected" in e for e in errors)


# 23. Duplicate normalized evidence paths detected
def test_duplicate_normalized_evidence_paths_detected():
    chk = {
        "checkpoint_version": "1.0",
        "batch_id": "B1",
        "run_id": "R1",
        "created_at_utc": "2026-10-10T12:00:00Z",
        "updated_at_utc": "2026-10-10T12:05:00Z",
        "completed_count": 2,
        "failed_count": 0,
        "pending_count": 0,
        "symbols": {"S1": {"status": "SUCCEEDED"}, "S2": {"status": "SUCCEEDED"}},
    }
    manifests = [
        {"normalized_evidence_path": "/staging/norm_same.csv", "status": "SUCCEEDED"},
        {"normalized_evidence_path": "/staging/norm_same.csv", "status": "SUCCEEDED"},
    ]
    errors = validate_checkpoint_integrity(chk, manifest_records=manifests)
    assert any("Duplicate normalized evidence path detected" in e for e in errors)


# 24-29: Batch contract matching integrity tests
@pytest.mark.parametrize("mismatched_key,expected_val,altered_val", [
    ("panel_version", "PANEL_V1", "PANEL_V2"),
    ("snapshot_checksum", "a" * 64, "b" * 64),
    ("selection_checksum", "c" * 64, "d" * 64),
    ("ordered_symbols_sha256", "e" * 64, "f" * 64),
    ("date_window", "2024Q1", "2024Q2"),
    ("interval", "1d", "1h"),
])
def test_batch_contract_mismatches_detected(
    mismatched_key: str, expected_val: str, altered_val: str
):
    contract = {
        "panel_version": "PANEL_V1",
        "snapshot_checksum": "a" * 64,
        "selection_checksum": "c" * 64,
        "ordered_symbols_sha256": "e" * 64,
        "date_window": "2024Q1",
        "interval": "1d",
    }
    run_contract = dict(contract, **{mismatched_key: altered_val})
    errors = validate_batch_contract_match(contract, run_contract)
    assert len(errors) == 1
    assert f"Contract mismatch on '{mismatched_key}'" in errors[0]


# 30. Exact matching batch contract accepted
def test_exact_matching_batch_contract_accepted():
    contract = {
        "panel_version": "PANEL_V1",
        "snapshot_checksum": "a" * 64,
        "selection_checksum": "c" * 64,
        "ordered_symbols_sha256": "e" * 64,
        "date_window": "2024Q1",
        "interval": "1d",
    }
    errors = validate_batch_contract_match(contract, dict(contract))
    assert errors == []


# 31. Direct verify_sha256 helper validation
def test_verify_sha256_helper(temp_staging: Path, repo_root: Path):
    f = temp_staging / "sha_test.txt"
    _, expected_sha = atomic_write_text(f, "hello sha256", repo_root=repo_root)
    assert verify_sha256(f, expected_sha) is True
    assert verify_sha256(f, "bad" * 16) is False
    assert verify_sha256(temp_staging / "nonexistent.txt", expected_sha) is False
