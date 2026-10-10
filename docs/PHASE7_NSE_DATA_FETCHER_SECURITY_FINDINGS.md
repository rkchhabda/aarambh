# Phase 7 NSEDataFetcher Security & Transport Safety Findings

**Document Identifier:** `PHASE7_NSE_DATA_FETCHER_SECURITY_FINDINGS`
**Governing Workstream:** Milestone 4.8 Safety Invariant & Vulnerability Assessment
**Audit Target:** `connector_review/nse_data_service.py`
**Safety Verdict:** `LIVE_PILOT_UNSAFE` (without internal connector remediation)
**Remediation Requirement:** `REQUIRES_INTERNAL_CONNECTOR_CHANGES`

---

## 1. Executive Summary

A static security and transport-layer audit of `connector_review/nse_data_service.py` reveals that while the wrapper successfully supports explicit calendar dates for historical data, it violates 14 of the 17 mandatory Phase 7 data acquisition safety invariants. Crucially, several critical controls cannot be enforced by an external adapter alone because the upstream `nse` package encapsulates and hides raw HTTP status codes, headers, and socket timeouts.

---

## 2. In-Depth Vulnerability & Risk Findings

### Finding SEC-01: Import-Time Process Termination (`sys.exit(1)`)
- **Code Reference:** `connector_review/nse_data_service.py:24-29`
- **Mechanism:** When `from nse import NSE` raises `ImportError`, the module catches the exception, prints installation instructions, and invokes `sys.exit(1)`.
- **Impact:** Any external test runner, validation harness, or adapter attempting to dynamically probe or import `nse_data_service` when `nse` is not installed is forcibly terminated. This prevents exception handling, mock injection, and graceful degradation.

### Finding SEC-02: Constructor Disk Mutation & Working Directory Pollution
- **Code Reference:** `connector_review/nse_data_service.py:91-107`
- **Mechanism:** `NSEDataFetcher.__init__` immediately executes `self.data_dir.mkdir(parents=True, exist_ok=True)` and instantiates `FileCache`, which executes `self.cache_dir.mkdir(...)`.
- **Impact:** By default, `DEFAULT_DATA_DIR = Path("./nse_data")` resolves relative to the current working directory. Instantiating the class creates `./nse_data` and `./nse_data/_cache` directly inside the Git repository, polluting the workspace. Furthermore, upstream `NSE` writes session cookies and HTTP artifacts into this folder.

### Finding SEC-03: Insufficient Request Spacing (0.5s vs 2.0s Minimum)
- **Code Reference:** `connector_review/nse_data_service.py:42, 112-114`
- **Mechanism:** `DEFAULT_RATE_LIMIT_SLEEP = 0.5`. `_rate_limit()` calls `time.sleep(0.5)`.
- **Impact:** Phase 7 acquisition rules strictly mandate a minimum delay of >= 2.0 seconds between requests. A 0.5-second interval risks triggering IP bans, rate limiting, and CAPTCHA challenges from NSE servers.

### Finding SEC-04: Missing Socket & Request Timeouts
- **Code Reference:** `connector_review/nse_data_service.py:109-111, 258-263`
- **Mechanism:** `NSEDataFetcher` does not configure connect or read timeouts on `_new_client()` or historical fetch calls.
- **Impact:** If NSE endpoints hang, stall, or drop connections, the calling process blocks indefinitely, hanging pipeline execution.

### Finding SEC-05: Complete Encapsulation of HTTP Denial & CAPTCHA Statuses
- **Code Reference:** `connector_review/nse_data_service.py:137, 258-263`
- **Mechanism:** The upstream `NSE` library internally handles HTTP requests via `httpx` or `requests` and returns either parsed JSON dicts or raises broad internal exceptions. HTTP status codes (401, 403, 429) are not propagated.
- **Impact:** The wrapper cannot distinguish between a legitimate empty result, an authorization failure (401), a security block (403), a rate-limit lockout (429), or a Cloudflare/NSE CAPTCHA interstitial. The required fail-closed response cannot be reliably triggered from the wrapper level.

### Finding SEC-06: Missing Exponential Backoff & Retry Logic
- **Code Reference:** `connector_review/nse_data_service.py:258-263`
- **Mechanism:** Zero retry or exponential backoff logic is implemented in `NSEDataFetcher`.
- **Impact:** Network hiccups cause immediate method termination or empty lists without structured retry auditing.

### Finding SEC-07: Non-Atomic Cache Writes & Concurrency Hazards
- **Code Reference:** `connector_review/nse_data_service.py:72-80`
- **Mechanism:** `FileCache.set()` writes directly to `path.open("w")` without using a temporary file or atomic `os.replace`. No file locks (`fcntl`/`msvcrt`) are acquired.
- **Impact:** An interrupted write (e.g. process termination, crash) leaves corrupted or partial JSON cache files. Multi-process callers (e.g., Uvicorn workers) can experience race conditions and cache corruption.

### Finding SEC-08: Error Message & Path Information Leakage
- **Code Reference:** `connector_review/nse_data_service.py:176, 412`
- **Mechanism:** `get_multiple_quotes` records `{"error": str(exc)}`. The CLI and FastAPI wrapper return raw exception text.
- **Impact:** Internal exception messages can leak filesystem paths, library versions, and network endpoints to callers or API consumers.

### Finding SEC-09: Unbounded Export Paths
- **Code Reference:** `connector_review/nse_data_service.py:286-318`
- **Mechanism:** `export_to_json` and `export_to_csv` accept arbitrary `filepath` paths, creating parent directories and overwriting existing files without path confinement checks.
- **Impact:** Risk of overwriting critical project files if an untrusted caller supplies an invalid destination path.

### Finding SEC-10: FastAPI Serving Wrapper Deficiencies
Inspection of the existing FastAPI serving wrapper reveals:
1. `detail=str(e)` on HTTP 502 exposes internal stack traces.
2. `/api/status` and `/api/history/{symbol}` have zero exception boundaries.
3. Symbol and date query strings are unvalidated before invocation.
4. Synchronous network and disk calls execute directly inside `async def` routes, blocking the Uvicorn asyncio event loop.
5. Lack of authentication or route throttling exposes the service as an open proxy.

---

## 3. Control Responsibility Boundary

### Controls Enforceable Externally (via Phase 7 Adapter):
- Strict symbol format validation (uppercase, alphanumeric only, length limits).
- ISO `YYYY-MM-DD` date validation and `start_date <= end_date` enforcement.
- Development cutoff date enforcement (`<= 2025-09-16`).
- Pilot security allowlist enforcement (`RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK`).
- Mandatory external staging root enforcement (`C:\Users\r_chh\gaurvideep_phase7_staging\nse500\`).
- Output schema verification against Phase 7 contracts.
- Deterministic SHA-256 checksum generation for raw and normalized outputs.
- Immutable request manifests and rejected-row ledgers.
- Inter-request pacing enforcement (inserting >= 2.0s delay between adapter calls).

### Controls Requiring Internal Connector Remediation:
- **Removal of `sys.exit(1)`:** Replace with standard `ImportError` to allow caller handling.
- **Transport Visibility:** Expose HTTP status codes (200, 401, 403, 429) and raw response bytes from upstream.
- **Socket Timeouts:** Implement explicit connect and read timeouts (e.g., 10.0s).
- **Transport Denial Detection:** Intercept HTML/CAPTCHA payloads before parsing.
- **Atomic Cache Operations:** Write via `.tmp` file and atomic rename; implement file locking.
- **Safe Directory Defaults:** Disallow unconfigured relative working directory paths.

---

## 4. Integration Verdict

```text
REQUIRES_DEPENDENCY_APPROVAL
REQUIRES_INTERNAL_CONNECTOR_CHANGES
LIVE_PILOT_UNSAFE
```

Because critical network safety controls cannot be enforced by an external wrapper alone, `connector_review/nse_data_service.py` is classified as **UNSAFE FOR LIVE PILOT** in its current unmodified form.
