"""Tests for Phase 7 governed batch execution pipeline with fake client."""

import json
from pathlib import Path
import tempfile
from typing import Any, Dict, List
import pytest

from phase7.sources.batch_checkpoint import (
    BatchSymbolStatus,
    load_checkpoint,
)
from phase7.sources.batch_contract import (
    BatchExitCode,
    BatchStatus,
)
from phase7.sources.batch_pilot import run_batch_pilot
from phase7.sources.batch_selection import (
    SelectionResult,
    save_selection_evidence,
)


def _generate_synthetic_rows(symbol: str, count: int = 60) -> List[Dict[str, Any]]:
    rows = []
    # Dates across Jan-Mar 2024
    for i in range(1, count + 1):
        day = (i % 28) + 1
        month = "Jan" if i <= 20 else ("Feb" if i <= 40 else "Mar")
        date_str = f"{day:02d}-{month}-2024"
        rows.append({
            "chSymbol": symbol,
            "chSeries": "EQ",
            "mtimestamp": date_str,
            "chOpeningPrice": 100.0 + i,
            "chTradeHighPrice": 105.0 + i,
            "chTradeLowPrice": 98.0 + i,
            "chClosingPrice": 102.0 + i,
            "chTotTradedQty": 1000 + i * 10,
            "chTotTradedVal": 102000.0 + i * 1000,
            "chTotalTrades": 50 + i,
            "vwap": 101.5 + i,
        })
    return rows


class FakeBatchClient:
    def __init__(self, failure_on_symbol: str = None, failure_exc=None):
        self.call_history: List[str] = []
        self.failure_on_symbol = failure_on_symbol
        self.failure_exc = failure_exc or RuntimeError("Upstream retrieval network failure")
        self.closed = False

    def fetch_equity_historical_data(self, symbol: str, start_date: str = "", end_date: str = "", interval: str = "1d", **kwargs):
        self.call_history.append(symbol)
        if self.failure_on_symbol and symbol == self.failure_on_symbol:
            raise self.failure_exc
        return _generate_synthetic_rows(symbol, count=60)

    def exit(self):
        self.closed = True


def _setup_test_selection(staging_root: Path, symbol_count: int = 20) -> List[str]:
    symbols = [f"SYM{i:02d}" for i in range(symbol_count)]
    import hashlib
    sel_res = SelectionResult(
        source_panel_version="CURRENT_NIFTY500_09Oct2026_8F4C439F",
        source_snapshot_checksum="8f4c439f35fffc8ec87f107ebc9e03aef00ad26301d0912711d808ac592d117d",
        source_constituent_count=500,
        exclusion_list=["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"],
        selection_algorithm="SHA256_ASC",
        selection_seed_string="MILESTONE_4_10B",
        selected_symbol_count=symbol_count,
        ordered_selected_symbols=symbols,
        ordered_symbols_hash=hashlib.sha256(",".join(symbols).encode("utf-8")).hexdigest(),
        selection_checksum=hashlib.sha256("\n".join(symbols).encode("utf-8")).hexdigest(),
        creation_timestamp="2026-10-10T11:00:00Z",
        classification="DETERMINISTIC_CURRENT_PANEL_OPERATIONAL_SAMPLE",
    )
    save_selection_evidence(sel_res, staging_root / "selection")
    return symbols


def test_batch_execution_all_twenty_symbols_succeed():
    with tempfile.TemporaryDirectory() as tmp_dir:
        staging_root = Path(tmp_dir) / "staging"
        staging_root.mkdir()
        symbols = _setup_test_selection(staging_root, 20)

        fake_client = FakeBatchClient()
        exit_code, summary = run_batch_pilot(
            staging_root=staging_root,
            client_factory=lambda **kw: fake_client,
            pacing_seconds=0.0,
        )

        assert exit_code == BatchExitCode.SUCCESS
        assert summary["completed_symbols"] == 20
        assert summary["total_symbols"] == 20
        assert fake_client.call_history == symbols
        assert fake_client.closed is True

        # Checkpoint verified
        cp_file = staging_root / "checkpoints" / "batch_checkpoint.json"
        assert cp_file.exists()
        cp = load_checkpoint(cp_file)
        assert cp.completed_symbols == 20
        assert cp.final_status == BatchStatus.SUCCEEDED

        # Audit file exists
        audit_file = staging_root / "audit" / "batch_audit.json"
        assert audit_file.exists()


def test_batch_execution_halts_on_first_failure():
    with tempfile.TemporaryDirectory() as tmp_dir:
        staging_root = Path(tmp_dir) / "staging"
        staging_root.mkdir()
        symbols = _setup_test_selection(staging_root, 20)

        # Fail on symbol index 2 (SYM02)
        fake_client = FakeBatchClient(failure_on_symbol="SYM02")
        exit_code, summary = run_batch_pilot(
            staging_root=staging_root,
            client_factory=lambda **kw: fake_client,
            pacing_seconds=0.0,
        )

        assert exit_code == BatchExitCode.RETRIEVAL_ERROR
        assert summary["completed_symbols"] == 2  # SYM00 and SYM01 succeeded
        # Calls were strictly SYM00, SYM01, SYM02 (stopped without attempting SYM03-SYM19)
        assert fake_client.call_history == ["SYM00", "SYM01", "SYM02"]
        assert fake_client.closed is True

        # Checkpoint preserved
        cp = load_checkpoint(staging_root / "checkpoints" / "batch_checkpoint.json")
        assert cp.symbol_states["SYM00"].status == BatchSymbolStatus.SUCCEEDED
        assert cp.symbol_states["SYM01"].status == BatchSymbolStatus.SUCCEEDED
        assert cp.symbol_states["SYM02"].status == BatchSymbolStatus.FAILED
        assert cp.symbol_states["SYM03"].status == BatchSymbolStatus.NOT_STARTED
        assert cp.final_status == BatchStatus.HALTED


def test_dry_run_passes_without_network_request():
    with tempfile.TemporaryDirectory() as tmp_dir:
        staging_root = Path(tmp_dir) / "staging"
        staging_root.mkdir()
        _setup_test_selection(staging_root, 20)

        exit_code, summary = run_batch_pilot(
            staging_root=staging_root,
            dry_run=True,
        )
        assert exit_code == BatchExitCode.SUCCESS
        assert summary["status"] == "DRY_RUN_PASSED"


def test_nineteen_completed_symbols_returns_nonzero():
    with tempfile.TemporaryDirectory() as tmp_dir:
        staging_root = Path(tmp_dir) / "staging"
        staging_root.mkdir()
        symbols = _setup_test_selection(staging_root, 20)

        # Fail on symbol 19 (SYM19) - so 19 succeed and 1 fails
        fake_client = FakeBatchClient(failure_on_symbol="SYM19")
        exit_code, summary = run_batch_pilot(
            staging_root=staging_root,
            client_factory=lambda **kw: fake_client,
            pacing_seconds=0.0,
        )

        assert exit_code != BatchExitCode.SUCCESS
        assert exit_code == BatchExitCode.RETRIEVAL_ERROR
        assert summary["completed_symbols"] == 19
        assert summary["total_symbols"] == 20
