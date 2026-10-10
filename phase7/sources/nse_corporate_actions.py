"""Phase 7 corporate action retrieval and verification wrapper.

Inspects fetcher capabilities and returns normalized CorporateActionRecord objects.
Strictly avoids inventing adjustment states for ambiguous corporate actions.
"""

from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List, Optional, Tuple

from phase7.sources.contracts import (
    CapabilityStatus,
    CorporateActionRecord,
)
from phase7.sources.pilot_guard import validate_symbol


def get_corporate_actions(
    fetcher: Any,
    symbol: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Tuple[CapabilityStatus, List[CorporateActionRecord]]:
    """Retrieve corporate actions from the provided fetcher or client.

    Returns (CapabilityStatus.UNAVAILABLE, []) if fetcher does not support corporate actions.
    """
    clean_symbol = validate_symbol(symbol) if symbol else None

    # Check for corporate action methods
    if hasattr(fetcher, "get_corporate_actions"):
        raw_actions = fetcher.get_corporate_actions(symbol=clean_symbol, start=start_date, end=end_date)
    elif hasattr(fetcher, "actions"):
        raw_actions = fetcher.actions(segment="equities", symbol=clean_symbol)
    else:
        # NSEDataFetcher has no corporate action capability
        return CapabilityStatus.UNAVAILABLE, []

    if not raw_actions or not isinstance(raw_actions, list):
        return CapabilityStatus.AVAILABLE, []

    records: List[CorporateActionRecord] = []
    ingestion_ts = datetime.now(timezone.utc).isoformat()

    for item in raw_actions:
        if not isinstance(item, dict):
            continue

        sym = item.get("symbol") or clean_symbol or "UNKNOWN"
        ex_date = str(item.get("exDate") or item.get("ex_date") or "")
        series = item.get("series", "EQ")
        if series != "EQ":
            continue

        action_type = str(item.get("purpose") or item.get("action_type") or "UNKNOWN")
        isin = item.get("isin")

        hasher = hashlib.sha256()
        hasher.update(f"{sym}|{ex_date}|{action_type}|{ingestion_ts}".encode("utf-8"))
        row_hash = hasher.hexdigest()

        rec = CorporateActionRecord(
            symbol=sym,
            isin=str(isin) if isin else None,
            action_type=action_type,
            announcement_timestamp=None,
            ex_date=ex_date,
            record_date=item.get("recordDate"),
            effective_date=item.get("effectiveDate"),
            ratio_numerator=None,
            ratio_denominator=None,
            cash_amount=None,
            currency="INR",
            status="RAW_ACTION",
            source_identifier="NSEDataFetcher",
            ingestion_timestamp=ingestion_ts,
            row_hash=row_hash,
        )
        records.append(rec)

    return CapabilityStatus.AVAILABLE, records
