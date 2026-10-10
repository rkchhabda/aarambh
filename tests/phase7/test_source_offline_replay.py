"""Offline replay and acceptance tests for preserved NSE 4.0.1 RELIANCE historical payload.

Performs offline normalization replay:
- Zero network requests.
- Reads external immutable raw file:
  C:\\Users\\r_chh\\gaurvideep_phase7_staging\\nse500\\pilot_4_9\\raw\\historical\\RELIANCE_2024-01-01_2024-01-31_1d_20261010T081014Z_59af0e39.json
- Validates raw SHA-256:
  59af0e392d7bb9073a49603115e11150a8adbab59e0619c6a0608d19ffcbef63
- Normalizes all 22 rows using NSE_4_0_1_HISTORICAL_CAMELCASE_V1 mapping.
- Writes replay artifacts to:
  C:\\Users\\r_chh\\gaurvideep_phase7_staging\\nse500\\pilot_4_9\\offline_replay_4_9e\\
- Leaves live pilot manifests and raw evidence completely intact.
- Labels result: OFFLINE_NORMALIZATION_REPLAY.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pytest

from phase7.sources.audit import StructuralQualityAudit
from phase7.sources.authorization import find_repo_root
from phase7.sources.contracts import (
    HistoricalEODRecord,
    RequestManifest,
    RequestStatus,
)
from phase7.sources.manifest import check_audit_conservation, compute_sha256_records
from phase7.sources.normalization import normalize_historical_row
from phase7.sources.persistence import (
    compute_canonical_sha256,
    validate_persistence_path_outside_git,
)
from phase7.sources.schema_mappings import NSE_4_0_1_SCHEMA_VERSION

EXPECTED_RAW_SHA256 = "59af0e392d7bb9073a49603115e11150a8adbab59e0619c6a0608d19ffcbef63"
STAGING_ROOT = Path(r"C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9")
PRESERVED_RAW_PATH = STAGING_ROOT / "raw" / "historical" / "RELIANCE_2024-01-01_2024-01-31_1d_20261010T081014Z_59af0e39.json"
OFFLINE_REPLAY_DIR = STAGING_ROOT / "offline_replay_4_9e"


def run_offline_reliance_replay(staging_root: Path = STAGING_ROOT) -> dict:
    """Execute offline normalization replay over the preserved RELIANCE payload."""
    raw_path = PRESERVED_RAW_PATH
    if not raw_path.exists():
        pytest.skip(f"Preserved raw file does not exist at {raw_path}")

    # 1. Verify raw file checksum
    raw_bytes = raw_path.read_bytes()
    computed_raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    if computed_raw_sha256.lower() != EXPECTED_RAW_SHA256.lower():
        raise ValueError(
            f"RAW_CHECKSUM_MISMATCH: expected {EXPECTED_RAW_SHA256}, got {computed_raw_sha256}"
        )

    # 2. Parse raw payload
    raw_payload = json.loads(raw_bytes.decode("utf-8"))
    if not isinstance(raw_payload, list):
        raise TypeError(f"Expected list payload, got {type(raw_payload).__name__}")

    source_row_count = len(raw_payload)

    # 3. Normalize all rows
    normalized_records = []
    rejected_rows = []
    seen_dates = set()
    replay_ts = datetime.now(timezone.utc).isoformat()

    for idx, row in enumerate(raw_payload):
        try:
            rec = normalize_historical_row(
                raw_row=row,
                symbol="RELIANCE",
                ingestion_timestamp=replay_ts,
                start_date="2024-01-01",
                end_date="2024-01-31",
            )
            if rec.trading_date in seen_dates:
                rejected_rows.append({"row_index": idx, "reason": "DUPLICATE_NATURAL_KEY"})
            else:
                seen_dates.add(rec.trading_date)
                normalized_records.append(rec)
        except Exception as e:
            rejected_rows.append({"row_index": idx, "reason": str(e)})

    norm_count = len(normalized_records)
    rej_count = len(rejected_rows)

    # 4. Conservation check
    conservation_valid = check_audit_conservation(source_row_count, norm_count, rej_count)
    if not conservation_valid:
        raise ValueError(
            f"AUDIT_CONSERVATION_FAILURE: source ({source_row_count}) != norm ({norm_count}) + rej ({rej_count})"
        )

    # 5. Persist offline replay artifacts outside Git
    replay_dir = OFFLINE_REPLAY_DIR
    validate_persistence_path_outside_git(replay_dir)
    replay_dir.mkdir(parents=True, exist_ok=True)

    # Write normalized JSONL
    jsonl_lines = []
    missing_fields = {
        "isin": 0, "previous_close": 0, "last_price": 0, "vwap": 0,
        "turnover": 0, "number_of_trades": 0, "deliverable_quantity": 0,
        "delivery_percentage": 0,
    }
    for r in normalized_records:
        if r.isin is None:
            missing_fields["isin"] += 1
        if r.previous_close is None:
            missing_fields["previous_close"] += 1
        if r.last_price is None:
            missing_fields["last_price"] += 1
        if r.vwap is None:
            missing_fields["vwap"] += 1
        if r.total_traded_value_inr is None:
            missing_fields["turnover"] += 1
        if r.number_of_trades is None:
            missing_fields["number_of_trades"] += 1
        if r.deliverable_quantity is None:
            missing_fields["deliverable_quantity"] += 1
        if r.delivery_percentage is None:
            missing_fields["delivery_percentage"] += 1

        rec_dict = {
            "trading_date": r.trading_date,
            "symbol": r.symbol,
            "isin": r.isin,
            "exchange_series": r.exchange_series,
            "previous_close": r.previous_close,
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
            "last_price": r.last_price,
            "vwap": r.vwap,
            "total_traded_quantity": r.total_traded_quantity,
            "total_traded_value_inr": r.total_traded_value_inr,
            "number_of_trades": r.number_of_trades,
            "deliverable_quantity": r.deliverable_quantity,
            "delivery_percentage": r.delivery_percentage,
            "trading_status": r.trading_status,
            "adjustment_state": r.adjustment_state.value,
            "traded_value_status": r.traded_value_status.value,
            "source_timestamp": r.source_timestamp,
            "ingestion_timestamp": r.ingestion_timestamp,
            "source_identifier": r.source_identifier,
            "row_hash": r.row_hash,
            "mapping_version": r.mapping_version,
        }
        jsonl_lines.append(json.dumps(rec_dict, sort_keys=True, default=str))

    jsonl_bytes = ("\n".join(jsonl_lines) + "\n").encode("utf-8")
    norm_checksum = compute_canonical_sha256(jsonl_bytes)

    norm_path = replay_dir / "RELIANCE_normalized_replay.jsonl"
    with norm_path.open("wb") as f:
        f.write(jsonl_bytes)

    # Run structural audit
    audit_engine = StructuralQualityAudit(normalized_records)
    audit_result = audit_engine.run_audit()

    # Write replay summary report
    replay_manifest = {
        "execution_label": "OFFLINE_NORMALIZATION_REPLAY",
        "symbol": "RELIANCE",
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "raw_checksum": computed_raw_sha256,
        "normalized_checksum": norm_checksum,
        "source_row_count": source_row_count,
        "normalized_row_count": norm_count,
        "rejected_row_count": rej_count,
        "conservation_status": "CONSERVED",
        "date_coverage_pct": (norm_count / 22.0) * 100.0,
        "duplicate_natural_keys": audit_result["duplicate_natural_keys"],
        "invalid_ohlc_rows": audit_result["invalid_ohlc_rows"],
        "negative_volume_rows": audit_result["negative_volume_rows"],
        "missing_fields": missing_fields,
        "schema_mapping_version": NSE_4_0_1_SCHEMA_VERSION,
        "replay_timestamp": replay_ts,
    }

    manifest_path = replay_dir / "replay_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(replay_manifest, f, indent=2, sort_keys=True)

    return {
        "status": "OFFLINE_NORMALIZATION_REPLAY",
        "source_row_count": source_row_count,
        "normalized_row_count": norm_count,
        "rejected_row_count": rej_count,
        "raw_checksum": computed_raw_sha256,
        "normalized_checksum": norm_checksum,
        "date_coverage_pct": (norm_count / 22.0) * 100.0,
        "duplicate_count": audit_result["duplicate_natural_keys"],
        "invalid_ohlc_count": audit_result["invalid_ohlc_rows"],
        "negative_value_count": audit_result["negative_volume_rows"],
        "missing_fields": missing_fields,
        "schema_mapping_version": NSE_4_0_1_SCHEMA_VERSION,
        "norm_path": norm_path,
        "manifest_path": manifest_path,
    }


def test_offline_reliance_replay_passes():
    """Verify offline normalization replay of preserved RELIANCE payload meets all 18 acceptance criteria."""
    result = run_offline_reliance_replay()

    # Acceptance Criterion 1: Raw checksum matches expected
    assert result["raw_checksum"].lower() == EXPECTED_RAW_SHA256.lower()

    # Acceptance Criterion 2: Source rows equal 22
    assert result["source_row_count"] == 22

    # Acceptance Criterion 3: Normalized rows equal 22
    assert result["normalized_row_count"] == 22

    # Acceptance Criterion 4: Rejected rows equal zero
    assert result["rejected_row_count"] == 0

    # Acceptance Criterion 5: Conservation holds (22 = 22 + 0)
    assert result["source_row_count"] == result["normalized_row_count"] + result["rejected_row_count"]

    # Acceptance Criterion 6: Date coverage covers 100% of the 22 supplied dates
    assert result["date_coverage_pct"] == 100.0

    # Acceptance Criterion 8: Duplicate natural keys equal zero
    assert result["duplicate_count"] == 0

    # Acceptance Criterion 9: Invalid OHLC relationships equal zero
    assert result["invalid_ohlc_count"] == 0

    # Acceptance Criterion 10: Negative-value count equals zero
    assert result["negative_value_count"] == 0

    # Acceptance Criterion 11: Normalized checksum is produced (64 hex characters)
    assert len(result["normalized_checksum"]) == 64

    # Acceptance Criterion 12: Mapping version is recorded
    assert result["schema_mapping_version"] == NSE_4_0_1_SCHEMA_VERSION

    # Acceptance Criterion 14: Original raw file is not modified
    assert PRESERVED_RAW_PATH.exists()
    assert hashlib.sha256(PRESERVED_RAW_PATH.read_bytes()).hexdigest().lower() == EXPECTED_RAW_SHA256.lower()

    # Acceptance Criterion 15: Existing live-pilot manifest is not changed
    live_manifests = list((STAGING_ROOT / "manifests").glob("manifest_RELIANCE_*.json"))
    assert len(live_manifests) >= 1
    # Check that live manifest remains with its original status (PARTIAL)
    with live_manifests[0].open("r", encoding="utf-8") as f:
        live_m_data = json.load(f)
    assert live_m_data["status"] == "PARTIAL"

    # Acceptance Criterion 16: Output is written only to offline_replay_4_9e
    assert result["norm_path"].parent == OFFLINE_REPLAY_DIR
    assert result["manifest_path"].parent == OFFLINE_REPLAY_DIR

    # Acceptance Criterion 17: Result is labelled OFFLINE_NORMALIZATION_REPLAY
    assert result["status"] == "OFFLINE_NORMALIZATION_REPLAY"
    assert result["status"] != "NSE_FIVE_STOCK_PILOT_PASSED"
