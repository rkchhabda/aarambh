"""Phase 7 governed 20-stock historical batch harness orchestrator and CLI.

Executes and coordinates the sequential historical batch acquisition pipeline with
fail-closed error handling, atomic checkpointing, and strict exit code mapping.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import uuid

from phase7.sources.authorization import find_repo_root
from phase7.sources.batch_audit import generate_batch_audit_payload, save_batch_audit
from phase7.sources.batch_authorization import (
    consume_batch_authorization_marker,
    validate_batch_authorization,
)
from phase7.sources.batch_checkpoint import (
    BatchCheckpoint,
    BatchSymbolStatus,
    InvalidResumeCheckpointError,
    SymbolCheckpoint,
    create_initial_batch_checkpoint,
    load_checkpoint,
    save_checkpoint,
    validate_resume_checkpoint,
)
from phase7.sources.batch_contract import (
    REQUIRED_AUTHORIZATION_SCOPE,
    REQUIRED_CLASSIFICATION,
    REQUIRED_END_DATE,
    REQUIRED_INTERVAL,
    REQUIRED_PANEL_VERSION,
    REQUIRED_SCHEMA_MAPPING_VERSION,
    REQUIRED_SNAPSHOT_CHECKSUM,
    REQUIRED_START_DATE,
    REQUIRED_SYMBOL_COUNT,
    BatchContract,
    BatchExitCode,
    BatchStatus,
    validate_batch_contract,
)
from phase7.sources.batch_selection import (
    SelectionResult,
    load_selection_manifest,
)
from phase7.sources.client_protocol import call_canonical_historical_retrieval
from phase7.sources.contracts import RequestStatus
from phase7.sources.http_client import HTTPSafetyError, inspect_payload_safety
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
    validate_persistence_path_outside_git,
)
from phase7.sources.rejections import RejectionLedger


def create_canonical_batch_contract(
    staging_root: Path,
    selection: SelectionResult,
    batch_id: Optional[str] = None,
) -> BatchContract:
    """Create canonical BatchContract binding the selection and staging root."""
    staging_root_hash = hashlib.sha256(str(staging_root.resolve()).encode("utf-8")).hexdigest()
    b_id = batch_id or f"batch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"

    contract = BatchContract(
        batch_id=b_id,
        source_panel_version=selection.source_panel_version,
        source_snapshot_checksum=selection.source_snapshot_checksum,
        selection_checksum=selection.selection_checksum,
        symbol_count=selection.selected_symbol_count,
        ordered_symbols_hash=selection.ordered_symbols_hash,
        start_date=REQUIRED_START_DATE,
        end_date=REQUIRED_END_DATE,
        interval=REQUIRED_INTERVAL,
        staging_root_hash=staging_root_hash,
        schema_mapping_version=REQUIRED_SCHEMA_MAPPING_VERSION,
        maximum_concurrency=1,
        minimum_request_spacing_seconds=2.0,
        maximum_retries=0,
        failure_threshold=1,
        authorization_scope=REQUIRED_AUTHORIZATION_SCOPE,
        classification=REQUIRED_CLASSIFICATION,
        batch_status=BatchStatus.INITIALIZED.value,
        created_timestamp=datetime.now(timezone.utc).isoformat(),
    )
    validate_batch_contract(contract)
    return contract


def run_batch_pilot(
    staging_root: Path,
    authorization_file: Optional[Path] = None,
    execute_live: bool = False,
    dry_run: bool = False,
    resume: bool = False,
    selection_dir: Optional[Path] = None,
    client_factory: Optional[Callable[..., Any]] = None,
    pacing_seconds: Optional[float] = None,
) -> Tuple[BatchExitCode, Dict[str, Any]]:
    """Execute the governed 20-stock batch pilot harness."""
    start_time = time.monotonic()
    staging_root = staging_root.resolve()

    # 1. Validate staging root is strictly outside repository root
    try:
        validate_persistence_path_outside_git(staging_root)
    except Exception as exc:
        return BatchExitCode.ARGUMENT_ERROR, {"error": f"Staging root inside repository: {exc}"}

    # 2. Load and validate selection evidence
    sel_dir = (selection_dir or (staging_root / "selection")).resolve()
    try:
        selection = load_selection_manifest(sel_dir)
    except Exception as exc:
        return BatchExitCode.SOURCE_PANEL_OR_SELECTION_MISMATCH, {
            "error": f"Failed to load selection manifest: {exc}"
        }

    # Check selection governance invariants
    if selection.source_panel_version != REQUIRED_PANEL_VERSION:
        return BatchExitCode.SOURCE_PANEL_OR_SELECTION_MISMATCH, {
            "error": f"Selection panel version mismatch: {selection.source_panel_version} != {REQUIRED_PANEL_VERSION}"
        }
    if selection.source_snapshot_checksum != REQUIRED_SNAPSHOT_CHECKSUM:
        return BatchExitCode.SOURCE_PANEL_OR_SELECTION_MISMATCH, {
            "error": f"Selection snapshot checksum mismatch: {selection.source_snapshot_checksum} != {REQUIRED_SNAPSHOT_CHECKSUM}"
        }
    if selection.selected_symbol_count != REQUIRED_SYMBOL_COUNT:
        return BatchExitCode.SOURCE_PANEL_OR_SELECTION_MISMATCH, {
            "error": f"Selection symbol count mismatch: {selection.selected_symbol_count} != {REQUIRED_SYMBOL_COUNT}"
        }

    # 3. Create and validate batch contract
    try:
        contract = create_canonical_batch_contract(staging_root, selection)
    except Exception as exc:
        return BatchExitCode.ARGUMENT_ERROR, {"error": f"Batch contract creation failed: {exc}"}

    # 4. Enforce authorization if live execution
    consumed_marker_path: Optional[Path] = None
    if execute_live:
        if not authorization_file or not authorization_file.exists():
            return BatchExitCode.AUTHORIZATION_ERROR, {
                "error": f"Live execution requires valid authorization marker: {authorization_file}"
            }
        try:
            consumed_marker_path = consume_batch_authorization_marker(
                marker_path=authorization_file,
                contract=contract,
                staging_root=staging_root,
            )
        except Exception as exc:
            return BatchExitCode.AUTHORIZATION_ERROR, {
                "error": f"Batch authorization validation/consumption failed: {exc}"
            }

    # 5. Checkpoint handling (initialize or resume)
    checkpoint_file = staging_root / "checkpoints" / "batch_checkpoint.json"
    checkpoint: BatchCheckpoint
    trusted_symbols: set = set()

    if resume:
        if not checkpoint_file.exists():
            return BatchExitCode.INVALID_RESUME_CHECKPOINT, {
                "error": f"Resume requested but checkpoint file does not exist: {checkpoint_file}"
            }
        try:
            checkpoint = load_checkpoint(checkpoint_file)
            trusted_symbols = validate_resume_checkpoint(
                checkpoint=checkpoint,
                contract=contract,
                governed_symbols=selection.ordered_selected_symbols,
            )
        except Exception as exc:
            return BatchExitCode.INVALID_RESUME_CHECKPOINT, {
                "error": f"Checkpoint resume validation failed: {exc}"
            }
    else:
        checkpoint = create_initial_batch_checkpoint(
            batch_id=contract.batch_id,
            ordered_symbols=selection.ordered_selected_symbols,
        )
        save_checkpoint(checkpoint, checkpoint_file)

    if dry_run and not execute_live:
        # Dry-run validation passed without network call
        duration = time.monotonic() - start_time
        return BatchExitCode.SUCCESS, {
            "status": "DRY_RUN_PASSED",
            "batch_id": contract.batch_id,
            "symbols_count": len(selection.ordered_selected_symbols),
            "duration_seconds": duration,
        }

    # 6. Client construction
    client = None
    client_closed = False
    try:
        if client_factory:
            client = client_factory(download_folder=staging_root / "raw", server=True, timeout=15)
        elif execute_live:
            from phase7.sources.client_factory import create_real_nse_client
            client = create_real_nse_client(download_folder=staging_root / "raw", server=True, timeout=15)
        else:
            return BatchExitCode.CLIENT_CONSTRUCTION_ERROR, {
                "error": "No client factory provided for non-live execution"
            }
    except Exception as exc:
        return BatchExitCode.CLIENT_CONSTRUCTION_ERROR, {
            "error": f"Client construction failed: {exc}"
        }

    # 7. Sequential retrieval loop
    symbols_to_process = selection.ordered_selected_symbols
    spacing = pacing_seconds if pacing_seconds is not None else contract.minimum_request_spacing_seconds

    exit_code = BatchExitCode.SUCCESS
    stop_reason: Optional[str] = None
    last_error_details: Dict[str, Any] = {}

    checkpoint.final_status = BatchStatus.IN_PROGRESS
    save_checkpoint(checkpoint, checkpoint_file)

    try:
        for idx, symbol in enumerate(symbols_to_process):
            if symbol in trusted_symbols:
                continue

            # Update symbol state to PENDING
            req_id = str(uuid.uuid4())
            sym_cp = checkpoint.symbol_states[symbol]
            sym_cp.status = BatchSymbolStatus.PENDING
            sym_cp.request_id = req_id
            save_checkpoint(checkpoint, checkpoint_file)

            # Build pending manifest
            now_iso = datetime.now(timezone.utc).isoformat()
            pending_man = build_pending_manifest(
                request_id=req_id,
                symbol=symbol,
                start_date=contract.start_date,
                end_date=contract.end_date,
                interval=contract.interval,
                retrieval_timestamp=now_iso,
                client_version="nse-4.0.1",
                source_identifier="NSE_DATA_FETCHER",
            )
            persist_request_manifest(pending_man, staging_root=staging_root)

            # Invoke retrieval exactly once
            raw_payload = None
            try:
                raw_payload = call_canonical_historical_retrieval(
                    client=client,
                    symbol=symbol,
                    start_date=contract.start_date,
                    end_date=contract.end_date,
                    interval=contract.interval,
                )
            except Exception as exc:
                stop_reason = f"Upstream retrieval error for {symbol}: {exc}"
                sym_cp.status = BatchSymbolStatus.FAILED
                sym_cp.error_message = stop_reason
                checkpoint.failed_symbols += 1
                checkpoint.pending_symbols -= 1
                checkpoint.stop_reason = stop_reason
                checkpoint.final_status = BatchStatus.HALTED
                save_checkpoint(checkpoint, checkpoint_file)
                exit_code = BatchExitCode.RETRIEVAL_ERROR
                last_error_details = {"symbol": symbol, "error": stop_reason}
                break

            # Payload safety inspection
            try:
                if raw_payload is None:
                    raise ValueError(f"Empty response received for {symbol}")
                if isinstance(raw_payload, str):
                    inspect_payload_safety(text_content=raw_payload)
                    raise ValueError(f"String/HTML payload received for {symbol}")
                if isinstance(raw_payload, list) and len(raw_payload) == 0:
                    raise ValueError(f"Empty data list returned for {symbol}")
                if isinstance(raw_payload, dict):
                    data_items = raw_payload.get("data")
                    if data_items is not None and isinstance(data_items, list) and len(data_items) == 0:
                        raise ValueError(f"Empty 'data' field returned for {symbol}")
            except Exception as exc:
                stop_reason = f"Payload safety rejection for {symbol}: {exc}"
                sym_cp.status = BatchSymbolStatus.FAILED
                sym_cp.error_message = stop_reason
                checkpoint.failed_symbols += 1
                checkpoint.pending_symbols -= 1
                checkpoint.stop_reason = stop_reason
                checkpoint.final_status = BatchStatus.HALTED
                save_checkpoint(checkpoint, checkpoint_file)
                exit_code = BatchExitCode.RETRIEVAL_ERROR
                last_error_details = {"symbol": symbol, "error": stop_reason}
                break

            # Raw persistence
            try:
                raw_path, raw_hash = persist_raw_payload(
                    payload=raw_payload,
                    staging_root=staging_root,
                    symbol=symbol,
                    start_date=contract.start_date,
                    end_date=contract.end_date,
                    interval=contract.interval,
                    retrieval_timestamp=now_iso,
                )
            except Exception as exc:
                stop_reason = f"Raw persistence failure for {symbol}: {exc}"
                sym_cp.status = BatchSymbolStatus.FAILED
                sym_cp.error_message = stop_reason
                checkpoint.failed_symbols += 1
                checkpoint.pending_symbols -= 1
                checkpoint.stop_reason = stop_reason
                checkpoint.final_status = BatchStatus.HALTED
                save_checkpoint(checkpoint, checkpoint_file)
                exit_code = BatchExitCode.PERSISTENCE_MANIFEST_ERROR
                last_error_details = {"symbol": symbol, "error": stop_reason}
                break

            # Normalization
            rejection_ledger = RejectionLedger(ledger_dir=staging_root / "rejected")
            normalized_records = []
            source_rows_list = raw_payload if isinstance(raw_payload, list) else raw_payload.get("data", [])
            if not isinstance(source_rows_list, list):
                source_rows_list = []

            for row_idx, row in enumerate(source_rows_list):
                try:
                    norm_rec = normalize_historical_row(
                        raw_row=row,
                        symbol=symbol,
                        start_date=contract.start_date,
                        end_date=contract.end_date,
                    )
                    normalized_records.append(norm_rec)
                except Exception as norm_err:
                    rejection_ledger.record_rejected_row(
                        symbol=symbol,
                        raw_payload=row,
                        reason=f"NORMALIZATION_REJECTION: {norm_err}",
                        timestamp=now_iso,
                        row_index=row_idx,
                        request_id=req_id,
                    )

            # Check if any normalization or rejection failure occurred under 1-fail threshold
            rej_count = len(rejection_ledger.rejected_rows)
            if rej_count > 0 or len(normalized_records) == 0:
                stop_reason = f"Schema normalization error for {symbol}: {rej_count} rejected, {len(normalized_records)} normalized"
                sym_cp.status = BatchSymbolStatus.FAILED
                sym_cp.error_message = stop_reason
                checkpoint.failed_symbols += 1
                checkpoint.pending_symbols -= 1
                checkpoint.stop_reason = stop_reason
                checkpoint.final_status = BatchStatus.HALTED
                save_checkpoint(checkpoint, checkpoint_file)
                exit_code = BatchExitCode.SCHEMA_NORMALIZATION_ERROR
                last_error_details = {"symbol": symbol, "error": stop_reason}
                break

            # Normalized persistence
            try:
                norm_path, norm_hash, _, _ = persist_normalized_records(
                    records=normalized_records,
                    staging_root=staging_root,
                    symbol=symbol,
                    start_date=contract.start_date,
                    end_date=contract.end_date,
                    interval=contract.interval,
                    retrieval_timestamp=now_iso,
                )
            except Exception as exc:
                stop_reason = f"Normalized persistence failure for {symbol}: {exc}"
                sym_cp.status = BatchSymbolStatus.FAILED
                sym_cp.error_message = stop_reason
                checkpoint.failed_symbols += 1
                checkpoint.pending_symbols -= 1
                checkpoint.stop_reason = stop_reason
                checkpoint.final_status = BatchStatus.HALTED
                save_checkpoint(checkpoint, checkpoint_file)
                exit_code = BatchExitCode.PERSISTENCE_MANIFEST_ERROR
                last_error_details = {"symbol": symbol, "error": stop_reason}
                break

            # Conservation check
            src_count = len(source_rows_list)
            norm_count = len(normalized_records)
            rej_count = len(rejection_ledger.rejected_rows)
            if src_count != norm_count + rej_count:
                stop_reason = f"Row conservation breach for {symbol}: {src_count} != {norm_count} + {rej_count}"
                sym_cp.status = BatchSymbolStatus.FAILED
                sym_cp.error_message = stop_reason
                checkpoint.failed_symbols += 1
                checkpoint.pending_symbols -= 1
                checkpoint.stop_reason = stop_reason
                checkpoint.final_status = BatchStatus.HALTED
                save_checkpoint(checkpoint, checkpoint_file)
                exit_code = BatchExitCode.PERSISTENCE_MANIFEST_ERROR
                last_error_details = {"symbol": symbol, "error": stop_reason}
                break

            # Finalize manifest
            final_manifest = build_manifest(
                request_id=req_id,
                symbol=symbol,
                start_date=contract.start_date,
                end_date=contract.end_date,
                interval=contract.interval,
                retrieval_timestamp=now_iso,
                raw_payload=raw_payload,
                normalized_records=normalized_records,
                status=RequestStatus.SUCCEEDED,
                raw_checksum=raw_hash,
                normalized_checksum=norm_hash,
                raw_file_path=str(raw_path),
                normalized_file_path=str(norm_path),
                rejected_row_count=rej_count,
                mapping_version=contract.schema_mapping_version,
            )
            man_path = persist_request_manifest(final_manifest, staging_root=staging_root)
            man_hash = hashlib.sha256(man_path.read_bytes()).hexdigest()

            # Update symbol checkpoint
            sym_cp.status = BatchSymbolStatus.SUCCEEDED
            sym_cp.raw_file_path = str(raw_path)
            sym_cp.normalized_file_path = str(norm_path)
            sym_cp.manifest_file_path = str(man_path)
            sym_cp.raw_checksum = raw_hash
            sym_cp.normalized_checksum = norm_hash
            sym_cp.manifest_checksum = man_hash
            sym_cp.source_rows = src_count
            sym_cp.normalized_rows = norm_count
            sym_cp.rejected_rows = rej_count

            # Update batch checkpoint
            checkpoint.completed_symbols += 1
            checkpoint.pending_symbols -= 1
            checkpoint.source_rows += src_count
            checkpoint.normalized_rows += norm_count
            checkpoint.rejected_rows += rej_count
            checkpoint.raw_checksums[symbol] = raw_hash
            checkpoint.normalized_checksums[symbol] = norm_hash
            checkpoint.manifest_checksums[symbol] = man_hash
            save_checkpoint(checkpoint, checkpoint_file)

            # Pacing floor
            if idx < len(symbols_to_process) - 1 and spacing > 0:
                time.sleep(spacing)

    finally:
        if client is not None:
            try:
                if hasattr(client, "exit"):
                    client.exit()
                elif hasattr(client, "close"):
                    client.close()
                client_closed = True
            except Exception as close_exc:
                client_closed = False
                if exit_code == BatchExitCode.SUCCESS:
                    exit_code = BatchExitCode.CLIENT_CLOSE_ERROR
                    stop_reason = f"Client close error: {close_exc}"

    duration_total = time.monotonic() - start_time

    # Final batch status evaluation
    if exit_code == BatchExitCode.SUCCESS:
        if checkpoint.completed_symbols == contract.symbol_count:
            checkpoint.final_status = BatchStatus.SUCCEEDED
            checkpoint.stop_reason = None
            save_checkpoint(checkpoint, checkpoint_file)
            # Generate and persist batch audit
            audit_payload = generate_batch_audit_payload(checkpoint, contract, duration_total)
            save_batch_audit(audit_payload, staging_root / "audit" / "batch_audit.json")
        else:
            checkpoint.final_status = BatchStatus.HALTED
            save_checkpoint(checkpoint, checkpoint_file)
            exit_code = BatchExitCode.INCOMPLETE_BATCH

    summary_result = {
        "batch_id": contract.batch_id,
        "exit_code": exit_code.value,
        "completed_symbols": checkpoint.completed_symbols,
        "total_symbols": contract.symbol_count,
        "source_rows": checkpoint.source_rows,
        "normalized_rows": checkpoint.normalized_rows,
        "rejected_rows": checkpoint.rejected_rows,
        "duration_seconds": duration_total,
        "client_closed": client_closed,
        "stop_reason": stop_reason or checkpoint.stop_reason,
        "last_error": last_error_details,
    }

    return exit_code, summary_result


def main() -> None:
    """CLI entry point for phase7.sources.batch_pilot."""
    parser = argparse.ArgumentParser(
        prog="phase7.sources.batch_pilot",
        description="Phase 7 governed 20-stock historical batch pilot CLI.",
    )
    parser.add_argument(
        "--staging-root",
        type=Path,
        required=True,
        help="External staging directory outside Git",
    )
    parser.add_argument(
        "--authorization-file",
        type=Path,
        default=None,
        help="Path to single-use batch authorization marker",
    )
    parser.add_argument(
        "--execute-live",
        action="store_true",
        help="Authorize live network requests",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform offline validation without network requests",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from existing validated checkpoint",
    )
    parser.add_argument(
        "--selection-dir",
        type=Path,
        default=None,
        help="Optional external path to selection files",
    )

    args = parser.parse_args()
    code, summary = run_batch_pilot(
        staging_root=args.staging_root,
        authorization_file=args.authorization_file,
        execute_live=args.execute_live,
        dry_run=args.dry_run,
        resume=args.resume,
        selection_dir=args.selection_dir,
    )
    print(f"Batch Pilot Exit Code: {code.value}")
    print(f"Summary: {json.dumps(summary, indent=2)}")
    sys.exit(code.value)


if __name__ == "__main__":
    main()
