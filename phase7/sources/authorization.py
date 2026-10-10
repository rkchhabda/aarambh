"""Single-use, scope-bound authorization marker management for Phase 7 live pilot.

Strictly enforces:
- Immutable authorization record outside Git repository
- Frozen pilot scope (milestone 4.9, FIVE_STOCK_NSE_LIVE_PILOT, 5 approved symbols, Jan 2024, 1d)
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
from typing import Any, Dict, List, Optional, Union
import uuid

from phase7.sources.contracts import PilotAuthorizationRecord

AUTHORIZATION_VERSION = "1.0"
PILOT_MILESTONE = "4.9"
PILOT_SCOPE = "FIVE_STOCK_NSE_LIVE_PILOT"
PILOT_APPROVED_SYMBOLS = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"]
PILOT_START_DATE = "2024-01-01"
PILOT_END_DATE = "2024-01-31"
PILOT_INTERVAL = "1d"
DEFAULT_EXPIRES_MINUTES = 30
ACTIVE_MARKER_FILENAME = "pilot_authorization.json"


def compute_staging_root_hash(staging_root: Union[Path, str]) -> str:
    """Compute deterministic SHA-256 hash for canonical resolved staging root path."""
    resolved = str(Path(staging_root).resolve()).strip()
    return hashlib.sha256(resolved.encode("utf-8")).hexdigest()


def compute_authorization_hash(data: Dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash for canonical authorization record fields."""
    canonical = {
        "authorization_version": str(data["authorization_version"]),
        "milestone": str(data["milestone"]),
        "scope": str(data["scope"]),
        "approved_symbols": list(data["approved_symbols"]),
        "start_date": str(data["start_date"]),
        "end_date": str(data["end_date"]),
        "interval": str(data["interval"]),
        "staging_root_hash": str(data["staging_root_hash"]),
        "issued_timestamp": str(data["issued_timestamp"]),
        "expires_timestamp": str(data["expires_timestamp"]),
        "single_use": bool(data["single_use"]),
        "nonce": str(data["nonce"]),
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


def validate_authorization_marker_path(
    marker_path: Union[Path, str],
    staging_root: Union[Path, str],
    repo_root: Optional[Path] = None,
) -> Path:
    """Ensure authorization marker path is absolute, outside Git, and under staging authorization dir."""
    m_path = Path(marker_path)
    if not m_path.is_absolute():
        raise ValueError(f"Authorization marker path must be absolute, got: '{marker_path}'")

    m_resolved = m_path.resolve()
    r_resolved = (repo_root or find_repo_root()).resolve()

    # Reject if inside Git repository or data/ of Git repository
    if m_resolved == r_resolved or r_resolved in m_resolved.parents:
        raise ValueError(
            f"Authorization marker '{m_resolved}' cannot reside inside Git repository '{r_resolved}'."
        )

    # Must reside under staging_root/authorization
    s_resolved = Path(staging_root).resolve()
    expected_auth_dir = s_resolved / "authorization"
    if m_resolved.parent != expected_auth_dir:
        raise ValueError(
            f"Authorization marker must reside directly within '{expected_auth_dir}', got: '{m_resolved.parent}'."
        )

    # Check consumed pattern
    if m_resolved.name.startswith("pilot_authorization.consumed."):
        raise PermissionError(
            f"Authorization marker '{m_resolved.name}' has already been consumed and cannot be reused."
        )

    if m_resolved.name != ACTIVE_MARKER_FILENAME:
        raise ValueError(
            f"Active authorization marker filename must be '{ACTIVE_MARKER_FILENAME}', got: '{m_resolved.name}'."
        )

    return m_resolved


def create_pilot_authorization(
    staging_root: Union[Path, str],
    expires_minutes: int = DEFAULT_EXPIRES_MINUTES,
    repo_root: Optional[Path] = None,
) -> Path:
    """Create a single-use, scope-bound pilot authorization marker outside Git."""
    if expires_minutes <= 0:
        raise ValueError(f"expires_minutes must be positive, got: {expires_minutes}")

    valid_staging = validate_staging_root(staging_root, repo_root=repo_root)
    auth_dir = valid_staging / "authorization"
    auth_dir.mkdir(parents=True, exist_ok=True)

    active_file = auth_dir / ACTIVE_MARKER_FILENAME
    if active_file.exists():
        raise FileExistsError(
            f"Active authorization marker already exists at '{active_file}'. "
            "Refusing to overwrite existing active marker."
        )

    staging_hash = compute_staging_root_hash(valid_staging)
    issued_dt = datetime.now(timezone.utc)
    expires_dt = issued_dt + timedelta(minutes=expires_minutes)

    nonce = str(uuid.uuid4())

    record_payload: Dict[str, Any] = {
        "authorization_version": AUTHORIZATION_VERSION,
        "milestone": PILOT_MILESTONE,
        "scope": PILOT_SCOPE,
        "approved_symbols": PILOT_APPROVED_SYMBOLS,
        "start_date": PILOT_START_DATE,
        "end_date": PILOT_END_DATE,
        "interval": PILOT_INTERVAL,
        "staging_root_hash": staging_hash,
        "issued_timestamp": issued_dt.isoformat(),
        "expires_timestamp": expires_dt.isoformat(),
        "single_use": True,
        "nonce": nonce,
    }

    auth_hash = compute_authorization_hash(record_payload)
    record_payload["authorization_hash"] = auth_hash

    # Write marker atomically
    temp_file = auth_dir / f".tmp_{nonce}.json"
    temp_file.write_text(json.dumps(record_payload, indent=2), encoding="utf-8")
    os.replace(str(temp_file), str(active_file))

    return active_file


def load_and_validate_authorization(
    marker_path: Union[Path, str],
    staging_root: Union[Path, str],
    expected_symbols: Optional[List[str]] = None,
    expected_start: Optional[str] = None,
    expected_end: Optional[str] = None,
    expected_interval: Optional[str] = None,
    repo_root: Optional[Path] = None,
) -> PilotAuthorizationRecord:
    """Load, verify, and validate all fields and constraints of an authorization marker."""
    m_path = Path(marker_path)
    if not m_path.exists():
        raise FileNotFoundError(f"Authorization marker not found at '{marker_path}'.")

    valid_path = validate_authorization_marker_path(
        m_path, staging_root=staging_root, repo_root=repo_root
    )

    try:
        content = valid_path.read_text(encoding="utf-8")
        data = json.loads(content)
    except Exception as exc:
        raise ValueError(f"Malformed authorization marker JSON in '{valid_path}': {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Malformed authorization marker: root must be a JSON object.")

    required_fields = [
        "authorization_version",
        "milestone",
        "scope",
        "approved_symbols",
        "start_date",
        "end_date",
        "interval",
        "staging_root_hash",
        "issued_timestamp",
        "expires_timestamp",
        "single_use",
        "nonce",
        "authorization_hash",
    ]
    for rf in required_fields:
        if rf not in data:
            raise ValueError(f"Missing required authorization field '{rf}'.")

    if data["authorization_version"] != AUTHORIZATION_VERSION:
        raise PermissionError(
            f"Invalid authorization version '{data['authorization_version']}', expected '{AUTHORIZATION_VERSION}'."
        )

    if data["milestone"] != PILOT_MILESTONE:
        raise PermissionError(
            f"Invalid milestone '{data['milestone']}', expected '{PILOT_MILESTONE}'."
        )

    if data["scope"] != PILOT_SCOPE:
        raise PermissionError(
            f"Invalid scope '{data['scope']}', expected '{PILOT_SCOPE}'."
        )

    if not isinstance(data["approved_symbols"], list):
        raise ValueError("approved_symbols must be a list.")
    if data["approved_symbols"] != PILOT_APPROVED_SYMBOLS:
        raise PermissionError(
            f"Approved symbols mismatch: got {data['approved_symbols']}, expected {PILOT_APPROVED_SYMBOLS}."
        )
    if expected_symbols is not None and expected_symbols != PILOT_APPROVED_SYMBOLS:
        raise PermissionError(
            f"Requested symbols {expected_symbols} do not match approved symbols {PILOT_APPROVED_SYMBOLS}."
        )

    if data["start_date"] != PILOT_START_DATE:
        raise PermissionError(
            f"Invalid start_date '{data['start_date']}', expected '{PILOT_START_DATE}'."
        )
    if expected_start is not None and expected_start != PILOT_START_DATE:
        raise PermissionError(
            f"Requested start date '{expected_start}' does not match approved start date '{PILOT_START_DATE}'."
        )

    if data["end_date"] != PILOT_END_DATE:
        raise PermissionError(
            f"Invalid end_date '{data['end_date']}', expected '{PILOT_END_DATE}'."
        )
    if expected_end is not None and expected_end != PILOT_END_DATE:
        raise PermissionError(
            f"Requested end date '{expected_end}' does not match approved end date '{PILOT_END_DATE}'."
        )

    if data["interval"] != PILOT_INTERVAL:
        raise PermissionError(
            f"Invalid interval '{data['interval']}', expected '{PILOT_INTERVAL}'."
        )
    if expected_interval is not None and expected_interval != PILOT_INTERVAL:
        raise PermissionError(
            f"Requested interval '{expected_interval}' does not match approved interval '{PILOT_INTERVAL}'."
        )

    expected_staging_hash = compute_staging_root_hash(staging_root)
    if data["staging_root_hash"] != expected_staging_hash:
        raise PermissionError(
            "Staging root hash mismatch: authorization marker is bound to another staging directory."
        )

    if data["single_use"] is not True:
        raise PermissionError(
            f"Authorization marker single_use must be strictly True, got: {data['single_use']}."
        )

    try:
        exp_dt = datetime.fromisoformat(data["expires_timestamp"])
    except Exception as exc:
        raise ValueError(f"Malformed expires_timestamp '{data['expires_timestamp']}': {exc}") from exc

    if exp_dt.tzinfo is None:
        exp_dt = exp_dt.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > exp_dt:
        raise PermissionError(
            f"Authorization marker expired at '{data['expires_timestamp']}'."
        )

    recomputed_hash = compute_authorization_hash(data)
    if data["authorization_hash"] != recomputed_hash:
        raise PermissionError(
            "Invalid authorization hash: marker has been tampered with or corrupted."
        )

    return PilotAuthorizationRecord(
        authorization_version=data["authorization_version"],
        milestone=data["milestone"],
        scope=data["scope"],
        approved_symbols=data["approved_symbols"],
        start_date=data["start_date"],
        end_date=data["end_date"],
        interval=data["interval"],
        staging_root_hash=data["staging_root_hash"],
        issued_timestamp=data["issued_timestamp"],
        expires_timestamp=data["expires_timestamp"],
        single_use=data["single_use"],
        nonce=data["nonce"],
        authorization_hash=data["authorization_hash"],
    )


def consume_authorization(marker_path: Union[Path, str]) -> Path:
    """Atomically consume the authorization marker by renaming it to consumed filename pattern."""
    m_path = Path(marker_path).resolve()
    if not m_path.exists():
        raise FileNotFoundError(f"Cannot consume authorization: marker not found at '{m_path}'.")

    if m_path.name.startswith("pilot_authorization.consumed."):
        raise PermissionError(f"Authorization marker '{m_path.name}' is already consumed.")

    ts_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    consumed_name = f"pilot_authorization.consumed.{ts_str}.json"
    consumed_path = m_path.parent / consumed_name

    try:
        os.replace(str(m_path), str(consumed_path))
    except Exception as exc:
        raise RuntimeError(
            f"AUTHORIZATION_CONSUMPTION_FAILED: Failed to atomically rename marker: {exc}"
        ) from exc

    if m_path.exists():
        raise RuntimeError(
            "AUTHORIZATION_CONSUMPTION_FAILED: Active authorization marker still exists after rename."
        )

    if not consumed_path.exists():
        raise RuntimeError(
            "AUTHORIZATION_CONSUMPTION_FAILED: Consumed authorization marker was not created."
        )

    return consumed_path


def build_authorization_parser() -> argparse.ArgumentParser:
    """Build CLI parser for phase7.sources.authorization."""
    parser = argparse.ArgumentParser(
        prog="phase7.sources.authorization",
        description="Phase 7 single-use pilot authorization management CLI.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to execute")

    create_parser = subparsers.add_parser(
        "create",
        help="Create a single-use scope-bound pilot authorization marker outside Git.",
    )
    create_parser.add_argument(
        "--staging-root",
        type=str,
        required=True,
        help="External staging root directory path (must be outside Git repository)",
    )
    create_parser.add_argument(
        "--expires-minutes",
        type=int,
        default=DEFAULT_EXPIRES_MINUTES,
        help=f"Validity duration in minutes (default: {DEFAULT_EXPIRES_MINUTES})",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for authorization marker generation."""
    parser = build_authorization_parser()
    args = parser.parse_args(argv)

    if args.subcommand is None:
        parser.print_help()
        return 0

    if args.subcommand == "create":
        try:
            marker_file = create_pilot_authorization(
                staging_root=args.staging_root,
                expires_minutes=args.expires_minutes,
            )
            record = load_and_validate_authorization(marker_file, staging_root=args.staging_root)
            print("AUTHORIZATION MARKER CREATED")
            print(f"Milestone: {record.milestone}")
            print(f"Scope: {record.scope}")
            print(f"Symbols: {','.join(record.approved_symbols)}")
            print(f"Date Window: {record.start_date} to {record.end_date}")
            print(f"Interval: {record.interval}")
            print(f"Single Use: {record.single_use}")
            print(f"Staging Root: {args.staging_root}")
            print(f"Expires: {record.expires_timestamp}")
            print(f"Marker Path: {marker_file}")
            print(f"Authorization Hash: {record.authorization_hash}")
            return 0
        except Exception as exc:
            print(f"AUTHORIZATION CREATION ERROR: {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
