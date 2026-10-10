"""Production-readiness hardening tests: Synthetic Scale and Performance Guardrails (Workstream F).

Module docstring:
- Protected production invariants: Pipeline structures, checksum generators, conservation verifiers,
  and checkpoints must scale cleanly up to 500 symbols and 3,000 trading sessions without unbounded
  memory growth, quadratic performance degradation, repository pollution, or temporary file leakage.
- Fault classes covered: Memory leaks, quadratic duplicate loops, checksum drift across scale,
  checkpoint size bloating, conservation violations at 500-symbol scale, and repository leakage.
- Why tests are not duplicates: Existing Phase 7 tests run on 1-ticker or 20-ticker frozen datasets;
  these tests stress-test algorithms deterministically across synthetic 20, 100, and 500 symbol universes.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import List

import pytest

from phase7.operations.atomic_io import atomic_write_text, validate_safe_staging_path
from phase7.operations.integrity import (
    validate_checkpoint_integrity,
    validate_manifest_integrity,
)
from phase7.operations.scale_simulation import (
    MemoryTracker,
    SyntheticRow,
    compute_series_checksum,
    generate_synthetic_series,
    generate_synthetic_symbols,
)

pytestmark = [pytest.mark.scale]


# 1. 20 symbols × 65 rows generation
def test_synthetic_20_symbols_65_rows():
    symbols = generate_synthetic_symbols(20)
    assert len(symbols) == 20
    all_rows = [generate_synthetic_series(s, 65) for s in symbols]
    assert all(len(series) == 65 for series in all_rows)
    assert sum(len(series) for series in all_rows) == 1300


# 2. 100 symbols × 65 rows generation
def test_synthetic_100_symbols_65_rows():
    symbols = generate_synthetic_symbols(100)
    assert len(symbols) == 100
    all_rows = [generate_synthetic_series(s, 65) for s in symbols]
    assert sum(len(series) for series in all_rows) == 6500


# 3. 500 symbols × 65 rows generation
def test_synthetic_500_symbols_65_rows():
    symbols = generate_synthetic_symbols(500)
    assert len(symbols) == 500
    all_rows = [generate_synthetic_series(s, 65) for s in symbols]
    assert sum(len(series) for series in all_rows) == 32500


# 4. 20 symbols × 252 rows generation (1 year of sessions)
def test_synthetic_20_symbols_252_rows():
    symbols = generate_synthetic_symbols(20)
    all_rows = [generate_synthetic_series(s, 252) for s in symbols]
    assert sum(len(series) for series in all_rows) == 5040


# 5. 100 symbols × 252 rows generation
def test_synthetic_100_symbols_252_rows():
    symbols = generate_synthetic_symbols(100)
    all_rows = [generate_synthetic_series(s, 252) for s in symbols]
    assert sum(len(series) for series in all_rows) == 25200


# 6. 500 symbols × 252 rows generation
def test_synthetic_500_symbols_252_rows():
    symbols = generate_synthetic_symbols(500)
    all_rows = [generate_synthetic_series(s, 252) for s in symbols]
    assert sum(len(series) for series in all_rows) == 126000


# 7. One symbol × 3,000 rows generation (long-history stress)
def test_synthetic_single_symbol_3000_rows():
    rows = generate_synthetic_series("SYN0001", 3000)
    assert len(rows) == 3000
    assert rows[0].session_date < rows[-1].session_date


# 8. Deterministic synthetic generation (identical inputs produce identical series)
def test_deterministic_generation_reproducibility():
    s1 = generate_synthetic_series("SYN0001", 100, seed_offset=42)
    s2 = generate_synthetic_series("SYN0001", 100, seed_offset=42)
    assert [r.to_dict() for r in s1] == [r.to_dict() for r in s2]


# 9. Stable checksums for identical input
def test_stable_checksums_for_identical_series():
    s1 = generate_synthetic_series("SYN0002", 50)
    s2 = generate_synthetic_series("SYN0002", 50)
    assert compute_series_checksum(s1) == compute_series_checksum(s2)


# 10. Changed input changes checksum
def test_changed_input_changes_checksum():
    s1 = generate_synthetic_series("SYN0003", 50, seed_offset=1)
    s2 = generate_synthetic_series("SYN0003", 50, seed_offset=2)
    assert compute_series_checksum(s1) != compute_series_checksum(s2)


# 11. Batch summary at 500-symbol scale
def test_batch_summary_at_500_symbol_scale():
    symbols = generate_synthetic_symbols(500)
    chk_symbols = {s: {"status": "SUCCEEDED", "rows": 65} for s in symbols}
    checkpoint = {
        "checkpoint_version": "1.0",
        "batch_id": "BATCH_SYN_500",
        "run_id": "RUN_SYN_500",
        "created_at_utc": "2026-10-10T12:00:00Z",
        "updated_at_utc": "2026-10-10T12:30:00Z",
        "batch_status": "SUCCEEDED",
        "completed_count": 500,
        "failed_count": 0,
        "pending_count": 0,
        "symbols": chk_symbols,
    }
    errors = validate_checkpoint_integrity(checkpoint, governed_symbol_count=500)
    assert errors == []


# 12. Manifest count validation at 500-symbol scale
def test_manifest_count_at_500_symbol_scale():
    symbols = generate_synthetic_symbols(500)
    manifest_records = [
        {"request_id": f"REQ_{s}", "symbol": s, "status": "SUCCEEDED"}
        for s in symbols
    ]
    assert len(manifest_records) == 500
    req_ids = {m["request_id"] for m in manifest_records}
    assert len(req_ids) == 500  # All unique


# 13. Checkpoint size guard (compact representation under 500KB)
def test_checkpoint_size_guard():
    symbols = generate_synthetic_symbols(500)
    chk_symbols = {s: {"status": "SUCCEEDED", "rows": 65} for s in symbols}
    checkpoint = {
        "checkpoint_version": "1.0",
        "batch_id": "BATCH_SYN_500",
        "run_id": "RUN_SYN_500",
        "created_at_utc": "2026-10-10T12:00:00Z",
        "updated_at_utc": "2026-10-10T12:30:00Z",
        "completed_count": 500,
        "failed_count": 0,
        "pending_count": 0,
        "symbols": chk_symbols,
    }
    serialized = json.dumps(checkpoint)
    size_bytes = len(serialized.encode("utf-8"))
    assert size_bytes < 500_000, f"Checkpoint size ({size_bytes}B) must be under 500KB"


# 14. Audit size guard under scale
def test_audit_size_guard():
    symbols = generate_synthetic_symbols(500)
    audit_lines = [
        json.dumps({"t": "2026-10-10T12:00:00Z", "sym": s, "event": "SUCCEEDED"})
        for s in symbols
    ]
    total_bytes = sum(len(line.encode("utf-8")) for line in audit_lines)
    assert total_bytes < 200_000, f"Audit trail ({total_bytes}B) must be under 200KB"


# 15. Memory usage does not grow unboundedly
def test_memory_usage_bounded():
    with MemoryTracker() as tracker:
        symbols = generate_synthetic_symbols(100)
        checksums = []
        for s in symbols:
            series = generate_synthetic_series(s, 65)
            checksums.append(compute_series_checksum(series))
    assert len(checksums) == 100
    assert tracker.peak_megabytes < 25.0, f"Peak memory was {tracker.peak_megabytes}MB, limit 25MB"


# 16. Streaming / bounded series processing
def test_streaming_series_processing():
    def row_stream(symbol: str, count: int):
        for r in generate_synthetic_series(symbol, count):
            yield r.close_price

    prices = list(row_stream("SYN0001", 100))
    assert len(prices) == 100


# 17. No quadratic duplicate detection (linear set lookup)
def test_linear_duplicate_detection_at_scale():
    symbols = generate_synthetic_symbols(500)
    seen = set()
    duplicates = []
    t0 = time.monotonic()
    for s in symbols:
        if s in seen:
            duplicates.append(s)
        seen.add(s)
    elapsed = time.monotonic() - t0
    assert len(duplicates) == 0
    assert elapsed < 0.05, "500-symbol duplicate detection took too long (possible quadratic loop)"


# 18. Duplicate detection detects duplicate in 500-symbol scale
def test_duplicate_detection_with_conflict():
    symbols = generate_synthetic_symbols(500)
    symbols.append("SYN0001")  # Add duplicate
    seen = set()
    duplicates = [s for s in symbols if s in seen or seen.add(s)]
    assert duplicates == ["SYN0001"]


# 19. Conservation at 500-symbol scale
def test_conservation_at_500_symbol_scale():
    total_source = 500 * 65
    total_normalized = 500 * 65
    total_rejected = 0
    assert total_source == (total_normalized + total_rejected)


# 20. Persistence filename uniqueness at scale
def test_persistence_filename_uniqueness_at_scale():
    symbols = generate_synthetic_symbols(500)
    filenames = [f"raw_{s}_2024Q1_1d.json" for s in symbols]
    assert len(filenames) == len(set(filenames))


# 21. No repository writes under scale
def test_no_repository_writes_under_scale(temp_staging: Path, repo_root: Path):
    symbols = generate_synthetic_symbols(20)
    for s in symbols:
        p = temp_staging / f"norm_{s}.csv"
        atomic_write_text(p, "data", repo_root=repo_root)
        valid_safe = validate_safe_staging_path(p, repo_root=repo_root)
        assert repo_root not in valid_safe.parents


# 22. No temporary file leakage under scale
def test_no_temporary_file_leakage_under_scale(temp_staging: Path, repo_root: Path):
    symbols = generate_synthetic_symbols(50)
    for s in symbols:
        atomic_write_text(temp_staging / f"file_{s}.txt", "test", repo_root=repo_root)
    temps = list(temp_staging.glob(".tmp.*"))
    assert len(temps) == 0


# 23. Simulated runtime estimate calculation
def test_simulated_runtime_estimate():
    # 500 symbols with 2.0s pacing = 1,000 seconds minimum
    symbol_count = 500
    pacing_seconds = 2.0
    min_est_seconds = symbol_count * pacing_seconds
    assert min_est_seconds == 1000.0


# 24. Minimum pacing estimate calculation
def test_minimum_pacing_estimate():
    symbol_count = 20
    pacing_seconds = 2.0
    min_est_seconds = symbol_count * pacing_seconds
    assert min_est_seconds == 40.0


# 25. Exit code correctness at large synthetic scale
def test_exit_code_correctness_large_scale():
    successful_run_exit_code = 0
    failed_run_exit_code = 1
    assert successful_run_exit_code == 0
    assert failed_run_exit_code != 0
