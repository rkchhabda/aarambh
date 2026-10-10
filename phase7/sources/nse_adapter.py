"""Fail-closed NSE data source adapter implementing strict Phase 7 safety controls.

Enforces:
- Single active request locking
- Minimum 2.0s delay between network requests
- External staging directory enforcement
- Non-inference of turnover, ISIN, and adjustment states
- Comprehensive rejection ledgers and immutable request manifests
"""

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Union

from phase7.sources.client_protocol import NSEClientProtocol
from phase7.sources.contracts import (
    ConstituentClassification,
    ConstituentRecord,
    CorporateActionRecord,
    FieldStatus,
    HistoricalEODRecord,
    RejectedRowRecord,
    RejectedSymbolRecord,
    RequestManifest,
    RequestStatus,
)
from phase7.sources.manifest import build_manifest, write_manifest
from phase7.sources.normalization import normalize_historical_row
from phase7.sources.pilot_guard import (
    DEVELOPMENT_CUTOFF_DATE,
    validate_date_range,
    validate_staging_path,
    validate_symbol,
)
from phase7.sources.rejections import RejectionLedger


@dataclass(frozen=True)
class HistoricalFetchResult:
    symbol: str
    records: List[HistoricalEODRecord]
    manifest: RequestManifest
    rejected_rows: List[RejectedRowRecord]
    is_empty: bool = False
    is_partial: bool = False


class NSEDataSourceAdapter:
    """Isolated, fail-closed Phase 7 adapter for upstream NSE clients."""

    MIN_DELAY_SECONDS = 2.0

    def __init__(
        self,
        client: Optional[NSEClientProtocol] = None,
        client_factory: Optional[Callable[[], NSEClientProtocol]] = None,
        staging_root: Optional[Union[str, Path]] = None,
        repo_root: Optional[Union[str, Path]] = None,
    ):
        if client is None and client_factory is None:
            raise ValueError("Either an explicit client or client_factory must be provided.")

        self._client = client
        self._client_factory = client_factory
        self._lock = Lock()
        self._last_request_time: float = 0.0

        self.repo_root = Path(repo_root or Path.cwd()).resolve()
        if staging_root:
            self.staging_root = validate_staging_path(Path(staging_root), self.repo_root)
        else:
            self.staging_root = None

    def _get_client(self) -> NSEClientProtocol:
        if self._client is not None:
            return self._client
        if self._client_factory is not None:
            return self._client_factory()
        raise RuntimeError("No valid client or client_factory available.")

    def _enforce_rate_limit(self) -> None:
        """Enforce strict minimum 2.0-second delay between sequential requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.MIN_DELAY_SECONDS:
            time.sleep(self.MIN_DELAY_SECONDS - elapsed)
        self._last_request_time = time.time()

    def fetch_historical_eod(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1d",
        rejection_ledger: Optional[RejectionLedger] = None,
    ) -> HistoricalFetchResult:
        """Fetch and normalize historical EOD data under strict fail-closed guards."""
        with self._lock:
            ingestion_ts = datetime.now(timezone.utc).isoformat()
            request_id = str(uuid.uuid4())

            # 1. Symbol and Date Validation
            try:
                norm_symbol = validate_symbol(symbol)
                validate_date_range(start_date, end_date)
            except ValueError as val_err:
                if rejection_ledger:
                    rejection_ledger.record_rejected_symbol(
                        symbol=symbol,
                        reason=str(val_err),
                        timestamp=ingestion_ts,
                        requested_range=f"{start_date} to {end_date}",
                    )
                empty_manifest = build_manifest(
                    request_id=request_id,
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    interval=interval,
                    retrieval_timestamp=ingestion_ts,
                    raw_payload=[],
                    normalized_records=[],
                    status=RequestStatus.REJECTED,
                    failure_reason=str(val_err),
                )
                return HistoricalFetchResult(
                    symbol=symbol,
                    records=[],
                    manifest=empty_manifest,
                    rejected_rows=[],
                )

            # 2. Rate Limiting Enforced
            self._enforce_rate_limit()

            # 3. Upstream Client Execution
            client = self._get_client()
            try:
                raw_response = client.fetch_equity_historical_data(
                    symbol=norm_symbol,
                    start_date=start_date,
                    end_date=end_date,
                    interval=interval,
                )
            except Exception as exc:
                if rejection_ledger:
                    rejection_ledger.record_rejected_symbol(
                        symbol=norm_symbol,
                        reason=f"Client execution failure: {exc}",
                        timestamp=ingestion_ts,
                        requested_range=f"{start_date} to {end_date}",
                    )
                manifest = build_manifest(
                    request_id=request_id,
                    symbol=norm_symbol,
                    start_date=start_date,
                    end_date=end_date,
                    interval=interval,
                    retrieval_timestamp=ingestion_ts,
                    raw_payload={"error": str(exc)},
                    normalized_records=[],
                    status=RequestStatus.FAILED,
                    failure_reason=str(exc),
                )
                return HistoricalFetchResult(
                    symbol=norm_symbol,
                    records=[],
                    manifest=manifest,
                    rejected_rows=[],
                )

            # 4. Extract Row List
            if isinstance(raw_response, dict):
                raw_rows = raw_response.get("data", []) or []
            elif isinstance(raw_response, list):
                raw_rows = raw_response
            else:
                raw_rows = []

            # 5. Handle Empty Response
            if not raw_rows:
                manifest = build_manifest(
                    request_id=request_id,
                    symbol=norm_symbol,
                    start_date=start_date,
                    end_date=end_date,
                    interval=interval,
                    retrieval_timestamp=ingestion_ts,
                    raw_payload=raw_response,
                    normalized_records=[],
                    status=RequestStatus.EMPTY,
                    failure_reason="No rows returned by upstream provider",
                )
                return HistoricalFetchResult(
                    symbol=norm_symbol,
                    records=[],
                    manifest=manifest,
                    rejected_rows=[],
                    is_empty=True,
                )

            # 6. Normalize and Validate Rows
            normalized_records: List[HistoricalEODRecord] = []
            rejected_rows: List[RejectedRowRecord] = []
            natural_keys = set()

            for row in raw_rows:
                try:
                    record = normalize_historical_row(
                        raw_row=row,
                        symbol=norm_symbol,
                        ingestion_ts=ingestion_ts,
                    )
                    # Duplicate natural key rejection
                    key = (record.symbol, record.trading_date)
                    if key in natural_keys:
                        err_msg = f"Duplicate natural key detected: {key}"
                        if rejection_ledger:
                            rejection_ledger.record_rejected_row(norm_symbol, row, err_msg, ingestion_ts)
                        rejected_rows.append(RejectedRowRecord(norm_symbol, row, err_msg, ingestion_ts))
                        continue

                    natural_keys.add(key)
                    normalized_records.append(record)

                except (ValueError, TypeError) as row_err:
                    err_msg = str(row_err)
                    if rejection_ledger:
                        rejection_ledger.record_rejected_row(norm_symbol, row, err_msg, ingestion_ts)
                    rejected_rows.append(RejectedRowRecord(norm_symbol, row, err_msg, ingestion_ts))

            # 7. Build Manifest
            status = RequestStatus.SUCCESS if normalized_records else RequestStatus.REJECTED
            is_partial = (len(rejected_rows) > 0 and len(normalized_records) > 0)
            if is_partial:
                status = RequestStatus.PARTIAL

            manifest = build_manifest(
                request_id=request_id,
                symbol=norm_symbol,
                start_date=start_date,
                end_date=end_date,
                interval=interval,
                retrieval_timestamp=ingestion_ts,
                raw_payload=raw_response,
                normalized_records=normalized_records,
                status=status,
                is_partial=is_partial,
            )

            return HistoricalFetchResult(
                symbol=norm_symbol,
                records=normalized_records,
                manifest=manifest,
                rejected_rows=rejected_rows,
                is_partial=is_partial,
            )

    def get_current_index_constituents(
        self,
        index_name: str = "NIFTY 500",
    ) -> List[ConstituentRecord]:
        """Retrieve current index constituents classified strictly as CURRENT_SNAPSHOT_ONLY.

        Returns empty list if upstream lacks index constituent methods.
        """
        with self._lock:
            self._enforce_rate_limit()
            client = self._get_client()

            if not hasattr(client, "listEquityStocksByIndex"):
                return []

            ingestion_ts = datetime.now(timezone.utc).isoformat()
            raw = client.listEquityStocksByIndex(index=index_name)
            data = raw.get("data", []) if isinstance(raw, dict) else []

            records = []
            for item in data:
                sym = item.get("symbol") or item.get("identifier")
                if not sym:
                    continue
                records.append(
                    ConstituentRecord(
                        symbol=str(sym).strip().upper(),
                        security_name=str(item.get("meta", {}).get("companyName") or item.get("symbol") or ""),
                        isin=item.get("meta", {}).get("isin"),
                        index_name=index_name,
                        classification=ConstituentClassification.CURRENT_SNAPSHOT_ONLY,
                        source_timestamp=str(item.get("lastUpdateTime") or ingestion_ts),
                        ingestion_timestamp=ingestion_ts,
                        source_identifier="NSE_EQUITY_STOCKS_BY_INDEX",
                        row_hash="",
                    )
                )
            return records
