# Phase 7 Security Review: Production FastAPI NSE Data Service Wrapper

## 1. Executive Summary

This document presents a comprehensive security, concurrency, and reliability audit of the existing FastAPI serving wrapper used in GaurviDEEP for NSE retrieval.

**Important Milestone 4.8 Boundary:** In accordance with strict milestone directives, the production FastAPI code is **NOT MODIFIED** during this milestone. These findings and recommendations serve as an authoritative technical review and future production remediation guide.

---

## 2. Audited Wrapper Implementation

```python
from fastapi import FastAPI, HTTPException
from nse_data_service import NSEDataFetcher

app = FastAPI(title="NSE Data API")
fetcher = NSEDataFetcher(data_dir="./nse_data", server_mode=True)

@app.get("/api/quote/{symbol}")
async def get_quote(symbol: str):
    try:
        return fetcher.get_live_quote(symbol)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/api/status")
async def get_status():
    return fetcher.get_market_status()

@app.get("/api/history/{symbol}")
async def get_history(symbol: str, start: str, end: str):
    return fetcher.get_historical_data(symbol, start, end)
```

---

## 3. Critical Security & Architectural Findings

### 3.1 Information Disclosure (`detail=str(e)`)
- **Vulnerability:** In `/api/quote/{symbol}`, raw upstream exceptions are serialized into the HTTP 502 response body: `detail=str(e)`.
- **Impact:** Upstream exceptions from `nse` or `requests` frequently contain absolute local file paths, internal IP addresses, upstream request URLs, session headers, and Python library stack traces.
- **Risk Level:** **HIGH** (CWE-209: Generation of Error Message Containing Sensitive Information).

### 3.2 Unhandled Exception Boundaries in `/api/status` and `/api/history`
- **Vulnerability:** Neither `/api/status` nor `/api/history/{symbol}` contains a `try...except` block or structured exception handler.
- **Impact:** Any upstream timeout, DNS resolution failure, JSON parsing error, or validation failure propagates unhandled to FastAPI, resulting in raw HTTP 500 Internal Server Error responses that can crash the worker process.
- **Risk Level:** **HIGH** (CWE-703: Improper Check or Handling of Exceptional Conditions).

### 3.3 Absence of Input Validation & Sanitization
- **Symbol Route Parameter:** `symbol: str` has no validation constraints. An attacker can supply path traversal fragments (`../../etc`), URL schemes, query parameters, or excessively long strings.
- **Date Query Strings:** `start: str` and `end: str` in `/api/history` are unvalidated strings. They are passed directly into `fetcher.get_historical_data`. While the fetcher attempts date parsing, malformed strings trigger internal ValueError exceptions that produce raw 500 responses.
- **Risk Level:** **MEDIUM-HIGH** (CWE-20: Improper Input Validation).

### 3.4 Blocking Synchronous I/O Inside Asynchronous Event Loop
- **Vulnerability:** The route handlers are declared `async def`, but call synchronous, blocking methods (`fetcher.get_live_quote`, `fetcher.get_historical_data`) that execute `time.sleep()` and synchronous network I/O (`requests.get`).
- **Impact:** Because Python asyncio uses a single-threaded event loop per worker, executing synchronous network calls directly in `async def` functions blocks the entire server event loop. All other incoming requests are frozen until the network call completes.
- **Risk Level:** **HIGH** (Concurrency Bottleneck / Denial of Service).

### 3.5 Uncontrolled Proxy & Lack of Authentication
- **Vulnerability:** The service exposes direct, unauthenticated HTTP endpoints for live quotes, status, and historical data.
- **Impact:** If deployed to a network without a reverse proxy enforcing authentication and throttling, the service functions as an open, unrestricted proxy for third-party automated scraping against NSE.
- **Risk Level:** **HIGH** (CWE-306: Missing Authentication for Critical Function).

### 3.6 Working Directory Dependency (`./nse_data`)
- **Vulnerability:** `data_dir="./nse_data"` is a relative path resolved against the current working directory (`os.getcwd()`).
- **Impact:** If the FastAPI server is started from different directories (e.g., repository root, `service/`, or system root), cache files and temporary data are scattered unpredictably.
- **Risk Level:** **MEDIUM** (Operational Reliability).

---

## 4. Production Remediation Roadmap (Recommended for Future Milestone)

1. **Structured Exception Mapping:**
   Replace `detail=str(e)` with generic public error messages and structured internal logging:
   ```python
   logger.error("Upstream quote retrieval failed for symbol %s: %s", symbol, exc, exc_info=True)
   raise HTTPException(status_code=502, detail="Upstream market data temporarily unavailable")
   ```
2. **Global Exception Handlers:**
   Implement `@app.exception_handler(Exception)` to guarantee clean JSON error envelopes across all routes.
3. **Strict Pydantic Schemas:**
   Validate `symbol` with strict regex (`^[A-Z0-9_\-\.&]{1,20}$`) and dates with `datetime.date` types.
4. **Threadpool Offloading (`run_in_threadpool`):**
   Offload blocking fetcher calls to a threadpool to prevent freezing the asyncio event loop:
   ```python
   from starlette.concurrency import run_in_threadpool
   return await run_in_threadpool(fetcher.get_historical_data, symbol, start, end)
   ```
5. **Rate Limiting & Authentication:**
   Introduce API key validation (`HTTPBearer` or `APIKeyHeader`) and per-IP / per-token token-bucket rate limiting (e.g., `slowapi`).
6. **Absolute Path Configuration:**
   Inject `data_dir` from an environment variable (e.g., `NSE_DATA_DIR`) or strict configuration object.
