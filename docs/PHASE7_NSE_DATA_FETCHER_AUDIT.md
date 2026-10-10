# Phase 7 Audit: Authoritative NSEDataFetcher Implementation

## 1. Executive Summary

- **Source File:** `connector_review/nse_data_service.py`
- **Class:** `NSEDataFetcher`
- **Underlying Engine:** Python package `nse` (version `4.0.1`, GPLv3)
- **Runtime Environment:** Python 3.12.10 (`.venv-phase7`)
- **Key Finding:** `NSEDataFetcher` implements explicit historical date range retrieval via `get_historical_data(symbol, start_date, end_date, interval="1d")`. It preserves explicit calendar windows without defaulting to `date.today()`.
- **Capability Gaps:** `NSEDataFetcher` lacks methods for index constituents (NIFTY 500), security master, corporate action adjustments, and historical point-in-time sector classifications.
- **Safety Status:** **UNSAFE_FOR_LIVE_PILOT** (due to upstream encapsulation of HTTP error codes, lack of transport-level 429 backoff, and local directory write behavior).

---

## 2. Source Code Identification & Integrity

| Property | Value |
| :--- | :--- |
| **Module Path** | `connector_review/nse_data_service.py` |
| **Class Name** | `NSEDataFetcher` |
| **Serving Wrapper** | FastAPI application provided in Milestone 4.8 specification |
| **Direct Dependency** | `nse` (version `4.0.1`) |
| **Licence** | GNU General Public License v3.0 (GPLv3) |
| **Module Status** | Untracked reference connector provided for static audit |

---

## 3. Public Method Inventory

| Method | Signature | Upstream Call | Date Support | Cache / Disk Behavior | Phase 7 Suitability |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `__init__` | `(data_dir="./nse_data", server_mode=True, cache_ttl=60, rate_limit_sleep=0.5)` | N/A | N/A | Creates `./nse_data/_cache` | High (requires staging isolation) |
| `get_live_quote` | `(symbol: str, use_cache=True, ttl=None)` | `NSE.equityQuote(symbol)` | Snapshot | FileCache JSON (TTL 60s) | Unverified (live snapshot only) |
| `get_multiple_quotes`| `(symbols: List[str], use_cache=True)` | Iterates `get_live_quote` | Snapshot | FileCache JSON | Unverified |
| `get_market_status` | `(use_cache=True, ttl=30)` | `NSE.status()` | Snapshot | FileCache JSON (TTL 30s) | Available |
| `get_historical_data`| `(symbol: str, start_date: str, end_date: str, interval="1d", use_cache=True)` | `NSE.fetch_equity_historical_data(...)` | Explicit `YYYY-MM-DD` | FileCache JSON (TTL 3600s) | Available via Fail-Closed Adapter |
| `export_to_json` | `(data: Any, filepath: Path)` | N/A | N/A | Writes JSON to disk | Utility only |
| `export_to_csv` | `(data: List[Dict], filepath: Path)` | N/A | N/A | Writes CSV to disk | Utility only |
| `clear_cache` | `()` | N/A | N/A | Deletes cache files | Utility only |

---

## 4. Deep Inspection of `get_historical_data`

### 4.1 Interface Contract
```python
def get_historical_data(
    self,
    symbol: str,
    start_date: str,
    end_date: str,
    interval: str = "1d",
    use_cache: bool = True,
) -> List[Dict[str, Any]]:
```

### 4.2 Parameter and Date Behavior
1. **Date Validation:** Parses `start_date` and `end_date` using `datetime.strptime(date, "%Y-%m-%d")`.
2. **Date Sequence:** Raises `ValueError("start_date must be before end_date")` if `start_dt > end_dt`.
3. **Range Warning:** Logs a warning if `(datetime.now() - start_dt).days > 730` (two-year window limitation).
4. **Range Preservation:** Passes exact `start_date` and `end_date` strings directly to `nse.fetch_equity_historical_data`. No substitution with `date.today()`.
5. **Pagination & Request Count:** Issues a single upstream call per invocation.
6. **Output Format:** Returns a list of dictionaries (`List[Dict[str, Any]]`) or empty list `[]`.

### 4.3 Reported Data Fields
The raw response contains exchange-reported fields:
- `CH_TIMESTAMP`: Trading date
- `CH_SERIES`: Exchange series (`EQ`)
- `CH_OPENING_PRICE`, `CH_TRADE_HIGH_PRICE`, `CH_TRADE_LOW_PRICE`, `CH_CLOSING_PRICE`
- `CH_PREVIOUS_CLS_PRICE`, `CH_LAST_TRADED_PRICE`, `VWAP`
- `CH_TOT_TRADED_QTY`: Volume
- `CH_TOT_TRADED_VAL`: Turnover (reported in INR)
- `CH_TOTAL_TRADES`: Trade count
- `COP_DELIV_QTY`, `COP_DELIV_PERC`: Delivery statistics
- `CH_ISIN`: Security identifier (when reported)

---

## 5. Critical Missing Capabilities

| Capability | In `NSEDataFetcher`? | Impact on Gate 1 Readiness |
| :--- | :--- | :--- |
| **NIFTY 500 Constituent List** | **NO** | Cannot reconstruct universe constituents point-in-time. |
| **Historical Constituent Changes** | **NO** | BLK-01 remains open (survivorship bias risk). |
| **Security Master & Symbol History**| **NO** | BLK-04 remains open (identifier mapping risk). |
| **Corporate Action Adjustments** | **NO** | BLK-02 remains open (dividend/split adjustment uncertainty). |
| **Point-in-Time Sector Classifications**| **NO** | Cannot produce historical sector-relative target features. |
| **Bhavcopy / Bulk Historical Reports**| **NO** | Single-stock iterative retrieval required (rate-limited). |

---

## 6. Safety & Transport Audit Findings

1. **HTTP Status Code Masking:** Upstream `nse==4.0.1` wraps HTTP transport errors inside generic `ConnectionError` strings without exposing raw HTTP status codes (e.g., 401, 403, 429).
2. **Missing Rate-Limit Backoff:** The fetcher uses a naive `time.sleep(0.5)`. There is no exponential backoff or dynamic 429 throttle handling.
3. **Implicit Working-Directory Writes:** The default `data_dir="./nse_data"` writes relative to the working directory, risking uncommitted repository pollution.
4. **Top-Level Import Hazard:** `nse_data_service.py` executes `sys.exit(1)` at module load if `nse` is not present, precluding direct module imports.
5. **Audit Verdict:** The implementation is **UNSAFE_FOR_LIVE_PILOT** without the Phase 7 isolated fail-closed adapter wrapper.
