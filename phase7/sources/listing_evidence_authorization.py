"""Single-use, scope-bound authorization marker management for Phase 7 official listing date evidence pilot.

Strictly enforces:
- Milestone 4.10C-2 scope binding (OFFICIAL_LISTING_DATE_EVIDENCE_PILOT)
- Symbol binding (PREMIERENE / Premier Energies Limited / NSE)
- Requested period end binding (2024-03-31)
- Approved domains binding (nsearchives.nseindia.com, nseindia.com, sebi.gov.in, bseindia.com)
- Maximum request count ceiling (5)
- Staging-root cryptographic binding (outside Git repository)
- Single-use policy (single_use=True) with atomic consumption before first request
- Zero market-price, batch resume, or model authorizations
"""

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

EVIDENCE_AUTHORIZATION_VERSION = "1.0"
EVIDENCE_MILESTONE = "4.10C-2"
EVIDENCE_SCOPE = "OFFICIAL_LISTING_DATE_EVIDENCE_PILOT"
EVIDENCE_REQUIRED_SYMBOL = "PREMIERENE"
EVIDENCE_REQUIRED_SECURITY_NAME = "Premier Energies Limited"
EVIDENCE_REQUIRED_EXCHANGE = "NSE"
EVIDENCE_REQUIRED_REQUESTED_END = "2024-03-31"
APPROVED_EVIDENCE_DOMAINS = [
    "nsearchives.nseindia.com",
    "nseindia.com",
    "sebi.gov.in",
    "bseindia.com",
]
MAXIMUM_REQUEST_COUNT = 5
DEFAULT_EXPIRES_MINUTES = 30
ACTIVE_MARKER_FILENAME = "listing_evidence_authorization.json"


@dataclass(frozen=True)
class ListingEvidenceAuthorizationRecord:
    authorization_version: str
    milestone: str
    scope: str
    symbol: str
    security_name: str
    exchange: str
    requested_period_end: str
    approved_domains: List[str]
    maximum_request_count: int
    staging_root_hash: str
    issued_timestamp: str
    expires_timestamp: str
    single_use: bool
    nonce: str
    authorization_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_staging_root_hash(staging_root: Union[Path, str]) -> str:
    """Compute deterministic SHA-256 hash for canonical resolved staging root path."""
    resolved = str(Path(staging_root).resolve()).strip()
    return hashlib.sha256(resolved.encode("utf-8")).hexdigest()


def compute_listing_evidence_authorization_hash(data: Dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash for canonical evidence authorization fields."""
    canonical = {
        "approved_domains": sorted(list(data["approved_domains"])),
        "authorization_version": str(data["authorization_version"]),
        "exchange": str(data["exchange"]),
        "expires_timestamp": str(data["expires_timestamp"]),
        "issued_timestamp": str(data["issued_timestamp"]),
        "maximum_request_count": int(data["maximum_request_count"]),
        "milestone": str(data["milestone"]),
        "nonce": str(data["nonce"]),
        "requested_period_end": str(data["requested_period_end"]),
        "scope": str(data["scope"]),
        "security_name": str(data["security_name"]),
        "single_use": bool(data["single_use"]),
        "staging_root_hash": str(data["staging_root_hash"]),
        "symbol": str(data["symbol"]),
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


def validate_listing_evidence_marker_path(
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


def create_listing_evidence_authorization(
    staging_root: Union[Path, str],
    symbol: str = EVIDENCE_REQUIRED_SYMBOL,
    security_name: str = EVIDENCE_REQUIRED_SECURITY_NAME,
    exchange: str = EVIDENCE_REQUIRED_EXCHANGE,
    requested_end: str = EVIDENCE_REQUIRED_REQUESTED_END,
    expires_minutes: int = DEFAULT_EXPIRES_MINUTES,
    repo_root: Optional[Path] = None,
) -> Tuple[Path, ListingEvidenceAuthorizationRecord]:
    """Create a single-use authorization marker for Milestone 4.10C-2 listing date evidence pilot."""
    valid_staging = validate_staging_root(staging_root, repo_root=repo_root)
    auth_dir = valid_staging / "authorization"
    auth_dir.mkdir(parents=True, exist_ok=True)

    marker_path = auth_dir / ACTIVE_MARKER_FILENAME
    if marker_path.exists():
        raise FileExistsError(
            f"Active authorization marker already exists at '{marker_path}'. Multiple active markers are strictly forbidden."
        )

    if symbol != EVIDENCE_REQUIRED_SYMBOL:
        raise ValueError(f"Unauthorized symbol for evidence pilot: {symbol} != {EVIDENCE_REQUIRED_SYMBOL}")
    if security_name != EVIDENCE_REQUIRED_SECURITY_NAME:
        raise ValueError(f"Unauthorized security_name: {security_name} != {EVIDENCE_REQUIRED_SECURITY_NAME}")
    if exchange != EVIDENCE_REQUIRED_EXCHANGE:
        raise ValueError(f"Unauthorized exchange: {exchange} != {EVIDENCE_REQUIRED_EXCHANGE}")
    if requested_end != EVIDENCE_REQUIRED_REQUESTED_END:
        raise ValueError(f"Unauthorized requested_end: {requested_end} != {EVIDENCE_REQUIRED_REQUESTED_END}")

    now_utc = datetime.now(timezone.utc)
    expires_utc = now_utc + timedelta(minutes=expires_minutes)

    staging_hash = compute_staging_root_hash(valid_staging)
    nonce = str(uuid.uuid4())

    payload: Dict[str, Any] = {
        "authorization_version": EVIDENCE_AUTHORIZATION_VERSION,
        "milestone": EVIDENCE_MILESTONE,
        "scope": EVIDENCE_SCOPE,
        "symbol": symbol,
        "security_name": security_name,
        "exchange": exchange,
        "requested_period_end": requested_end,
        "approved_domains": sorted(APPROVED_EVIDENCE_DOMAINS),
        "maximum_request_count": MAXIMUM_REQUEST_COUNT,
        "staging_root_hash": staging_hash,
        "issued_timestamp": now_utc.isoformat(),
        "expires_timestamp": expires_utc.isoformat(),
        "single_use": True,
        "nonce": nonce,
    }

    auth_hash = compute_listing_evidence_authorization_hash(payload)
    payload["authorization_hash"] = auth_hash

    # Atomic write via temp file
    temp_path = marker_path.with_suffix(f".tmp.{uuid.uuid4().hex}")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temp_path, marker_path)

    record = ListingEvidenceAuthorizationRecord(**payload)
    return marker_path, record


def load_and_validate_listing_evidence_authorization(
    marker_path: Union[Path, str],
    staging_root: Union[Path, str],
    expected_symbol: str = EVIDENCE_REQUIRED_SYMBOL,
    expected_exchange: str = EVIDENCE_REQUIRED_EXCHANGE,
    repo_root: Optional[Path] = None,
) -> ListingEvidenceAuthorizationRecord:
    """Load, verify cryptographic authenticity, scope, single-use policy, and expiration."""
    valid_marker = validate_listing_evidence_marker_path(marker_path, staging_root, repo_root=repo_root)
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
        "symbol",
        "security_name",
        "exchange",
        "requested_period_end",
        "approved_domains",
        "maximum_request_count",
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

    if data["milestone"] != EVIDENCE_MILESTONE:
        raise ValueError(
            f"Authorization marker milestone mismatch: expected '{EVIDENCE_MILESTONE}', got '{data['milestone']}'"
        )

    if data["scope"] != EVIDENCE_SCOPE:
        raise ValueError(
            f"Authorization marker scope mismatch: expected '{EVIDENCE_SCOPE}', got '{data['scope']}'"
        )

    if data["symbol"] != expected_symbol:
        raise ValueError(
            f"Authorization marker symbol mismatch: expected '{expected_symbol}', got '{data['symbol']}'"
        )

    if data["exchange"] != expected_exchange:
        raise ValueError(
            f"Authorization marker exchange mismatch: expected '{expected_exchange}', got '{data['exchange']}'"
        )

    if not data["single_use"]:
        raise ValueError("Authorization marker must have single_use=True.")

    if data["maximum_request_count"] > MAXIMUM_REQUEST_COUNT:
        raise ValueError(
            f"Maximum request count exceeds ceiling: {data['maximum_request_count']} > {MAXIMUM_REQUEST_COUNT}"
        )

    s_resolved = validate_staging_root(staging_root, repo_root=repo_root)
    computed_staging_hash = compute_staging_root_hash(s_resolved)
    if data["staging_root_hash"] != computed_staging_hash:
        raise ValueError(
            "Authorization marker bound to a different staging root. Path tampering detected."
        )

    computed_auth_hash = compute_listing_evidence_authorization_hash(data)
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

    return ListingEvidenceAuthorizationRecord(**data)


def consume_listing_evidence_authorization(marker_path: Union[Path, str]) -> Path:
    """Atomically consume single-use authorization marker before first evidence request."""
    m_path = Path(marker_path).resolve()
    if not m_path.exists():
        raise FileNotFoundError(f"Cannot consume non-existent authorization marker at '{m_path}'.")

    now_utc_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    consumed_name = f"listing_evidence_authorization.consumed.{now_utc_str}.json"
    consumed_path = m_path.parent / consumed_name

    # Atomic rename prevents reuse
    os.replace(m_path, consumed_path)

    if m_path.exists():
        raise RuntimeError("Consumption failed: active authorization marker still exists.")

    return consumed_path


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for listing evidence authorization marker management."""
    parser = argparse.ArgumentParser(
        description="Phase 7 PREMIERENE Official Listing Date Evidence Pilot Authorization Manager"
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    create_parser = subparsers.add_parser("create", help="Create a single-use evidence authorization marker")
    create_parser.add_argument(
        "--symbol",
        default=EVIDENCE_REQUIRED_SYMBOL,
        help=f"Target symbol (default: {EVIDENCE_REQUIRED_SYMBOL})",
    )
    create_parser.add_argument(
        "--security-name",
        default=EVIDENCE_REQUIRED_SECURITY_NAME,
        help=f"Target security name (default: {EVIDENCE_REQUIRED_SECURITY_NAME})",
    )
    create_parser.add_argument(
        "--exchange",
        default=EVIDENCE_REQUIRED_EXCHANGE,
        help=f"Exchange (default: {EVIDENCE_REQUIRED_EXCHANGE})",
    )
    create_parser.add_argument(
        "--requested-end",
        default=EVIDENCE_REQUIRED_REQUESTED_END,
        help=f"Requested historical period end (default: {EVIDENCE_REQUIRED_REQUESTED_END})",
    )
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
    """CLI entry point for listing evidence authorization marker generation."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "create":
        try:
            marker_path, record = create_listing_evidence_authorization(
                staging_root=args.staging_root,
                symbol=args.symbol,
                security_name=args.security_name,
                exchange=args.exchange,
                requested_end=args.requested_end,
                expires_minutes=args.expires_minutes,
            )
            print("LISTING EVIDENCE AUTHORIZATION MARKER CREATED")
            print(f"Milestone: {record.milestone}")
            print(f"Scope: {record.scope}")
            print(f"Symbol: {record.symbol}")
            print(f"Security Name: {record.security_name}")
            print(f"Exchange: {record.exchange}")
            print(f"Requested Period End: {record.requested_period_end}")
            print(f"Single Use: {record.single_use}")
            print(f"Max Requests: {record.maximum_request_count}")
            print(f"Staging Root: {args.staging_root}")
            print(f"Expires: {record.expires_timestamp}")
            print(f"Marker Path: {marker_path}")
            print(f"Authorization Hash: {record.authorization_hash}")
            return 0
        except Exception as e:
            print(f"ERROR: Failed to create listing evidence authorization marker: {e}", file=sys.stderr)
            return 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
