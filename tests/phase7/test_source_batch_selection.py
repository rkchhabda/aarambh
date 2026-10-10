"""Tests for Phase 7 deterministic 20-symbol selection and freezing."""

import hashlib
import json
from pathlib import Path
import tempfile
import pytest

from phase7.sources.batch_selection import (
    EXCLUDED_FIVE_PILOT_SYMBOLS,
    SELECTION_CLASSIFICATION,
    SelectionResult,
    calculate_ordered_symbols_hash,
    load_selection_manifest,
    perform_deterministic_selection,
    save_selection_evidence,
)


def _create_mock_snapshot(path: Path, count: int = 500, symbols=None) -> str:
    """Helper to create synthetic snapshot file with specified symbols and return SHA-256."""
    if symbols is None:
        symbols = [f"SYM{i:04d}" for i in range(count)]
    rows = []
    for s in symbols:
        rows.append(
            json.dumps({
                "symbol": s,
                "classification": "CURRENT_SNAPSHOT_ONLY",
                "exchange_series": "EQ",
            })
        )
    content = "\n".join(rows).encode("utf-8")
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def test_frozen_snapshot_checksum_validation():
    with tempfile.TemporaryDirectory() as tmp_dir:
        snap_path = Path(tmp_dir) / "snapshot.jsonl"
        expected_hash = _create_mock_snapshot(snap_path, 500)
        
        # Valid checksum matches
        result = perform_deterministic_selection(
            snapshot_path=snap_path,
            expected_checksum=expected_hash,
        )
        assert result.selected_symbol_count == 20
        assert result.source_constituent_count == 500

        # Mismatched checksum raises ValueError
        with pytest.raises(ValueError, match="Snapshot checksum mismatch"):
            perform_deterministic_selection(
                snapshot_path=snap_path,
                expected_checksum="0000000000000000000000000000000000000000000000000000000000000000",
            )


def test_exact_500_symbol_source_count_enforced():
    with tempfile.TemporaryDirectory() as tmp_dir:
        snap_path = Path(tmp_dir) / "snapshot.jsonl"
        # Only 400 symbols
        h = _create_mock_snapshot(snap_path, 400)
        with pytest.raises(ValueError, match="Expected exactly 500 unique symbols"):
            perform_deterministic_selection(
                snapshot_path=snap_path,
                expected_checksum=h,
            )


def test_deterministic_selection_reproducibility():
    with tempfile.TemporaryDirectory() as tmp_dir:
        snap_path = Path(tmp_dir) / "snapshot.jsonl"
        h = _create_mock_snapshot(snap_path, 500)
        
        res1 = perform_deterministic_selection(snapshot_path=snap_path, expected_checksum=h)
        res2 = perform_deterministic_selection(snapshot_path=snap_path, expected_checksum=h)
        
        assert res1.ordered_selected_symbols == res2.ordered_selected_symbols
        assert res1.selection_checksum == res2.selection_checksum
        assert res1.ordered_symbols_hash == res2.ordered_symbols_hash


def test_changing_panel_version_changes_selection_hash():
    with tempfile.TemporaryDirectory() as tmp_dir:
        snap_path = Path(tmp_dir) / "snapshot.jsonl"
        h = _create_mock_snapshot(snap_path, 500)
        
        res1 = perform_deterministic_selection(
            snapshot_path=snap_path,
            expected_checksum=h,
            panel_version="CURRENT_NIFTY500_09Oct2026_8F4C439F",
        )
        res2 = perform_deterministic_selection(
            snapshot_path=snap_path,
            expected_checksum=h,
            panel_version="CURRENT_NIFTY500_10Oct2026_DIFFERENT",
        )
        assert res1.selection_checksum != res2.selection_checksum


def test_changing_symbol_changes_selection_hash():
    with tempfile.TemporaryDirectory() as tmp_dir:
        syms1 = [f"SYM{i:04d}" for i in range(500)]
        p1 = Path(tmp_dir) / "snap1.jsonl"
        h1 = _create_mock_snapshot(p1, 500, syms1)
        res1 = perform_deterministic_selection(snapshot_path=p1, expected_checksum=h1)

        # Replace one of the symbols that was actually selected
        target_to_replace = res1.ordered_selected_symbols[0]
        syms2 = [s if s != target_to_replace else "REPLACED999" for s in syms1]

        p2 = Path(tmp_dir) / "snap2.jsonl"
        h2 = _create_mock_snapshot(p2, 500, syms2)
        res2 = perform_deterministic_selection(snapshot_path=p2, expected_checksum=h2)

        assert res1.selection_checksum != res2.selection_checksum


def test_five_previous_pilot_symbols_are_excluded():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Include the five pilot symbols in the 500
        syms = list(EXCLUDED_FIVE_PILOT_SYMBOLS) + [f"OTHER{i:04d}" for i in range(495)]
        p = Path(tmp_dir) / "snap.jsonl"
        h = _create_mock_snapshot(p, 500, syms)
        
        res = perform_deterministic_selection(snapshot_path=p, expected_checksum=h)
        for excluded in EXCLUDED_FIVE_PILOT_SYMBOLS:
            assert excluded not in res.ordered_selected_symbols
        assert res.selected_symbol_count == 20


def test_selection_evidence_persistence_and_loading():
    with tempfile.TemporaryDirectory() as tmp_dir:
        p = Path(tmp_dir) / "snap.jsonl"
        h = _create_mock_snapshot(p, 500)
        res = perform_deterministic_selection(snapshot_path=p, expected_checksum=h)
        
        sel_dir = Path(tmp_dir) / "selection"
        saved = save_selection_evidence(res, sel_dir)
        
        assert saved["selected_symbols"].exists()
        assert saved["manifest"].exists()
        assert saved["audit"].exists()
        
        # Verify loading manifest
        loaded = load_selection_manifest(sel_dir)
        assert loaded.ordered_selected_symbols == res.ordered_selected_symbols
        assert loaded.selection_checksum == res.selection_checksum
        assert loaded.classification == SELECTION_CLASSIFICATION
