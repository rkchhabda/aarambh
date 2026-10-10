# Phase 7 Protocol: Governed 20-Stock Historical Batch Pilot Harness

## 1. Executive Summary & Objective

- **Milestone:** Milestone 4.10B (Build Governed 20-Stock Historical Batch Harness)
- **Status:** `NSE_20_STOCK_BATCH_HARNESS_READY_LIVE_EXECUTION_NOT_AUTHORIZED`
- **Future Execution Scope:** Milestone 4.10C (`TWENTY_STOCK_THREE_MONTH_NSE_BATCH_PILOT`)
- **Objective:** Establish, validate, and freeze an automated batch acquisition harness for 20 deterministically selected operational equities over Q1 2024 (2024-01-01 through 2024-03-31) at 1d interval, with fail-closed safety controls, per-symbol atomic checkpointing, and strict resume verification.
- **Classification:** `DETERMINISTIC_CURRENT_PANEL_OPERATIONAL_SAMPLE`
- **Live Execution Authorization:** **Strictly NOT authorized in Milestone 4.10B**

---

## 2. Governed Batch Contract Specifications

The batch harness binds the following immutable operational parameters:

| Parameter | Governed Value | Enforcement Rule |
|---|---|---|
| **Batch ID** | `BATCH_4_10C_HISTORICAL_20STOCK_2024Q1` | Unique batch identity |
| **Source Panel Version** | `CURRENT_NIFTY500_09Oct2026_8F4C439F` | Binds frozen Milestone 4.10A snapshot |
| **Source Snapshot Checksum** | `8f4c439f35fffc8ec87f107ebc9e03aef00ad26301d0912711d808ac592d117d` | Validates frozen snapshot integrity |
| **Selection Checksum** | `60dd03580442b1f874f364206da5d9bf252a4abf1ff93801d4b58e93fdee7b1d` | Cryptographic hash of ordered 20 symbols |
| **Ordered Symbols Hash** | `26e4be7c9cfd366b630b0b714f0afd65a223ffae91edad6e231060e6b95c4ee3` | Comma-separated sequence hash |
| **Symbol Count** | `20` | Strict equality; reject $\ne 20$ |
| **Start Date** | `2024-01-01` | Fixed Q1 2024 horizon |
| **End Date** | `2024-03-31` | Fixed Q1 2024 horizon |
| **Interval** | `1d` | Daily trading sessions only |
| **Maximum Concurrency** | `1` | Strictly sequential execution |
| **Minimum Request Spacing** | `2.0 seconds` | Upstream rate-limiting protection |
| **Maximum Retries** | `0` | Zero automated retries |
| **Failure Threshold** | `1 failed symbol` | Immediate halt on first failure |
| **Schema Mapping Version** | `NSE_4_0_1_HISTORICAL_CAMELCASE_V1` | Governed `nse==4.0.1` historical parser |
| **Staging Root Hash** | `b7442791cce0e5f448cbdfc0f39a10820f637383e8b349a95083142d08467ce8` | Binds external staging root |
| **Classification** | `DETERMINISTIC_CURRENT_PANEL_OPERATIONAL_SAMPLE` | Operational capability sample only |

---

## 3. Exit Code Contract

The batch orchestrator maps execution results to deterministic exit codes:

| Exit Code | Enumeration Constant | Condition |
|---|---|---|
| **0** | `SUCCESS` | All 20 symbols complete cleanly; batch acceptance passes |
| **2** | `ARGUMENT_ERROR` | Command-line argument, contract, or parameter validation error |
| **3** | `AUTHORIZATION_ERROR` | Missing, invalid, expired, or tampered authorization marker |
| **4** | `CLIENT_CONSTRUCTION_ERROR` | Upstream client factory or session bootstrap error |
| **5** | `RETRIEVAL_ERROR` | Upstream network failure, timeout, denial, or safety violation |
| **6** | `SCHEMA_NORMALIZATION_ERROR` | Missing trading date, invalid OHLC bounds, or normalization failure |
| **7** | `PERSISTENCE_MANIFEST_ERROR` | Persistence write failure, checksum error, or conservation breach |
| **8** | `INCOMPLETE_BATCH` | Execution terminated with $< 20$ completed symbols |
| **9** | `CLIENT_CLOSE_ERROR` | Upstream client cleanup failure during shutdown |
| **10** | `UNEXPECTED_INTERNAL_ERROR` | Unhandled runtime exception |
| **11** | `INVALID_RESUME_CHECKPOINT` | Corrupted, mismatched, or invalid resume checkpoint |
| **12** | `SOURCE_PANEL_OR_SELECTION_MISMATCH` | Selection evidence or panel version mismatch |

---

## 4. Expected Scale & Runtime Estimation

Without processing live market data, the harness parameters project:
- **Historical Requests:** 20 requests
- **Concurrency:** 1 (sequential)
- **Minimum Pacing Floor:** 20 requests $\times$ 2.0s = approximately 40 seconds
- **Additional Overhead:** Client construction, upstream network latency, SHA-256 computation, disk serialization (~15–30s)
- **Estimated Total Runtime:** Approximately 60 to 90 seconds
- **Expected Trading Days:** Approximately 60 to 65 sessions across Q1 2024
- **Expected Total Normalized Rows:** Approximately 1,200 to 1,300 rows

---

## 5. Safety & Blocker Boundaries

1. **BLK-01 (Absence of Point-in-Time Historical NIFTY 500 Constituent Membership):**
   - Remains **`STILL_BLOCKED`**.
   - The 20-stock operational sample is derived from a current snapshot (`CURRENT_SNAPSHOT_ONLY`). It is not point-in-time and does not provide historical index additions/deletions.
2. **BLK-02 (Missing OHLCV Prices and Daily Traded Value / Turnover):**
   - Remains **`PILOT_CAPABILITY_CONFIRMED_GATE1_NOT_PASSED`**.
   - Technical batch harness capability is confirmed offline; Gate 1 real-data evaluation across full panel is not passed.
3. **BLK-04 (Static Sector Classification Lacks Historical Reclassification Timestamps):**
   - Remains **`STILL_BLOCKED`**.
4. **Milestone 5 Quarantine:**
   - Strictly **BLOCKED**. Zero model training, zero baseline ranking, zero returns calculation.
