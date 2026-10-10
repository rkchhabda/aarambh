"""Tests for Phase 7 batch checkpointing."""

import json
from pathlib import Path
import tempfile
import pytest

from phase7.sources.batch_checkpoint import (
    BatchCheckpoint,
    BatchSymbolStatus,
    SymbolCheckpoint,
    create_initial_batch_checkpoint,
    load_checkpoint,
    save_checkpoint,
)
from phase7.sources.batch_contract import BatchStatus


def test_checkpoint_initialization_and_serialization():
    symbols = [f"SYM{i}" for i in range(20)]
    cp = create_initial_batch_checkpoint(batch_id="batch_001", ordered_symbols=symbols)
    
    assert cp.batch_id == "batch_001"
    assert cp.total_symbols == 20
    assert cp.completed_symbols == 0
    assert cp.pending_symbols == 20
    assert cp.failed_symbols == 0
    assert cp.final_status == BatchStatus.INITIALIZED
    assert len(cp.symbol_states) == 20
    for sym in symbols:
        assert cp.symbol_states[sym].status == BatchSymbolStatus.NOT_STARTED


def test_checkpoint_save_and_load_roundtrip():
    with tempfile.TemporaryDirectory() as tmp_dir:
        cp_file = Path(tmp_dir) / "checkpoints" / "batch_checkpoint.json"
        symbols = ["SYM1", "SYM2"]
        cp = create_initial_batch_checkpoint(batch_id="batch_002", ordered_symbols=symbols)
        
        # Update symbol 1
        cp.symbol_states["SYM1"].status = BatchSymbolStatus.SUCCEEDED
        cp.symbol_states["SYM1"].source_rows = 60
        cp.symbol_states["SYM1"].normalized_rows = 60
        cp.completed_symbols = 1
        cp.pending_symbols = 1
        cp.source_rows = 60
        cp.normalized_rows = 60
        cp.raw_checksums["SYM1"] = "raw_hash_1"
        cp.normalized_checksums["SYM1"] = "norm_hash_1"
        
        save_checkpoint(cp, cp_file)
        assert cp_file.exists()
        
        loaded = load_checkpoint(cp_file)
        assert loaded.batch_id == "batch_002"
        assert loaded.completed_symbols == 1
        assert loaded.symbol_states["SYM1"].status == BatchSymbolStatus.SUCCEEDED
        assert loaded.symbol_states["SYM1"].source_rows == 60
        assert loaded.raw_checksums["SYM1"] == "raw_hash_1"
        assert loaded.symbol_states["SYM2"].status == BatchSymbolStatus.NOT_STARTED
