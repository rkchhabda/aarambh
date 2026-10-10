# Phase 7 Structural Audit: Milestone 4.9 Five-Stock NSE Pilot (Attempt 3 Post HTTP/2 Dependency Resolution)

## 1. Executive Summary

This structural audit evaluates the technical architecture and compliance of the Five-Stock NSE Live Pilot framework under Milestone 4.9 following HTTP/2 dependency resolution.

- **Audited Target:** `phase7.sources.pilot`, `phase7.sources.authorization`, and `phase7.sources.client_factory`
- **Execution Event:** Fresh single-use marker created outside Git (`b6f65c768dc00545bc7322b5560cbd3d95d62f8dd5a79bd815e266e2b938ef7c`); pre-flight validation passed; active marker atomically renamed to consumed state (`pilot_authorization.consumed.20261010T072920Z.json`); factory invoked with canonical keyword arguments; `nse.NSE` client constructed cleanly over HTTP/2 transport and initial session cookies persisted to staging `raw/nse_cookies_httpx.json`.
- **Audit Outcome:** Pre-flight boundaries, atomic consumption, factory contract, and HTTP/2 transport initialization functioned deterministically. However, `run_pilot()` returned immediately after client instantiation without triggering the per-symbol historical retrieval loop. Acceptance criteria failed (0/5 symbols completed, 0.0% date coverage). Zero market data was downloaded into Git or staging.

---

## 2. Structural Acceptance Criteria Compliance Matrix

| # | Acceptance Criterion | Required Threshold | Observed State | Compliance Status |
| :---: | :--- | :--- | :--- | :--- | :---: |
| 1 | Securities returning $\ge 1$ valid record | Exactly 5/5 | 0/5 (Loop not invoked) | **FAIL** |
| 2 | Date session coverage | $\ge 95\%$ | 0.0% | **FAIL** |
| 3 | Dates within 2024-01-01..2024-01-31 | 100% | 0 rows outside range | **PASS** |
| 4 | Duplicate natural keys | Exactly 0 | 0 duplicates | **PASS** |
| 5 | Invalid OHLC relationships | Exactly 0 | 0 invalid | **PASS** |
| 6 | Negative prices | Exactly 0 | 0 negative | **PASS** |
| 7 | Negative volume | Exactly 0 | 0 negative | **PASS** |
| 8 | Empty responses accepted as success | Exactly 0 | 0 accepted | **PASS** |
| 9 | HTML responses accepted as data | Exactly 0 | 0 accepted | **PASS** |
| 10 | CAPTCHA responses accepted as data | Exactly 0 | 0 accepted | **PASS** |
| 11 | ConnectionError events | 0 (or halts pilot) | 0 encountered | **PASS** |
| 12 | TimeoutError events | 0 (or halts pilot) | 0 encountered | **PASS** |
| 13 | Access-denied events | 0 (or halts pilot) | 0 encountered | **PASS** |
| 14 | Raw checksum coverage | 100% | N/A (0 payloads) | **PASS** |
| 15 | Normalized checksum coverage | 100% | N/A (0 records) | **PASS** |
| 16 | Reason codes for all rejected rows | 100% | 0 rejected rows | **PASS** |
| 17 | Repository market-data path changes | Exactly 0 | 0 files written to repo | **PASS** |
| 18 | Downloaded files staged in Git | Exactly 0 | 0 files staged | **PASS** |
| 19 | Target datasets generated | Exactly 0 | 0 targets generated | **PASS** |
| 20 | Models trained or fit | Exactly 0 | 0 models trained | **PASS** |
| 21 | Performance metrics calculated | Exactly 0 | 0 metrics calculated | **PASS** |

---

## 3. Structural Evaluation of Safety Invariants

### 3.1 Single-Use Authorization Marker Lifecycle
- Fresh marker was generated under `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9\authorization\pilot_authorization.json` via `phase7.sources.authorization`.
- During live pilot invocation, the marker was verified against scope, dates, interval, staging root hash, and expiration, and was atomically renamed via `os.replace` to `pilot_authorization.consumed.20261010T072920Z.json`.
- The active marker ceased to exist before client construction was attempted.
- The consumed marker cannot be reused.

### 3.2 External Staging Isolation
- The configured staging root `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9` is located strictly outside the Git repository tree.
- Transport initialization persisted session cookies (`nse_cookies_httpx.json`, 1493 bytes) strictly in the external staging `raw/` directory. Zero files were written to `C:\Users\r_chh\OneDrive - optgbrc\Apps\GaurviDEEP`.

### 3.3 Factory Interface and HTTP/2 Transport Compliance
- `phase7/sources/pilot.py` invoked `client_factory(download_folder=download_folder, server=True, timeout=15)`.
- No obsolete keywords (`data_dir`, `server_mode`) were passed.
- Upstream `nse.NSE` client constructed cleanly with `http2=True` without the missing-`h2` error.

### 3.4 Unwired Historical Retrieval Pipeline Defect
- `phase7/sources/pilot.py` currently terminates after Step 14 (`return 0`) without invoking the sequential symbol retrieval loop.
- In strict adherence to governance directives:
  - Source code was not modified during execution.
  - The defect is documented.
  - The marker was not recreated.
  - Live pilot is recorded as `NSE_FIVE_STOCK_PILOT_FAILED`.
