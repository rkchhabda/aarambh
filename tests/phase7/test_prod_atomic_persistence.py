"""Production-readiness hardening tests: Filesystem and Atomic Persistence (Workstream A).

Module docstring:
- Protected production invariants: All external raw/normalized evidence, manifests, and checkpoints
  must be written atomically, fsync-flushed, SHA-256 verified, strictly outside the Git repository,
  and protected against silent overwrites, partial writes, disk exhaustion, or path traversal.
- Fault classes covered: Disk-full (ENOSPC), permission denied (EACCES), interrupted writes,
  stale temporary files, filename/path length limits, illegal Windows characters, and repo escape.
- Why tests are not duplicates: Existing Phase 7 tests verify high-level batch pipeline calls;
  these tests isolate low-level OS persistence primitives, atomic file swaps, fsync durability,
  and filesystem failure recovery without touching live NSE data or existing frozen staging.
"""

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import tempfile
import time
from unittest.mock import MagicMock, patch
import uuid

import pytest

from phase7.operations.atomic_io import (
    AtomicIOError,
    ChecksumIntegrityError,
    FilenameValidationError,
    FileOverwriteRefusedError,
    StagingPathViolation,
    atomic_write_bytes,
    atomic_write_text,
    cleanup_stale_temporary_files,
    find_repository_root,
    validate_filename,
    validate_safe_staging_path,
)
from phase7.operations.fault_injection import (
    InjectedDiskFullError,
    InjectedPermissionDeniedError,
)

pytestmark = [pytest.mark.unit]


# 1. Temporary-file creation failure
def test_temp_file_creation_failure(temp_staging: Path, repo_root: Path):
    target = temp_staging / "data1.txt"
    def fault(phase, path):
        if phase == "pre_create":
            raise OSError("Failed to create temporary file")
    with pytest.raises(OSError, match="Failed to create temporary file"):
        atomic_write_bytes(target, b"test", repo_root=repo_root, fault_hook=fault)
    assert not target.exists()


# 2. Temporary-file write failure
def test_temp_file_write_failure(temp_staging: Path, repo_root: Path):
    target = temp_staging / "data2.txt"
    def fault(phase, path):
        if phase == "during_write":
            raise IOError("Write failed mid-stream")
    with pytest.raises(IOError, match="Write failed mid-stream"):
        atomic_write_bytes(target, b"payload", repo_root=repo_root, fault_hook=fault)
    assert not target.exists()


# 3. Flush failure
def test_flush_failure(temp_staging: Path, repo_root: Path):
    target = temp_staging / "data3.txt"
    def fault(phase, path):
        if phase == "during_flush":
            raise IOError("Flush failed")
    with pytest.raises(IOError, match="Flush failed"):
        atomic_write_bytes(target, b"payload", repo_root=repo_root, fault_hook=fault)
    assert not target.exists()


# 4. fsync failure when supported handled gracefully
def test_fsync_failure_handled_gracefully(temp_staging: Path, repo_root: Path):
    target = temp_staging / "data4.txt"
    with patch("os.fsync", side_effect=OSError("fsync not supported on filesystem")):
        path, sha = atomic_write_bytes(target, b"payload", repo_root=repo_root)
    assert path.exists()
    assert sha == hashlib.sha256(b"payload").hexdigest()


# 5. Atomic rename failure cleans up temporary file
def test_atomic_rename_failure_cleanup(temp_staging: Path, repo_root: Path):
    target = temp_staging / "data5.txt"
    with patch("os.replace", side_effect=OSError("Atomic rename failed")):
        with pytest.raises(OSError, match="Atomic rename failed"):
            atomic_write_bytes(target, b"payload", repo_root=repo_root)
    assert not target.exists()
    # Ensure no leftover temporary files in staging
    assert len(list(temp_staging.glob(".tmp.*"))) == 0


# 6. Destination already exists with identical content succeeds
def test_destination_already_exists_identical_succeeds(temp_staging: Path, repo_root: Path):
    target = temp_staging / "data6.txt"
    target.write_bytes(b"identical")
    path, sha = atomic_write_bytes(target, b"identical", repo_root=repo_root, allow_overwrite=False)
    assert path == target
    assert sha == hashlib.sha256(b"identical").hexdigest()


# 7. Destination already exists with different content refused
def test_destination_already_exists_different_refused(temp_staging: Path, repo_root: Path):
    target = temp_staging / "data7.txt"
    target.write_bytes(b"initial_bytes")
    with pytest.raises(FileOverwriteRefusedError, match="Immutable file .* already exists"):
        atomic_write_bytes(target, b"new_bytes", repo_root=repo_root, allow_overwrite=False)


# 8. Source disappears before rename
def test_source_disappears_before_rename(temp_staging: Path, repo_root: Path):
    target = temp_staging / "data8.txt"
    def fault(phase, path):
        if phase == "pre_rename" and path.exists():
            path.unlink()
    with pytest.raises(FileNotFoundError):
        atomic_write_bytes(target, b"payload", repo_root=repo_root, fault_hook=fault)
    assert not target.exists()


# 9. Permission denied on target directory
def test_permission_denied_target_directory(temp_staging: Path, repo_root: Path):
    target = temp_staging / "data9.txt"
    def fault(phase, path):
        if phase == "pre_write":
            raise InjectedPermissionDeniedError("Access denied")
    with pytest.raises(PermissionError, match="Access denied"):
        atomic_write_bytes(target, b"payload", repo_root=repo_root, fault_hook=fault)


# 10. Permission denied on target file during write
def test_permission_denied_during_write(temp_staging: Path, repo_root: Path):
    target = temp_staging / "data10.txt"
    def fault(phase, path):
        if phase == "during_write":
            raise InjectedPermissionDeniedError("Write permission denied")
    with pytest.raises(PermissionError, match="Write permission denied"):
        atomic_write_bytes(target, b"payload", repo_root=repo_root, fault_hook=fault)


# 11. Disk-full simulation (ENOSPC)
def test_disk_full_simulation(temp_staging: Path, repo_root: Path):
    target = temp_staging / "data11.txt"
    def fault(phase, path):
        if phase == "during_write":
            raise InjectedDiskFullError("No space left on device")
    with pytest.raises(OSError) as exc_info:
        atomic_write_bytes(target, b"payload", repo_root=repo_root, fault_hook=fault)
    assert exc_info.value.errno == 28
    assert not target.exists()


# 12. Short-write simulation
def test_short_write_simulation(temp_staging: Path, repo_root: Path):
    target = temp_staging / "data12.txt"
    def fault(phase, path):
        if phase == "pre_rename":
            # Truncate temporary file before rename to simulate partial write
            path.write_bytes(b"short")
    with pytest.raises(ChecksumIntegrityError, match="Checksum mismatch after write"):
        atomic_write_bytes(target, b"full_length_payload", repo_root=repo_root, fault_hook=fault)


# 13. Interrupted write leaves temporary file cleaned up
def test_interrupted_write_cleans_temporary_file(temp_staging: Path, repo_root: Path):
    target = temp_staging / "data13.txt"
    def fault(phase, path):
        if phase == "during_write":
            raise RuntimeError("Interrupt signal received")
    with pytest.raises(RuntimeError, match="Interrupt signal"):
        atomic_write_bytes(target, b"test", repo_root=repo_root, fault_hook=fault)
    assert not target.exists()
    assert len(list(temp_staging.glob(".tmp.*"))) == 0


# 14. Corrupted temporary file cleaned up on error
def test_corrupt_temporary_file_cleaned(temp_staging: Path, repo_root: Path):
    target = temp_staging / "data14.txt"
    def fault(phase, path):
        if phase == "pre_rename":
            path.write_bytes(b"corrupt")
    with pytest.raises(ChecksumIntegrityError):
        atomic_write_bytes(target, b"expected", repo_root=repo_root, fault_hook=fault)
    assert len(list(temp_staging.glob(".tmp.*"))) == 0


# 15. Stale temporary file purged safely by cleanup
def test_stale_temporary_file_purged_safely(temp_staging: Path):
    stale_file = temp_staging / ".tmp.1234.stale"
    stale_file.write_bytes(b"leftover from crashed process")
    # Set back modification time by 2 hours
    old_time = time.time() - 7200
    os.utime(stale_file, (old_time, old_time))

    cleaned = cleanup_stale_temporary_files(temp_staging, max_age_seconds=3600.0)
    assert stale_file in cleaned
    assert not stale_file.exists()


# 16. Fresh temporary file not purged by cleanup
def test_fresh_temporary_file_not_purged(temp_staging: Path):
    fresh_file = temp_staging / ".tmp.5678.fresh"
    fresh_file.write_bytes(b"active temp")

    cleaned = cleanup_stale_temporary_files(temp_staging, max_age_seconds=3600.0)
    assert fresh_file not in cleaned
    assert fresh_file.exists()
    fresh_file.unlink()


# 17. Zero-byte write handling
def test_zero_byte_write_succeeds_when_allowed(temp_staging: Path, repo_root: Path):
    target = temp_staging / "empty.txt"
    path, sha = atomic_write_bytes(target, b"", repo_root=repo_root)
    assert path.exists()
    assert path.stat().st_size == 0
    assert sha == hashlib.sha256(b"").hexdigest()


# 18. File truncated after write detected by checksum
def test_file_truncated_after_write_detected(temp_staging: Path, repo_root: Path):
    target = temp_staging / "data18.txt"
    def fault(phase, path):
        if phase == "pre_rename":
            path.write_bytes(b"")
    with pytest.raises(ChecksumIntegrityError):
        atomic_write_bytes(target, b"some content", repo_root=repo_root, fault_hook=fault)


# 19. Filename collision at identical timestamp has unique UUID temp name
def test_filename_collision_unique_temp_names(temp_staging: Path, repo_root: Path):
    target = temp_staging / "collision.txt"
    names_seen = []
    def fault(phase, path):
        if phase == "during_write":
            names_seen.append(path.name)
    atomic_write_bytes(target, b"data1", repo_root=repo_root, allow_overwrite=True, fault_hook=fault)
    atomic_write_bytes(target, b"data2", repo_root=repo_root, allow_overwrite=True, fault_hook=fault)
    assert len(names_seen) == 2
    assert names_seen[0] != names_seen[1]


# 20. Run directory collision handling
def test_run_directory_collision_safely_handled(temp_staging: Path, repo_root: Path):
    run_dir = temp_staging / "RUN_001"
    run_dir.mkdir(parents=True, exist_ok=True)
    f1 = run_dir / "file1.txt"
    f2 = run_dir / "file2.txt"
    p1, _ = atomic_write_text(f1, "run1", repo_root=repo_root)
    p2, _ = atomic_write_text(f2, "run2", repo_root=repo_root)
    assert p1.exists() and p2.exists()


# 21. Invalid Windows filename characters rejected
@pytest.mark.parametrize("invalid_char", ["<", ":"])
def test_invalid_windows_filename_characters_rejected(invalid_char: str):
    filename = f"bad{invalid_char}name.json"
    with pytest.raises(FilenameValidationError):
        validate_filename(filename)


# 22. Windows reserved device names rejected
@pytest.mark.parametrize("reserved", ["CON", "NUL", "COM1"])
def test_windows_reserved_device_names_rejected(reserved: str):
    with pytest.raises(FilenameValidationError, match="reserved device name"):
        validate_filename(f"{reserved}.json")


# 23. Excessive filename length (>255 chars) rejected
def test_excessive_filename_length_rejected():
    long_name = "a" * 256 + ".txt"
    with pytest.raises(FilenameValidationError, match="exceeds maximum limit"):
        validate_filename(long_name)


# 24. Relative path rejection
def test_relative_path_rejected(repo_root: Path):
    with pytest.raises(StagingPathViolation, match="Path must be absolute"):
        validate_safe_staging_path("relative/path/file.txt", repo_root=repo_root)


# 25. Repository path rejection
def test_repository_path_rejected(repo_root: Path):
    inside_repo = repo_root / "phase7" / "data.txt"
    with pytest.raises(StagingPathViolation, match="cannot reside within Git repository"):
        validate_safe_staging_path(inside_repo, repo_root=repo_root)


# 26. Repository root itself rejection
def test_repository_root_itself_rejected(repo_root: Path):
    with pytest.raises(StagingPathViolation, match="cannot reside within Git repository"):
        validate_safe_staging_path(repo_root, repo_root=repo_root)


# 27. UNC path rejection
def test_unc_path_rejected(repo_root: Path):
    unc_path = r"\\network_share\folder\file.txt"
    with pytest.raises(StagingPathViolation, match="UNC network paths are strictly prohibited"):
        validate_safe_staging_path(unc_path, repo_root=repo_root)


# 28. Device path rejection
def test_device_path_rejected(repo_root: Path):
    dev_path = r"\\.\PhysicalDrive0"
    with pytest.raises(StagingPathViolation, match="Device paths are strictly prohibited"):
        validate_safe_staging_path(dev_path, repo_root=repo_root)


# 29. Null byte path injection rejection
def test_null_byte_path_rejected(repo_root: Path):
    null_path = f"/staging/data\x00.txt"
    with pytest.raises(StagingPathViolation, match="Null byte injection"):
        validate_safe_staging_path(null_path, repo_root=repo_root)


# 30. Trailing dot or space filename rejected
def test_trailing_dot_or_space_rejected():
    with pytest.raises(FilenameValidationError, match="cannot end with dot or space"):
        validate_filename("filename. ")
    with pytest.raises(FilenameValidationError, match="cannot end with dot or space"):
        validate_filename("filename.")


# 31. Raw file overwrite refusal
def test_raw_file_overwrite_refused(temp_staging: Path, repo_root: Path):
    raw_file = temp_staging / "raw_RELIANCE.json"
    atomic_write_bytes(raw_file, b'{"v": 1}', repo_root=repo_root)
    with pytest.raises(FileOverwriteRefusedError):
        atomic_write_bytes(raw_file, b'{"v": 2}', repo_root=repo_root, allow_overwrite=False)


# 32. Normalized file overwrite refusal
def test_normalized_file_overwrite_refused(temp_staging: Path, repo_root: Path):
    norm_file = temp_staging / "norm_RELIANCE.csv"
    atomic_write_text(norm_file, "date,close\n2024-01-01,100\n", repo_root=repo_root)
    with pytest.raises(FileOverwriteRefusedError):
        atomic_write_text(norm_file, "date,close\n2024-01-01,105\n", repo_root=repo_root, allow_overwrite=False)


# 33. Manifest overwrite refusal
def test_manifest_overwrite_refused(temp_staging: Path, repo_root: Path):
    mf_file = temp_staging / "manifest_RELIANCE.json"
    atomic_write_text(mf_file, '{"status": "SUCCEEDED"}', repo_root=repo_root)
    with pytest.raises(FileOverwriteRefusedError):
        atomic_write_text(mf_file, '{"status": "FAILED"}', repo_root=repo_root, allow_overwrite=False)


# 34. Checkpoint overwrite policy allows explicit overwrite
def test_checkpoint_overwrite_allowed_with_flag(temp_staging: Path, repo_root: Path):
    chk_file = temp_staging / "checkpoint.json"
    atomic_write_text(chk_file, '{"completed": 1}', repo_root=repo_root, allow_overwrite=True)
    p, sha = atomic_write_text(chk_file, '{"completed": 2}', repo_root=repo_root, allow_overwrite=True)
    assert p.exists()
    assert "2" in p.read_text(encoding="utf-8")


# 35. Cleanup of temporary files preserves finalized evidence
def test_cleanup_preserves_finalized_evidence(temp_staging: Path, repo_root: Path):
    final_file = temp_staging / "final_evidence.csv"
    atomic_write_text(final_file, "data", repo_root=repo_root)
    stale_temp = temp_staging / ".tmp.999.partial"
    stale_temp.write_bytes(b"stale")
    os.utime(stale_temp, (time.time() - 7200, time.time() - 7200))

    cleaned = cleanup_stale_temporary_files(temp_staging, max_age_seconds=3600.0)
    assert stale_temp in cleaned
    assert final_file.exists(), "Final evidence must never be deleted by temporary cleanup"
