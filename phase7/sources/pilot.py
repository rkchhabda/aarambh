"""Dedicated Phase 7 five-stock live pilot preparation and CLI entry point.

Strictly enforces:
- Exact pilot symbols: RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK
- Exact pilot period: 2024-01-01 through 2024-01-31
- Exact interval: 1d
- External staging directory strictly outside repository root
- Single-use, scope-bound authorization marker stored outside Git
- Atomic authorization marker consumption prior to client creation
- Sequential retrieval loop with minimum 2.0s pacing and single active request
- Upstream payload safety inspection (HTML, CAPTCHA, empty rejection)
- Immutable external raw JSON and normalized JSONL persistence
- Comprehensive RequestManifest lifecycle (PENDING -> SUCCEEDED / FAILED / HALTED)
- Rejection ledger logging with sanitized reason codes
- Strict conservation invariant: source_row_count = normalized_row_count + rejected_row_count
- Deterministic client closure in finally block
- Complete exit code contract (0, 2, 3, 4, 5, 6, 7, 8, 9, 10)
- Fail-closed execution without reusable secret phrases or bypass credentials
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from threading import Lock
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

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
from phase7.sources.client_protocol import call_canonical_historical_retrieval
from phase7.sources.contracts import (
    HistoricalEODRecord,
    PilotExitCode,
    PilotOutcome,
    PilotStopReason,
    RequestManifest,
    RequestStatus,
    SessionBootstrapAudit,
)
from phase7.sources.http_client import (
    HTTPSafetyError,
    HTTPSafetyViolationType,
    inspect_payload_safety,
)
from phase7.sources.manifest import (
    build_manifest,
    build_pending_manifest,
    check_audit_conservation,
)
from phase7.sources.normalization import normalize_historical_row
from phase7.sources.persistence import (
    persist_normalized_records,
    persist_raw_payload,
    persist_request_manifest,
)
from phase7.sources.pilot_guard import validate_pilot_parameters
from phase7.sources.rejections import RejectionLedger


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
    pacing_seconds: float = 2.0,
    catch_exceptions: bool = False,
) -> int:
    """Run pilot validation or live execution with atomic authorization consumption and complete pipeline."""
    try:
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

        # Step 12: Build external staging directories
        download_folder = valid_staging / "raw"
        download_folder.mkdir(parents=True, exist_ok=True)
        (valid_staging / "normalized" / "historical").mkdir(parents=True, exist_ok=True)
        (valid_staging / "manifests").mkdir(parents=True, exist_ok=True)
        (valid_staging / "rejections").mkdir(parents=True, exist_ok=True)

        # Step 13: Invoke client factory
        if client_factory is None:
            from phase7.sources.client_factory import create_real_nse_client
            client_factory = create_real_nse_client

        try:
            client = client_factory(
                download_folder=download_folder,
                server=True,
                timeout=15,
            )
        except TypeError as exc:
            raise RuntimeError(
                f"CLIENT_FACTORY_PARAMETER_MISMATCH_HALT: {exc}"
            ) from exc

    except ValueError as val_err:
        if catch_exceptions:
            print(f"PILOT ARGUMENT ERROR: {val_err}", file=sys.stderr)
            return PilotExitCode.ARGUMENT_ERROR.value
        raise
    except PermissionError as perm_err:
        if catch_exceptions:
            print(f"PILOT AUTHORIZATION/SCOPE ERROR: {perm_err}", file=sys.stderr)
            return PilotExitCode.AUTHORIZATION_ERROR.value
        raise
    except RuntimeError as run_err:
        if catch_exceptions:
            if "CLIENT_FACTORY" in str(run_err):
                return PilotExitCode.CLIENT_CONSTRUCTION_ERROR.value
            return PilotExitCode.AUTHORIZATION_ERROR.value
        raise

    # Audit tracking initialized
    audit = SessionBootstrapAudit()
    audit.client_initialization_count = 1
    audit.session_bootstrap_network_activity_detected = True

    client_closed = False
    close_error = None
    pilot_outcome = PilotOutcome.FAILED
    exit_code = PilotExitCode.INCOMPLETE_EXECUTION_ERROR

    completed_symbols: List[str] = []
    symbol_manifests: List[RequestManifest] = []
    rejections_dir = valid_staging / "rejections"
    ledger = RejectionLedger(rejections_dir)
    request_lock = Lock()
    last_request_time = 0.0

    print("Executing authorized live pilot with single-use authorization...")
    print(f"Consumed Marker: {consumed_marker}")
    print(f"Client Initialized: {type(client).__name__}")

    try:
        for sym_idx, symbol in enumerate(symbols):
            with request_lock:
                # Rate limiting pacing
                now = time.time()
                elapsed = now - last_request_time
                if last_request_time > 0 and elapsed < pacing_seconds:
                    time.sleep(pacing_seconds - elapsed)
                last_request_time = time.time()

                req_id = str(uuid.uuid4())
                req_start_ts = datetime.now(timezone.utc).isoformat()
                req_start_time = time.time()

                # Step 6: Create and persist PENDING request manifest
                pending_manifest = build_pending_manifest(
                    request_id=req_id,
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    interval=interval,
                    retrieval_timestamp=req_start_ts,
                    client_version="nse-4.0.1",
                    source_identifier="NSE_DATA_FETCHER",
                )
                try:
                    persist_request_manifest(pending_manifest, staging_root=valid_staging, repo_root=repo_root)
                except Exception as exc:
                    print(f"PILOT_HALT: Manifest persistence failure: {exc}", file=sys.stderr)
                    exit_code = PilotExitCode.PERSISTENCE_MANIFEST_ERROR
                    pilot_outcome = PilotOutcome.HALTED_ON_SAFETY_CONTROL
                    break

                # Step 8: Call historical retrieval client exactly once
                audit.historical_retrieval_request_count += 1
                try:
                    raw_response = call_canonical_historical_retrieval(
                        client=client,
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        interval=interval,
                    )
                except (ConnectionError, TimeoutError) as net_err:
                    audit.historical_retrieval_response_count += 1
                    err_reason = (
                        PilotStopReason.CONNECTION_ERROR
                        if isinstance(net_err, ConnectionError)
                        else PilotStopReason.TIMEOUT_ERROR
                    )
                    print(f"PILOT_HALT: Upstream network failure ({err_reason.value}): {net_err}", file=sys.stderr)
                    failed_manifest = build_manifest(
                        request_id=req_id,
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        interval=interval,
                        retrieval_timestamp=req_start_ts,
                        raw_payload={},
                        normalized_records=[],
                        status=RequestStatus.FAILED,
                        failure_reason=err_reason.value,
                    )
                    persist_request_manifest(failed_manifest, staging_root=valid_staging, repo_root=repo_root)
                    exit_code = PilotExitCode.RETRIEVAL_ERROR
                    pilot_outcome = PilotOutcome.HALTED_ON_SAFETY_CONTROL
                    break
                except Exception as call_err:
                    audit.historical_retrieval_response_count += 1
                    print(f"PILOT_HALT: Upstream retrieval exception: {call_err}", file=sys.stderr)
                    exit_code = PilotExitCode.RETRIEVAL_ERROR
                    pilot_outcome = PilotOutcome.HALTED_ON_SAFETY_CONTROL
                    break

                audit.historical_retrieval_response_count += 1
                req_end_time = time.time()
                duration_sec = req_end_time - req_start_time

                # Step 10-14: Payload safety and empty check
                if raw_response is None:
                    print("PILOT_HALT: Empty payload received (None).", file=sys.stderr)
                    empty_manifest = build_manifest(
                        request_id=req_id,
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        interval=interval,
                        retrieval_timestamp=req_start_ts,
                        raw_payload={},
                        normalized_records=[],
                        status=RequestStatus.EMPTY,
                        failure_reason=PilotStopReason.EMPTY_RESPONSE.value,
                    )
                    persist_request_manifest(empty_manifest, staging_root=valid_staging, repo_root=repo_root)
                    exit_code = PilotExitCode.SCHEMA_NORMALIZATION_ERROR
                    pilot_outcome = PilotOutcome.HALTED_ON_SAFETY_CONTROL
                    break

                if isinstance(raw_response, str):
                    try:
                        inspect_payload_safety(text_content=raw_response)
                    except HTTPSafetyError as safe_err:
                        err_code = (
                            PilotStopReason.HTML_PAYLOAD_REJECTED
                            if safe_err.violation_type == HTTPSafetyViolationType.HTML_PAYLOAD_REJECTED
                            else PilotStopReason.CAPTCHA_DETECTED
                        )
                        print(f"PILOT_HALT: Payload safety violation ({err_code.value}): {safe_err}", file=sys.stderr)
                        exit_code = PilotExitCode.SCHEMA_NORMALIZATION_ERROR
                        pilot_outcome = PilotOutcome.HALTED_ON_SAFETY_CONTROL
                        break
                    try:
                        raw_response = json.loads(raw_response)
                    except Exception:
                        print("PILOT_HALT: String payload is not valid JSON.", file=sys.stderr)
                        exit_code = PilotExitCode.SCHEMA_NORMALIZATION_ERROR
                        pilot_outcome = PilotOutcome.HALTED_ON_SAFETY_CONTROL
                        break

                if isinstance(raw_response, bytes):
                    try:
                        decoded = raw_response.decode("utf-8")
                        inspect_payload_safety(text_content=decoded)
                        raw_response = json.loads(decoded)
                    except Exception as byte_err:
                        print(f"PILOT_HALT: Bytes decode or safety failure: {byte_err}", file=sys.stderr)
                        exit_code = PilotExitCode.SCHEMA_NORMALIZATION_ERROR
                        pilot_outcome = PilotOutcome.HALTED_ON_SAFETY_CONTROL
                        break

                serialized_check = json.dumps(raw_response, default=str)
                try:
                    inspect_payload_safety(text_content=serialized_check)
                except HTTPSafetyError as safe_err:
                    err_code = (
                        PilotStopReason.HTML_PAYLOAD_REJECTED
                        if safe_err.violation_type == HTTPSafetyViolationType.HTML_PAYLOAD_REJECTED
                        else PilotStopReason.CAPTCHA_DETECTED
                    )
                    print(f"PILOT_HALT: Payload safety violation ({err_code.value}): {safe_err}", file=sys.stderr)
                    exit_code = PilotExitCode.SCHEMA_NORMALIZATION_ERROR
                    pilot_outcome = PilotOutcome.HALTED_ON_SAFETY_CONTROL
                    break

                # Extract raw rows from permitted shapes
                if isinstance(raw_response, list):
                    raw_rows = raw_response
                elif isinstance(raw_response, dict) and "data" in raw_response and isinstance(raw_response["data"], list):
                    raw_rows = raw_response["data"]
                else:
                    print("PILOT_HALT: Unexpected response payload structure.", file=sys.stderr)
                    exit_code = PilotExitCode.SCHEMA_NORMALIZATION_ERROR
                    pilot_outcome = PilotOutcome.HALTED_ON_SAFETY_CONTROL
                    break

                if len(raw_rows) == 0:
                    print("PILOT_HALT: Response contains zero rows.", file=sys.stderr)
                    empty_manifest = build_manifest(
                        request_id=req_id,
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        interval=interval,
                        retrieval_timestamp=req_start_ts,
                        raw_payload=raw_response,
                        normalized_records=[],
                        status=RequestStatus.EMPTY,
                        failure_reason=PilotStopReason.EMPTY_RESPONSE.value,
                    )
                    persist_request_manifest(empty_manifest, staging_root=valid_staging, repo_root=repo_root)
                    exit_code = PilotExitCode.SCHEMA_NORMALIZATION_ERROR
                    pilot_outcome = PilotOutcome.HALTED_ON_SAFETY_CONTROL
                    break

                # Step 15-16: Persist raw payload outside Git and compute SHA-256
                try:
                    raw_path, raw_hash = persist_raw_payload(
                        payload=raw_response,
                        staging_root=valid_staging,
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        interval=interval,
                        retrieval_timestamp=req_start_ts,
                        repo_root=repo_root,
                    )
                except Exception as raw_err:
                    print(f"PILOT_HALT: Raw payload persistence error: {raw_err}", file=sys.stderr)
                    exit_code = PilotExitCode.PERSISTENCE_MANIFEST_ERROR
                    pilot_outcome = PilotOutcome.HALTED_ON_SAFETY_CONTROL
                    break

                # Step 17-22: Normalize rows and perform rigorous checks
                normalized_records: List[HistoricalEODRecord] = []
                rejected_rows_list = []
                seen_dates = set()
                halt_reason: Optional[PilotStopReason] = None

                for row_idx, row in enumerate(raw_rows):
                    if not isinstance(row, dict):
                        rej_rec = ledger.record_rejected_row(
                            symbol=symbol,
                            raw_payload={"item": str(row)},
                            reason="UNEXPECTED_ROW_TYPE",
                            timestamp=req_start_ts,
                            row_index=row_idx,
                            request_id=req_id,
                        )
                        rejected_rows_list.append(rej_rec)
                        continue

                    try:
                        record = normalize_historical_row(
                            raw_row=row,
                            symbol=symbol,
                            source_identifier="NSE_DATA_FETCHER",
                            ingestion_timestamp=req_start_ts,
                        )
                    except ValueError as row_err:
                        err_str = str(row_err)
                        if "SYMBOL_IDENTITY_CONFLICT" in err_str:
                            halt_reason = PilotStopReason.SYMBOL_IDENTITY_CONFLICT
                            break
                        if "exceeds high" in err_str or "outside [low, high]" in err_str or "Non-positive price" in err_str:
                            halt_reason = PilotStopReason.INVALID_OHLC
                            break
                        if "Negative volume" in err_str or "Negative traded value" in err_str:
                            halt_reason = PilotStopReason.NEGATIVE_VALUE
                            break

                        rej_rec = ledger.record_rejected_row(
                            symbol=symbol,
                            raw_payload=row,
                            reason=err_str,
                            timestamp=req_start_ts,
                            row_index=row_idx,
                            request_id=req_id,
                        )
                        rejected_rows_list.append(rej_rec)
                        continue

                    # Validate row date within governed range
                    if record.trading_date < start_date or record.trading_date > end_date:
                        halt_reason = PilotStopReason.OUT_OF_RANGE_DATE
                        break

                    # Detect duplicate natural key
                    if record.trading_date in seen_dates:
                        halt_reason = PilotStopReason.DUPLICATE_NATURAL_KEY
                        break
                    seen_dates.add(record.trading_date)

                    normalized_records.append(record)

                if halt_reason is not None:
                    print(f"PILOT_HALT: Row validation triggered halt: {halt_reason.value}", file=sys.stderr)
                    halt_manifest = build_manifest(
                        request_id=req_id,
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        interval=interval,
                        retrieval_timestamp=req_start_ts,
                        raw_payload=raw_response,
                        normalized_records=normalized_records,
                        status=RequestStatus.HALTED,
                        failure_reason=halt_reason.value,
                        raw_file_path=str(raw_path),
                        raw_checksum=raw_hash,
                        duration_seconds=duration_sec,
                    )
                    persist_request_manifest(halt_manifest, staging_root=valid_staging, repo_root=repo_root)
                    exit_code = PilotExitCode.SCHEMA_NORMALIZATION_ERROR
                    pilot_outcome = PilotOutcome.HALTED_ON_SAFETY_CONTROL
                    break

                # Required conservation check: source_row_count = normalized_row_count + rejected_row_count
                source_count = len(raw_rows)
                norm_count = len(normalized_records)
                rej_count = len(rejected_rows_list)
                if not check_audit_conservation(source_count, norm_count, rej_count):
                    print("PILOT_HALT: Audit conservation failure.", file=sys.stderr)
                    halt_manifest = build_manifest(
                        request_id=req_id,
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        interval=interval,
                        retrieval_timestamp=req_start_ts,
                        raw_payload=raw_response,
                        normalized_records=normalized_records,
                        status=RequestStatus.HALTED,
                        failure_reason=PilotStopReason.AUDIT_CONSERVATION_FAILURE.value,
                        raw_file_path=str(raw_path),
                        raw_checksum=raw_hash,
                        duration_seconds=duration_sec,
                    )
                    persist_request_manifest(halt_manifest, staging_root=valid_staging, repo_root=repo_root)
                    exit_code = PilotExitCode.PERSISTENCE_MANIFEST_ERROR
                    pilot_outcome = PilotOutcome.HALTED_ON_SAFETY_CONTROL
                    break

                # Under 5-stock protocol: PARTIAL must halt the pilot
                if rej_count > 0:
                    print("PILOT_HALT: Partial rows rejected under 5-stock protocol.", file=sys.stderr)
                    part_manifest = build_manifest(
                        request_id=req_id,
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        interval=interval,
                        retrieval_timestamp=req_start_ts,
                        raw_payload=raw_response,
                        normalized_records=normalized_records,
                        status=RequestStatus.PARTIAL,
                        is_partial=True,
                        failure_reason="Partial rows rejected",
                        raw_file_path=str(raw_path),
                        raw_checksum=raw_hash,
                        duration_seconds=duration_sec,
                    )
                    persist_request_manifest(part_manifest, staging_root=valid_staging, repo_root=repo_root)
                    exit_code = PilotExitCode.SCHEMA_NORMALIZATION_ERROR
                    pilot_outcome = PilotOutcome.HALTED_ON_SAFETY_CONTROL
                    break

                # Never succeed with zero normalized rows
                if norm_count == 0:
                    print("PILOT_HALT: Zero normalized rows produced.", file=sys.stderr)
                    exit_code = PilotExitCode.SCHEMA_NORMALIZATION_ERROR
                    pilot_outcome = PilotOutcome.HALTED_ON_SAFETY_CONTROL
                    break

                # Step 23-24: Persist normalized records and compute checksum
                try:
                    norm_path, norm_hash, row_count, missing_fields = persist_normalized_records(
                        records=normalized_records,
                        staging_root=valid_staging,
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        interval=interval,
                        retrieval_timestamp=req_start_ts,
                        repo_root=repo_root,
                    )
                except Exception as norm_err:
                    print(f"PILOT_HALT: Normalized persistence error: {norm_err}", file=sys.stderr)
                    exit_code = PilotExitCode.PERSISTENCE_MANIFEST_ERROR
                    pilot_outcome = PilotOutcome.HALTED_ON_SAFETY_CONTROL
                    break

                # Step 25-26: Finalize the manifest
                final_manifest = build_manifest(
                    request_id=req_id,
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    interval=interval,
                    retrieval_timestamp=req_start_ts,
                    raw_payload=raw_response,
                    normalized_records=normalized_records,
                    status=RequestStatus.SUCCEEDED,
                    client_version="nse-4.0.1",
                    source_identifier="NSE_DATA_FETCHER",
                    raw_checksum=raw_hash,
                    normalized_checksum=norm_hash,
                    raw_file_path=str(raw_path),
                    normalized_file_path=str(norm_path),
                    schema_version="phase7-eod-v1.0",
                    missing_fields=missing_fields,
                    rejected_row_count=rej_count,
                    duration_seconds=duration_sec,
                )
                try:
                    persist_request_manifest(final_manifest, staging_root=valid_staging, repo_root=repo_root)
                except Exception as man_err:
                    print(f"PILOT_HALT: Final manifest persistence error: {man_err}", file=sys.stderr)
                    exit_code = PilotExitCode.PERSISTENCE_MANIFEST_ERROR
                    pilot_outcome = PilotOutcome.HALTED_ON_SAFETY_CONTROL
                    break

                # Persist rejections ledger
                ledger.persist()

                completed_symbols.append(symbol)
                symbol_manifests.append(final_manifest)
                audit.symbols_completed += 1

        # Check final outcome
        if len(completed_symbols) == len(symbols) and len(symbols) == 5:
            pilot_outcome = PilotOutcome.PASSED
            exit_code = PilotExitCode.SUCCESS
        else:
            if exit_code == PilotExitCode.INCOMPLETE_EXECUTION_ERROR:
                pilot_outcome = PilotOutcome.FAILED
                exit_code = PilotExitCode.INCOMPLETE_EXECUTION_ERROR
    finally:
        # Client closure in finally block
        if client is not None:
            try:
                if hasattr(client, "exit"):
                    client.exit()
                elif hasattr(client, "close"):
                    client.close()
                client_closed = True
                audit.client_close_count += 1
            except Exception as close_exc:
                close_error = close_exc
                print(f"PILOT_WARNING: Client closure error: {close_exc}", file=sys.stderr)
                if exit_code == PilotExitCode.SUCCESS:
                    exit_code = PilotExitCode.CLIENT_CLOSE_ERROR
                    pilot_outcome = PilotOutcome.FAILED

    print(f"FINAL OUTCOME: {pilot_outcome.value}")
    print(f"Symbols Completed: {len(completed_symbols)}/{len(symbols)}")
    print(f"Client Initialized: {audit.client_initialization_count}")
    print(f"Client Closed: {audit.client_close_count}")
    print(f"Exit Code: {exit_code.value}")
    return exit_code.value


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
            catch_exceptions=False,
        )
    except ValueError as exc:
        print(f"PILOT ARGUMENT ERROR: {exc}", file=sys.stderr)
        return PilotExitCode.ARGUMENT_ERROR.value
    except PermissionError as exc:
        print(f"PILOT AUTHORIZATION/SCOPE ERROR: {exc}", file=sys.stderr)
        return PilotExitCode.AUTHORIZATION_ERROR.value
    except RuntimeError as exc:
        if "CLIENT_FACTORY" in str(exc):
            print(f"PILOT CLIENT FACTORY ERROR: {exc}", file=sys.stderr)
            return PilotExitCode.CLIENT_CONSTRUCTION_ERROR.value
        print(f"PILOT AUTHORIZATION/RUNTIME ERROR: {exc}", file=sys.stderr)
        return PilotExitCode.AUTHORIZATION_ERROR.value
    except Exception as exc:
        print(f"PILOT UNEXPECTED ERROR: {exc}", file=sys.stderr)
        return PilotExitCode.UNEXPECTED_INTERNAL_ERROR.value


if __name__ == "__main__":
    sys.exit(main())
