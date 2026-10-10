"""Tests enforcing the strict immutability of the halted Milestone 4.10C run."""

import json
from pathlib import Path
import pytest

from phase7.sources.batch_contract import BatchContract
from phase7.sources.batch_selection import load_selection_manifest

STAGING_ROOT = Path(r"C:\Users\r_chh\gaurvideep_phase7_staging\nse500\batch_4_10c")


def test_frozen_selection_immutability():
    sel_dir = STAGING_ROOT / "selection"
    manifest = load_selection_manifest(sel_dir)

    assert manifest.selected_symbol_count == 20
    assert manifest.selection_checksum == "60dd03580442b1f874f364206da5d9bf252a4abf1ff93801d4b58e93fdee7b1d"
    assert manifest.ordered_symbols_hash == "26e4be7c9cfd366b630b0b714f0afd65a223ffae91edad6e231060e6b95c4ee3"
    assert manifest.ordered_selected_symbols[0] == "PREMIERENE"
    assert manifest.source_panel_version == "CURRENT_NIFTY500_09Oct2026_8F4C439F"


def test_original_batch_contract_immutability():
    contract_file = STAGING_ROOT / "contracts" / "batch_contract.json"
    assert contract_file.exists()
    c_data = json.loads(contract_file.read_text(encoding="utf-8"))
    contract = BatchContract(**c_data)

    assert contract.compute_contract_hash() == "ed076001b43ab59a740859948edac11e3769ee0baa3660b28d48b5dac61b3427"
    assert contract.batch_id == "BATCH_4_10C_HISTORICAL_20STOCK_2024Q1"
    assert contract.start_date == "2024-01-01"
    assert contract.end_date == "2024-03-31"


def test_halted_run_checkpoint_immutability():
    run_dir = STAGING_ROOT / "runs" / "BATCH_4_10C_HISTORICAL_20STOCK_2024Q1_20261010T112814Z"
    assert run_dir.exists(), f"Halted run directory must exist: {run_dir}"

    cp_file = run_dir / "checkpoints" / "batch_checkpoint.json"
    if not cp_file.exists():
        cp_file = STAGING_ROOT / "checkpoints" / "batch_checkpoint.json"
    assert cp_file.exists()

    cp_data = json.loads(cp_file.read_text(encoding="utf-8"))
    assert cp_data["final_status"] == "HALTED"
    assert cp_data["completed_symbols"] == 0
    assert cp_data["failed_symbols"] == 1
    assert cp_data["pending_symbols"] == 19
    assert cp_data["symbol_states"]["PREMIERENE"]["status"] == "FAILED"
    assert "PREMIERENE" in cp_data["stop_reason"]


def test_consumed_marker_remains_consumed_and_no_active_marker():
    auth_dir = STAGING_ROOT / "authorization"
    active_marker = auth_dir / "batch_authorization.json"
    consumed_marker = auth_dir / "batch_authorization.consumed.20261010T112814Z.json"

    # Active marker must not exist
    assert not active_marker.exists()

    # Consumed marker must exist
    assert consumed_marker.exists()

    # Consumed marker is valid JSON and records single_use=True
    c_data = json.loads(consumed_marker.read_text(encoding="utf-8"))
    assert c_data["single_use"] is True
    assert c_data["milestone"] == "4.10C"
