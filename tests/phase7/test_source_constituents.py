"""Tests for NIFTY 500 constituent retrieval, classification, and survivorship guardrails."""

import pytest

from phase7.sources.contracts import (
    ConstituentClassification,
    ConstituentRecord,
)
from phase7.sources.nse_constituents import get_nifty500_constituents


class FetcherWithoutConstituents:
    """Standard NSEDataFetcher without constituent retrieval capability."""

    def get_live_quote(self, symbol: str):
        return {"symbol": symbol}


class FetcherWithConstituents:
    """Mock fetcher providing current constituent retrieval."""

    def __init__(self, data):
        self.data = data

    def get_nifty500_constituents(self):
        return self.data


def test_source_unavailable_when_fetcher_lacks_method():
    """Verify SOURCE_UNAVAILABLE is returned when fetcher lacks constituent method."""
    fetcher = FetcherWithoutConstituents()
    classification, records = get_nifty500_constituents(fetcher)

    assert classification == ConstituentClassification.SOURCE_UNAVAILABLE
    assert records == []


def test_no_legacy_universe_fallback():
    """Verify function does NOT fall back to features.universe or 138-stock list."""
    fetcher = FetcherWithoutConstituents()
    _, records = get_nifty500_constituents(fetcher)
    assert len(records) != 138  # Strict: no fixed 138 stocks
    assert len(records) == 0


def test_current_snapshot_only_classification():
    """Verify returned constituents are strictly marked CURRENT_SNAPSHOT_ONLY."""
    mock_data = [
        {"symbol": "RELIANCE", "companyName": "Reliance Industries Ltd", "isin": "INE002A01018"},
        {"symbol": "TCS", "companyName": "Tata Consultancy Services Ltd", "isin": "INE467B01029"},
        {"symbol": "HDFCBANK", "companyName": "HDFC Bank Ltd", "isin": "INE040A01034"},
    ]
    fetcher = FetcherWithConstituents(mock_data)
    classification, records = get_nifty500_constituents(fetcher)

    assert classification == ConstituentClassification.CURRENT_SNAPSHOT_ONLY
    assert len(records) == 3

    for rec in records:
        assert isinstance(rec, ConstituentRecord)
        assert rec.classification == ConstituentClassification.CURRENT_SNAPSHOT_ONLY
        assert rec.index_name == "NIFTY 500"
        assert rec.row_hash is not None and len(rec.row_hash) == 64


def test_symbol_deduplication_and_isin_handling():
    """Verify duplicates are dropped and ISIN is preserved without inference."""
    mock_data = [
        {"symbol": "INFY", "companyName": "Infosys Ltd", "isin": "INE009A01021"},
        {"symbol": "INFY", "companyName": "Infosys Ltd Duplicate", "isin": "INE009A01021"},
        {"symbol": "ICICIBANK", "companyName": "ICICI Bank Ltd"},  # Missing ISIN
    ]
    fetcher = FetcherWithConstituents(mock_data)
    _, records = get_nifty500_constituents(fetcher)

    assert len(records) == 2
    symbols = [r.symbol for r in records]
    assert symbols == ["INFY", "ICICIBANK"]

    icici = next(r for r in records if r.symbol == "ICICIBANK")
    assert icici.isin is None  # ISIN not inferred
