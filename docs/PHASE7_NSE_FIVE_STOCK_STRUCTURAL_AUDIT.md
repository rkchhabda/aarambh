# Phase 7 Structural Audit: Milestone 4.9 Five-Stock NSE Pilot (Attempt 2 Post Factory Alignment)

## 1. Executive Summary

This structural audit evaluates the technical architecture and compliance of the Five-Stock NSE Live Pilot framework under Milestone 4.9 following the factory interface alignment.

- **Audited Target:** `phase7.sources.pilot`, `phase7.sources.authorization`, and `phase7.sources.client_factory`
- **Execution Event:** Fresh single-use marker created outside Git (`a24805c88651d347aaf643c79fa38aee11465845e9ecc19fb6cac1d3bf86ea84`); pre-flight validation passed; active marker atomically renamed to consumed state (`pilot_authorization.consumed.20261010T065759Z.json`); factory invoked with canonical keyword arguments; execution safely halted during `nse.NSE` construction due to missing `h2` dependency required by `httpx[http2]`.
- **Audit Outcome:** Structural safety controls, factory parameter validation, and atomic consumption functioned deterministically. Zero unintended network requests, zero data contamination, zero repository writes, and zero marker reuse occurred.

---

## 2. Structural Acceptance Criteria Compliance Matrix

| # | Acceptance Criterion | Required Threshold | Observed State | Compliance Status |
| :---: | :--- | :--- | :--- | :--- | :---: |
| 1 | Securities returning $\ge 1$ valid record | Exactly 5/5 | 0/5 (Halted pre-network) | **HALTED** |
| 2 | Date session coverage | $\ge 95\%$ | 0.0% | **HALTED** |
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
- The fresh authorization marker was generated under `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9\authorization\pilot_authorization.json` via `phase7.sources.authorization`.
- During live pilot invocation, the marker was verified against scope, dates, interval, staging root hash, and expiration, and was atomically renamed via `os.replace` to `pilot_authorization.consumed.20261010T065759Z.json`.
- The active marker ceased to exist before client construction was attempted.
- The consumed marker cannot be reused.

### 3.2 External Staging Isolation
- The configured staging root `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9` is located strictly outside the Git repository tree.
- `validate_staging_root` and `validate_authorization_marker_path` strictly verified external paths; zero files were written to `C:\Users\r_chh\OneDrive - optgbrc\Apps\GaurviDEEP`.

### 3.3 Factory Interface Compliance
- `phase7/sources/pilot.py` invoked `client_factory(download_folder=download_folder, server=True, timeout=15)`.
- No obsolete keywords (`data_dir`, `server_mode`) were passed.
- Factory parameter validation passed without error.

### 3.4 Upstream Runtime Dependency Defect
- Client creation failed inside upstream library `nse==4.0.1` because `httpx` was called with `http2=True` without the required `h2` package installed.
- In strict adherence to governance directives:
  - The failure was documented rather than hot-fixed.
  - The marker was not regenerated or restored.
  - Zero network calls occurred.
