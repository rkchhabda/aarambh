# Phase 7 NSEDataFetcher Source & Capability Audit

**Document Identifier:** `PHASE7_NSE_DATA_FETCHER_SOURCE_AUDIT`
**Governing Workstream:** Milestone 4.8 Static Source Inspection
**Audit Target:** `connector_review/nse_data_service.py`
**Source SHA-256 Checksum:** `E841C2C1CB943D60D8A783842EA0DFD4E71EE6C0D9CE92EB17B9C39CC48A7105`
**Audit Mode:** Static Analysis (Zero Execution, Zero Network, Zero Package Installation)
**Integration Status:** `NSE_DATA_FETCHER_SOURCE_AUDITED_INTEGRATION_NOT_AUTHORIZED`

---

## 1. Source & Integrity Inventory

| Attribute | Verified Value / Finding |
|---|---|
| **Relative Source Path** | `connector_review/nse_data_service.py` |
| **File Size** | 14,081 bytes |
| **Line Count** | 418 lines |
| **Character Encoding** | UTF-8 (without BOM) |
| **Syntax Compilation** | Succeeded (`py_compile` exit code 0 under Python 3.12.10) |
| **Shebang** | `#!/usr/bin/env python3` |
| **Top-Level Docstring** | *"A self-contained wrapper around the ``nse`` package for live quotes, market status, and historical NSE equity data. It includes a small file cache and CLI."* |
| **Stated Installation** | `pip install "nse[server]"` |
| **Stated Usage Notice** | *"Important: review NSE access terms and licensing before commercial use."* |
| **Embedded Secrets Audit** | **0 occurrences found** across `api_key`, `password`, `secret`, `token`, `cookie`, `authorization`, `bearer`, `session_id`, `x-api-key`, `private_key` |

---

## 2. Imports & Architectural Dependencies

### Standard Library Imports
- `argparse` (CLI parsing)
- `csv` (CSV file output)
- `json` (JSON serialization and cache storage)
- `logging` (Log stream formatting)
- `sys` (Process management)
- `time` (Timestamping and rate-limiting sleeps)
- `datetime.datetime` (Date validation and formatting)
- `pathlib.Path` (Filesystem path manipulation)
- `typing.Any`, `typing.Dict`, `typing.List`, `typing.Optional` (Type annotations)

### Third-Party Import & Critical Defect
- `from nse import NSE` (Lines 24–29):
  ```python
  try:
      from nse import NSE
  except ImportError:
      print("ERROR: Required library 'nse' not installed.")
      print('Install it with: pip install "nse[server]"')
      sys.exit(1)
  ```
  **Finding:** Importing `nse_data_service.py` when `nse` is missing executes `sys.exit(1)`. This immediately kills the host Python interpreter, preventing callers from handling `ImportError` gracefully or injecting mocks.

---

## 3. Class & Method Inventory

### Class: `FileCache` (Lines 46–84)
- **`__init__(self, cache_dir: Path)`**: Resolves `self.cache_dir = Path(cache_dir) / "_cache"`. Immediate side effect: `self.cache_dir.mkdir(parents=True, exist_ok=True)`.
- **`_path_for(self, key: str) -> Path`**: Sanitizes key characters to `[a-zA-Z0-9-_.]`. Returns `cache_dir / f"{safe}.json"`.
- **`get(self, key: str) -> Optional[Any]`**: Reads JSON cache file. If expired (`expires_at < time.time()`), unlinks the file and returns `None`. Silently catches exceptions at `DEBUG` logging.
- **`set(self, key: str, value: Any, ttl: int = 60) -> None`**: Writes JSON object `{"expires_at": time.time() + ttl, "value": value}` via `json.dump(..., default=str)`. Direct file overwrite; non-atomic write.
- **`clear(self) -> None`**: Deletes all `*.json` files in `cache_dir`.

### Class: `NSEDataFetcher` (Lines 86–322)
- **`__init__(self, data_dir: Path = DEFAULT_DATA_DIR, server_mode: bool = True, cache_ttl: int = DEFAULT_CACHE_TTL, rate_limit_sleep: float = DEFAULT_RATE_LIMIT_SLEEP)`**:
  - Defaults: `data_dir=Path("./nse_data")`, `server_mode=True`, `cache_ttl=60`, `rate_limit_sleep=0.5`.
  - Immediate side effect: `self.data_dir.mkdir(parents=True, exist_ok=True)` and instantiates `FileCache`.
- **`_new_client(self) -> NSE`**: Instantiates `NSE(download_folder=self.data_dir, server=self.server_mode)`.
- **`_rate_limit(self) -> None`**: Calls `time.sleep(self.rate_limit_sleep)`.
- **`_cache_key(*parts: str) -> str`**: Static method joining string components with `_`.
- **`get_live_quote(self, symbol: str, use_cache: bool = True, ttl: Optional[int] = None) -> Dict[str, Any]`**:
  - Normalizes symbol (`upper().strip()`).
  - Checks cache key `quote_{symbol}`.
  - Calls `_rate_limit()` and executes `raw = nse.equityQuote(symbol)`.
  - Calls `nse.exit()` inside a `finally` block.
  - Extracts fields into normalized dictionary.
- **`get_multiple_quotes(self, symbols: List[str], use_cache: bool = True) -> Dict[str, Dict[str, Any]]`**:
  - Iterates sequentially over symbols; catches broad `Exception`, returning `{"error": str(exc)}`.
- **`get_market_status(self, use_cache: bool = True, ttl: int = DEFAULT_STATUS_TTL) -> Dict[str, Any]`**:
  - Executes `raw = nse.status()`.
  - Maps market states assuming positional indices: 0 (capital), 1 (currency), 2 (commodity), 3 (debt).
- **`get_historical_data(self, symbol: str, start_date: str, end_date: str, interval: str = "1d", use_cache: bool = True) -> List[Dict[str, Any]]`**:
  - Normalizes symbol.
  - Validates `YYYY-MM-DD` date strings using `datetime.strptime`.
  - Checks `start_dt > end_dt` and raises `ValueError`.
  - Checks `(datetime.now() - start_dt).days > 730` (`MAX_HISTORICAL_DAYS`); logs warning but does not reject.
  - Checks cache key `history_{symbol}_{start}_{end}_{interval}`.
  - Calls `_rate_limit()` and executes `data = nse.fetch_equity_historical_data(symbol=symbol, start_date=start_date, end_date=end_date, interval=interval)`.
  - Calls `nse.exit()` inside `finally`.
  - Extracts `data.get("data", [])` or raw list. Returns `[]` on empty response.
- **`export_to_json(data: Any, filepath: Path) -> Path`**: Static method writing JSON payload to arbitrary caller-supplied path.
- **`export_to_csv(data: List[Dict], filepath: Path) -> Path`**: Static method writing CSV with union of row headers. Encodes nested lists/dicts as JSON strings.
- **`clear_cache(self) -> None`**: Wipes all files from cache directory.

### Standalone Functions (Lines 324–417)
- **`build_parser() -> argparse.ArgumentParser`**: Configures CLI subparsers (`quote`, `quotes`, `status`, `history`, `clear-cache`).
- **`print_human_quote(result: Dict[str, Any]) -> None`**: Formats live quote fields for console display.
- **`main() -> None`**: CLI entry point with exception handling.

---

## 4. Historical-Data Behavior Analysis

Unlike the legacy `features/data_provider.py` connector (which hardcodes `end_d = date.today()` and trailing 365 days):
1. **Explicit Calendar Range Supported:** `NSEDataFetcher.get_historical_data` explicitly accepts `start_date` and `end_date` parameters.
2. **Date Preservation:** Caller-supplied start and end dates are preserved and passed directly to the upstream method without substitution.
3. **Format Validation:** Strict ISO `YYYY-MM-DD` parsing via `datetime.strptime`.
4. **730-Day Boundary Warning:** If the start date is older than 730 days (2 years), the method logs a warning (`"Start date %s is older than two years..."`) but proceeds to send the request.
5. **Verdict:** `EXPLICIT_DATE_RANGE_SUPPORTED_BY_WRAPPER` is verified. However, `FULL_DATE_RANGE_CONFIRMED_BY_LIVE_SOURCE` remains unverified until live testing.

---

## 5. Live-Quote & Historical Schema Evaluation

### Live Quote Schema Extracted
- `symbol`
- `last_price` (`priceInfo.lastPrice`)
- `change` (`priceInfo.change`)
- `pct_change` (`priceInfo.pChange`)
- `day_high` (`priceInfo.intraDayHighLow.max`)
- `day_low` (`priceInfo.intraDayHighLow.min`)
- `open` (`priceInfo.open`)
- `previous_close` (`priceInfo.previousClose`)
- `volume` (`securityWiseDP.quantityTraded`)
- `vwap` (`priceInfo.vwap`)
- `market_cap` (`marketDeptOrderBook.marketCap`)
- `sector` (`metadata.industry`)
- `timestamp` (`metadata.lastUpdateTime`)
- `raw` (Full upstream response dictionary)

### Critical Schema Gaps for Gate 1
- **Traded Value in INR (`turnover`):** Not extracted in live quote.
- **ISIN:** Not extracted in live quote or historical wrapper.
- **Exchange Series:** Not extracted.
- **Number of Trades:** Not extracted.
- **Deliverable Quantity & Delivery Percentage:** Not extracted.
- **Trade Status & Adjustment State:** Not provided.

---

## 6. Filesystem & Network Side Effects

1. **Working Directory Mutation:** Instantiating `NSEDataFetcher` with default `DEFAULT_DATA_DIR = Path("./nse_data")` creates `./nse_data` and `./nse_data/_cache` directly inside the current working directory.
2. **Upstream Session Side Effects:** The upstream `nse.NSE` class writes session cookies and temporary HTTP artifacts directly into the `download_folder`.
3. **Encapsulated Network Layer:** All network requests are made by the upstream `nse` package using `httpx` (with `server=True`) or `requests`. HTTP response status codes (200, 401, 403, 429), response headers, and transport timeouts are completely hidden from `NSEDataFetcher`.

---

## 7. Capability Classification Matrix

| Capability Dimension | Classification | Audit Finding |
|---|---|---|
| Live single-symbol quote | `IMPLEMENTED_IN_WRAPPER` | Functional wrapper around `nse.equityQuote`. |
| Multiple quotes | `IMPLEMENTED_IN_WRAPPER` | Sequential loop with individual error capture. |
| Market status | `PARTIALLY_IMPLEMENTED` | Relies on fragile positional array indices. |
| Explicit historical date range | `IMPLEMENTED_IN_WRAPPER` | Explicit `start_date` and `end_date` parameters passed upstream. |
| Daily interval support | `IMPLEMENTED_IN_WRAPPER` | Default `1d` supported. |
| Historical OHLCV schema | `DELEGATED_TO_UPSTREAM_UNVERIFIED` | Raw upstream dictionaries returned without Phase 7 contract validation. |
| Exchange-reported turnover | `NOT_IMPLEMENTED` | Missing from quote extraction; historical unverified. |
| VWAP | `PARTIALLY_IMPLEMENTED` | Extracted in quote; historical unverified. |
| ISIN | `NOT_IMPLEMENTED` | Not extracted from quote or historical payloads. |
| NIFTY 500 constituents | `NOT_IMPLEMENTED` | **Zero constituent or index membership methods exist.** |
| Corporate actions | `NOT_IMPLEMENTED` | **Zero corporate action methods exist.** |
| Security master | `NOT_IMPLEMENTED` | **Zero security master methods exist.** |
| Historical sector classification | `NOT_IMPLEMENTED` | Only current industry snapshot in live quote. |
| Delisted / removed security coverage | `DELEGATED_TO_UPSTREAM_UNVERIFIED` | Upstream behavior unknown. |
| HTTP denial / CAPTCHA detection | `NOT_ENFORCED_BY_SUPPLIED_WRAPPER` | Upstream library encapsulates network response codes. |
| Rate-limit delay (>= 2.0s) | `REQUIRES_INTERNAL_REMEDIATION` | Default 0.5s violates safety threshold. |
| Checksum & manifest generation | `NOT_IMPLEMENTED` | Must be provided by external Phase 7 adapter. |
| Process isolation on import failure | `REQUIRES_INTERNAL_REMEDIATION` | `sys.exit(1)` terminates calling process. |
