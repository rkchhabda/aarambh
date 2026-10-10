"""Phase 7 NIFTY 500 constituent source wrapper, normalization and classification.

Strictly enforces:
- SOURCE_UNAVAILABLE when client lacks constituent retrieval capability
- Input guard: index_name must be strictly 'NIFTY 500'
- CURRENT_SNAPSHOT_ONLY classification for live index snapshots (survivorship bias prevention)
- Prohibition of features.universe or legacy 138-stock fallback
- Validation of row counts, symbol hygiene, and duplicate prevention
- Row conservation: source_row_count = normalized_row_count + rejected_row_count
- Plausibility check: 490 to 510 unique symbols
"""

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from phase7.sources.contracts import (
    ConstituentClassification,
    ConstituentRecord,
    RejectedRowRecord,
)
from phase7.sources.pilot_guard import validate_symbol

AUTHORIZED_INDEX_NAME = "NIFTY 500"


def validate_index_name(index_name: str) -> str:
    """Validate that index_name is exactly 'NIFTY 500'.

    Raises:
        ValueError: If index_name is not authorized, blank, URL, path, or multiple indices.
    """
    if not index_name or not isinstance(index_name, str):
        raise ValueError("Index name must be a non-empty string.")

    cleaned = index_name.strip()
    if not cleaned:
        raise ValueError("Index name cannot be blank.")

    # Reject path separators, URL query fragments, commas, newlines
    if any(c in cleaned for c in ("/", "\\", ":", "?", "#", "\x00", "\n", "\r", "\t", ",")):
        raise ValueError(f"Index name '{cleaned}' contains forbidden path, URL, or delimiter characters.")

    if cleaned.upper() != AUTHORIZED_INDEX_NAME:
        raise ValueError(
            f"Index name '{cleaned}' is not authorized. Only '{AUTHORIZED_INDEX_NAME}' is permitted under Milestone 4.10A."
        )

    return AUTHORIZED_INDEX_NAME


def fetch_current_index_constituents(
    client: Any,
    index_name: str = AUTHORIZED_INDEX_NAME,
) -> Tuple[List[ConstituentRecord], List[RejectedRowRecord], Dict[str, Any]]:
    """Retrieve, validate, and normalize current NIFTY 500 constituents from upstream client.

    Returns:
        (normalized_records, rejected_records, audit_metadata)

    Raises:
        ValueError: If index name is unauthorized or response is invalid/HTML/CAPTCHA.
        ConnectionError: If transport connectivity fails.
        TimeoutError: If request times out.
    """
    validated_index = validate_index_name(index_name)

    # Perform upstream constituent retrieval via supported client interfaces
    if hasattr(client, "listEquityStocksByIndex"):
        raw_response = client.listEquityStocksByIndex(index=validated_index)
    elif hasattr(client, "get_nifty500_constituents"):
        raw_response = client.get_nifty500_constituents()
    elif hasattr(client, "get_index_constituents"):
        raw_response = client.get_index_constituents(validated_index)
    else:
        return [], [], {
            "error": "SOURCE_UNAVAILABLE",
            "classification": ConstituentClassification.SOURCE_UNAVAILABLE.value,
            "source_row_count": 0,
            "normalized_row_count": 0,
            "rejected_row_count": 0,
            "conservation_holds": True,
        }

    if raw_response is None:
        raise ValueError("Upstream returned None/empty response.")

    # Check for HTML error or CAPTCHA pages
    if isinstance(raw_response, str):
        if "<html" in raw_response.lower() or "<!doctype" in raw_response.lower():
            raise ValueError("HTML response received instead of JSON data payload.")
        if "captcha" in raw_response.lower():
            raise ValueError("CAPTCHA response received from upstream.")
        try:
            raw_response = json.loads(raw_response)
        except Exception as e:
            raise ValueError(f"Failed to parse upstream string payload as JSON: {e}") from e

    if not isinstance(raw_response, (dict, list)):
        raise TypeError(f"Unexpected response type from upstream: {type(raw_response).__name__}")

    raw_list: List[Dict[str, Any]] = []
    source_timestamp: str = datetime.now(timezone.utc).isoformat()
    source_report_date: Optional[str] = None

    if isinstance(raw_response, dict):
        if "timestamp" in raw_response and isinstance(raw_response["timestamp"], str):
            source_timestamp = raw_response["timestamp"].strip()
            # Attempt parsing date from timestamp e.g. "10-Oct-2026 15:30:00"
            m = re.match(r"^(\d{2}-[A-Za-z]{3}-\d{4})", source_timestamp)
            if m:
                source_report_date = m.group(1)

        raw_data_field = raw_response.get("data")
        if raw_data_field is None:
            raise ValueError("Upstream dictionary payload missing 'data' key.")
        if not isinstance(raw_data_field, list):
            raise TypeError(f"Upstream 'data' field is not a list: {type(raw_data_field).__name__}")
        raw_list = raw_data_field
    elif isinstance(raw_response, list):
        raw_list = raw_response

    if not raw_list:
        raise ValueError("Upstream returned empty constituent list.")

    ingestion_ts = datetime.now(timezone.utc).isoformat()

    records: List[ConstituentRecord] = []
    rejected_rows: List[RejectedRowRecord] = []
    seen_symbols: set[str] = set()
    seen_isins: set[str] = set()

    missing_symbols_count = 0
    invalid_symbols_count = 0
    duplicate_symbols_count = 0
    missing_isins_count = 0
    duplicate_isins_count = 0
    missing_series_count = 0
    missing_sectors_count = 0
    missing_industries_count = 0

    for idx, row in enumerate(raw_list):
        if not isinstance(row, dict):
            rejected_rows.append(
                RejectedRowRecord(
                    symbol="UNKNOWN",
                    raw_payload={"item": str(row)},
                    reason="NON_DICT_ROW_PAYLOAD",
                    timestamp=ingestion_ts,
                    row_index=idx,
                )
            )
            continue

        raw_sym = row.get("symbol") or (
            row.get("meta", {}).get("symbol") if isinstance(row.get("meta"), dict) else None
        )

        # Detect index summary header row (e.g. symbol is "NIFTY 500" or matches index name)
        if raw_sym and str(raw_sym).strip().upper() in (validated_index, "NIFTY 500") or row.get("identifier") == validated_index:
            rejected_rows.append(
                RejectedRowRecord(
                    symbol=str(raw_sym),
                    raw_payload=row,
                    reason="INDEX_HEADER_ROW_SKIPPED",
                    timestamp=ingestion_ts,
                    row_index=idx,
                )
            )
            continue

        if not raw_sym:
            missing_symbols_count += 1
            rejected_rows.append(
                RejectedRowRecord(
                    symbol="MISSING",
                    raw_payload=row,
                    reason="MISSING_SYMBOL",
                    timestamp=ingestion_ts,
                    row_index=idx,
                )
            )
            continue

        # Validate symbol format
        try:
            clean_sym = validate_symbol(str(raw_sym))
        except ValueError as ve:
            invalid_symbols_count += 1
            rejected_rows.append(
                RejectedRowRecord(
                    symbol=str(raw_sym),
                    raw_payload=row,
                    reason=f"INVALID_SYMBOL_FORMAT: {ve}",
                    timestamp=ingestion_ts,
                    row_index=idx,
                )
            )
            continue

        # Check for duplicate natural key (symbol)
        if clean_sym in seen_symbols:
            duplicate_symbols_count += 1
            rejected_rows.append(
                RejectedRowRecord(
                    symbol=clean_sym,
                    raw_payload=row,
                    reason="DUPLICATE_NATURAL_KEY",
                    timestamp=ingestion_ts,
                    row_index=idx,
                )
            )
            continue

        seen_symbols.add(clean_sym)

        # Extract security name
        sec_name = (
            (row.get("meta", {}).get("companyName") if isinstance(row.get("meta"), dict) else None)
            or row.get("companyName")
            or row.get("security_name")
            or clean_sym
        )

        # Extract ISIN
        isin_val = (
            (row.get("meta", {}).get("isin") if isinstance(row.get("meta"), dict) else None)
            or row.get("isin")
        )
        clean_isin: Optional[str] = None
        if isin_val and isinstance(isin_val, str) and isin_val.strip():
            clean_isin = isin_val.strip().upper()
            if clean_isin in seen_isins:
                duplicate_isins_count += 1
            else:
                seen_isins.add(clean_isin)
        else:
            missing_isins_count += 1

        # Extract exchange series
        series_val = (
            row.get("series")
            or (
                row.get("meta", {}).get("activeSeries", [None])[0]
                if isinstance(row.get("meta"), dict) and row.get("meta", {}).get("activeSeries")
                else None
            )
        )
        clean_series = str(series_val).strip().upper() if series_val else None
        if not clean_series:
            missing_series_count += 1

        # Extract industry & sector
        meta_dict = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        industry_val = meta_dict.get("industry") or row.get("industry")
        clean_industry = str(industry_val).strip() if industry_val else None
        if not clean_industry:
            missing_industries_count += 1

        sector_val = meta_dict.get("sector") or row.get("sector")
        clean_sector = str(sector_val).strip() if sector_val else None
        if not clean_sector:
            missing_sectors_count += 1

        # Row-level source timestamp
        row_ts = str(row.get("lastUpdateTime") or source_timestamp)

        # Deterministic row hash
        hasher = hashlib.sha256()
        hash_payload = f"{clean_sym}|{validated_index}|{clean_isin or ''}|{clean_series or ''}|{ingestion_ts}"
        hasher.update(hash_payload.encode("utf-8"))
        row_hash = hasher.hexdigest()

        rec = ConstituentRecord(
            symbol=clean_sym,
            security_name=str(sec_name),
            isin=clean_isin,
            index_name=validated_index,
            classification=ConstituentClassification.CURRENT_SNAPSHOT_ONLY,
            source_timestamp=row_ts,
            ingestion_timestamp=ingestion_ts,
            source_identifier="NSEDataFetcher",
            row_hash=row_hash,
            index_code=validated_index,
            exchange_series=clean_series,
            sector=clean_sector,
            industry=clean_industry,
            source_report_date=source_report_date,
        )
        records.append(rec)

    # Conservation verification
    source_row_count = len(raw_list)
    normalized_row_count = len(records)
    rejected_row_count = len(rejected_rows)
    conservation_holds = (source_row_count == normalized_row_count + rejected_row_count)

    unique_symbols_count = len(seen_symbols)
    # Structural plausibility range: 490 to 510 unique symbols
    is_plausible = (490 <= unique_symbols_count <= 510)

    audit: Dict[str, Any] = {
        "index_name": validated_index,
        "source_row_count": source_row_count,
        "normalized_row_count": normalized_row_count,
        "rejected_row_count": rejected_row_count,
        "conservation_holds": conservation_holds,
        "unique_symbols": unique_symbols_count,
        "duplicate_symbols": duplicate_symbols_count,
        "missing_symbols": missing_symbols_count,
        "invalid_symbols": invalid_symbols_count,
        "unique_isins": len(seen_isins),
        "duplicate_isins": duplicate_isins_count,
        "missing_isins": missing_isins_count,
        "missing_series": missing_series_count,
        "missing_sectors": missing_sectors_count,
        "missing_industries": missing_industries_count,
        "is_plausible_count": is_plausible,
        "classification": ConstituentClassification.CURRENT_SNAPSHOT_ONLY.value,
        "source_report_date": source_report_date,
        "source_timestamp": source_timestamp,
    }

    return records, rejected_rows, audit


def get_nifty500_constituents(
    fetcher: Any,
    index_name: str = AUTHORIZED_INDEX_NAME,
) -> Tuple[ConstituentClassification, List[ConstituentRecord]]:
    """Legacy helper for backwards compatibility.

    Calls fetch_current_index_constituents and returns (classification, records).
    """
    try:
        records, _, _ = fetch_current_index_constituents(fetcher, index_name=index_name)
        if not records:
            return ConstituentClassification.SOURCE_UNAVAILABLE, []
        return ConstituentClassification.CURRENT_SNAPSHOT_ONLY, records
    except Exception:
        return ConstituentClassification.SOURCE_UNAVAILABLE, []
