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

---

## 4. Milestone 4.9E Normalization Alignment & Replay Audit

1. **Versioned Mapping Introduced:** `NSE_4_0_1_HISTORICAL_CAMELCASE_V1` implemented in `phase7/sources/schema_mappings.py`.
2. **Deterministic Locale-Independent Date Parser:** Validates `%d-%b-%Y` via explicit English month dictionary without depending on platform locale.
3. **Numeric Bounds & NaN/Inf Rejection:** Mandatory fields strictly reject NaN, Infinity, negative prices, and negative quantities.
4. **Offline Replay Compliance:**
   - 22 source rows $\rightarrow$ 22 normalized rows $\rightarrow$ 0 rejected rows.
   - Conservation holds: $22 = 22 + 0$.
   - SHA-256 raw checksum verified: `59af0e392d7bb9073a49603115e11150a8adbab59e0619c6a0608d19ffcbef63`.
   - SHA-256 normalized checksum generated: `be10e3ca0fc0298c751457aaa822b05c1254839634b7958f6e16aab9e1759a0b`.
   - Zero duplicate keys, zero invalid OHLC bounds, zero negative values.
   - Preserved in `<staging>/offline_replay_4_9e/` without modifying live pilot evidence.

---

## 5. Milestone 4.9 Final Live Pilot Execution & Structural Audit (Attempt 5)

### 5.1 Structural Acceptance Criteria Compliance Matrix (Attempt 5 Live Execution)

| # | Acceptance Criterion | Required Threshold | Observed State | Compliance Status |
| :---: | :--- | :--- | :--- | :--- | :---: |
| 1 | Securities returning $\ge 1$ valid record | Exactly 5/5 | 5/5 (`RELIANCE`, `TCS`, `HDFCBANK`, `INFY`, `ICICIBANK`) | **PASS** |
| 2 | Date session coverage | $\ge 95\%$ | 100.0% (22/22 trading sessions across all 5 symbols) | **PASS** |
| 3 | Dates within 2024-01-01..2024-01-31 | 100% | 110/110 records within January 2024 | **PASS** |
| 4 | Duplicate natural keys | Exactly 0 | 0 duplicates across all 5 symbols | **PASS** |
| 5 | Invalid OHLC relationships | Exactly 0 | 0 invalid bounds (low $\le$ open/close $\le$ high) | **PASS** |
| 6 | Negative prices | Exactly 0 | 0 negative prices | **PASS** |
| 7 | Negative volume | Exactly 0 | 0 negative volume | **PASS** |
| 8 | Empty responses accepted as success | Exactly 0 | 0 accepted | **PASS** |
| 9 | HTML responses accepted as data | Exactly 0 | 0 accepted | **PASS** |
| 10 | CAPTCHA responses accepted as data | Exactly 0 | 0 accepted | **PASS** |
| 11 | ConnectionError events | 0 (or halts pilot) | 0 encountered | **PASS** |
| 12 | TimeoutError events | 0 (or halts pilot) | 0 encountered | **PASS** |
| 13 | Access-denied events | 0 (or halts pilot) | 0 encountered | **PASS** |
| 14 | Raw checksum coverage | 100% | 5/5 retrieved raw payloads hashed (100%) | **PASS** |
| 15 | Normalized checksum coverage | 100% | 5/5 normalized JSONL files hashed (100%) | **PASS** |
| 16 | Reason codes for all rejected rows | 100% | 0 rows rejected; conservation holds $110 = 110 + 0$ | **PASS** |
| 17 | Repository market-data path changes | Exactly 0 | 0 files written to repository | **PASS** |
| 18 | Downloaded files staged in Git | Exactly 0 | 0 files staged in Git | **PASS** |
| 19 | Target datasets generated | Exactly 0 | 0 targets generated | **PASS** |
| 20 | Models trained or fit | Exactly 0 | 0 models trained | **PASS** |
| 21 | Performance metrics calculated | Exactly 0 | 0 metrics calculated | **PASS** |

### 5.2 Cryptographic Evidence & Conservation Invariants
- **Source Row Count:** 110
- **Normalized Row Count:** 110
- **Rejected Row Count:** 0
- **Conservation Formula:** $\text{source\_row\_count} (110) = \text{normalized\_row\_count} (110) + \text{rejected\_row\_count} (0)$ (**100% Conserved**)
- **Verified SHA-256 Checksums:**
  - `RELIANCE`: Raw `59af0e392d7bb9073a49603115e11150a8adbab59e0619c6a0608d19ffcbef63` / Norm `5ec58018253227a893fd2c551dc5581408314a74748867f970c8a8004abd4e4b`
  - `TCS`: Raw `353beb31b7ed737a952621fb6e5c8f09eaa812fa0d793575b64ea07e8b9d61eb` / Norm `60c56dfd6684c413e9ad32a1bf6873d5c41d08660712f91419ad46ebebbbdd17`
  - `HDFCBANK`: Raw `234c028f393978854d9253c549be921b25a3b95aaa85e7fa4656ae149a3d5aea` / Norm `090ff2af9794f86b978f7e9e5af9fd2ea4c5fd04f6753caf9bad1fcd2f017215`
  - `INFY`: Raw `0a6611aa8ad70b69b6d2d08a2741385722181b7c5ce6b1e02f0f03d87f0d29c4` / Norm `5dd6031f1ecef8235b169523d6bc9c9328d76c526d79d06184e069275646e58b`
  - `ICICIBANK`: Raw `22838751d58eca9a89d421717b6dbdd1fe25942c3372ad9cc4dab23abb833ebe` / Norm `40992f803628250cb1cf41522c3717822cdc7df3ec5fc3c62dd9433c87910a49`
- **Request Manifests:** All 5 manifests finalized with status `SUCCEEDED`.
- **Single-Use Authorization:** Fifth marker atomically consumed to `pilot_authorization.consumed.20261010T084213Z.json`; active marker absent; all 5 consumed markers preserved outside Git.

### 5.3 Governed Dataset Classification & Strict Negative Declarations
- **Exact Classification:** `FIVE_STOCK_LIVE_CAPABILITY_SAMPLE_NOT_RESEARCH_DATASET`
- **Strict Constraints:**
  - NOT survivorship-free
  - NOT point-in-time NIFTY 500
  - NOT Gate 1 passed
  - NOT production-ready
  - NOT validated alpha
  - NOT suitable for model training
  - NOT evidence of investment performance

### 5.4 Blocker Status Post-Pilot
- **BLK-01:** `STILL_BLOCKED`
- **BLK-02:** `PILOT_CAPABILITY_CONFIRMED_GATE1_NOT_PASSED`
- **BLK-04:** `STILL_BLOCKED`
- **Milestone 4.9 Closure Status:** `NSE_FIVE_STOCK_PILOT_CLOSED_SUCCESSFULLY`
