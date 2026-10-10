"""Unit tests for NSEDataSourceAdapter using mocked/fake clients with zero live network calls."""

import time
from typing import Any, Dict, List, Optional
import pytest
from phase7.sources.client_protocol import NSEClientProtocol
from phase7.sources.contracts import (
    ConstituentClassification,
    FieldStatus,
    RequestStatus,
)
from phase7.sources.nse_adapter import NSEDataSourceAdapter
from phase7.sources.rejections import RejectionLedger


class FakeNSEClient:
    """Mock NSE client implementing NSEClientProtocol for offline testing."""

    def __init__(
        self,
        historical_response: Any = None,
        quote_response: Optional[Dict[str, Any]] = None,
        status_response: Optional[Dict[str, Any]] = None,
        index_response: Optional[Dict[str, Any]] = None,
        raise_on_history: Optional[Exception] = None,
    ):
        self.historical_response = historical_response or []
        self.quote_response = quote_response or {}
        self.status_response = status_response or {}
        self.index_response = index_response or {}
        self.raise_on_history = raise_on_history
        self.calls: List[Dict[str, Any]] = []

    def fetch_equity_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1d",
    ) -> Any:
        self.calls.append({
            "method": "fetch_equity_historical_data",
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "interval": interval,
        })
        if self.raise_on_history:
            raise self.raise_on_history
        return self.historical_response

    def equityQuote(self, symbol: str) -> Dict[str, Any]:
        return self.quote_response

    def status(self) -> Dict[str, Any]:
        return self.status_response

    def listEquityStocksByIndex(self, index: str = "NIFTY 50") -> Dict[str, Any]:
        return self.index_response

    def actions(self, segment="equities", symbol=None, from_date=None, to_date=None) -> List[Dict[str, Any]]:
        return []

    def exit(self) -> None:
        pass


def test_adapter_valid_historical_fetch(tmp_path):
    """Verify adapter successfully normalizes clean fake responses."""
    fake_rows = [
        {
            "CH_TIMESTAMP": "2024-01-15",
            "CH_OPENING_PRICE": "2500.0",
            "CH_TRADE_HIGH_PRICE": "2550.0",
            "CH_TRADE_LOW_PRICE": "2490.0",
            "CH_CLOSING_PRICE": "2525.0",
            "CH_TOT_TRADED_QTY": "1000",
            "CH_TOT_TRADED_VAL": "2520000.0",
        },
        {
            "CH_TIMESTAMP": "2024-01-16",
            "CH_OPENING_PRICE": "2525.0",
            "CH_TRADE_HIGH_PRICE": "2560.0",
            "CH_TRADE_LOW_PRICE": "2510.0",
            "CH_CLOSING_PRICE": "2540.0",
            "CH_TOT_TRADED_QTY": "2000",
            "CH_TOT_TRADED_VAL": "5060000.0",
        },
    ]
    client = FakeNSEClient(historical_response={"data": fake_rows})
    adapter = NSEDataSourceAdapter(client=client, staging_root=tmp_path / "staging")

    result = adapter.fetch_historical_eod("reliance", "2024-01-01", "2024-01-31")

    assert result.symbol == "RELIANCE"
    assert len(result.records) == 2
    assert result.manifest.status == RequestStatus.SUCCESS
    assert result.manifest.row_count == 2
    assert not result.is_empty
    assert not result.is_partial
    assert len(client.calls) == 1
    assert client.calls[0]["symbol"] == "RELIANCE"


def test_adapter_empty_response_handling(tmp_path):
    """Verify fail-closed handling of empty upstream responses."""
    client = FakeNSEClient(historical_response=[])
    adapter = NSEDataSourceAdapter(client=client, staging_root=tmp_path / "staging")

    result = adapter.fetch_historical_eod("TCS", "2024-01-01", "2024-01-31")

    assert result.is_empty
    assert result.manifest.status == RequestStatus.EMPTY
    assert len(result.records) == 0


def test_adapter_partial_rejection_and_ledger(tmp_path):
    """Verify that rows with invalid OHLC are rejected while valid rows are retained."""
    fake_rows = [
        # Valid row
        {
            "CH_TIMESTAMP": "2024-01-15",
            "open": 100.0,
            "high": 110.0,
            "low": 90.0,
            "close": 105.0,
            "volume": 1000,
        },
        # Invalid row: low > high
        {
            "CH_TIMESTAMP": "2024-01-16",
            "open": 100.0,
            "high": 90.0,
            "low": 110.0,
            "close": 95.0,
            "volume": 1000,
        },
    ]
    client = FakeNSEClient(historical_response=fake_rows)
    ledger = RejectionLedger(tmp_path / "ledgers")
    adapter = NSEDataSourceAdapter(client=client, staging_root=tmp_path / "staging")

    result = adapter.fetch_historical_eod("INFY", "2024-01-01", "2024-01-31", rejection_ledger=ledger)

    assert result.is_partial
    assert result.manifest.status == RequestStatus.PARTIAL
    assert len(result.records) == 1
    assert len(result.rejected_rows) == 1
    assert len(ledger.rejected_rows) == 1
    assert "low (110.0) exceeds high (90.0)" in ledger.rejected_rows[0].reason


def test_adapter_duplicate_natural_keys_rejected(tmp_path):
    """Verify that duplicate (symbol, date) rows are rejected."""
    fake_rows = [
        {"CH_TIMESTAMP": "2024-01-15", "open": 100, "high": 110, "low": 90, "close": 105, "volume": 100},
        {"CH_TIMESTAMP": "2024-01-15", "open": 100, "high": 110, "low": 90, "close": 105, "volume": 100},
    ]
    client = FakeNSEClient(historical_response=fake_rows)
    adapter = NSEDataSourceAdapter(client=client, staging_root=tmp_path / "staging")

    result = adapter.fetch_historical_eod("HDFCBANK", "2024-01-01", "2024-01-31")

    assert len(result.records) == 1
    assert len(result.rejected_rows) == 1
    assert "Duplicate natural key" in result.rejected_rows[0].reason


def test_adapter_upstream_exception_fail_closed(tmp_path):
    """Verify that upstream network or transport errors produce FAILED manifests without process crash."""
    client = FakeNSEClient(raise_on_history=ConnectionError("NSE connection refused"))
    adapter = NSEDataSourceAdapter(client=client, staging_root=tmp_path / "staging")

    result = adapter.fetch_historical_eod("ICICIBANK", "2024-01-01", "2024-01-31")

    assert result.manifest.status == RequestStatus.FAILED
    assert "NSE connection refused" in (result.manifest.failure_reason or "")
    assert len(result.records) == 0


def test_adapter_rate_limit_spacing(tmp_path):
    """Verify that the adapter enforces at least 2.0s delay between sequential calls."""
    client = FakeNSEClient(historical_response=[])
    adapter = NSEDataSourceAdapter(client=client, staging_root=tmp_path / "staging")

    t0 = time.time()
    adapter.fetch_historical_eod("RELIANCE", "2024-01-01", "2024-01-05")
    t1 = time.time()
    adapter.fetch_historical_eod("TCS", "2024-01-01", "2024-01-05")
    t2 = time.time()

    # The second call must have waited so elapsed >= 2.0s
    assert (t2 - t1) >= 1.95


def test_adapter_current_constituents_classification(tmp_path):
    """Verify that constituent retrieval is classified as CURRENT_SNAPSHOT_ONLY."""
    mock_index_data = {
        "data": [
            {"symbol": "RELIANCE", "identifier": "RELIANCEEQ", "meta": {"companyName": "Reliance Industries", "isin": "INE002A01018"}},
            {"symbol": "TCS", "identifier": "TCSEQ", "meta": {"companyName": "Tata Consultancy Services", "isin": "INE467B01029"}},
        ]
    }
    client = FakeNSEClient(index_response=mock_index_data)
    adapter = NSEDataSourceAdapter(client=client, staging_root=tmp_path / "staging")

    constituents = adapter.get_current_index_constituents("NIFTY 500")

    assert len(constituents) == 2
    for c in constituents:
        assert c.classification == ConstituentClassification.CURRENT_SNAPSHOT_ONLY
        assert c.index_name == "NIFTY 500"
