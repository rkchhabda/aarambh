"""Single-use, scope-bound authorization marker management for Phase 7 NIFTY 500 constituent snapshot pilot.

Strictly enforces:
- Immutable authorization record outside Git repository
- Frozen pilot scope (milestone 4.10A, CURRENT_NIFTY500_CONSTITUENT_SNAPSHOT_PILOT, index_name="NIFTY 500")
- Single-use policy (single_use=True) with atomic consumption before client creation
- Staging-root cryptographic binding (staging_root_hash)
- Zero reusable secrets, bypass values, or persistent authentication strings
- Rejection of markers inside Git, relative paths, symlinks/junctions into repo
"""

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, Optional, Union
import uuid

from phase7.sources.contracts import SnapshotAuthorizationRecord

SNAPSHOT_AUTHORIZATION_VERSION = "1.0"
SNAPSHOT_MILESTONE = "4.10A"
SNAPSHOT_SCOPE = "CURRENT_NIFTY500_CONSTITUENT_SNAPSHOT_PILOT"
SNAPSHOT_INDEX_NAME = "NIFTY 500"
DEFAULT_EXPIRES_MINUTES = 30
ACTIVE_MARKER_FILENAME = "snapshot_authorization.json"


def compute_staging_root_hash(staging_root: Union[Path, str]) -> str:
    """Compute deterministic SHA-256 hash for canonical resolved staging root path."""
    resolved = str(Path(staging_root).resolve()).strip()
    return hashlib.sha256(resolved.encode("utf-8")).hexdigest()


def compute_snapshot_authorization_hash(data: Dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash for canonical authorization record fields."""
    canonical = {
        "authorization_version": str(data["authorization_version"]),
        "expires_timestamp": str(data["expires_timestamp"]),
        "index_name": str(data["index_name"]),
        "issued_timestamp": str(data["issued_timestamp"]),
        "milestone": str(data["milestone"]),
        "nonce": str(data["nonce"]),
        "scope": str(data["scope"]),
        "single_use": bool(data["single_use"]),
        "staging_root_hash": str(data["staging_root_hash"]),
    }
    raw = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def find_repo_root(start_dir: Optional[Path] = None) -> Path:
    """Locate the enclosing Git repository root or fallback to start directory."""
    curr = (start_dir or Path.cwd()).resolve()
    while curr != curr.parent:
        if (curr / ".git").exists():
            return curr
        curr = curr.parent
    return (start_dir or Path.cwd()).resolve()


def validate_staging_root(
    staging_root: Union[Path, str], repo_root: Optional[Path] = None
) -> Path:
    """Validate that staging root is absolute and strictly outside the Git repository."""
    s_path = Path(staging_root)
    if not s_path.is_absolute():
        raise ValueError(f"Staging root path must be absolute, got: '{staging_root}'")

    s_resolved = s_path.resolve()
    r_resolved = (repo_root or find_repo_root()).resolve()

    if s_resolved == r_resolved or r_resolved in s_resolved.parents:
        raise ValueError(
            f"Staging root '{s_resolved}' must be strictly external and cannot be located within Git repository '{r_resolved}'."
        )

    return s_resolved


def validate_snapshot_marker_path(
    marker_path: Union[Path, str],
    staging_root: Union[Path, str],
    repo_root: Optional[Path] = None,
) -> Path:
    """Ensure authorization marker path is absolute, outside Git, and under staging authorization dir."""
    m_path = Path(marker_path)
    if not m_path.is_absolute():
        raise ValueError(f"Authorization marker path must be absolute, got: '{marker_path}'")

    m_resolved = m_path.resolve()
    s_resolved = validate_staging_root(staging_root, repo_root=repo_root)

    expected_dir = (s_resolved / "authorization").resolve()
    if m_resolved.parent != expected_dir:
        raise ValueError(
            f"Authorization marker must reside directly in staging authorization directory '{expected_dir}', got: '{m_resolved.parent}'"
        )

    return m_resolved


def create_snapshot_authorization(
    staging_root: Union[Path, str],
    expires_minutes: int = DEFAULT_EXPIRES_MINUTES,
    repo_root: Optional[Path] = None,
) -> tuple[Path, SnapshotAuthorizationRecord]:
    """Create a single-use authorization marker for Milestone 4.10A constituent snapshot."""
    valid_staging = validate_staging_root(staging_root, repo_root=repo_root)
    auth_dir = valid_staging / "authorization"
    auth_dir.mkdir(parents=True, exist_ok=True)

    marker_path = auth_dir / ACTIVE_MARKER_FILENAME
    if marker_path.exists():
        raise FileExistsError(
            f"Active authorization marker already exists at '{marker_path}'. Multiple active markers are strictly forbidden."
        )

    now_utc = datetime.now(timezone.utc)
    expires_utc = now_utc + timedelta(minutes=expires_minutes)

    staging_hash = compute_staging_root_hash(valid_staging)
    nonce = str(uuid.uuid4())

    payload: Dict[str, Any] = {
        "authorization_version": SNAPSHOT_AUTHORIZATION_VERSION,
        "milestone": SNAPSHOT_MILESTONE,
        "scope": SNAPSHOT_SCOPE,
        "index_name": SNAPSHOT_INDEX_NAME,
        "staging_root_hash": staging_hash,
        "issued_timestamp": now_utc.isoformat(),
        "expires_timestamp": expires_utc.isoformat(),
        "single_use": True,
        "nonce": nonce,
    }

    auth_hash = compute_snapshot_authorization_hash(payload)
    payload["authorization_hash"] = auth_hash

    # Atomic write via temp file
    temp_path = marker_path.with_suffix(f".tmp.{uuid.uuid4().hex}")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temp_path, marker_path)

    record = SnapshotAuthorizationRecord(**payload)
    return marker_path, record


def load_and_validate_snapshot_authorization(
    marker_path: Union[Path, str],
    staging_root: Union[Path, str],
    expected_index: str = "NIFTY 500",
    repo_root: Optional[Path] = None,
) -> SnapshotAuthorizationRecord:
    """Load, verify cryptographic authenticity, scope, single-use policy, and expiration."""
    valid_marker = validate_snapshot_marker_path(marker_path, staging_root, repo_root=repo_root)
    if not valid_marker.exists():
        raise FileNotFoundError(f"Authorization marker not found at '{valid_marker}'.")

    raw_text = valid_marker.read_text(encoding="utf-8")
    try:
        data = json.loads(raw_text)
    except Exception as e:
        raise ValueError(f"Authorization marker contains malformed JSON: {e}") from e

    required_keys = [
        "authorization_version",
        "milestone",
        "scope",
        "index_name",
        "staging_root_hash",
        "issued_timestamp",
        "expires_timestamp",
        "single_use",
        "nonce",
        "authorization_hash",
    ]
    missing = [k for k in required_keys if k not in data]
    if missing:
        raise ValueError(f"Authorization marker missing required fields: {missing}")

    if data["milestone"] != SNAPSHOT_MILESTONE:
        raise ValueError(
            f"Authorization marker milestone mismatch: expected '{SNAPSHOT_MILESTONE}', got '{data['milestone']}'"
        )

    if data["scope"] != SNAPSHOT_SCOPE:
        raise ValueError(
            f"Authorization marker scope mismatch: expected '{SNAPSHOT_SCOPE}', got '{data['scope']}'"
        )

    if data["index_name"].upper() != expected_index.upper():
        raise ValueError(
            f"Authorization marker index mismatch: expected '{expected_index}', got '{data['index_name']}'"
        )

    if not data["single_use"]:
        raise ValueError("Authorization marker must have single_use=True.")

    s_resolved = validate_staging_root(staging_root, repo_root=repo_root)
    computed_staging_hash = compute_staging_root_hash(s_resolved)
    if data["staging_root_hash"] != computed_staging_hash:
        raise ValueError(
            "Authorization marker bound to a different staging root. Path tampering detected."
        )

    computed_auth_hash = compute_snapshot_authorization_hash(data)
    if data["authorization_hash"] != computed_auth_hash:
        raise ValueError("Authorization marker hash mismatch. Content tampering detected.")

    try:
        expires_ts = datetime.fromisoformat(data["expires_timestamp"])
    except Exception as e:
        raise ValueError(f"Invalid expires_timestamp format: {e}") from e

    now_utc = datetime.now(timezone.utc)
    if now_utc > expires_ts:
        raise PermissionError(
            f"Authorization marker expired at '{expires_ts.isoformat()}'. Current time is '{now_utc.isoformat()}'."
        )

    return SnapshotAuthorizationRecord(**data)


def consume_snapshot_authorization(marker_path: Union[Path, str]) -> Path:
    """Atomically consume single-use authorization marker before client creation."""
    m_path = Path(marker_path).resolve()
    if not m_path.exists():
        raise FileNotFoundError(f"Cannot consume non-existent authorization marker at '{m_path}'.")

    now_utc_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    consumed_name = f"snapshot_authorization.consumed.{now_utc_str}.json"
    consumed_path = m_path.parent / consumed_name

    # Atomic rename prevents reuse
    os.replace(m_path, consumed_path)

    if m_path.exists():
        raise RuntimeError("Consumption failed: active authorization marker still exists.")

    return consumed_path


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for constituent snapshot authorization marker management."""
    parser = argparse.ArgumentParser(
        description="Phase 7 NIFTY 500 Constituent Snapshot Pilot Single-Use Authorization Manager"
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    create_parser = subparsers.add_parser("create", help="Create a single-use snapshot authorization marker")
    create_parser.add_argument(
        "--staging-root",
        required=True,
        help="Absolute path to external staging root directory",
    )
    create_parser.add_argument(
        "--expires-minutes",
        type=int,
        default=DEFAULT_EXPIRES_MINUTES,
        help=f"Validity duration in minutes (default: {DEFAULT_EXPIRES_MINUTES})",
    )

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point for constituent authorization marker generation."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "create":
        try:
            marker_path, record = create_snapshot_authorization(
                staging_root=args.staging_root,
                expires_minutes=args.expires_minutes,
            )
            print("SNAPSHOT AUTHORIZATION MARKER CREATED")
            print(f"Milestone: {record.milestone}")
            print(f"Scope: {record.scope}")
            print(f"Index Name: {record.index_name}")
            print(f"Single Use: {record.single_use}")
            print(f"Staging Root: {args.staging_root}")
            print(f"Expires: {record.expires_timestamp}")
            print(f"Marker Path: {marker_path}")
            print(f"Authorization Hash: {record.authorization_hash}")
            return 0
        except Exception as e:
            print(f"ERROR: Failed to create snapshot authorization marker: {e}", file=sys.stderr)
            return 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
