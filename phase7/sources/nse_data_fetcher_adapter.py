"""Fail-closed Phase 7 adapter wrapping the authoritative NSEDataFetcher.

Strictly enforces:
- Dependency injection for NSEDataFetcherProtocol (no module-load side effects)
- Strict symbol and ISO date range validation
- Phase 7 development cutoff (2025-09-16)
- Detection and rejection of empty, HTML, CAPTCHA, and malformed responses
- Explicit capability discovery
- Fail-closed safety status (UNSAFE_FOR_LIVE_PILOT due to upstream transport encapsulation)
- Normalized HistoricalEODRecord generation with non-inferred fields
- External staging directory enforcement and immutable request manifests
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock
import time
from typing import Any, Callable, Dict, List, Optional, Union
import uuid

from phase7.sources.contracts import (
    CapabilityStatus,
    ConstituentClassification,
    ConstituentRecord,
    FieldStatus,
    HistoricalEODRecord,
    NSEDataFetcherProtocol,
    RejectedRowRecord,
    RejectedSymbolRecord,
    RequestManifest,
    RequestStatus,
)
from phase7.sources.http_client import (
    HTTPSafetyError,
    HTTPSafetyViolationType,
    inspect_payload_safety,
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


class NSEDataFetcherAdapter:
    """Isolated, fail-closed Phase 7 adapter for NSEDataFetcher."""

    MIN_DELAY_SECONDS = 2.0
    ADAPTER_VERSION = "phase7-nse-fetcher-adapter-v1.0.0"

    def __init__(
        self,
        fetcher: Optional[NSEDataFetcherProtocol] = None,
        fetcher_factory: Optional[Callable[[], NSEDataFetcherProtocol]] = None,
        staging_root: Optional[Union[str, Path]] = None,
        repo_root: Optional[Union[str, Path]] = None,
    ):
        if fetcher is None and fetcher_factory is None:
            raise ValueError("Either an explicit fetcher or fetcher_factory must be provided.")

        self._fetcher = fetcher
        self._fetcher_factory = fetcher_factory
        self._lock = Lock()
        self._last_request_time: float = 0.0

        self.repo_root = Path(repo_root or Path.cwd()).resolve()
        if staging_root:
            self.staging_root = validate_staging_path(Path(staging_root), self.repo_root)
        else:
            self.staging_root = None

        # Upstream NSEDataFetcher encapsulates HTTP status codes inside ConnectionError strings
        # and defaults to writing ./nse_data relative to cwd. Therefore internal transport safety
        # cannot be guaranteed without internal fetcher changes.
        self.safety_status: str = "UNSAFE_FOR_LIVE_PILOT"

    def _get_fetcher(self) -> NSEDataFetcherProtocol:
        if self._fetcher is not None:
            return self._fetcher
        if self._fetcher_factory is not None:
            return self._fetcher_factory()
        raise RuntimeError("No valid fetcher or fetcher_factory available.")

    def _enforce_rate_limit(self) -> None:
        """Enforce minimum 2.0-second delay between sequential network requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.MIN_DELAY_SECONDS:
            time.sleep(self.MIN_DELAY_SECONDS - elapsed)
        self._last_request_time = time.time()

    def discover_capabilities(self) -> Dict[str, CapabilityStatus]:
        """Detect and return capability statuses for standard retrieval methods."""
        fetcher = self._get_fetcher()
        caps = {
            "get_live_quote": CapabilityStatus.AVAILABLE if hasattr(fetcher, "get_live_quote") else CapabilityStatus.NOT_IMPLEMENTED,
            "get_market_status": CapabilityStatus.AVAILABLE if hasattr(fetcher, "get_market_status") else CapabilityStatus.NOT_IMPLEMENTED,
            "get_historical_data": CapabilityStatus.AVAILABLE if hasattr(fetcher, "get_historical_data") else CapabilityStatus.NOT_IMPLEMENTED,
            "get_nifty500_constituents": CapabilityStatus.AVAILABLE if hasattr(fetcher, "get_nifty500_constituents") else CapabilityStatus.UNAVAILABLE,
            "get_index_constituents": CapabilityStatus.AVAILABLE if hasattr(fetcher, "get_index_constituents") else CapabilityStatus.UNAVAILABLE,
            "get_corporate_actions": CapabilityStatus.AVAILABLE if hasattr(fetcher, "get_corporate_actions") else CapabilityStatus.UNAVAILABLE,
            "get_security_master": CapabilityStatus.AVAILABLE if hasattr(fetcher, "get_security_master") else CapabilityStatus.UNAVAILABLE,
            "get_sector_classification": CapabilityStatus.PARTIAL if hasattr(fetcher, "get_live_quote") else CapabilityStatus.UNAVAILABLE,
        }
        return caps

    def get_live_quote(self, symbol: str) -> Dict[str, Any]:
        """Wrap get_live_quote with symbol validation and safety inspection."""
        clean_symbol = validate_symbol(symbol)
        fetcher = self._get_fetcher()
        with self._lock:
            self._enforce_rate_limit()
            res = fetcher.get_live_quote(clean_symbol)

        # Inspect safety if serialized
        if isinstance(res, str):
            inspect_payload_safety(text_content=res)
        return res

    def get_market_status(self) -> Dict[str, Any]:
        """Wrap get_market_status with safety inspection."""
        fetcher = self._get_fetcher()
        with self._lock:
            self._enforce_rate_limit()
            res = fetcher.get_market_status()

        if isinstance(res, str):
            inspect_payload_safety(text_content=res)
        return res

    def fetch_historical_eod(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1d",
        rejection_ledger: Optional[RejectionLedger] = None,
    ) -> HistoricalFetchResult:
        """Fetch and normalize historical EOD data for a single symbol and date window."""
        request_id = str(uuid.uuid4())
        retrieval_timestamp = datetime.now(timezone.utc).isoformat()

        # Step 1: Strict input validation
        try:
            clean_symbol = validate_symbol(symbol)
            clean_start, clean_end = validate_date_range(start_date, end_date)
        except ValueError as exc:
            if rejection_ledger:
                rejection_ledger.record_symbol_rejection(
                    RejectedSymbolRecord(
                        symbol=symbol,
                        reason=str(exc),
                        timestamp=retrieval_timestamp,
                        requested_range=f"{start_date}..{end_date}",
                    )
                )
            manifest = build_manifest(
                request_id=request_id,
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval=interval,
                retrieval_timestamp=retrieval_timestamp,
                client_version=self.ADAPTER_VERSION,
                source_identifier="NSEDataFetcher",
                status=RequestStatus.REJECTED,
                row_count=0,
                raw_payload="",
                normalized_records=[],
                failure_reason=str(exc),
            )
            return HistoricalFetchResult(
                symbol=symbol,
                records=[],
                manifest=manifest,
                rejected_rows=[],
                is_empty=True,
            )

        # Step 2: Rate-limited retrieval under lock
        fetcher = self._get_fetcher()
        with self._lock:
            self._enforce_rate_limit()
            try:
                raw_response = fetcher.get_historical_data(
                    symbol=clean_symbol,
                    start=clean_start,
                    end=clean_end,
                )
            except Exception as exc:
                if rejection_ledger:
                    rejection_ledger.record_symbol_rejection(
                        RejectedSymbolRecord(
                            symbol=clean_symbol,
                            reason=f"Upstream exception: {exc}",
                            timestamp=retrieval_timestamp,
                            requested_range=f"{clean_start}..{clean_end}",
                        )
                    )
                manifest = build_manifest(
                    request_id=request_id,
                    symbol=clean_symbol,
                    start_date=clean_start,
                    end_date=clean_end,
                    interval=interval,
                    retrieval_timestamp=retrieval_timestamp,
                    client_version=self.ADAPTER_VERSION,
                    source_identifier="NSEDataFetcher",
                    status=RequestStatus.FAILED,
                    row_count=0,
                    raw_payload="",
                    normalized_records=[],
                    failure_reason=str(exc),
                )
                return HistoricalFetchResult(
                    symbol=clean_symbol,
                    records=[],
                    manifest=manifest,
                    rejected_rows=[],
                    is_empty=True,
                )

        # Step 3: Payload safety checks
        if isinstance(raw_response, str):
            inspect_payload_safety(text_content=raw_response)

        # Inspect if raw response contains HTML or CAPTCHA inside stringified fields
        raw_serialized = json.dumps(raw_response, default=str)
        inspect_payload_safety(text_content=raw_serialized)

        # Step 4: Extract list of row dicts
        raw_rows: List[Dict[str, Any]] = []
        if isinstance(raw_response, dict):
            raw_rows = raw_response.get("data", []) or []
        elif isinstance(raw_response, list):
            raw_rows = raw_response

        if not raw_rows:
            manifest = build_manifest(
                request_id=request_id,
                symbol=clean_symbol,
                start_date=clean_start,
                end_date=clean_end,
                interval=interval,
                retrieval_timestamp=retrieval_timestamp,
                client_version=self.ADAPTER_VERSION,
                source_identifier="NSEDataFetcher",
                status=RequestStatus.EMPTY,
                row_count=0,
                raw_payload=raw_serialized,
                normalized_records=[],
            )
            return HistoricalFetchResult(
                symbol=clean_symbol,
                records=[],
                manifest=manifest,
                rejected_rows=[],
                is_empty=True,
            )

        # Step 5: Normalization and rejection ledger
        normalized_records: List[HistoricalEODRecord] = []
        rejected_rows: List[RejectedRowRecord] = []
        seen_dates = set()

        for row in raw_rows:
            if not isinstance(row, dict):
                rej = RejectedRowRecord(
                    symbol=clean_symbol,
                    raw_payload={"item": str(row)},
                    reason="Row is not a dictionary",
                    timestamp=retrieval_timestamp,
                )
                rejected_rows.append(rej)
                if rejection_ledger:
                    rejection_ledger.record_row_rejection(rej)
                continue

            try:
                record = normalize_historical_row(
                    raw_row=row,
                    symbol=clean_symbol,
                    source_identifier="NSEDataFetcher",
                    ingestion_timestamp=retrieval_timestamp,
                )
                # Check duplicate natural key
                if record.trading_date in seen_dates:
                    rej = RejectedRowRecord(
                        symbol=clean_symbol,
                        raw_payload=row,
                        reason=f"Duplicate natural key: date {record.trading_date} already ingested",
                        timestamp=retrieval_timestamp,
                    )
                    rejected_rows.append(rej)
                    if rejection_ledger:
                        rejection_ledger.record_row_rejection(rej)
                    continue

                seen_dates.add(record.trading_date)
                normalized_records.append(record)
            except ValueError as val_err:
                rej = RejectedRowRecord(
                    symbol=clean_symbol,
                    raw_payload=row,
                    reason=str(val_err),
                    timestamp=retrieval_timestamp,
                )
                rejected_rows.append(rej)
                if rejection_ledger:
                    rejection_ledger.record_row_rejection(rej)

        is_partial = len(rejected_rows) > 0 and len(normalized_records) > 0
        final_status = (
            RequestStatus.PARTIAL
            if is_partial
            else (RequestStatus.SUCCESS if normalized_records else RequestStatus.REJECTED)
        )

        manifest = build_manifest(
            request_id=request_id,
            symbol=clean_symbol,
            start_date=clean_start,
            end_date=clean_end,
            interval=interval,
            retrieval_timestamp=retrieval_timestamp,
            client_version=self.ADAPTER_VERSION,
            source_identifier="NSEDataFetcher",
            status=final_status,
            row_count=len(normalized_records),
            raw_payload=raw_serialized,
            normalized_records=normalized_records,
            is_partial=is_partial,
            failure_reason="Partial rows rejected" if is_partial else None,
        )

        if self.staging_root:
            write_manifest(manifest, self.staging_root)

        return HistoricalFetchResult(
            symbol=clean_symbol,
            records=normalized_records,
            manifest=manifest,
            rejected_rows=rejected_rows,
            is_empty=len(normalized_records) == 0,
            is_partial=is_partial,
        )
