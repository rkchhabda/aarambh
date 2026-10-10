"""Tests for NSEDataFetcherAdapter wrapping NSEDataFetcherProtocol with fake/mock instances."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import pytest

from phase7.sources.contracts import (
    CapabilityStatus,
    NSEDataFetcherProtocol,
    RequestStatus,
)
from phase7.sources.nse_data_fetcher_adapter import (
    HistoricalFetchResult,
    NSEDataFetcherAdapter,
)


class FakeNSEDataFetcher:
    """Mock fetcher implementing NSEDataFetcherProtocol without external libraries or network."""

    def __init__(self, historical_data: Optional[List[Dict[str, Any]]] = None):
        self.historical_data = historical_data if historical_data is not None else []
        self.calls: List[Dict[str, Any]] = []

    def get_live_quote(self, symbol: str) -> Dict[str, Any]:
        self.calls.append({"method": "get_live_quote", "symbol": symbol})
        return {
            "symbol": symbol,
            "last_price": 2500.0,
            "open": 2490.0,
            "raw": {"symbol": symbol},
        }

    def get_market_status(self) -> Dict[str, Any]:
        self.calls.append({"method": "get_market_status"})
        return {"capital_market": "Normal", "status": "OPEN"}

    def get_historical_data(self, symbol: str, start: str, end: str) -> List[Dict[str, Any]]:
        self.calls.append({"method": "get_historical_data", "symbol": symbol, "start": start, "end": end})
        return self.historical_data


def test_adapter_protocol_conformance_and_capability_discovery():
    """Verify adapter discovers capabilities without making network calls."""
    fetcher = FakeNSEDataFetcher()
    assert isinstance(fetcher, NSEDataFetcherProtocol)

    adapter = NSEDataFetcherAdapter(fetcher=fetcher)
    caps = adapter.discover_capabilities()

    assert caps["get_live_quote"] == CapabilityStatus.AVAILABLE
    assert caps["get_market_status"] == CapabilityStatus.AVAILABLE
    assert caps["get_historical_data"] == CapabilityStatus.AVAILABLE
    assert caps["get_nifty500_constituents"] == CapabilityStatus.UNAVAILABLE
    assert caps["get_corporate_actions"] == CapabilityStatus.UNAVAILABLE
    assert caps["get_security_master"] == CapabilityStatus.UNAVAILABLE
    assert caps["get_sector_classification"] == CapabilityStatus.PARTIAL


def test_adapter_safety_status():
    """Verify adapter reports fail-closed safety status for live execution."""
    fetcher = FakeNSEDataFetcher()
    adapter = NSEDataFetcherAdapter(fetcher=fetcher)
    assert adapter.safety_status == "UNSAFE_FOR_LIVE_PILOT"


def test_historical_fetch_exact_parameters_passed():
    """Verify exact symbol, start, and end dates are passed to the fetcher without today() substitution."""
    fetcher = FakeNSEDataFetcher(
        historical_data=[
            {
                "CH_TIMESTAMP": "2024-01-05",
                "CH_SERIES": "EQ",
                "CH_OPENING_PRICE": 2400.0,
                "CH_TRADE_HIGH_PRICE": 2450.0,
                "CH_TRADE_LOW_PRICE": 2390.0,
                "CH_CLOSING_PRICE": 2440.0,
                "CH_TOT_TRADED_QTY": 100000,
                "CH_TOT_TRADED_VAL": 244000000.0,
            }
        ]
    )
    adapter = NSEDataFetcherAdapter(fetcher=fetcher)
    res = adapter.fetch_historical_eod(
        symbol="reliance",
        start_date="2024-01-01",
        end_date="2024-01-31",
    )

    assert len(fetcher.calls) == 1
    call = fetcher.calls[0]
    assert call["method"] == "get_historical_data"
    assert call["symbol"] == "RELIANCE"  # Normalized to uppercase
    assert call["start"] == "2024-01-01"  # Exact start preserved
    assert call["end"] == "2024-01-31"    # Exact end preserved, not today()
    assert res.manifest.status == RequestStatus.SUCCESS
    assert len(res.records) == 1
    assert res.records[0].symbol == "RELIANCE"
    assert res.records[0].trading_date == "2024-01-05"


def test_historical_fetch_empty_response():
    """Verify empty response returns EMPTY status without crashing."""
    fetcher = FakeNSEDataFetcher(historical_data=[])
    adapter = NSEDataFetcherAdapter(fetcher=fetcher)
    res = adapter.fetch_historical_eod(
        symbol="TCS",
        start_date="2024-01-01",
        end_date="2024-01-31",
    )
    assert res.is_empty is True
    assert res.manifest.status == RequestStatus.EMPTY
    assert len(res.records) == 0


def test_live_quote_and_status_delegation():
    """Verify get_live_quote and get_market_status methods delegate properly."""
    fetcher = FakeNSEDataFetcher()
    adapter = NSEDataFetcherAdapter(fetcher=fetcher)

    quote = adapter.get_live_quote("infy")
    assert quote["symbol"] == "INFY"

    status = adapter.get_market_status()
    assert status["capital_market"] == "Normal"

    assert len(fetcher.calls) == 2
    assert fetcher.calls[0]["method"] == "get_live_quote"
    assert fetcher.calls[0]["symbol"] == "INFY"
    assert fetcher.calls[1]["method"] == "get_market_status"
