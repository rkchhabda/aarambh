"""Unit tests for rejected symbol and row ledger management."""

import json
from pathlib import Path
import pytest
from phase7.sources.rejections import RejectionLedger


def test_rejection_ledger_recording_and_persistence(tmp_path):
    """Verify recording of rejected symbols and malformed rows into audit files."""
    ledger = RejectionLedger(tmp_path)

    # Record rejected symbol
    sym_rec = ledger.record_rejected_symbol(
        symbol="INVALID/SYMBOL",
        reason="Forbidden path characters",
        timestamp="2026-10-10T10:00:00Z",
        requested_range="2024-01-01 to 2024-01-31",
    )
    assert sym_rec.symbol == "INVALID/SYMBOL"
    assert len(ledger.rejected_symbols) == 1

    # Record rejected row
    bad_payload = {"date": "2024-01-15", "open": 100, "high": 90, "low": 110, "close": 95}
    row_rec = ledger.record_rejected_row(
        symbol="RELIANCE",
        raw_payload=bad_payload,
        reason="low (110) exceeds high (90)",
        timestamp="2026-10-10T10:00:00Z",
    )
    assert row_rec.symbol == "RELIANCE"
    assert len(ledger.rejected_rows) == 1

    # Persist ledgers
    paths = ledger.persist()
    assert "symbols" in paths
    assert "rows" in paths

    with paths["symbols"].open("r", encoding="utf-8") as f:
        sym_data = json.load(f)
    assert len(sym_data) == 1
    assert sym_data[0]["symbol"] == "INVALID/SYMBOL"

    with paths["rows"].open("r", encoding="utf-8") as f:
        row_data = json.load(f)
    assert len(row_data) == 1
    assert "low (110) exceeds high (90)" in row_data[0]["reason"]
