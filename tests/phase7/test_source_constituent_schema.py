"""Unit tests for Phase 7 constituent snapshot schema parsing and normalization.

Tests:
- Fake client method invoked exactly once with exact argument
- Empty, HTML, CAPTCHA, and unexpected response types rejected
- List response and dict data-list response accepted
- Index summary header row excluded as rejected row; conservation holds
- Missing symbol, invalid symbol, and duplicate symbol rejection
- Honest tracking of optional fields (ISIN, series, sector, industry)
- Row conservation holds: source_row_count = normalized_row_count + rejected_row_count
- Plausibility verification
"""

import pytest

from phase7.sources.contracts import (
    ConstituentClassification,
    ConstituentRecord,
    RejectedRowRecord,
)
from phase7.sources.nse_constituents import (
    fetch_current_index_constituents,
)


class MockNSEClient:
    def __init__(self, response_payload=None, raise_exc=None):
        self.response_payload = response_payload
        self.raise_exc = raise_exc
        self.call_count = 0
        self.last_index_arg = None

    def listEquityStocksByIndex(self, index: str = "NIFTY 50"):
        self.call_count += 1
        self.last_index_arg = index
        if self.raise_exc:
            raise self.raise_exc
        return self.response_payload


def test_upstream_called_once_with_exact_argument():
    """Client method listEquityStocksByIndex is called exactly once with index='NIFTY 500'."""
    client = MockNSEClient(response_payload={"data": [{"symbol": "TCS"}]})
    records, rejected, audit = fetch_current_index_constituents(client, "NIFTY 500")

    assert client.call_count == 1
    assert client.last_index_arg == "NIFTY 500"
    assert len(records) == 1
    assert records[0].symbol == "TCS"


def test_empty_response_rejected():
    """Empty or None response raises ValueError."""
    client = MockNSEClient(response_payload=None)
    with pytest.raises(ValueError, match="None/empty"):
        fetch_current_index_constituents(client, "NIFTY 500")

    client2 = MockNSEClient(response_payload={"data": []})
    with pytest.raises(ValueError, match="empty constituent list"):
        fetch_current_index_constituents(client2, "NIFTY 500")


def test_html_response_rejected():
    """HTML error or gateway response raises ValueError."""
    client = MockNSEClient(response_payload="<html><head><title>Error</title></head><body>502 Bad Gateway</body></html>")
    with pytest.raises(ValueError, match="HTML response received"):
        fetch_current_index_constituents(client, "NIFTY 500")


def test_captcha_response_rejected():
    """CAPTCHA-like response raises ValueError."""
    client = MockNSEClient(response_payload="<html><body>Please verify with captcha to continue</body></html>")
    with pytest.raises(ValueError, match="HTML response received"):
        fetch_current_index_constituents(client, "NIFTY 500")

    client2 = MockNSEClient(response_payload='{"error": "captcha_required"}')
    with pytest.raises(ValueError, match="CAPTCHA"):
        fetch_current_index_constituents(client2, "NIFTY 500")


def test_connectivity_and_timeout_errors_propagate():
    """ConnectionError and TimeoutError propagate cleanly for caller handling."""
    client_conn = MockNSEClient(raise_exc=ConnectionError("Connection aborted by peer"))
    with pytest.raises(ConnectionError):
        fetch_current_index_constituents(client_conn, "NIFTY 500")

    client_to = MockNSEClient(raise_exc=TimeoutError("Request timed out"))
    with pytest.raises(TimeoutError):
        fetch_current_index_constituents(client_to, "NIFTY 500")


def test_unexpected_response_type_rejected():
    """Non-dict and non-list response raises TypeError."""
    client = MockNSEClient(response_payload=12345)
    with pytest.raises(TypeError, match="Unexpected response type"):
        fetch_current_index_constituents(client, "NIFTY 500")


def test_recognized_list_response_accepted():
    """Top-level list of dictionaries is accepted."""
    client = MockNSEClient(response_payload=[
        {"symbol": "RELIANCE", "companyName": "Reliance Industries", "isin": "INE002A01018"},
        {"symbol": "INFY", "companyName": "Infosys Limited", "isin": "INE009A01021"},
    ])
    records, rejected, audit = fetch_current_index_constituents(client, "NIFTY 500")
    assert len(records) == 2
    assert audit["conservation_holds"] is True
    assert records[0].symbol == "RELIANCE"
    assert records[1].symbol == "INFY"


def test_index_header_row_excluded_and_conserved():
    """Header row with symbol matching index name is excluded as rejected row; conservation holds."""
    client = MockNSEClient(response_payload={
        "name": "NIFTY 500",
        "timestamp": "10-Oct-2026 15:30:00",
        "data": [
            {"symbol": "NIFTY 500", "identifier": "NIFTY 500", "lastPrice": 22000.0},
            {"symbol": "RELIANCE", "companyName": "Reliance", "isin": "INE002A01018", "series": "EQ"},
            {"symbol": "TCS", "companyName": "Tata Consultancy", "isin": "INE467B01029", "series": "EQ"},
        ]
    })
    records, rejected, audit = fetch_current_index_constituents(client, "NIFTY 500")

    assert audit["source_row_count"] == 3
    assert audit["normalized_row_count"] == 2
    assert audit["rejected_row_count"] == 1
    assert audit["conservation_holds"] is True
    assert len(records) == 2
    assert len(rejected) == 1
    assert rejected[0].symbol == "NIFTY 500"
    assert rejected[0].reason == "INDEX_HEADER_ROW_SKIPPED"


def test_missing_and_invalid_symbols_rejected():
    """Missing and invalid symbol formats are rejected."""
    client = MockNSEClient(response_payload={
        "data": [
            {"symbol": "", "companyName": "Empty Sym"},
            {"symbol": "INVALID/SYMBOL", "companyName": "Slash Sym"},
            {"symbol": "VALID1", "companyName": "Valid Co 1"},
        ]
    })
    records, rejected, audit = fetch_current_index_constituents(client, "NIFTY 500")

    assert len(records) == 1
    assert records[0].symbol == "VALID1"
    assert audit["missing_symbols"] == 1
    assert audit["invalid_symbols"] == 1
    assert audit["source_row_count"] == 3
    assert audit["conservation_holds"] is True


def test_duplicate_symbol_rejected():
    """Duplicate symbol in the response is rejected on second occurrence."""
    client = MockNSEClient(response_payload={
        "data": [
            {"symbol": "HDFCBANK", "companyName": "HDFC Bank"},
            {"symbol": "HDFCBANK", "companyName": "HDFC Bank Duplicate"},
            {"symbol": "ICICIBANK", "companyName": "ICICI Bank"},
        ]
    })
    records, rejected, audit = fetch_current_index_constituents(client, "NIFTY 500")

    assert len(records) == 2
    assert audit["duplicate_symbols"] == 1
    assert audit["conservation_holds"] is True
    assert any(r.reason == "DUPLICATE_NATURAL_KEY" for r in rejected)


def test_missing_isin_and_series_recorded_honestly():
    """Missing optional fields (ISIN, series, sector, industry) are stored as None without failing."""
    client = MockNSEClient(response_payload={
        "data": [
            {"symbol": "STOCKA"},  # No ISIN, series, sector, or industry
        ]
    })
    records, rejected, audit = fetch_current_index_constituents(client, "NIFTY 500")

    assert len(records) == 1
    rec = records[0]
    assert rec.isin is None
    assert rec.exchange_series is None
    assert rec.sector is None
    assert rec.industry is None
    assert audit["missing_isins"] == 1
    assert audit["missing_series"] == 1
    assert audit["missing_sectors"] == 1
    assert audit["missing_industries"] == 1


def test_plausibility_bounds_validation():
    """Plausibility check flags count outside 490 to 510."""
    # Small test count: 3 stocks -> is_plausible_count is False
    client = MockNSEClient(response_payload={
        "data": [{"symbol": f"SYM{i}"} for i in range(50)]
    })
    records, rejected, audit = fetch_current_index_constituents(client, "NIFTY 500")
    assert audit["is_plausible_count"] is False

    # 500 stocks -> is_plausible_count is True
    client500 = MockNSEClient(response_payload={
        "data": [{"symbol": f"SYM{i}"} for i in range(500)]
    })
    records500, rejected500, audit500 = fetch_current_index_constituents(client500, "NIFTY 500")
    assert audit500["is_plausible_count"] is True
    assert len(records500) == 500
