# Phase 7 — Milestone 4.7: NSE 500 Connector Structural Audit

**Repository:** GaurviDEEP
**Working Branch:** `phase7-research`
**Governing Milestone:** Milestone 4.7 (Existing Connector NIFTY 500 Data Acquisition & Safety Audit)
**Execution Timestamp:** 2026-10-10T06:05:00 UTC

---

## 1. Candidate Connector Structural Inventory

This audit evaluates all candidate data connectors currently present in the GaurviDEEP codebase across architecture, environment compatibility, parameter contracts, and failure semantics.

### 1.1 Connector Architecture Matrix

| Connector Module | Internal Location | Primary Upstream Source | Transport Engine | Runtime Target | Status in `.venv-phase7` |
|---|---|---|---|---|---|
| **Live / EOD Provider** | [features/data_provider.py](file:///C:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/features/data_provider.py) | NSE Direct (`nse.NSE`), Yahoo Finance REST, Stooq | `requests`, `httpx` (via `nse`), `urllib` | Service serving layer (`service/app.py`) | **BROKEN:** Missing `requests` and `nse` packages |
| **CA Harvester** | [scripts/phase6/harvest_corporate_actions.py](file:///C:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/scripts/phase6/harvest_corporate_actions.py) | `api/corporates-corporateActions` | `requests.Session` | Phase 6 offline pipeline | **BROKEN:** Missing `requests` package; Phase 6 boundary |
| **XBRL Harvester** | [scripts/phase6/harvest_nse_metadata.py](file:///C:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/scripts/phase6/harvest_nse_metadata.py) | `api/corporates-financial-results` | `requests.Session` | Phase 6 offline pipeline | **BROKEN:** Missing `requests` package; Phase 6 boundary |
| **10Y Backfill** | [scripts/verification/backfill_covid_history.py](file:///C:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/scripts/verification/backfill_covid_history.py) | Yahoo Finance Chart API | Standard `urllib.request` | Verification scripts | **NON-NSE:** Yahoo Finance only; lacks volume & turnover |

---

## 2. Field-by-Field Contract Schema Mapping

The table below maps fields provided by the candidate connectors against the immutable Phase 7 canonical contracts defined in [phase7/data/contracts.py](file:///C:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/phase7/data/contracts.py).

### 2.1 Daily Equity Price & Turnover ([DailyPriceRecord](file:///C:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/phase7/data/contracts.py))

| Phase 7 Contract Field | Type Required | Supplied by `_fetch_nse_historical` | Supplied by `backfill_covid_history` | Field Status | Remarks / Gaps |
|---|---|---|---|---|---|
| `trading_date` | `datetime.date` | Yes (`mTimestamp`) | Yes (`Date`) | **SOURCE_REPORTED** | Clean date parsing |
| `symbol` | `str` | Yes (`clean_sym`) | Yes (`ticker`) | **SOURCE_REPORTED** | Uppercase symbol |
| `isin` | `str` | **No** (`None`) | **No** (`None`) | **MISSING** | Connector does not capture ISIN |
| `open` | `Decimal` | Yes (`chOpeningPrice`) | **No** (`None`) | **SOURCE_REPORTED** | Absent in backfill script |
| `high` | `Decimal` | Yes (`chTradeHighPrice`) | **No** (`None`) | **SOURCE_REPORTED** | Absent in backfill script |
| `low` | `Decimal` | Yes (`chTradeLowPrice`) | **No** (`None`) | **SOURCE_REPORTED** | Absent in backfill script |
| `close` | `Decimal` | Yes (`chClosingPrice`) | Yes (`Close`) | **SOURCE_REPORTED** | Nominal Close |
| `volume` | `int` | Yes (`chTotTradedQty`) | **No** (`None`) | **SOURCE_REPORTED** | Absent in backfill script |
| `traded_value_inr` | `Decimal` | **No** (`None`) | **No** (`None`) | **MISSING** | Traded turnover in INR omitted |
| `traded_value_status` | `TradedValueStatus` | **No** | **No** | **MISSING** | Cannot claim `EXCHANGE_REPORTED` |
| `price_adjustment_state` | `PriceAdjustmentState` | `RAW` | `SPLIT_ADJUSTED` | **UNVERIFIED** | Adjustment method unverified |
| `vwap` | `Optional[Decimal]` | **No** (`None`) | **No** (`None`) | **NOT_PROVIDED** | Omitted |
| `number_of_trades` | `Optional[int]` | **No** (`None`) | **No** (`None`) | **NOT_PROVIDED** | Omitted |
| `deliverable_quantity` | `Optional[int]` | **No** (`None`) | **No** (`None`) | **NOT_PROVIDED** | Requires separate delivery Bhavcopy |
| `delivery_percentage` | `Optional[Decimal]` | **No** (`None`) | **No** (`None`) | **NOT_PROVIDED** | Requires separate delivery Bhavcopy |
| `source_timestamp` | `datetime` (UTC) | **No** (Date only) | **No** (Date only) | **MISSING** | Intra-day exchange broadcast timestamp absent |
| `row_hash` | `str` (SHA-256) | **No** | **No** | **MISSING** | No deterministic hashing in connector |

### 2.2 Corporate Action ([CorporateActionRecord](file:///C:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/phase7/data/contracts.py))

| Phase 7 Contract Field | Type Required | Supplied by `harvest_corporate_actions.py` | Field Status | Remarks / Gaps |
|---|---|---|---|---|
| `symbol` | `str` | Yes (`symbol`) | **SOURCE_REPORTED** | Clean ticker |
| `isin` | `str` | Yes (`isin`) | **SOURCE_REPORTED** | 12-char ISIN provided |
| `action_type` | `CorporateActionType` | **Partial** (`subject` text) | **DERIVED** | Text string requires regex parser |
| `announcement_timestamp` | `datetime` (UTC) | **No** (`caBroadcastDate` is null) | **MISSING** | Lookahead vulnerability |
| `ex_date` | `date` | Yes (`exDate`) | **SOURCE_REPORTED** | DD-Mon-YYYY parsed |
| `record_date` | `Optional[date]` | Yes (`recDate`) | **SOURCE_REPORTED** | DD-Mon-YYYY parsed |
| `effective_date` | `date` | **No** | **MISSING** | Inferred from ex-date |
| `ratio_numerator` | `Optional[Decimal]` | **No** | **DERIVED** | Requires text regex extraction |
| `ratio_denominator` | `Optional[Decimal]` | **No** | **DERIVED** | Requires text regex extraction |
| `cash_amount` | `Optional[Decimal]` | **No** | **DERIVED** | Requires text regex extraction |
| `source_timestamp` | `datetime` (UTC) | **No** | **MISSING** | Absent |
| `row_hash` | `str` (SHA-256) | **No** | **MISSING** | Absent |

### 2.3 Point-in-Time Index Membership ([PITMembershipRecord](file:///C:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/phase7/data/contracts.py))

| Phase 7 Contract Field | Type Required | Supplied by Any Existing Connector | Field Status | Remarks / Gaps |
|---|---|---|---|---|
| `index_code` | `str` | **None** | **MISSING** | No constituent connector exists |
| `symbol` | `str` | **None** | **MISSING** | Only static list exists |
| `isin` | `str` | **None** | **MISSING** | Absent |
| `membership_action` | `MembershipAction` | **None** | **MISSING** | Addition / removal events absent |
| `effective_from` | `date` | **None** | **MISSING** | Absent |
| `effective_to` | `Optional[date]` | **None** | **MISSING** | Absent |
| `source_timestamp` | `datetime` (UTC) | **None** | **MISSING** | Circular broadcast date absent |

---

## 3. Connector Safety Rule Audit (Phase B)

Detailed analysis of the 17 non-negotiable connector safety invariants:

```
[SAFETY RULE 1] Request timeout configured:
  - features/data_provider.py: Partial (Yahoo 8s, scanner 1.8s, nse direct UNCONFIGURED).
  - scripts/phase6/harvest_corporate_actions.py: Pass (timeout=15s).

[SAFETY RULE 2] Maximum retries <= 2:
  - harvest_corporate_actions.py: FAIL (retries=3).
  - harvest_nse_metadata.py: FAIL (retries=3).

[SAFETY RULE 3] Exponential backoff:
  - All existing connectors: FAIL (constant sleep or 0 sleep; zero backoff).

[SAFETY RULE 4] Maximum concurrency = 1:
  - fast_download_xbrl.py: FAIL (max_workers=24).
  - features/data_provider.py: Pass (single-threaded).

[SAFETY RULE 5] Delay between requests >= 2.0s:
  - harvest_corporate_actions.py: FAIL (time.sleep(1.0)).
  - harvest_nse_metadata.py: FAIL (time.sleep(1.0)).
  - features/data_provider.py: FAIL (0.0s delay in sequential loops).

[SAFETY RULES 6-9] Fail-closed on 401, 403, 429, CAPTCHA:
  - features/data_provider.py: FAIL (catches generic Exception, falls back silently).
  - harvest_corporate_actions.py: FAIL (retries on error, does not abort process).

[SAFETY RULES 10-11] Reject empty / HTML error responses:
  - features/data_provider.py: FAIL (reads raw resp.text into pd.read_csv without content-type check).

[SAFETY RULE 12] Response schema validated:
  - All connectors: FAIL (zero Pydantic / dataclass contract validation).

[SAFETY RULES 14-15] Checksums and rejected ledgers:
  - All connectors: FAIL (zero SHA-256 checksums; zero rejected ledger logging).

[SAFETY RULE 16] Raw files immutable:
  - All connectors: FAIL (overwrites files in place).

[SAFETY RULE 17] No secrets logged:
  - Pass (zero secrets present).
```

---

## 4. Root Cause of Pilot Failure

The pilot execution failed because of three insurmountable structural barriers:

1. **Environmental Quarantine Boundary:** The Phase 7 research virtual environment (`.venv-phase7`) strictly excludes web-scraping libraries (`requests`, `nse`, `httpx`). Because Rule 12 forbids package installation and Rule 11 forbids modifying `requirements-phase7.txt`, existing connectors cannot execute inside `.venv-phase7`.
2. **Hardcoded Trailing Date Window:** `_fetch_nse_historical()` was authored exclusively for live serving. It computes `end_d = date.today()` and subtracts `days=365`. It has no parameters accepting explicit historical date ranges (such as `2024-01-01` to `2024-01-31`).
3. **Absence of NIFTY 500 Constituent Engine:** While the third-party `nse` library has an uncalled method `listEquityStocksByIndex`, no GaurviDEEP module invokes it, stores its output, or translates it into Phase 7 contracts.

**Verdict:** In accordance with the governing instructions, existing connector code was **not modified**, no scraping was executed outside governance, and the milestone safely terminated with **`NSE_CONNECTOR_PILOT_FAILED`**.

---

## 5. Milestone 4.8 Authoritative NSEDataFetcher Audit & Remediation

Following the owner's provision of the authoritative `NSEDataFetcher` (`connector_review/nse_data_service.py`):
1. **Source Inspection:** Confirmed `NSEDataFetcher.get_historical_data(symbol, start_date, end_date, interval="1d")` supports explicit calendar boundaries.
2. **Phase 7 Fail-Closed Adapter:** Implemented `NSEDataFetcherAdapter` in `phase7/sources/nse_data_fetcher_adapter.py`.
3. **Safety Status:** Marked `UNSAFE_FOR_LIVE_PILOT` due to upstream error encapsulation in `nse==4.0.1`.
4. **Mocked Unit Test Verification:** All 40 adapter tests pass 100% offline with zero network calls.
5. **Pilot Status:** Dedicated CLI `phase7.sources.pilot` prepared for Milestone 4.9. Live calls not executed in Milestone 4.8. Status: `NSE_DATA_FETCHER_ADAPTED_LIVE_PILOT_NOT_AUTHORIZED`.
