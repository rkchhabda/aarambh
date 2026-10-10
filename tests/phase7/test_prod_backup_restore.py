"""Production-readiness hardening tests: Backup, Restore, and Disaster Recovery (Workstream H).

Module docstring:
- Protected production invariants: Offline backups must be created and restored strictly outside Git,
  capture complete inventory SHA-256 manifests, exclude temporary (.tmp.*) and sensitive session files,
  preserve raw/normalized evidence bit-for-bit, and detect any archive tampering or file omission.
- Fault classes covered: Corrupted backup archive, missing inventory file, altered file checksums,
  temporary file leakage into archives, session cookie leakage into archives, and restoration reconciliation failures.
- Why tests are not duplicates: Existing Phase 7 tests don't have backup/disaster recovery suites;
  these tests provide the governed offline backup and restoration validator required for production readiness.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from phase7.operations.atomic_io import atomic_write_bytes, atomic_write_text
from phase7.operations.backup_restore import (
    BackupInventoryError,
    create_offline_backup,
    restore_and_verify_backup,
    should_exclude_from_backup,
)

pytestmark = [pytest.mark.unit]


@pytest.fixture
def sample_staging_tree(temp_staging: Path, repo_root: Path) -> Path:
    src = temp_staging / "source_env"
    src.mkdir(parents=True, exist_ok=True)

    # 1. Raw file
    atomic_write_bytes(src / "raw_SYN0001.json", b'{"candles": [1, 2, 3]}', repo_root=repo_root)

    # 2. Normalized file
    atomic_write_text(src / "norm_SYN0001.csv", "date,close\n2024-01-01,100\n", repo_root=repo_root)

    # 3. Manifest file
    atomic_write_text(src / "manifest_SYN0001.json", '{"status": "SUCCEEDED"}', repo_root=repo_root)

    # 4. Checkpoint file
    atomic_write_text(src / "checkpoint.json", '{"completed": 1}', repo_root=repo_root, allow_overwrite=True)

    # 5. Contract file
    atomic_write_text(src / "batch_contract.json", '{"panel": "P1"}', repo_root=repo_root)

    # 6. Excluded temporary file
    (src / ".tmp.1234.partial").write_text("temp data", encoding="utf-8")

    # 7. Excluded cookie file
    (src / "user.cookie").write_text("secret_cookie", encoding="utf-8")

    return src


# 1. Backup inventory generation
def test_backup_inventory_generation(sample_staging_tree: Path, temp_staging: Path, repo_root: Path):
    backup_root = temp_staging / "backups"
    bk_folder = create_offline_backup(sample_staging_tree, backup_root, "BK_01", repo_root=repo_root)
    assert (bk_folder / "backup_inventory.json").exists()


# 2. Backup inventory contains SHA-256 for all files
def test_backup_inventory_checksums(sample_staging_tree: Path, temp_staging: Path, repo_root: Path):
    backup_root = temp_staging / "backups"
    bk_folder = create_offline_backup(sample_staging_tree, backup_root, "BK_02", repo_root=repo_root)
    inv = json.loads((bk_folder / "backup_inventory.json").read_text(encoding="utf-8"))
    assert inv["file_count"] >= 5
    for f in inv["files"]:
        assert len(f["sha256"]) == 64


# 3. Raw evidence copied bit-for-bit without modification
def test_raw_evidence_copied_unmodified(sample_staging_tree: Path, temp_staging: Path, repo_root: Path):
    backup_root = temp_staging / "backups"
    bk_folder = create_offline_backup(sample_staging_tree, backup_root, "BK_03", repo_root=repo_root)
    src_raw = (sample_staging_tree / "raw_SYN0001.json").read_bytes()
    bk_raw = (bk_folder / "raw_SYN0001.json").read_bytes()
    assert src_raw == bk_raw


# 4. Normalized evidence copied bit-for-bit without modification
def test_normalized_evidence_copied_unmodified(sample_staging_tree: Path, temp_staging: Path, repo_root: Path):
    backup_root = temp_staging / "backups"
    bk_folder = create_offline_backup(sample_staging_tree, backup_root, "BK_04", repo_root=repo_root)
    src_norm = (sample_staging_tree / "norm_SYN0001.csv").read_bytes()
    bk_norm = (bk_folder / "norm_SYN0001.csv").read_bytes()
    assert src_norm == bk_norm


# 5. Manifests copied without modification
def test_manifests_copied_unmodified(sample_staging_tree: Path, temp_staging: Path, repo_root: Path):
    backup_root = temp_staging / "backups"
    bk_folder = create_offline_backup(sample_staging_tree, backup_root, "BK_05", repo_root=repo_root)
    src_mf = (sample_staging_tree / "manifest_SYN0001.json").read_bytes()
    bk_mf = (bk_folder / "manifest_SYN0001.json").read_bytes()
    assert src_mf == bk_mf


# 6. Checkpoints copied without modification
def test_checkpoints_copied_unmodified(sample_staging_tree: Path, temp_staging: Path, repo_root: Path):
    backup_root = temp_staging / "backups"
    bk_folder = create_offline_backup(sample_staging_tree, backup_root, "BK_06", repo_root=repo_root)
    src_chk = (sample_staging_tree / "checkpoint.json").read_bytes()
    bk_chk = (bk_folder / "checkpoint.json").read_bytes()
    assert src_chk == bk_chk


# 7. Authorization records remain immutable
def test_contract_copied_unmodified(sample_staging_tree: Path, temp_staging: Path, repo_root: Path):
    backup_root = temp_staging / "backups"
    bk_folder = create_offline_backup(sample_staging_tree, backup_root, "BK_07", repo_root=repo_root)
    src_c = (sample_staging_tree / "batch_contract.json").read_bytes()
    bk_c = (bk_folder / "batch_contract.json").read_bytes()
    assert src_c == bk_c


# 8. Backup excludes active temporary files
def test_backup_excludes_temporary_files(sample_staging_tree: Path, temp_staging: Path, repo_root: Path):
    backup_root = temp_staging / "backups"
    bk_folder = create_offline_backup(sample_staging_tree, backup_root, "BK_08", repo_root=repo_root)
    assert not (bk_folder / ".tmp.1234.partial").exists()


# 9. Backup excludes cookie and session files
def test_backup_excludes_cookie_files(sample_staging_tree: Path, temp_staging: Path, repo_root: Path):
    backup_root = temp_staging / "backups"
    bk_folder = create_offline_backup(sample_staging_tree, backup_root, "BK_09", repo_root=repo_root)
    assert not (bk_folder / "user.cookie").exists()


# 10. Restore to a new external path
def test_restore_to_new_external_path(sample_staging_tree: Path, temp_staging: Path, repo_root: Path):
    backup_root = temp_staging / "backups"
    restore_root = temp_staging / "restored"
    bk_folder = create_offline_backup(sample_staging_tree, backup_root, "BK_10", repo_root=repo_root)
    success, errors = restore_and_verify_backup(bk_folder, restore_root, repo_root=repo_root)
    assert success is True
    assert errors == []
    assert (restore_root / "raw_SYN0001.json").exists()


# 11. Restored raw checksum matches
def test_restored_raw_checksum_matches(sample_staging_tree: Path, temp_staging: Path, repo_root: Path):
    backup_root = temp_staging / "backups"
    restore_root = temp_staging / "restored"
    bk_folder = create_offline_backup(sample_staging_tree, backup_root, "BK_11", repo_root=repo_root)
    restore_and_verify_backup(bk_folder, restore_root, repo_root=repo_root)
    sha_orig = hashlib.sha256((sample_staging_tree / "raw_SYN0001.json").read_bytes()).hexdigest()
    sha_restored = hashlib.sha256((restore_root / "raw_SYN0001.json").read_bytes()).hexdigest()
    assert sha_orig == sha_restored


# 12. Restored normalized checksum matches
def test_restored_normalized_checksum_matches(sample_staging_tree: Path, temp_staging: Path, repo_root: Path):
    backup_root = temp_staging / "backups"
    restore_root = temp_staging / "restored"
    bk_folder = create_offline_backup(sample_staging_tree, backup_root, "BK_12", repo_root=repo_root)
    restore_and_verify_backup(bk_folder, restore_root, repo_root=repo_root)
    sha_orig = hashlib.sha256((sample_staging_tree / "norm_SYN0001.csv").read_bytes()).hexdigest()
    sha_restored = hashlib.sha256((restore_root / "norm_SYN0001.csv").read_bytes()).hexdigest()
    assert sha_orig == sha_restored


# 13. Restored manifests reconcile
def test_restored_manifests_reconcile(sample_staging_tree: Path, temp_staging: Path, repo_root: Path):
    backup_root = temp_staging / "backups"
    restore_root = temp_staging / "restored"
    bk_folder = create_offline_backup(sample_staging_tree, backup_root, "BK_13", repo_root=repo_root)
    restore_and_verify_backup(bk_folder, restore_root, repo_root=repo_root)
    mf_data = json.loads((restore_root / "manifest_SYN0001.json").read_text(encoding="utf-8"))
    assert mf_data["status"] == "SUCCEEDED"


# 14. Missing backup file detected
def test_missing_backup_file_detected(sample_staging_tree: Path, temp_staging: Path, repo_root: Path):
    backup_root = temp_staging / "backups"
    restore_root = temp_staging / "restored"
    bk_folder = create_offline_backup(sample_staging_tree, backup_root, "BK_14", repo_root=repo_root)
    # Delete a file from backup before restore
    (bk_folder / "raw_SYN0001.json").unlink()
    success, errors = restore_and_verify_backup(bk_folder, restore_root, repo_root=repo_root)
    assert success is False
    assert any("Missing file in backup archive" in e for e in errors)


# 15. Corrupted backup rejected
def test_corrupted_backup_rejected(sample_staging_tree: Path, temp_staging: Path, repo_root: Path):
    backup_root = temp_staging / "backups"
    restore_root = temp_staging / "restored"
    bk_folder = create_offline_backup(sample_staging_tree, backup_root, "BK_15", repo_root=repo_root)
    # Corrupt one file
    (bk_folder / "norm_SYN0001.csv").write_bytes(b"tampered")
    success, errors = restore_and_verify_backup(bk_folder, restore_root, repo_root=repo_root)
    assert success is False
    assert any("Checksum mismatch" in e or "Size mismatch" in e for e in errors)
