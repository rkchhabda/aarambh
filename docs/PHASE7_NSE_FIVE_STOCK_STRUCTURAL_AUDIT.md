# Phase 7 Structural Audit: Milestone 4.9 Five-Stock NSE Pilot (Attempt 4 Post Pipeline Wiring)

## 1. Executive Summary

This structural audit evaluates the technical architecture and runtime behavior of the Five-Stock NSE Live Pilot framework under Milestone 4.9 following sequential pipeline wiring.

- **Audited Target:** `phase7.sources.pilot`, `phase7.sources.authorization`, `phase7.sources.persistence`, `phase7.sources.manifest`, and `phase7.sources.normalization`
- **Execution Event:** Fresh single-use marker created outside Git (`860461fd7227519c6e724dada2baf4122390d5477aa08bd6dc20faac41628e38`); pre-flight validation passed; active marker atomically renamed to consumed state (`pilot_authorization.consumed.20261010T081013Z.json`); factory invoked with canonical keyword arguments; `nse.NSE` client constructed cleanly; historical request issued for `RELIANCE`; 22 real daily trading records received from upstream NSE; raw JSON safely persisted outside Git (`raw/historical/RELIANCE_...json`); normalization failed on field key casing (`mtimestamp`); row conservation held; pilot halted safely on `PARTIAL` status; remaining symbols were protected; client closed cleanly.
- **Audit Outcome:** End-to-end network retrieval, raw persistence, cryptographic hashing, single-active request isolation, row conservation, safety halting, and clean client disposal functioned deterministically. The attempt halted on an upstream schema field key mismatch in `normalization.py`. Exit code 6 was returned. Status: `NSE_FIVE_STOCK_PILOT_HALTED_ON_SAFETY_CONTROL`.

---

## 2. Structural Acceptance Criteria Compliance Matrix

| # | Acceptance Criterion | Required Threshold | Observed State | Compliance Status |
| :---: | :--- | :--- | :--- | :--- | :---: |
| 1 | Securities returning $\ge 1$ valid record | Exactly 5/5 | 0/5 (Halted on Symbol 1 schema mismatch) | **FAIL** |
| 2 | Date session coverage | $\ge 95\%$ | 0.0% (0 normalized records produced) | **FAIL** |
| 3 | Dates within 2024-01-01..2024-01-31 | 100% | 22 raw records all within Jan 2024 | **PASS** |
| 4 | Duplicate natural keys | Exactly 0 | 0 duplicates | **PASS** |
| 5 | Invalid OHLC relationships | Exactly 0 | 0 invalid in raw data | **PASS** |
| 6 | Negative prices | Exactly 0 | 0 negative | **PASS** |
| 7 | Negative volume | Exactly 0 | 0 negative | **PASS** |
| 8 | Empty responses accepted as success | Exactly 0 | 0 accepted | **PASS** |
| 9 | HTML responses accepted as data | Exactly 0 | 0 accepted | **PASS** |
| 10 | CAPTCHA responses accepted as data | Exactly 0 | 0 accepted | **PASS** |
| 11 | ConnectionError events | 0 (or halts pilot) | 0 encountered | **PASS** |
| 12 | TimeoutError events | 0 (or halts pilot) | 0 encountered | **PASS** |
| 13 | Access-denied events | 0 (or halts pilot) | 0 encountered | **PASS** |
| 14 | Raw checksum coverage | 100% | 1/1 retrieved raw payloads hashed (100%) | **PASS** |
| 15 | Normalized checksum coverage | 100% | N/A (0 normalized files written) | **PASS** |
| 16 | Reason codes for all rejected rows | 100% | 22/22 rows recorded with reason code | **PASS** |
| 17 | Repository market-data path changes | Exactly 0 | 0 files written to repository | **PASS** |
| 18 | Downloaded files staged in Git | Exactly 0 | 0 files staged in Git | **PASS** |
| 19 | Target datasets generated | Exactly 0 | 0 targets generated | **PASS** |
| 20 | Models trained or fit | Exactly 0 | 0 models trained | **PASS** |
| 21 | Performance metrics calculated | Exactly 0 | 0 metrics calculated | **PASS** |

---

## 3. Structural Evaluation of Safety Invariants

### 3.1 Single-Use Authorization Marker Lifecycle
- Fresh marker was generated under `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9\authorization\pilot_authorization.json` via `phase7.sources.authorization`.
- During live pilot invocation, the marker was verified against scope, dates, interval, staging root hash, and expiration, and was atomically renamed via `os.replace` to `pilot_authorization.consumed.20261010T081013Z.json`.
- The active marker ceased to exist before client construction was attempted.
- Four total consumed markers exist in staging; none can be reused.

### 3.2 External Staging Isolation & Raw Persistence
- Staging root `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9` is strictly external to Git.
- Raw payload for `RELIANCE` was serialized cleanly without credentials or headers and atomically written to:
  `raw/historical/RELIANCE_2024-01-01_2024-01-31_1d_20261010T081014Z_59af0e39.json`
- Deterministic SHA-256 hash was computed: `59af0e392d7bb9073a49603115e11150a8adbab59e0619c6a0608d19ffcbef63`.
- Zero market data files entered the Git repository working tree.

### 3.3 Upstream Schema Key Disparity Analysis
- Upstream `nse==4.0.1` returned a JSON payload with camelCase and lowercase field keys:
  - Timestamp: `'mtimestamp'` containing dates such as `'01-Jan-2024'`
  - Prices: `'chOpeningPrice'`, `'chTradeHighPrice'`, `'chTradeLowPrice'`, `'chClosingPrice'`
  - Volume & Value: `'chTotTradedQty'`, `'chTotTradedVal'`, `'chTotalTrades'`, `'vwap'`
  - Identifiers: `'chSymbol'`, `'chSeries'`
- The existing normalization logic in `phase7/sources/normalization.py` checked uppercase/title keys (`CH_TIMESTAMP`, `mTIMESTAMP`, `date`, `Date`, `trading_date`).
- Because `'mtimestamp'` was not recognized, `normalize_historical_row` raised `ValueError("Missing trading date in row payload")` for all 22 rows.

### 3.4 Safety Halting and Client Cleanup
- Conservation check verified: $\text{source} (22) = \text{normalized} (0) + \text{rejected} (22)$.
- Under the 5-stock protocol, partial rows trigger an immediate halt:
  - Manifest written with status `PARTIAL`.
  - Remaining securities (`TCS`, `HDFCBANK`, `INFY`, `ICICIBANK`) were safely never contacted.
  - Client session closed cleanly via `client.exit()` in `finally` block (`client_close_count = 1`).
  - Process returned exit code 6 (`PilotExitCode.SCHEMA_NORMALIZATION_ERROR`).
- In strict adherence to governance directives:
  - Source code was not modified during execution.
  - The defect is documented.
  - The marker was not recreated.
  - Live pilot outcome is recorded as `NSE_FIVE_STOCK_PILOT_HALTED_ON_SAFETY_CONTROL`.
