# Phase 7 — Milestone 4.7: Existing Connector NIFTY 500 Data Pull Report

**Repository:** GaurviDEEP
**Working Branch:** `phase7-research`
**Governing Milestone:** Milestone 4.7 (Existing Connector NIFTY 500 Data Acquisition & Safety Audit)
**Execution Timestamp:** 2026-10-10T06:05:00 UTC
**Required Final Status:** `NSE_CONNECTOR_PILOT_FAILED`

---

> [!IMPORTANT]
> **Strict Governance Mandate:** In compliance with Milestone 4.7 instructions, data acquisition was authorized strictly via existing application connectors. The tightly controlled five-security pilot was evaluated against the 15 mandatory Pilot Acceptance Criteria and Phase B Connector Safety Rules. **Because the existing connectors failed runtime import in `.venv-phase7`, lacked NIFTY 500 constituent retrieval implementation, and violated multiple Phase B safety rules, the pilot failed and full dataset pulling was halted.** Milestone 5 remains strictly blocked.

---

## 1. Executive Summary

Milestone 4.7 authorized the discovery, verification, and pilot execution of GaurviDEEP's existing data connectors to retrieve the NIFTY 500 dataset from NSE-compatible sources.

### Key Audit Findings:
1. **Missing NIFTY 500 Retrieval Implementation:** GaurviDEEP possesses **zero** internal functions or classes for retrieving NIFTY 500 constituent lists. The application relies exclusively on a hardcoded, static 138-stock list ([features/universe.py](file:///C:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/features/universe.py)), which is strictly prohibited from being substituted for historical or current NIFTY 500 membership (Rule 21).
2. **Environment & Runtime Incompatibility:** The existing connector ([features/data_provider.py](file:///C:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/features/data_provider.py)) relies on `requests` and the external `nse` package (v4.0.1). Neither package is installed in the mandatory research virtual environment (`.venv-phase7\Scripts\python.exe`, Python 3.12.10). Attempting import raises `ModuleNotFoundError: No module named 'requests'`. Modifying `requirements-phase7.txt` or installing packages is strictly prohibited (Rules 11, 12, 13).
3. **Phase B Safety Violations:** The existing connectors violate multiple non-negotiable safety rules:
   - Exceeds retry threshold (harvesting uses 3 retries vs. maximum 2 permitted).
   - Insufficient request delay (`time.sleep(1.0)` vs. mandatory $\ge 2.0$s).
   - Zero exponential backoff.
   - Catches generic `Exception` and silently fails over to third-party unadjusted providers instead of immediately failing closed on HTTP 401, 403, 429, or CAPTCHA blocks.
   - Zero SHA-256 checksum generation or rejected-record ledger tracking.
4. **Historical Depth Limitation:** The internal `_fetch_nse_historical()` function hardcodes `end_d = date.today()` and trailing `days=365`. It cannot retrieve the requested pilot window (`2024-01-01` to `2024-01-31`) nor the full research window (`2014-01-01` to `2025-09-16`).
5. **Verdict:** Pilot failed on preconditions, runtime safety, and data availability. **Full pull halted. Final Status: `NSE_CONNECTOR_PILOT_FAILED`.**

---

## 2. Pre-Flight Verification Audit Matrix (Items 1–16)

| # | Verification Dimension | Mandated Value | Actual State | Conformance |
|---|---|---|---|---|
| **1** | Repository Root | `C:\Users\r_chh\OneDrive - optgbrc\Apps\GaurviDEEP` | `C:\Users\r_chh\OneDrive - optgbrc\Apps\GaurviDEEP` | **PASS** |
| **2** | Current Branch | `phase7-research` | `phase7-research` | **PASS** |
| **3** | Working-Tree Status | Clean | `nothing to commit, working tree clean` | **PASS** |
| **4** | Current HEAD | `8e946d6` | `8e946d6ff872756f7728eab8e66f131e9808376c` (`8e946d6`) | **PASS** |
| **5** | Remote Tracking State | `origin/phase7-research` | Ahead by 1 commit (`8e946d6`) | **PASS** |
| **6** | Python Executable | `.venv-phase7\Scripts\python.exe` | [python.exe](file:///C:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/.venv-phase7/Scripts/python.exe) | **PASS** |
| **7** | Python Version | `Python 3.12.10` | `Python 3.12.10` | **PASS** |
| **8** | Phase 6 Closure Tag | `phase6-closed-2026-10-04` present | Present (`phase6-closed-2026-10-04`) | **PASS** |
| **9** | External Staging Directory | `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\` | Present with `raw`, `normalized`, `audit`, `manifests`, `rejected` | **PASS** |
| **10** | Existing Connectors Discovered | Cataloged | 4 candidate modules inspected | **PASS** |
| **11** | NIFTY 500 Constituent Connector | Cataloged | **DEFECT:** 0 application functions exist; static 138-ticker list only | **FAIL** |
| **12** | EOD Historical Data Connector | Cataloged | `features/data_provider.py` (caps at 365d; fails in `.venv-phase7`) | **DEFECT** |
| **13** | Corporate Action Connector | Cataloged | `scripts/phase6/harvest_corporate_actions.py` (fails in `.venv-phase7`) | **DEFECT** |
| **14** | Cache & Retry Implementation | Cataloged | In-memory 300s TTL; 3 retries (violates $\le 2$ rule) | **DEFECT** |
| **15** | Environment Variables | Cataloged | Zero auth env vars required; public endpoints only | **PASS** |
| **16** | Credential Requirements | None | Confirmed: no credentials required or configured | **PASS** |

---

## 3. Discovery Findings (Phase A)

| Connector Module | Authority Function | Target Data | Supported Universe | Date Range Capability | Runtime Compatibility |
|---|---|---|---|---|---|
| [features/data_provider.py](file:///C:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/features/data_provider.py) | `_fetch_nse_historical` | Trailing OHLCV | Single active ticker | Trailing 365 days only | **FAILED:** Missing `requests` & `nse` in `.venv-phase7` |
| [features/data_provider.py](file:///C:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/features/data_provider.py) | `fetch_index_quotes` | Live Indices | NIFTY 50, SENSEX | Current intraday snapshot | **FAILED:** Missing `requests` & `nse` in `.venv-phase7` |
| [scripts/phase6/harvest_corporate_actions.py](file:///C:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/scripts/phase6/harvest_corporate_actions.py) | `harvest_ca_ticker` | Corporate actions | 138 static tickers | Lifetime history | **FAILED:** Missing `requests` in `.venv-phase7`; Phase 6 boundary |
| [scripts/phase6/harvest_nse_metadata.py](file:///C:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/scripts/phase6/harvest_nse_metadata.py) | `harvest_ticker_metadata` | Filing metadata | 138 static tickers | 2018–2025 (XBRL) | **FAILED:** Missing `requests` in `.venv-phase7`; Phase 6 boundary |

**Crucial Finding:** There is **no developed application code in GaurviDEEP** that calls `listEquityStocksByIndex("NIFTY 500")` or retrieves NIFTY 500 constituents.

---

## 4. Phase B: Connector Safety Review & Defect Log

| Safety Rule | Rule Requirement | Existing Connector Reality | Defect Classification |
|---|---|---|---|
| **Rule 1** | Request timeout configured | `features/data_provider.py` lacks timeout in `_fetch_nse_historical` | `DEFECT_TIMEOUT_UNCONFIGURED` |
| **Rule 2** | Max retries $\le 2$ | `harvest_corporate_actions.py` uses `retries = 3` | `DEFECT_EXCESSIVE_RETRIES` |
| **Rule 3** | Exponential backoff | Uses constant `time.sleep(2)` or none | `DEFECT_NO_EXPONENTIAL_BACKOFF` |
| **Rule 4** | Concurrency $= 1$ | `fast_download_xbrl.py` uses `max_workers = 24` | `DEFECT_HIGH_CONCURRENCY` |
| **Rule 5** | Inter-request delay $\ge 2.0$s | Uses `time.sleep(1.0)` or 0 | `DEFECT_INSUFFICIENT_THROTTLE` |
| **Rule 6–9** | Fail-closed on 401, 403, 429, CAPTCHA | Catches generic `Exception`, falls back silently to Yahoo | `DEFECT_SILENT_FAILOVER_LEAKAGE` |
| **Rule 10–11** | Reject empty / HTML error responses | Tier 2 Stooq parses raw text directly | `DEFECT_UNVALIDATED_PAYLOAD` |
| **Rule 12** | Response schema validation | No validation against Phase 7 dataclass contracts | `DEFECT_SCHEMA_UNVALIDATED` |
| **Rule 14–15** | Checksum manifests & rejected ledger | Zero checksum generation; zero rejected ledger | `DEFECT_AUDIT_TRAIL_ABSENT` |
| **Rule 16** | Immutable raw files | In-place overwriting of JSON files | `DEFECT_MUTABLE_RAW_FILES` |

Per Phase B governing instructions:
> *"If the existing connector violates any of these safety rules: Do not alter it in this milestone. Record the defect. Stop before full download. Propose a separate connector-safety patch."*

---

## 5. Five-Security Pilot Execution & Outcome (Phase D)

### Pilot Specifications:
- **Securities:** `RELIANCE`, `TCS`, `HDFCBANK`, `INFY`, `ICICIBANK`.
- **Target Period:** `2024-01-01` through `2024-01-31`.
- **Runtime:** `.venv-phase7\Scripts\python.exe`.

### Pilot Evaluation Results:
1. **Constituent Sourcing (Phase C):** **FAILED.** No connector exists in the application to query current NIFTY 500 constituents. Using the static 138-stock list is prohibited.
2. **Runtime Execution:** **FAILED.** `import features.data_provider` terminates with `ModuleNotFoundError: No module named 'requests'`.
3. **Date Filtering:** **FAILED.** `_fetch_nse_historical()` does not accept user-specified historical windows; it hardcodes `end_d = date.today()` and trailing 365 days.
4. **Field Availability:** **FAILED.** Existing connector omits VWAP, total traded value turnover, and delivery statistics.
5. **Criteria Compliance:** 0 of 5 securities successfully retrieved. 0 expected trading sessions populated.

**Pilot Outcome:** **PILOT FAILED.**
In accordance with Pilot Acceptance Criteria: Full pull (Phase E) was **NOT initiated**.

---

## 6. Checkpoint Classification & Governance State

- **Current Constituent List:** `NOT_RETRIEVED_CONNECTOR_ABSENT`
- **Historical Prices for Current Panel:** `CURRENT_PANEL_HISTORICAL_PRICES_SURVIVORSHIP_BIASED`
- **Historical Membership (BLK-01):** `STILL_BLOCKED`
- **Historical Daily Market Data (BLK-02):** `STILL_BLOCKED`
- **Historical Sector Classification (BLK-04):** `STILL_BLOCKED`
- **Milestone 5 Status:** **STRICTLY BLOCKED.**

**Final Milestone Status:** **`NSE_CONNECTOR_PILOT_FAILED`**
