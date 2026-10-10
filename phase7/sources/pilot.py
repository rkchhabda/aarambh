"""Dedicated Phase 7 five-stock live pilot preparation and CLI entry point.

Strictly enforces:
- Exact pilot symbols: RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK
- Exact pilot period: 2024-01-01 through 2024-01-31
- External staging directory strictly outside repository root
- Live execution requires explicit flag AND exact owner authorization phrase:
  'AUTHORIZE MILESTONE 4.9: FIVE-STOCK NSE LIVE PILOT'
- Fail-closed execution without hardcoded bypass tokens
"""

import argparse
from pathlib import Path
import sys
from typing import List, Optional

from phase7.sources.pilot_guard import (
    APPROVED_PILOT_SYMBOLS,
    PILOT_END_DATE,
    PILOT_START_DATE,
    validate_pilot_parameters,
    validate_staging_path,
)

REQUIRED_PILOT_PHRASE = "AUTHORIZE MILESTONE 4.9: FIVE-STOCK NSE LIVE PILOT"


def build_pilot_parser() -> argparse.ArgumentParser:
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
        "--staging-root",
        type=str,
        required=True,
        help="Path to external staging root directory (must be outside repository)",
    )
    parser.add_argument(
        "--execute-live",
        action="store_true",
        default=False,
        help="Flag to authorize live network execution",
    )
    parser.add_argument(
        "--owner-authorization",
        type=str,
        default="",
        help=f"Exact owner authorization phrase: '{REQUIRED_PILOT_PHRASE}'",
    )
    return parser


def validate_pilot_cli_args(
    symbols_str: str,
    start_date: str,
    end_date: str,
    staging_root_str: str,
    execute_live: bool,
    owner_authorization: str,
    repo_root: Optional[Path] = None,
) -> None:
    """Validate all pilot CLI arguments against strict Phase 7 guardrails."""
    symbols = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]

    # Validate symbols and date range
    validate_pilot_parameters(symbols, start_date, end_date)

    # Validate staging path
    repo = Path(repo_root or Path.cwd()).resolve()
    validate_staging_path(Path(staging_root_str), repo)

    # Validate live execution authorization
    if execute_live:
        if owner_authorization != REQUIRED_PILOT_PHRASE:
            raise PermissionError(
                f"Live pilot execution blocked: owner authorization phrase must match exactly '{REQUIRED_PILOT_PHRASE}'."
            )


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_pilot_parser()
    args = parser.parse_args(argv)

    try:
        validate_pilot_cli_args(
            symbols_str=args.symbols,
            start_date=args.start,
            end_date=args.end,
            staging_root_str=args.staging_root,
            execute_live=args.execute_live,
            owner_authorization=args.owner_authorization,
        )
    except Exception as exc:
        print(f"PILOT VALIDATION ERROR: {exc}", file=sys.stderr)
        return 1

    if not args.execute_live:
        print("PHASE 7 FIVE-STOCK PILOT: Prepared and validated.")
        print("STATUS: PILOT_PREPARED_LIVE_EXECUTION_NOT_AUTHORIZED")
        print(f"Symbols: {args.symbols}")
        print(f"Date Window: {args.start} to {args.end}")
        print(f"Staging Root: {args.staging_root}")
        return 0

    print("Executing authorized live pilot...")
    # Live execution logic will be invoked in Milestone 4.9 when authorized
    return 0


if __name__ == "__main__":
    sys.exit(main())
