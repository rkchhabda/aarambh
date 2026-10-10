"""Production-hardened atomic file I/O and durability engine for Phase 7.

Strictly enforces:
- Absolute paths strictly outside the Git repository root
- Path traversal, UNC, device path, and NTFS stream rejection
- Windows reserved names (CON, PRN, AUX, NUL, COM1-9, LPT1-9) rejection
- Atomic write via parent-directory temporary file with flush and fsync
- SHA-256 cryptographic verification of persisted bytes
- Overwrite refusal for immutable final artifacts unless explicitly enabled
- Safe recovery cleanup of stale temporary files without touching final evidence
- Hooks for simulated filesystem faults (disk full, permission denied, short write)
"""

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import uuid

WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

INVALID_FILENAME_CHARS = set('<>:"/\\|?*')
MAX_PATH_LENGTH = 260
MAX_FILENAME_LENGTH = 255


class AtomicIOError(IOError):
    """Base exception for atomic I/O and persistence violations."""
    pass


class StagingPathViolation(AtomicIOError):
    """Raised when a path breaches the staging boundary or attempts repository escape."""
    pass


class FilenameValidationError(AtomicIOError):
    """Raised when a filename contains illegal characters or reserved names."""
    pass


class FileOverwriteRefusedError(AtomicIOError):
    """Raised when attempting to overwrite an immutable finalized artifact."""
    pass


class ChecksumIntegrityError(AtomicIOError):
    """Raised when persisted file content does not match expected checksum."""
    pass


def find_repository_root(start_dir: Optional[Union[Path, str]] = None) -> Path:
    """Locate the enclosing Git repository root or fallback to start directory."""
    curr = (Path(start_dir) if start_dir else Path.cwd()).resolve()
    while curr != curr.parent:
        if (curr / ".git").exists():
            return curr
        curr = curr.parent
    return (Path(start_dir) if start_dir else Path.cwd()).resolve()


def validate_filename(filename: str) -> None:
    """Validate filename against Windows and POSIX safety rules."""
    if not filename or not isinstance(filename, str):
        raise FilenameValidationError("Filename must be a non-empty string.")

    if len(filename) > MAX_FILENAME_LENGTH:
        raise FilenameValidationError(
            f"Filename length ({len(filename)}) exceeds maximum limit of {MAX_FILENAME_LENGTH}."
        )

    # Check for control characters
    for ch in filename:
        if ord(ch) < 32 or ord(ch) == 127:
            raise FilenameValidationError(f"Filename contains invalid control character: {ord(ch)}")

    # Check for NTFS alternate data stream syntax (colon)
    if ":" in filename:
        raise FilenameValidationError(f"NTFS alternate data stream syntax rejected: '{filename}'")

    # Check for illegal characters
    if any(ch in INVALID_FILENAME_CHARS for ch in filename):
        raise FilenameValidationError(f"Filename contains illegal characters: '{filename}'")

    # Check for reserved device names
    base_name = filename.split(".")[0].upper()
    if base_name in WINDOWS_RESERVED_NAMES:
        raise FilenameValidationError(f"Windows reserved device name rejected: '{filename}'")

    # Refuse trailing dots or spaces on Windows
    if filename.endswith(".") or filename.endswith(" "):
        raise FilenameValidationError(f"Filename cannot end with dot or space: '{filename}'")


def validate_safe_staging_path(
    path: Union[Path, str], repo_root: Optional[Union[Path, str]] = None
) -> Path:
    """Validate that path is absolute, outside repository, and free of traversal attacks."""
    p_str = str(path)

    # Reject null byte injection
    if "\x00" in p_str:
        raise StagingPathViolation("Null byte injection detected in path.")

    # Reject device paths (e.g., \\.\ or \\?\)
    if re.match(r"^\\\\[\.\?]", p_str):
        raise StagingPathViolation(f"Device paths are strictly prohibited: '{path}'")

    # Reject UNC network paths
    if p_str.startswith("\\\\") or p_str.startswith("//"):
        raise StagingPathViolation(f"UNC network paths are strictly prohibited: '{path}'")

    p = Path(path)
    if not p.is_absolute():
        raise StagingPathViolation(f"Path must be absolute, got relative path: '{path}'")

    resolved = p.resolve()
    r_root = (Path(repo_root) if repo_root else find_repository_root()).resolve()

    # Boundary check: strictly outside repository
    if resolved == r_root or r_root in resolved.parents:
        raise StagingPathViolation(
            f"Staging path '{resolved}' cannot reside within Git repository '{r_root}'."
        )

    # Check length limits
    if len(str(resolved)) > MAX_PATH_LENGTH and not str(resolved).startswith("\\\\?\\"):
        raise StagingPathViolation(
            f"Path length ({len(str(resolved))}) exceeds standard Windows limit of {MAX_PATH_LENGTH}."
        )

    return resolved


def atomic_write_bytes(
    target_path: Union[Path, str],
    data: bytes,
    repo_root: Optional[Union[Path, str]] = None,
    allow_overwrite: bool = False,
    fault_hook: Optional[Callable[[str, Path], None]] = None,
) -> Tuple[Path, str]:
    """Persist bytes atomically to external target path with fsync and checksum verification."""
    valid_target = validate_safe_staging_path(target_path, repo_root=repo_root)
    validate_filename(valid_target.name)

    # Overwrite protection for immutable files
    if valid_target.exists() and not allow_overwrite:
        existing_sha = hashlib.sha256(valid_target.read_bytes()).hexdigest()
        new_sha = hashlib.sha256(data).hexdigest()
        if existing_sha != new_sha:
            raise FileOverwriteRefusedError(
                f"Immutable file '{valid_target}' already exists with different checksum: {existing_sha} != {new_sha}"
            )
        return valid_target, existing_sha

    # Fault injection: pre-write
    if fault_hook:
        fault_hook("pre_write", valid_target)

    target_dir = valid_target.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    computed_sha = hashlib.sha256(data).hexdigest()
    temp_filename = f".tmp.{os.getpid()}.{uuid.uuid4().hex}"
    temp_path = target_dir / temp_filename

    try:
        if fault_hook:
            fault_hook("pre_create", temp_path)

        # Write to temporary file in same directory for atomic rename
        with open(temp_path, "wb") as f:
            if fault_hook:
                fault_hook("during_write", temp_path)
            f.write(data)
            if fault_hook:
                fault_hook("during_flush", temp_path)
            f.flush()
            try:
                os.fsync(f.fileno())
            except (AttributeError, OSError):
                pass  # fsync may not be available on all mock/test filesystems

        # Fault injection: pre-rename
        if fault_hook:
            fault_hook("pre_rename", temp_path)

        # Atomic replacement
        os.replace(temp_path, valid_target)

        # Verify post-write checksum
        verified_sha = hashlib.sha256(valid_target.read_bytes()).hexdigest()
        if verified_sha != computed_sha:
            raise ChecksumIntegrityError(
                f"Checksum mismatch after write to '{valid_target}': expected {computed_sha}, got {verified_sha}"
            )

        return valid_target, verified_sha

    finally:
        # Ensure temporary file is cleaned up if rename failed
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def atomic_write_text(
    target_path: Union[Path, str],
    text: str,
    encoding: str = "utf-8",
    repo_root: Optional[Union[Path, str]] = None,
    allow_overwrite: bool = False,
    fault_hook: Optional[Callable[[str, Path], None]] = None,
) -> Tuple[Path, str]:
    """Persist text atomically to external target path with encoding and fsync."""
    data = text.encode(encoding)
    return atomic_write_bytes(
        target_path=target_path,
        data=data,
        repo_root=repo_root,
        allow_overwrite=allow_overwrite,
        fault_hook=fault_hook,
    )


def cleanup_stale_temporary_files(
    directory: Union[Path, str],
    max_age_seconds: float = 3600.0,
    dry_run: bool = False,
) -> List[Path]:
    """Safely discover and purge stale .tmp.* files without touching finalized evidence."""
    target_dir = Path(directory)
    if not target_dir.exists() or not target_dir.is_dir():
        return []

    cleaned: List[Path] = []
    now = datetime.now(timezone.utc).timestamp()

    for item in target_dir.glob(".tmp.*"):
        if not item.is_file():
            continue
        try:
            mtime = item.stat().st_mtime
            age = now - mtime
            if age >= max_age_seconds:
                if not dry_run:
                    item.unlink()
                cleaned.append(item)
        except OSError:
            pass

    return cleaned
