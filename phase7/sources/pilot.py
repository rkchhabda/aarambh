"""Dedicated Phase 7 five-stock live pilot preparation and CLI entry point.

Strictly enforces:
- Exact pilot symbols: RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK
- Exact pilot period: 2024-01-01 through 2024-01-31
- Exact interval: 1d
- External staging directory strictly outside repository root
- Single-use, scope-bound authorization marker stored outside Git
- Atomic authorization marker consumption prior to client creation
- Fail-closed execution without reusable secret phrases or bypass credentials
"""

import argparse
from pathlib import Path
import sys
from typing import Any, Callable, List, Optional

from phase7.sources.authorization import (
    ACTIVE_MARKER_FILENAME,
    PILOT_APPROVED_SYMBOLS,
    PILOT_END_DATE,
    PILOT_INTERVAL,
    PILOT_START_DATE,
    consume_authorization,
    load_and_validate_authorization,
    validate_authorization_marker_path,
    validate_staging_root,
)
from phase7.sources.pilot_guard import (
    APPROVED_PILOT_SYMBOLS,
    validate_pilot_parameters,
    validate_staging_path,
)


def build_pilot_parser() -> argparse.ArgumentParser:
    """Build CLI parser for phase7.sources.pilot."""
    parser = argparse.ArgumentParser(
        prog="phase7.sources.pilot",
        description="Phase 7 five-stock pilot execution CLI.",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        help="Comma-separated ticker symbols (strictly RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK for pilot)",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=PILOT_START_DATE,
        help="Start date YYYY-MM-DD (strictly 2024-01-01 for pilot)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=PILOT_END_DATE,
        help="End date YYYY-MM-DD (strictly 2024-01-31 for pilot)",
    )
    parser.add_argument(
        "--interval",
        type=str,
        default=PILOT_INTERVAL,
        help="Retrieval interval (strictly 1d for pilot)",
    )
    parser.add_argument(
        "--staging-root",
        type=str,
        required=True,
        help="Path to external staging root directory (must be outside repository)",
    )
    parser.add_argument(
        "--authorization-file",
        type=str,
        default="",
        help=f"Path to single-use authorization marker ({ACTIVE_MARKER_FILENAME}) outside Git",
    )
    parser.add_argument(
        "--execute-live",
        action="store_true",
        default=False,
        help="Flag to authorize live network execution",
    )
    return parser


def validate_pilot_cli_args(
    symbols_str: str,
    start_date: str,
    end_date: str,
    interval: str,
    staging_root_str: str,
    authorization_file_str: str = "",
    execute_live: bool = False,
    repo_root: Optional[Path] = None,
) -> None:
    """Validate pilot CLI arguments and boundaries without consuming authorization."""
    symbols = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]

    # Validate symbols and date range
    validate_pilot_parameters(symbols, start_date, end_date)

    if interval != PILOT_INTERVAL:
        raise ValueError(
            f"Pilot interval must be exactly '{PILOT_INTERVAL}', got '{interval}'."
        )

    # Validate staging root path
    validate_staging_root(staging_root_str, repo_root=repo_root)

    # Validate authorization file path if provided
    if authorization_file_str:
        validate_authorization_marker_path(
            authorization_file_str,
            staging_root=staging_root_str,
            repo_root=repo_root,
        )
    elif execute_live:
        raise ValueError(
            "Live execution requires a valid --authorization-file path."
        )


def run_pilot(
    symbols_str: str,
    start_date: str,
    end_date: str,
    interval: str,
    staging_root_str: str,
    authorization_file_str: str = "",
    execute_live: bool = False,
    client_factory: Optional[Callable[..., Any]] = None,
    repo_root: Optional[Path] = None,
) -> int:
    """Run pilot validation or live execution with atomic authorization consumption."""
    # Step 1: Validate CLI arguments
    validate_pilot_cli_args(
        symbols_str=symbols_str,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
        staging_root_str=staging_root_str,
        authorization_file_str=authorization_file_str,
        execute_live=execute_live,
        repo_root=repo_root,
    )

    symbols = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]

    # Step 2: If not execute-live, perform dry-run and exit
    if not execute_live:
        print("PHASE 7 FIVE-STOCK PILOT: Prepared and validated.")
        print("STATUS: PILOT_PREPARED_LIVE_EXECUTION_NOT_AUTHORIZED")
        print(f"Symbols: {','.join(symbols)}")
        print(f"Date Window: {start_date} to {end_date}")
        print(f"Interval: {interval}")
        print(f"Staging Root: {staging_root_str}")
        return 0

    # Step 3: Validate exact scope for live execution
    if symbols != PILOT_APPROVED_SYMBOLS:
        raise PermissionError(
            f"Live pilot symbols must be strictly {PILOT_APPROVED_SYMBOLS}, got {symbols}."
        )

    if start_date != PILOT_START_DATE or end_date != PILOT_END_DATE:
        raise PermissionError(
            f"Live pilot date window must be strictly {PILOT_START_DATE} to {PILOT_END_DATE}."
        )

    if interval != PILOT_INTERVAL:
        raise PermissionError(
            f"Live pilot interval must be strictly {PILOT_INTERVAL}."
        )

    # Step 4: Validate staging root
    valid_staging = validate_staging_root(staging_root_str, repo_root=repo_root)

    # Step 5 & 6: Load and validate authorization marker
    if not authorization_file_str:
        raise PermissionError("Live pilot execution requires --authorization-file.")

    auth_path = Path(authorization_file_str)
    record = load_and_validate_authorization(
        marker_path=auth_path,
        staging_root=valid_staging,
        expected_symbols=symbols,
        expected_start=start_date,
        expected_end=end_date,
        expected_interval=interval,
        repo_root=repo_root,
    )

    # Step 7: Atomically rename the active authorization file to consumed pattern
    consumed_marker = consume_authorization(auth_path)

    # Step 8: Verify active marker no longer exists
    if auth_path.exists():
        raise RuntimeError(
            "AUTHORIZATION_CONSUMPTION_FAILED: Active authorization marker still exists after rename."
        )

    # Step 9: Only then create the NSE client
    if client_factory is None:
        from phase7.sources.client_factory import create_real_nse_client
        client_factory = create_real_nse_client

    client = client_factory(data_dir=str(valid_staging), server_mode=True)

    # Step 10: Only then permit network retrieval
    print("Executing authorized live pilot with single-use authorization...")
    print(f"Consumed Marker: {consumed_marker}")
    print(f"Client Initialized: {type(client).__name__}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for phase7.sources.pilot."""
    parser = build_pilot_parser()
    args = parser.parse_args(argv)

    try:
        return run_pilot(
            symbols_str=args.symbols,
            start_date=args.start,
            end_date=args.end,
            interval=args.interval,
            staging_root_str=args.staging_root,
            authorization_file_str=args.authorization_file,
            execute_live=args.execute_live,
        )
    except Exception as exc:
        print(f"PILOT VALIDATION ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
