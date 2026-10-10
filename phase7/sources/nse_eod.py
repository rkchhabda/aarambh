"""Phase 7 historical end-of-day (EOD) data retrieval and normalization interface.

Wraps NSEDataFetcherAdapter to provide validated, canonical EOD records.
"""

from pathlib import Path
from typing import List, Optional, Union

from phase7.sources.contracts import (
    HistoricalEODRecord,
    NSEDataFetcherProtocol,
)
from phase7.sources.nse_data_fetcher_adapter import (
    HistoricalFetchResult,
    NSEDataFetcherAdapter,
)
from phase7.sources.rejections import RejectionLedger


def fetch_symbol_eod_history(
    fetcher: NSEDataFetcherProtocol,
    symbol: str,
    start_date: str,
    end_date: str,
    interval: str = "1d",
    staging_root: Optional[Union[str, Path]] = None,
    rejection_ledger: Optional[RejectionLedger] = None,
) -> HistoricalFetchResult:
    """Fetch and normalize historical EOD data for a single symbol using the adapter."""
    adapter = NSEDataFetcherAdapter(
        fetcher=fetcher,
        staging_root=staging_root,
    )
    return adapter.fetch_historical_eod(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval=interval,
        rejection_ledger=rejection_ledger,
    )
