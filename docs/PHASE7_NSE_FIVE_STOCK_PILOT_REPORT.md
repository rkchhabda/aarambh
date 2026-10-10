# Phase 7 Report: Milestone 4.9 Five-Stock NSE Pilot Execution (Attempt 4 Post Pipeline Wiring)

## 1. Executive Summary

- **Milestone:** Milestone 4.9 (Re-Authorized Five-Stock NSE Live Pilot — Post Historical Retrieval Pipeline Wiring)
- **Status Date:** 2026-10-10
- **Final Milestone Status:** `NSE_FIVE_STOCK_PILOT_HALTED_ON_SAFETY_CONTROL`
- **Starting Commit:** `1dec29ba201421a768860ee439904daebb444c24`
- **Process Exit Code:** `6` (`PilotExitCode.SCHEMA_NORMALIZATION_ERROR`)
- **Client Initialization Count:** 1
- **Client Close Count:** 1 (`client.exit()` executed cleanly in `finally` block)
- **Session Bootstrap Status:** Confirmed (Upstream session bootstrap network activity confirmed by presence of external session-credential file `raw/nse_cookies_httpx.json`)
- **Historical Retrieval Request Count:** 1 (`RELIANCE`)
- **Historical Retrieval Response Count:** 1
- **Historical Source Rows Retrieved:** 22 (Genuine daily trading session rows for RELIANCE across 2024-01-01 to 2024-01-31)
- **Normalized Row Count:** 0
- **Rejected Row Count:** 22
- **Historical Symbols Completed:** 0 / 5
- **Market Data Files Inside Git Repository:** **0 (Zero)**
- **Prior Consumed Markers:**
  1. `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9\authorization\pilot_authorization.consumed.20261010T063226Z.json`
  2. `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9\authorization\pilot_authorization.consumed.20261010T065759Z.json`
  3. `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9\authorization\pilot_authorization.consumed.20261010T072920Z.json`
- **Attempt 4 Authorization Marker Creation Timestamp:** `2026-10-10T08:09:09.789039+00:00`
- **Attempt 4 Authorization Marker Consumption Timestamp:** `2026-10-10T08:10:13Z`
- **Attempt 4 Consumed Marker Path:** `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9\authorization\pilot_authorization.consumed.20261010T081013Z.json`
- **Attempt 4 Nonce:** `d683d69f-5226-4d32-ba89-3e75e399e228`
- **Attempt 4 Authorization Hash:** `860461fd7227519c6e724dada2baf4122390d5477aa08bd6dc20faac41628e38`
- **Raw Payload Persistence:** Staged outside Git to:
  `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9\raw\historical\RELIANCE_2024-01-01_2024-01-31_1d_20261010T081014Z_59af0e39.json`
- **Raw Checksum (SHA-256):** `59af0e392d7bb9073a49603115e11150a8adbab59e0619c6a0608d19ffcbef63`
- **Manifest Persistence:** Staged outside Git to:
  `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9\manifests\manifest_RELIANCE_986f7d47-95a2-47fe-a82f-e97b4c0d8c5f.json`
- **Manifest Status:** `PARTIAL`
- **Halting / Blocker Condition:** Upstream schema field naming mismatch. `nse==4.0.1` returned a JSON list of 22 trading day dictionaries with camelCase/lowercase keys (`mtimestamp`, `chOpeningPrice`, `chClosingPrice`, `chTradeHighPrice`, `chTradeLowPrice`, `chTotTradedQty`, `chTotTradedVal`, `chTotalTrades`, `vwap`, `chSeries`, `chSymbol`). The normalization module (`phase7/sources/normalization.py`) checked `CH_TIMESTAMP`, `mTIMESTAMP`, `date`, `Date`, but omitted lowercase `mtimestamp`. This triggered `ValueError("Missing trading date in row payload")` for all 22 rows.
- **Safety Invariant Enforcement:** Under the governed 5-stock protocol, `rej_count > 0` prohibits success and requires an immediate halt. The pilot logged `PILOT_HALT: Partial rows rejected under 5-stock protocol.`, marked the manifest as `PARTIAL`, safely halted without querying remaining symbols (`TCS`, `HDFCBANK`, `INFY`, `ICICIBANK`), closed the client cleanly, and returned exit code 6.

---

## 2. Pre-Flight Verification Audit

All mandatory pre-flight checks were executed and passed prior to marker creation:

| # | Check Item | Requirement | Measured State | Verdict |
| :---: | :--- | :--- | :--- | :--- | :---: |
| 1 | Repository Root | GaurviDEEP workspace root | `C:\Users\r_chh\OneDrive - optgbrc\Apps\GaurviDEEP` | **PASS** |
| 2 | Current Branch | `phase7-research` | `phase7-research` | **PASS** |
| 3 | Working Tree Status | 100% clean | Clean (0 modified, 0 untracked) | **PASS** |
| 4 | Staged Files | None | 0 staged files | **PASS** |
| 5 | HEAD SHA | `1dec29b` | `1dec29ba201421a768860ee439904daebb444c24` | **PASS** |
| 6 | Remote Tracking | Verified tracking | Tracking `origin/phase7-research` (ahead 8 unpushed commits) | **PASS** |
| 7 | Python Executable | `.venv-phase7\Scripts\python.exe` | Verified | **PASS** |
| 8 | Python Version | 3.12.10 | Python 3.12.10 | **PASS** |
| 9 | Installed `nse` Version | 4.0.1 | 4.0.1 | **PASS** |
| 10 | Installed `httpx` Version | 0.28.1 | 0.28.1 | **PASS** |
| 11 | Installed `h2` Version | 4.4.1 | 4.4.1 | **PASS** |
| 12 | Installed `hpack` Version | 4.2.0 | 4.2.0 | **PASS** |
| 13 | Installed `hyperframe` Version | 6.1.0 | 6.1.0 | **PASS** |
| 14 | `pip check` Result | Clean | No broken requirements found | **PASS** |
| 15 | Complete Test Baseline | 318 tests passing | 318 passed in 16.86s | **PASS** |
| 16 | External Staging Root | Dedicated directory | `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9` | **PASS** |
| 17 | Staging Location Check | Outside Git repository | Verified outside repository root | **PASS** |
| 18 | Repository Data Isolation | Zero repository writes | Confirmed zero writes to repo `data/` | **PASS** |
| 19 | Prior Consumed Markers | 3 existing consumed | Verified 3 consumed markers intact | **PASS** |
| 20 | Phase 6 Closure Tag | `phase6-closed-2026-10-04` | Intact | **PASS** |
| 21 | BLK-01 Status | Open | `STILL_BLOCKED` (Constituent history absent) | **PASS** |
| 22 | BLK-02 Status | Open | `STILL_BLOCKED` (Historical OHLCV unverified live)| **PASS** |
| 23 | BLK-04 Status | Open | `STILL_BLOCKED` (Sector classification absent) | **PASS** |
| 24 | Full NIFTY 500 Pull | Not authorized | Confirmed strictly unauthorized | **PASS** |

---

## 3. Authorization Marker Lifecycle

1. **Creation:**
   ```powershell
   .venv-phase7\Scripts\python.exe -m phase7.sources.authorization create `
       --staging-root "C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9" `
       --expires-minutes 30
   ```
   - **Issued Timestamp:** `2026-10-10T08:09:09.789039+00:00`
   - **Nonce:** `d683d69f-5226-4d32-ba89-3e75e399e228`
   - **Staging Root Hash:** `126f001a548b054bff73c218b02e781d42a0af7c647532b68718db8c73d61df3`
   - **Authorization Hash:** `860461fd7227519c6e724dada2baf4122390d5477aa08bd6dc20faac41628e38`
   - **Active Path:** `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9\authorization\pilot_authorization.json`

2. **Atomic Consumption:**
   During canonical invocation, `phase7.sources.pilot` validated the scope, dates, interval, staging root hash, and authorization hash. It then executed an atomic `os.replace` rename to:
   `pilot_authorization.consumed.20261010T081013Z.json`
   The active marker was verified removed before client creation.

---

## 4. Canonical Pilot Command Execution

In accordance with owner instructions:
```powershell
.venv-phase7\Scripts\python.exe -m phase7.sources.pilot `
    --symbols RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK `
    --start 2024-01-01 `
    --end 2024-01-31 `
    --interval 1d `
    --staging-root "C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9" `
    --authorization-file "C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9\authorization\pilot_authorization.json" `
    --execute-live
```

### Execution Output
```text
PILOT_HALT: Partial rows rejected under 5-stock protocol.
Executing authorized live pilot with single-use authorization...
Consumed Marker: C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9\authorization\pilot_authorization.consumed.20261010T081013Z.json
Client Initialized: NSE
FINAL OUTCOME: NSE_FIVE_STOCK_PILOT_HALTED_ON_SAFETY_CONTROL
Symbols Completed: 0/5
Client Initialized: 1
Client Closed: 1
Exit Code: 6
Pilot exit code: 6
```

---

## 5. Defect Analysis: Upstream Key Name Schema Disparity

1. **Defect Location:** [`phase7/sources/normalization.py`](file:///C:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/phase7/sources/normalization.py) lines 68–74:
   ```python
   # Extract date
   date_val = (
       raw_row.get("CH_TIMESTAMP")
       or raw_row.get("mTIMESTAMP")
       or raw_row.get("date")
       or raw_row.get("Date")
       or raw_row.get("trading_date")
   )
   ```
2. **Upstream Observed Shape:** `nse==4.0.1` method `fetch_equity_historical_data` returned 22 records for RELIANCE (trading days in Jan 2024) with the following exact field dictionary keys:
   ```python
   [
       'ch52WeekHighPrice',
       'ch52WeekLowPrice',
       'chClosingPrice',
       'chLastTradedPrice',
       'chOpeningPrice',
       'chPreviousClsPrice',
       'chSeries',
       'chSymbol',
       'chTotTradedQty',
       'chTotTradedVal',
       'chTotalTrades',
       'chTradeHighPrice',
       'chTradeLowPrice',
       'mtimestamp',
       'vwap'
   ]
   ```
3. **Disparity:** Upstream timestamp field is `'mtimestamp'` (all lowercase) containing date string like `'01-Jan-2024'`, whereas normalization specifically searched `'mTIMESTAMP'` (uppercase TIMESTAMP) or `'CH_TIMESTAMP'`. Furthermore, prices and volumes use `'chOpeningPrice'`, `'chClosingPrice'`, `'chTradeHighPrice'`, `'chTradeLowPrice'`, `'chTotTradedQty'`, `'chTotTradedVal'`, `'vwap'`, and `'chSeries'`.
4. **Governing Rule Applied:**
   > *"Do not modify source code during this execution. If another defect is found: Document it. Do not repair it during this execution. Stop when it affects safety or validity."*
5. **Action Taken:** Execution terminated on safety halt; marker remains consumed; raw payload was safely saved to external staging (`raw/historical/RELIANCE_...json`); zero market data was committed or staged in Git.

---

## 6. Permitted Execution Metrics

- **Requested Symbol Count:** 5 (`RELIANCE`, `TCS`, `HDFCBANK`, `INFY`, `ICICIBANK`)
- **Completed Symbol Count:** 0
- **client_initialization_count:** 1
- **client_close_count:** 1
- **session_bootstrap_network_event_count:** Confirmed (`raw/nse_cookies_httpx.json`)
- **historical_retrieval_request_count:** 1 (`RELIANCE`)
- **historical_retrieval_response_count:** 1
- **historical_symbols_completed:** 0
- **historical_source_row_count:** 22
- **Failed / Stopped Symbol:** `RELIANCE` (Symbol 1)
- **First Stop Condition:** `SCHEMA_MISMATCH` / `PARTIAL_ROWS_REJECTED` (`ValueError: Missing trading date in row payload` due to `'mtimestamp'` key casing)
- **Factory Invocation Parameters:**
  - `download_folder`: `Path("C:\\Users\\r_chh\\gaurvideep_phase7_staging\\nse500\\pilot_4_9\\raw")`
  - `server`: `True`
  - `timeout`: `15`
- **Source Row Count:** 22
- **Normalized Row Count:** 0
- **Rejected Row Count:** 22
- **Expected Date Coverage:** 0.0%
- **Duplicate Count:** 0
- **Invalid OHLC Count:** 0
- **Negative Value Count:** 0
- **Missing Field Counts:** 22 (missing trading date in normalization mapping)
- **Unexpected Source Field Counts:** 0
- **Raw Checksum Count:** 1 (`59af0e392d7bb9073a49603115e11150a8adbab59e0619c6a0608d19ffcbef63`)
- **Normalized Checksum Count:** 0
- **ConnectionError Count:** 0
- **TimeoutError Count:** 0
- **Access Denied / CAPTCHA Count:** 0
- **Safety Stop Count:** 1 (`PILOT_HALT: Partial rows rejected under 5-stock protocol.`)
- **Process Exit Code:** 6 (`PilotExitCode.SCHEMA_NORMALIZATION_ERROR`)
- **Final Outcome:** `NSE_FIVE_STOCK_PILOT_HALTED_ON_SAFETY_CONTROL`

---

## 7. Corrective Recommendation

1. Authorize Milestone 4.9E code correction checkpoint to align `phase7/sources/normalization.py` field extraction logic with observed upstream `nse==4.0.1` historical payload schema:
   - Date: map `mtimestamp` (format `%d-%b-%Y`, e.g., `'01-Jan-2024'`).
   - Open: map `chOpeningPrice`.
   - High: map `chTradeHighPrice`.
   - Low: map `chTradeLowPrice`.
   - Close: map `chClosingPrice`.
   - Volume: map `chTotTradedQty`.
   - Turnover: map `chTotTradedVal`.
   - Trades: map `chTotalTrades`.
   - VWAP: map `vwap`.
   - Series: map `chSeries`.
   - Symbol: map `chSymbol`.
2. Add deterministic test fixtures with exact `nse==4.0.1` observed payload shape in `tests/phase7/test_source_eod_normalization.py`.
3. Request explicit owner re-authorization (`RE-AUTHORIZE MILESTONE 4.9 AFTER NORMALIZATION SCHEMA FIX`) to create a fresh marker and execute the live pilot.

---

## 8. Milestone 4.9E Offline Replay Verification

In Milestone 4.9E, explicit source-field mappings and locale-independent date parsing for `NSE_4_0_1_HISTORICAL_CAMELCASE_V1` were implemented and verified through an offline replay of the preserved RELIANCE payload without network requests.

### 8.1 Replay Execution Metrics
- **Replay Status:** `OFFLINE_NORMALIZATION_REPLAY`
- **Source File:** `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9\raw\historical\RELIANCE_2024-01-01_2024-01-31_1d_20261010T081014Z_59af0e39.json`
- **Source SHA-256:** `59af0e392d7bb9073a49603115e11150a8adbab59e0619c6a0608d19ffcbef63`
- **Source Rows:** 22
- **Normalized Rows:** 22
- **Rejected Rows:** 0
- **Conservation Status:** `CONSERVED` ($22 = 22 + 0$)
- **Date Coverage:** 100.0% (22 of 22 trading sessions in Jan 2024)
- **Duplicate Natural Keys:** 0
- **Invalid OHLC Rows:** 0
- **Negative Value Rows:** 0
- **Missing Required Fields:** 0
- **Missing Optional Fields:** `isin` (22), `deliverable_quantity` (22), `delivery_percentage` (22) (all explicitly `NOT_PROVIDED` or `None`)
- **Normalized Checksum:** `be10e3ca0fc0298c751457aaa822b05c1254839634b7958f6e16aab9e1759a0b`
- **Replay Output Directory:** `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9\offline_replay_4_9e\`
- **Original Evidence Integrity:** Preserved unchanged; original raw file hash intact; live `manifest_RELIANCE_*.json` preserved with `status: PARTIAL`.
