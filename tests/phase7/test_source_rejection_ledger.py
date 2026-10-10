"""Tests for rejection ledgers and partial payload isolation during fetch."""

import json
from pathlib import Path
import pytest

from phase7.sources.contracts import (
    RequestStatus,
)
from phase7.sources.nse_data_fetcher_adapter import (
    NSEDataFetcherAdapter,
)
from phase7.sources.rejections import RejectionLedger


class MockFetcherWithMixedRows:
    """Mock fetcher returning mixed valid and invalid rows."""

    def __init__(self, rows):
        self.rows = rows

    def get_historical_data(self, symbol: str, start: str, end: str):
        return self.rows


def test_rejected_symbol_ledger_logging(tmp_path):
    """Verify invalid symbols are recorded into the rejected symbols ledger."""
    ledger = RejectionLedger(tmp_path)
    adapter = NSEDataFetcherAdapter(fetcher=MockFetcherWithMixedRows([]))

    # Symbol with path traversal
    res = adapter.fetch_historical_eod(
        symbol="../BAD_SYM",
        start_date="2024-01-01",
        end_date="2024-01-31",
        rejection_ledger=ledger,
    )

    assert res.manifest.status == RequestStatus.REJECTED
    assert len(ledger.rejected_symbols) == 1
    assert ledger.rejected_symbols[0].symbol == "../BAD_SYM"
    assert "forbidden path" in ledger.rejected_symbols[0].reason


def test_partial_response_and_rejected_row_ledger(tmp_path):
    """Verify partial response: valid row accepted, bad row rejected and logged."""
    ledger = RejectionLedger(tmp_path)
    mixed_rows = [
        {
            "CH_TIMESTAMP": "2024-01-05",
            "CH_OPENING_PRICE": 100.0,
            "CH_TRADE_HIGH_PRICE": 105.0,
            "CH_TRADE_LOW_PRICE": 98.0,
            "CH_CLOSING_PRICE": 102.0,
            "CH_TOT_TRADED_QTY": 50000,
        },
        {
            # Invalid: high < low
            "CH_TIMESTAMP": "2024-01-08",
            "CH_OPENING_PRICE": 100.0,
            "CH_TRADE_HIGH_PRICE": 90.0,
            "CH_TRADE_LOW_PRICE": 110.0,
            "CH_CLOSING_PRICE": 95.0,
            "CH_TOT_TRADED_QTY": 50000,
        },
        {
            # Invalid: duplicate date 2024-01-05
            "CH_TIMESTAMP": "2024-01-05",
            "CH_OPENING_PRICE": 101.0,
            "CH_TRADE_HIGH_PRICE": 106.0,
            "CH_TRADE_LOW_PRICE": 99.0,
            "CH_CLOSING_PRICE": 103.0,
            "CH_TOT_TRADED_QTY": 40000,
        },
    ]
    fetcher = MockFetcherWithMixedRows(mixed_rows)
    adapter = NSEDataFetcherAdapter(fetcher=fetcher)

    res = adapter.fetch_historical_eod(
        symbol="TCS",
        start_date="2024-01-01",
        end_date="2024-01-31",
        rejection_ledger=ledger,
    )

    assert res.is_partial is True
    assert res.manifest.status == RequestStatus.PARTIAL
    assert len(res.records) == 1
    assert len(res.rejected_rows) == 2
    assert len(ledger.rejected_rows) == 2

    paths = ledger.persist()
    assert paths["rows"].exists()
    with paths["rows"].open("r", encoding="utf-8") as f:
        saved_rows = json.load(f)
    assert len(saved_rows) == 2
