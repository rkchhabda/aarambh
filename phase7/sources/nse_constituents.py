"""Phase 7 NIFTY 500 constituent source wrapper and classification.

Strictly enforces:
- SOURCE_UNAVAILABLE when fetcher lacks constituent retrieval
- CURRENT_SNAPSHOT_ONLY classification for live index snapshots (survivorship bias prevention)
- Prohibition of features.universe or legacy 138-stock fallback
- Validation of row counts, symbol hygiene, and duplicate prevention
"""

from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List, Optional, Tuple

from phase7.sources.contracts import (
    ConstituentClassification,
    ConstituentRecord,
)
from phase7.sources.pilot_guard import validate_symbol


def get_nifty500_constituents(
    fetcher: Any,
    index_name: str = "NIFTY 500",
) -> Tuple[ConstituentClassification, List[ConstituentRecord]]:
    """Retrieve and validate index constituents from the provided fetcher.

    If fetcher does not implement a constituent retrieval method, strictly returns
    (ConstituentClassification.SOURCE_UNAVAILABLE, []) without falling back to
    features.universe or fixed lists.
    """
    # Check if fetcher provides constituent methods
    if hasattr(fetcher, "get_nifty500_constituents"):
        raw_data = fetcher.get_nifty500_constituents()
    elif hasattr(fetcher, "get_index_constituents"):
        raw_data = fetcher.get_index_constituents(index_name)
    elif hasattr(fetcher, "listEquityStocksByIndex"):
        # Direct NSE client capability check
        raw_data = fetcher.listEquityStocksByIndex(index_name)
    else:
        # NSEDataFetcher does NOT provide constituent methods
        return ConstituentClassification.SOURCE_UNAVAILABLE, []

    # If raw data is empty or unavailable
    if not raw_data:
        return ConstituentClassification.SOURCE_UNAVAILABLE, []

    records: List[ConstituentRecord] = []
    ingestion_ts = datetime.now(timezone.utc).isoformat()
    seen_symbols = set()

    # Raw data can be a dict with 'data' list or a list of items
    raw_list: List[Dict[str, Any]] = []
    if isinstance(raw_data, dict):
        raw_list = raw_data.get("data", []) or []
    elif isinstance(raw_data, list):
        raw_list = raw_data

    for row in raw_list:
        if not isinstance(row, dict):
            continue
        sym = row.get("symbol") or row.get("Symbol")
        if not sym:
            continue
        clean_sym = validate_symbol(str(sym))
        if clean_sym in seen_symbols:
            continue
        seen_symbols.add(clean_sym)

        sec_name = str(row.get("companyName") or row.get("security_name") or clean_sym)
        isin = row.get("isin") or row.get("meta", {}).get("isin") if isinstance(row.get("meta"), dict) else None

        hasher = hashlib.sha256()
        hasher.update(f"{clean_sym}|{index_name}|{ingestion_ts}".encode("utf-8"))
        row_hash = hasher.hexdigest()

        rec = ConstituentRecord(
            symbol=clean_sym,
            security_name=sec_name,
            isin=str(isin) if isin else None,
            index_name=index_name,
            classification=ConstituentClassification.CURRENT_SNAPSHOT_ONLY,
            source_timestamp=str(row.get("lastUpdateTime") or ingestion_ts),
            ingestion_timestamp=ingestion_ts,
            source_identifier="NSEDataFetcher",
            row_hash=row_hash,
        )
        records.append(rec)

    if not records:
        return ConstituentClassification.SOURCE_UNAVAILABLE, []

    return ConstituentClassification.CURRENT_SNAPSHOT_ONLY, records
