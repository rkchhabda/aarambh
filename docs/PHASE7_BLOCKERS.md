# Phase 7 — Research Blockers & Dependency Registry

**Repository:** GaurviDEEP
**Working Branch:** `phase7-research`
**Governing Standard:** Non-Negotiable Safety and Governance Rules (Rule 18: *"If a real-data dependency is missing, implement only its interface, schema, validator, test fixture, and documentation. Mark the capability BLOCKED. Never substitute invented data."*)
**Status Date:** 2026-10-05

---

## 1. Blocker Summary Matrix

| Blocker ID | Severity | Description | Modules Affected | Current Status | Safe Interim Work |
|---|---|---|---|---|---|
| **BLK-01** | `CRITICAL` | Absence of Point-in-Time Historical Nifty 500 Constituent Membership | `phase7/data/universe.py` | **CONTRACT_READY_REAL_DATA_BLOCKED** | Contracts & builder implemented; awaiting real membership data |
| **BLK-02** | `CRITICAL` | Missing OHLCV Prices and Daily Traded Value (Turnover) | `phase7/data/loaders.py`, `phase7/portfolio/costs.py` | **CONTRACT_READY_REAL_DATA_BLOCKED** | Contracts & loaders implemented; awaiting real OHLCV data |
| **BLK-03** | `REQUIRED_BEFORE_MODELING` | Missing Comprehensive Point-in-Time Financial Statements (Balance Sheet, Cash Flow) | `phase7/features/quality.py`, `phase7/features/valuation.py` | **OPEN / DEFERRED FROM INITIAL MODEL SCOPE** | SUE data is available as an experimental feature, but does NOT resolve missing point-in-time balance sheet / cash flow data; comprehensive accounting modeling deferred |
| **BLK-04** | `REQUIRED_BEFORE_MODELING` | Static Sector Classification Lacks Historical Reclassification Timestamps | `phase7/data/contracts.py`, `phase7/targets/engine.py` | **BLOCKED** | Static current sector mappings are prohibited as historical fallback. Historical sector-relative research remains blocked without valid point-in-time classification or an approved preregistration amendment. |
| **BLK-05** | `REQUIRED_BEFORE_MODELING` | Absence of Historical Analyst Consensus Estimates & Revisions | `phase7/features/analyst.py` | **BLOCKED** | Formal exclusion of Family 4 in initial model iteration |
| **BLK-06** | `REQUIRED_BEFORE_MODELING` | Python 3.14.4 Runtime C-Level Access Violation in Datetime Operations | `tests/phase7/`, CI runner | **Mitigation defined through Python 3.12 standardization; resolution pending creation and verification of .venv-phase7.** | Use standard Python library structures; run non-crashing tests |
| **BLK-07** | `REQUIRED_BEFORE_HOLDOUT` | Phase 7 Physical Sealed Holdout Vault Specification & Encryption Protocol | `docs/PHASE7_HOLDOUT_PROTOCOL.md` | **PENDING GATE 4** | Draft protocol document; zero access to Phase 6 vault |
| **BLK-08** | `OPTIONAL_ENHANCEMENT` | Absence of Machine-Readable Corporate Announcement Feed with First-Seen Timestamps | `phase7/features/announcements.py` | **DEFERRED** | Document schema; mark feature family inactive in Milestone 1 |

---

## 2. Detailed Blocker Specifications

### BLK-01: Absence of Point-in-Time Historical Nifty 500 Constituent Membership
- **Blocker ID:** `BLK-01`
- **Missing Input or Problem:** The repository possesses no machine-readable dataset recording historical Nifty 500 constituent additions, deletions, and effective dates across 2016–2026. The static legacy universe is prohibited as a Phase 7 universe provider and protected by automated boundary tests. Only a static 138-ticker list (`features/universe.py`) exists.
- **Why It Matters:** Evaluating models using current or recent index members retrospectively introduces severe survivorship bias and retrospective membership leakage, violating Non-Negotiable Rule 5 and Gate 1 Data Integrity requirements.
- **Evidence:** Comprehensive repository search for index membership history returned zero constituent change logs. `features/universe.py` explicitly states: *"Canonical tradable universe (Nifty 100, de-listed/invalid names removed)... 138 tickers"*.
- **Files or Modules Affected:** `phase7/data/universe.py`, `phase7/validation/walk_forward.py`.
- **Exact Information or Action Required from Owner:** Provide point-in-time Nifty 500 historical constituent membership table (columns: `effective_date`, `symbol`, `action` [ADD/REMOVE], `source_timestamp`) or authorize sourcing via official NSE historical index rebalancing circulars.
- **Safe Interim Work Possible:** Implement canonical schema (`PITMembershipRecord`), universe validator, exclusion reason codes (`NOT_IN_PIT_UNIVERSE`), fail-closed builder (`PointInTimeUniverseBuilder`), and unit-test fixtures. (Completed in Milestone 2).
- **Resolution Test:** Verification script testing that the universe for date $t$ excludes securities added to Nifty 500 at $t+k$ and includes securities active at $t$ even if later delisted.
- **Current Status:** **CONTRACT_READY_REAL_DATA_BLOCKED.** Canonical contract (`PITMembershipRecord`) and universe builder interface implemented. Real historical Nifty 500 constituent addition/deletion records are unavailable; Gate 1 real-data evaluation cannot proceed until genuine point-in-time data is ingested.

---

### BLK-02: Missing OHLCV Prices and Daily Traded Value (Turnover) for Nifty 500 Universe
- **Blocker ID:** `BLK-02`
- **Severity:** `CRITICAL`
- **Missing Input or Problem:** The available price file (`data/multi/historical_10y_raw.csv`) contains only 138 tickers and provides only the `Close` price. It contains no `Open`, `High`, `Low`, `Volume`, or daily traded value (turnover).
- **Why It Matters:**
  1. The preregistered universe filter mandates a 60-day median daily traded value $\ge$ INR 10 crore. This cannot be evaluated without volume/turnover.
  2. Portfolio execution mandates $t+1$ executable prices (open/VWAP), which cannot be computed from $t$ Close.
  3. Market impact and trade capacity modeling require volume.
- **Evidence:** `df.columns` in `data/multi/historical_10y_raw.csv` returns strictly `['date', 'ticker', 'Close']`.
- **Files or Modules Affected:** `phase7/data/loaders.py`, `phase7/portfolio/costs.py`, `phase7/targets/engine.py`.
- **Exact Information or Action Required from Owner:** Procure or authorize ingestion of official unadjusted and adjusted daily OHLCV + Turnover data for all historical Nifty 500 constituents from 2016-01-01 to present.
- **Safe Interim Work Possible:** Build `DailyPriceRecord` data contract, volume-weighted liquidity filter interface, fail-closed loaders (`CSVDataLoader`, `JSONLinesDataLoader`), and synthetic unit-test fixtures. (Completed in Milestone 2).
- **Resolution Test:** Automated check asserting `Open`, `High`, `Low`, `Close`, `Volume`, and `TradedValue` are non-null for all active universe securities on trading days.
- **Current Status:** **CONTRACT_READY_REAL_DATA_BLOCKED.** Canonical contracts and streaming fail-closed loaders implemented. Real complete historical OHLCV and daily traded value remain unavailable.

---

### BLK-03: Missing Comprehensive Point-in-Time Financial Statements
- **Blocker ID:** `BLK-03`
- **Severity:** `REQUIRED_BEFORE_MODELING`
- **Missing Input or Problem:** While quarterly SUE (EPS/PAT) is available for 134 tickers in `sue_features_quarterly.csv`, full balance sheets, cash flow statements, debt items, and promoter shareholding/pledging records are missing.
- **Why It Matters:** Permitted Feature Family 2 (Quality & Accounting: ROCE, OCF/PAT, FCF margin, Net Debt/EBITDA, promoter pledging) requires verified financial statement line items with publication timestamps (`broadCastDate` / `filingDate`).
- **Evidence:** Only quarterly EPS and PAT exist in `data/fundamentals/sue_features_quarterly.csv`. No balance sheet disclosures (Assets, Liabilities, Debt, Equity) are extracted in structured format.
- **Files or Modules Affected:** `phase7/features/quality.py`, `phase7/features/valuation.py`.
- **Exact Information or Action Required from Owner:** Confirm whether commercial fundamental data (CMIE Prowess, Capitaline, or licensed XBRL parser) will be contracted, or approve narrowing initial Phase 7 feature families to Momentum, Price-Volume, and SUE only.
- **Safe Interim Work Possible:** Build accounting feature computation interface with formal schemas; test using small synthetic financial statement fixtures.
- **Resolution Test:** Pipeline parsing quarterly balance sheets and verifying that publication timestamps strictly precede prediction timestamps.
- **Current Status:** **OPEN / DEFERRED FROM INITIAL MODEL SCOPE.** SUE data is available as a separately identified experimental feature under a 20-day or 60-day ranking hypothesis, but this does NOT resolve the lack of point-in-time comprehensive balance-sheet, cash-flow, and debt statements. Comprehensive accounting and quality feature families lacking verified point-in-time filings remain formally deferred from the initial model development cycle until verified point-in-time filing datasets are procured.

---

### BLK-04: Static Sector Classification Lacks Historical Reclassification Timestamps
- **Blocker ID:** `BLK-04`
- **Severity:** `REQUIRED_BEFORE_MODELING`
- **Missing Input or Problem:** `data/multi/ticker_sectors.json` records single static sectors and industries for 138 tickers without effective start/end dates. Static current sector mappings are prohibited as historical fallback. Historical sector-relative research remains blocked without valid point-in-time classification or an approved preregistration amendment.
- **Why It Matters:** Sector-relative return target calculation ($R_{i, 20d} - R_{\text{sector}, 20d}$) and sector concentration constraints ($\le 25\%$) rely on accurate sector classification. Reclassifications (e.g. index restructuring) must not be applied backwards.
- **Evidence:** `ticker_sectors.json` has schema `{"TICKER": {"sector": "...", "industry": "..."}}` with no timestamps.
- **Files or Modules Affected:** `phase7/data/contracts.py`, `phase7/targets/engine.py`, `phase7/portfolio/constraints.py`.
- **Exact Information or Action Required from Owner:** Confirm whether NSE/AMFI historical sector classification master is available, or approve preregistration amendment.
- **Safe Interim Work Possible:** Implement `PITSectorClassificationRecord` contract supporting temporal validity ranges (`effective_from`, `effective_to`).
- **Resolution Test:** Unit test asserting that sector assignments query against `effective_date`.
- **Current Status:** **BLOCKED.** Static current sector mappings are prohibited as historical fallback. Historical sector-relative research remains blocked without valid point-in-time classification or an approved preregistration amendment.

---

### BLK-05: Absence of Historical Analyst Consensus Estimates & Revisions
- **Blocker ID:** `BLK-05`
- **Severity:** `REQUIRED_BEFORE_MODELING`
- **Missing Input or Problem:** Zero historical consensus analyst revisions or forward estimate data exists in the repository.
- **Why It Matters:** Permitted Feature Family 4 requires genuine point-in-time timestamped consensus estimates. Non-Negotiable Rule 10 strictly forbids substituting current estimates for historical estimates.
- **Evidence:** No analyst forecast data exists in `data/`.
- **Files or Modules Affected:** `phase7/features/revisions.py`.
- **Exact Information or Action Required from Owner:** Confirm whether consensus data (e.g. Refinitiv I/B/E/S or FactSet) is available. If not, formally exclude Feature Family 4 from initial preregistered scope.
- **Safe Interim Work Possible:** Specify interface and mark Feature Family 4 as `INACTIVE_EXCLUDED_NO_PIT_DATA`.
- **Resolution Test:** None; marked excluded.
- **Current Status:** **BLOCKED / EXCLUDED.**

---

### BLK-06: Python 3.14.4 Runtime C-Level Access Violation in Datetime Operations
- **Blocker ID:** `BLK-06`
- **Severity:** `REQUIRED_BEFORE_MODELING`
- **Missing Input or Problem:** The current host Python runtime is Python 3.14.4 (`C:\Python314\python.exe`). Running `pytest test_features.py` results in a fatal Windows access violation in `pandas.core.arrays.datetimes._generate_range`.
- **Why It Matters:** Test execution and numerical calculations will crash non-deterministically during walk-forward fold generation or time-series indexing.
- **Evidence:** Fatal crash log captured during Milestone 0: `Windows fatal exception: access violation` in `datetimes.py:439`. Python 3.14 is a development/pre-release build.
- **Files or Modules Affected:** All Python execution environments and CI scripts.
- **Exact Information or Action Required from Owner:** Standardize execution on Python 3.12 under `.venv-phase7`. Do not mark resolved until: (1) Python 3.12 is installed; (2) `.venv-phase7` is created; (3) dependencies install successfully; (4) applicable Phase 7 tests pass under Python 3.12; (5) legacy datetime tests run successfully without crash; (6) interpreter and dependency versions are recorded.
- **Safe Interim Work Possible:** Implement modules using standard library primitives (`Decimal`, `datetime`, `dataclasses`, `hashlib`, `enum`); non-crashing tests run cleanly under host Python.
- **Resolution Test:** `pytest test_features.py` and Phase 7 test suites exit with code 0 without access violation under Python 3.12.
- **Current Status:** **Mitigation defined through Python 3.12 standardization; resolution pending creation and verification of .venv-phase7.**

---

### BLK-07: Phase 7 Sealed Holdout Protocol & Distinct Vault Location
- **Blocker ID:** `BLK-07`
- **Severity:** `REQUIRED_BEFORE_HOLDOUT`
- **Missing Input or Problem:** Phase 6 holdout vaults (`window_a_sealed.7z`, `window_b_sealed.7z`) are sealed and immutable under Phase 6 governance. Phase 7 requires an independent holdout vault, separate encryption keys, and formal temporal boundaries.
- **Why It Matters:** Non-Negotiable Rule 1 strictly prohibits accessing Phase 6 vaults. Phase 7 must have an uncompromised holdout protocol designed before development candidate freezing.
- **Evidence:** `docs/holdout_access_log.md` covers Phase 6 only. No Phase 7 holdout vault currently exists.
- **Files or Modules Affected:** `docs/PHASE7_HOLDOUT_PROTOCOL.md`, `phase7/governance/holdout.py`.
- **Exact Information or Action Required from Owner:** Define Phase 7 holdout date range, external vault storage directory, and confirmation of key management protocol prior to Milestone 10.
- **Safe Interim Work Possible:** Author `docs/PHASE7_HOLDOUT_PROTOCOL.md` establishing physical separation rules.
- **Resolution Test:** Verification that Phase 7 holdout path is completely separate from `gaurvideep_vault` and recorded in immutable ledger.
- **Current Status:** **PENDING MILESTONE 10 / GATE 4.**

---

### BLK-08: Absence of Corporate Announcements Feed with First-Seen Timestamps
- **Blocker ID:** `BLK-08`
- **Severity:** `OPTIONAL_ENHANCEMENT`
- **Missing Input or Problem:** No point-in-time feed of unstructured/semi-structured corporate announcements (e.g. order wins, ratings, management changes) with verified first-seen dissemination timestamps is present.
- **Why It Matters:** Permitted Feature Family 5 requires verifiable dissemination timestamps.
- **Evidence:** Only structured corporate actions (`*_ca.json`) exist in `data/fundamentals/corporate_actions/`.
- **Files or Modules Affected:** `phase7/features/announcements.py`.
- **Exact Information or Action Required from Owner:** Defer Feature Family 5 to a future research extension or provide an authenticated NSE/BSE announcements feed.
- **Safe Interim Work Possible:** Mark Family 5 as deferred in preregistration.
- **Resolution Test:** None; deferred.
- **Current Status:** **DEFERRED.**
