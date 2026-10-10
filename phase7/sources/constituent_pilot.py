"""Phase 7 NIFTY 500 Current Constituent Snapshot Pilot Driver.

Strictly enforces:
- Milestone 4.10A authorization marker validation and atomic consumption
- Single constituent request to upstream NSE
- Fail-closed validation and isolation outside Git repository
- Conservation invariant: source_row_count = normalized_row_count + rejected_row_count
- Plausibility range: 490 to 510 unique symbols
- Panel-version identifier generation: CURRENT_NIFTY500_<DATE>_<HASH[:8].upper()>
- Deterministic client closure in finally block
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

from phase7.sources.client_factory import create_real_nse_client
from phase7.sources.constituent_authorization import (
    consume_snapshot_authorization,
    load_and_validate_snapshot_authorization,
    validate_staging_root,
)
from phase7.sources.constituent_persistence import (
    save_normalized_snapshot,
    save_raw_snapshot,
    save_rejected_rows,
    save_snapshot_manifest,
)
from phase7.sources.contracts import (
    ConstituentRecord,
    ConstituentSnapshotManifest,
    RejectedRowRecord,
    RequestStatus,
    SnapshotPilotExitCode,
    SnapshotPilotOutcome,
)
from phase7.sources.nse_constituents import (
    AUTHORIZED_INDEX_NAME,
    fetch_current_index_constituents,
    validate_index_name,
)


def run_snapshot_pilot(
    index_name: str,
    staging_root: Union[Path, str],
    authorization_file: Union[Path, str],
    execute_live: bool = False,
    client_factory: Any = create_real_nse_client,
) -> int:
    """Execute the governed NIFTY 500 constituent snapshot pilot.

    Returns process exit code adhering to SnapshotPilotExitCode contract.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()
    retrieval_ts = datetime.now(timezone.utc).isoformat()
    ts_file_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # Step 1: Input guards
    try:
        valid_index = validate_index_name(index_name)
    except Exception as e:
        print(f"PILOT_HALT: Argument error on index name '{index_name}': {e}", file=sys.stderr)
        return SnapshotPilotExitCode.ARGUMENT_ERROR.value

    try:
        valid_staging = validate_staging_root(staging_root)
    except Exception as e:
        print(f"PILOT_HALT: Staging root validation failure: {e}", file=sys.stderr)
        return SnapshotPilotExitCode.ARGUMENT_ERROR.value

    # Step 2: Validate single-use authorization marker
    auth_file_path = Path(authorization_file)
    try:
        auth_record = load_and_validate_snapshot_authorization(
            marker_path=auth_file_path,
            staging_root=valid_staging,
            expected_index=valid_index,
        )
    except Exception as e:
        print(f"PILOT_HALT: Authorization marker validation failed: {e}", file=sys.stderr)
        return SnapshotPilotExitCode.AUTHORIZATION_ERROR.value

    if not execute_live:
        print("Pre-flight validation passed. Live execution flag --execute-live was not supplied. Exiting safely.")
        return SnapshotPilotExitCode.SUCCESS.value

    # Step 3: Write initial PENDING manifest
    initial_manifest = ConstituentSnapshotManifest(
        request_id=request_id,
        index_name=valid_index,
        retrieval_timestamp=retrieval_ts,
        client_version="nse-4.0.1",
        source_identifier="NSEDataFetcher",
        status=RequestStatus.PENDING,
        source_row_count=0,
        normalized_row_count=0,
        rejected_row_count=0,
        unique_symbols=0,
        duplicate_symbols=0,
        missing_symbols=0,
        unique_isins=0,
        duplicate_isins=0,
        missing_isins=0,
        missing_series=0,
        missing_sectors=0,
        missing_industries=0,
        classification="CURRENT_SNAPSHOT_ONLY",
        raw_checksum="",
        normalized_checksum="",
        panel_version_id="",
    )
    try:
        save_snapshot_manifest(initial_manifest, valid_staging)
    except Exception as e:
        print(f"PILOT_HALT: Failed to write initial manifest: {e}", file=sys.stderr)
        return SnapshotPilotExitCode.PERSISTENCE_MANIFEST_ERROR.value

    # Step 4: Atomically consume authorization marker
    try:
        consumed_path = consume_snapshot_authorization(auth_file_path)
        print(f"Consumed Marker: {consumed_path}")
    except Exception as e:
        print(f"PILOT_HALT: Failed to atomically consume authorization marker: {e}", file=sys.stderr)
        return SnapshotPilotExitCode.AUTHORIZATION_ERROR.value

    # Step 5: Construct client
    client = None
    client_init_count = 0
    client_close_count = 0
    try:
        raw_download_dir = valid_staging / "raw"
        raw_download_dir.mkdir(parents=True, exist_ok=True)
        client = client_factory(download_folder=raw_download_dir, server=True, timeout=15)
        client_init_count = 1
        print("Client Initialized: NSE")
    except Exception as e:
        print(f"PILOT_HALT: Client construction failure: {e}", file=sys.stderr)
        return SnapshotPilotExitCode.CLIENT_CONSTRUCTION_ERROR.value

    # Step 6: Upstream retrieval & normalization
    raw_path: Optional[Path] = None
    raw_checksum = ""
    norm_path: Optional[Path] = None
    norm_checksum = ""
    panel_version_id = ""

    try:
        # Retrieve raw response directly for raw serialization
        if hasattr(client, "listEquityStocksByIndex"):
            raw_payload = client.listEquityStocksByIndex(index=valid_index)
        else:
            print("PILOT_HALT: Client lacks listEquityStocksByIndex method.", file=sys.stderr)
            return SnapshotPilotExitCode.CLIENT_CONSTRUCTION_ERROR.value

        # Persist immutable raw payload outside Git
        raw_path, raw_checksum = save_raw_snapshot(
            raw_payload=raw_payload,
            staging_root=valid_staging,
            timestamp_str=ts_file_str,
        )

        # Normalize snapshot records
        # Fake client or wrapper to normalize the retrieved payload
        class _PayloadClient:
            def listEquityStocksByIndex(self, index: str = "NIFTY 500"):
                return raw_payload

        records, rejected_rows, audit = fetch_current_index_constituents(
            client=_PayloadClient(),
            index_name=valid_index,
        )

        # Persist rejected rows if any
        if rejected_rows:
            save_rejected_rows(rejected_rows, valid_staging, timestamp_str=ts_file_str)

        # Step 7: Acceptance criteria checks
        # Check conservation
        if not audit["conservation_holds"]:
            print(f"PILOT_HALT: Conservation failure: source={audit['source_row_count']}, norm={audit['normalized_row_count']}, rej={audit['rejected_row_count']}", file=sys.stderr)
            return SnapshotPilotExitCode.SCHEMA_NORMALIZATION_ERROR.value

        # Check plausibility (490 to 510 unique symbols)
        if not audit["is_plausible_count"]:
            print(f"PILOT_HALT: Unique symbol count {audit['unique_symbols']} outside plausibility range [490, 510].", file=sys.stderr)
            return SnapshotPilotExitCode.SCHEMA_NORMALIZATION_ERROR.value

        # Check duplicate symbols == 0, missing symbols == 0, invalid symbols == 0
        if audit["duplicate_symbols"] > 0 or audit["missing_symbols"] > 0 or audit["invalid_symbols"] > 0:
            print(f"PILOT_HALT: Symbol hygiene check failed: dups={audit['duplicate_symbols']}, missing={audit['missing_symbols']}, invalid={audit['invalid_symbols']}", file=sys.stderr)
            return SnapshotPilotExitCode.SCHEMA_NORMALIZATION_ERROR.value

        if audit["normalized_row_count"] == 0:
            print("PILOT_HALT: Normalized row count is 0.", file=sys.stderr)
            return SnapshotPilotExitCode.SCHEMA_NORMALIZATION_ERROR.value

        # Step 8: Persist normalized records outside Git
        norm_path, norm_checksum = save_normalized_snapshot(
            records=records,
            staging_root=valid_staging,
            timestamp_str=ts_file_str,
        )

        # Step 9: Generate panel-version identifier
        # Format: CURRENT_NIFTY500_<DATE>_<HASH[:8].upper()>
        date_stamp = audit.get("source_report_date")
        if date_stamp:
            date_clean = re.sub(r"[^0-9A-Za-z]", "", date_stamp)
        else:
            date_clean = datetime.now(timezone.utc).strftime("%Y%m%d")
        panel_version_id = f"CURRENT_NIFTY500_{date_clean}_{norm_checksum[:8].upper()}"

        # Step 10: Finalize manifest
        duration = time.time() - start_time
        final_manifest = ConstituentSnapshotManifest(
            request_id=request_id,
            index_name=valid_index,
            retrieval_timestamp=retrieval_ts,
            client_version="nse-4.0.1",
            source_identifier="NSEDataFetcher",
            status=RequestStatus.SUCCEEDED,
            source_row_count=audit["source_row_count"],
            normalized_row_count=audit["normalized_row_count"],
            rejected_row_count=audit["rejected_row_count"],
            unique_symbols=audit["unique_symbols"],
            duplicate_symbols=audit["duplicate_symbols"],
            missing_symbols=audit["missing_symbols"],
            unique_isins=audit["unique_isins"],
            duplicate_isins=audit["duplicate_isins"],
            missing_isins=audit["missing_isins"],
            missing_series=audit["missing_series"],
            missing_sectors=audit["missing_sectors"],
            missing_industries=audit["missing_industries"],
            classification=audit["classification"],
            raw_checksum=raw_checksum,
            normalized_checksum=norm_checksum,
            panel_version_id=panel_version_id,
            raw_file_path=str(raw_path) if raw_path else None,
            normalized_file_path=str(norm_path) if norm_path else None,
            duration_seconds=duration,
        )
        save_snapshot_manifest(final_manifest, valid_staging)

        print(f"FINAL OUTCOME: {SnapshotPilotOutcome.PASSED.value}")
        print(f"Panel Version ID: {panel_version_id}")
        print(f"Unique Symbols: {audit['unique_symbols']}")
        print(f"Source Rows: {audit['source_row_count']}")
        print(f"Normalized Rows: {audit['normalized_row_count']}")
        print(f"Rejected Rows: {audit['rejected_row_count']}")
        print(f"Raw Checksum: {raw_checksum}")
        print(f"Normalized Checksum: {norm_checksum}")
        print(f"Client Initialized: {client_init_count}")
        print("Exit Code: 0")

        return SnapshotPilotExitCode.SUCCESS.value

    except ConnectionError as ce:
        print(f"PILOT_HALT: Upstream connectivity failure: {ce}", file=sys.stderr)
        return SnapshotPilotExitCode.RETRIEVAL_ERROR.value
    except TimeoutError as te:
        print(f"PILOT_HALT: Upstream timeout failure: {te}", file=sys.stderr)
        return SnapshotPilotExitCode.RETRIEVAL_ERROR.value
    except (ValueError, TypeError) as se:
        print(f"PILOT_HALT: Schema normalization failure: {se}", file=sys.stderr)
        return SnapshotPilotExitCode.SCHEMA_NORMALIZATION_ERROR.value
    except Exception as e:
        print(f"PILOT_HALT: Unexpected internal error: {e}", file=sys.stderr)
        return SnapshotPilotExitCode.UNEXPECTED_INTERNAL_ERROR.value
    finally:
        if client is not None and hasattr(client, "exit"):
            try:
                client.exit()
                client_close_count = 1
                print(f"Client Closed: {client_close_count}")
            except Exception as e:
                print(f"WARNING: Error closing client: {e}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for constituent snapshot pilot execution."""
    parser = argparse.ArgumentParser(
        description="Phase 7 NIFTY 500 Current Constituent Snapshot Pilot Execution"
    )
    parser.add_argument(
        "--index-name",
        default=AUTHORIZED_INDEX_NAME,
        help=f"Index name to retrieve constituents for (default: '{AUTHORIZED_INDEX_NAME}')",
    )
    parser.add_argument(
        "--staging-root",
        required=True,
        help="Absolute path to external staging root directory",
    )
    parser.add_argument(
        "--authorization-file",
        required=True,
        help="Absolute path to single-use authorization marker JSON file",
    )
    parser.add_argument(
        "--execute-live",
        action="store_true",
        default=False,
        help="Authorize live upstream network call",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for constituent snapshot pilot."""
    parser = build_parser()
    args = parser.parse_args(argv)

    exit_code = run_snapshot_pilot(
        index_name=args.index_name,
        staging_root=args.staging_root,
        authorization_file=args.authorization_file,
        execute_live=args.execute_live,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
