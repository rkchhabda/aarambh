# Phase 7 — Data Acquisition Specification

**Repository:** GaurviDEEP  
**Working Branch:** `phase7-research`  
**Governing Milestone:** Milestone 4.5 (Gate 1 Data Readiness Specification)  
**Status Date:** 2026-10-09  
**Status:** PREREGISTERED PROCUREMENT SPECIFICATION (NON-ACQUISITION CHECKPOINT)  

---

> [!IMPORTANT]
> **Strict Governance Mandate:** This document defines technical specifications and acceptance standards for future data procurement to resolve blockers BLK-01, BLK-02, and BLK-04. **This document DOES NOT authorize data acquisition, downloading, scraping, vendor contact, or account creation.** All research execution remains under `VALIDATION_FRAMEWORK_READY_REAL_DATA_BLOCKED`. Milestone 5 remains strictly blocked.

---

## 1. Scope, Temporal Coverage & Historical Warm-Up

To satisfy the pre-registered Phase 7 research mandate and eliminate survivorship, lookahead, and restatement biases, procured datasets must provide comprehensive point-in-time market, universe, and corporate action data for the liquid Indian equity universe.

### 1.1 Temporal Coverage Windows
- **Active Research Evaluation Window:** `2015-01-01` through `2025-09-16` (encompassing primary Phase 7 walk-forward development and out-of-sample holdout partitions).
- **Mandatory Historical Warm-Up Window:** `2014-01-01` or earlier through `2014-12-31`.
  - Required to compute the 252-trading-day history eligibility filter (`min_trading_history_days: 252`).
  - Required to calculate 12-minus-1 momentum ($t-252 \to t-21$).
  - Required to calculate rolling 252-day OLS beta ($\hat{\beta}_{i, t}$) for the 60-day residual return target.
  - Required to calculate 200-session moving averages for exposure overlays.
- **Recommended Raw Data Start Date:** **`2013-01-01` or earlier** (provides buffer for index reconstitutions and long-term liquidity baselines).

---

## 2. Table A: Historical Point-in-Time Nifty 500 Membership (Resolves BLK-01)

### 2.1 Purpose & Anti-Survivorship Invariant
Modern or static index constituent lists must never be projected backward retrospectively. Historical additions, deletions, re-inclusions, and effective dates must be applied strictly on the dates mandated by official exchange circulars.

### 2.2 Required Schema & Field Specifications

| Field Name | Type | Nullable | Description / Invariants |
|---|---|---|---|
| `index_code` | `VARCHAR(20)` | No | Canonical index identifier (e.g. `NIFTY_500`). |
| `security_name` | `VARCHAR(150)` | No | Full legal entity name active at the time of the event. |
| `symbol` | `VARCHAR(20)` | No | Uppercase NSE equity ticker symbol active on event date. |
| `isin` | `VARCHAR(12)` | No | 12-character alphanumeric ISIN code (`^[A-Z]{2}[A-Z0-9]{9}[0-9]$`). |
| `membership_action` | `VARCHAR(20)` | No | Event category: `ADD`, `REMOVE`, `RENAME`, `REPLACE`. |
| `announcement_timestamp` | `TIMESTAMP` | Yes | Official circular dissemination timestamp (UTC ISO 8601). |
| `effective_from` | `DATE` | No | First trading session date on which membership became active. |
| `effective_to` | `DATE` | Yes | Last trading session date of membership (`NULL` if currently active). |
| `source_timestamp` | `TIMESTAMP` | No | Original exchange broadcast timestamp (UTC ISO 8601). |
| `ingestion_timestamp` | `TIMESTAMP` | No | Ingestion pipeline audit timestamp (UTC ISO 8601). |
| `source_identifier` | `VARCHAR(100)` | No | Provider or feed identifier (e.g. `NSE_CIRCULAR_INDEX_RECON`). |
| `source_document_identifier` | `VARCHAR(100)` | Yes | Circular notice number (e.g. `NSE/CML/2021/045`). |
| `row_hash` | `CHAR(64)` | No | Deterministic SHA-256 canonical row hash. |

### 2.3 Required Event & Interval Coverage
The membership dataset must explicitly capture and resolve:
1. **Periodic Index Rebalancings:** Semi-annual rebalancing additions and exclusions.
2. **Ad-Hoc Replacements:** Replacements due to mergers, demergers, corporate restructurings, or capital reductions.
3. **Symbol and Ticker Migrations:** Symbol change tracking linking the same corporate entity across ticker updates.
4. **ISIN Changes:** Tracking ISIN changes resulting from capital re-organizations or face value splits.
5. **Historical Re-additions:** Entities removed in one rebalance and re-included in a subsequent rebalance must be preserved as distinct half-open intervals $[\text{effective\_from}, \text{effective\_to})$.
6. **Delistings & Suspensions:** Compulsory and voluntary delisting exclusions.
7. **Index Renaming / Taxonomy Changes:** Historical tracking of index methodology revisions.

---

## 3. Table B: Historical Daily Market Data & Liquidity (Resolves BLK-02)

### 3.1 Purpose & Execution Alignment Invariant
Daily market data must provide unadjusted and adjusted OHLCV along with daily traded value (turnover) for every security that was a constituent of the Nifty 500 at any point during 2014–2025. Datasets restricted strictly to currently traded equities are prohibited due to survivorship bias.

### 3.2 Required Schema & Field Specifications

| Field Name | Type | Nullable | Description / Invariants |
|---|---|---|---|
| `trading_date` | `DATE` | No | Session date (`YYYY-MM-DD`). |
| `security_name` | `VARCHAR(150)` | No | Entity name active on trading date. |
| `symbol` | `VARCHAR(20)` | No | Uppercase NSE equity ticker symbol. |
| `isin` | `VARCHAR(12)` | No | 12-character alphanumeric ISIN code. |
| `exchange_series` | `VARCHAR(5)` | No | Exchange series (e.g. `EQ`, `BE`, `BZ`). |
| `previous_close` | `DECIMAL(18,4)` | No | Official previous session closing price in INR. |
| `open` | `DECIMAL(18,4)` | No | Session opening price in INR. |
| `high` | `DECIMAL(18,4)` | No | Session high price in INR. |
| `low` | `DECIMAL(18,4)` | No | Session low price in INR. |
| `close` | `DECIMAL(18,4)` | No | Session closing price in INR. |
| `last_price` | `DECIMAL(18,4)` | Yes | Last traded price in INR. |
| `vwap` | `DECIMAL(18,4)` | Yes | Official session volume-weighted average price. |
| `adjusted_close` | `DECIMAL(18,4)` | Yes | Corporate-action adjusted closing price (if supplied). |
| `total_traded_quantity` | `BIGINT` | No | Total shares traded during session. |
| `total_traded_value_inr` | `DECIMAL(20,4)` | No | Total daily traded value (turnover) in INR. |
| `number_of_trades` | `BIGINT` | Yes | Total ticket count / executed trades. |
| `deliverable_quantity` | `BIGINT` | Yes | Deliverable volume (shares transferred). |
| `delivery_percentage` | `DECIMAL(6,2)` | Yes | Deliverable quantity as percentage of total traded quantity. |
| `trading_status` | `VARCHAR(20)` | No | Session status: `ACTIVE`, `SUSPENDED`, `HALTED`. |
| `suspension_status` | `VARCHAR(20)` | No | `NOT_SUSPENDED`, `SUSPENDED_CIRCUIT`, `SUSPENDED_REGULATORY`. |
| `price_adjustment_state` | `VARCHAR(30)` | No | `RAW`, `SPLIT_ADJUSTED`, `TOTAL_RETURN_ADJUSTED`. |
| `traded_value_status` | `VARCHAR(30)` | No | Provenance: `EXCHANGE_REPORTED` or `DERIVED_FROM_PRICE_VOLUME`. |
| `source_timestamp` | `TIMESTAMP` | No | Dissemination timestamp (UTC ISO 8601). |
| `ingestion_timestamp` | `TIMESTAMP` | No | Ingestion timestamp (UTC ISO 8601). |
| `source_identifier` | `VARCHAR(100)` | No | Source feed identifier. |
| `row_hash` | `CHAR(64)` | No | Deterministic SHA-256 canonical row hash. |

### 3.3 Traded Value Provenance Standard
- **Exchange-Reported Traded Value Preferred:** Primary acceptance criteria requires official exchange-reported daily traded value (`total_traded_value_inr`).
- **Derived Value Restriction:** If traded value is derived ($\text{Volume} \times \text{VWAP}$ or $\text{Volume} \times \text{Close}$), the record MUST be explicitly flagged as `traded_value_status = 'DERIVED_FROM_PRICE_VOLUME'`. Derived turnover must never be misrepresented as exchange-reported turnover.

---

## 4. Table C: Corporate Actions Master

### 4.1 Purpose & Total-Return Adjustment Invariant
All corporate restructuring events and entitlements must be verified to compute total return adjustment factors and preserve survivorship and execution continuity across splits, bonuses, dividends, and mergers.

### 4.2 Required Schema & Field Specifications

| Field Name | Type | Nullable | Description / Invariants |
|---|---|---|---|
| `symbol` | `VARCHAR(20)` | No | NSE equity ticker symbol. |
| `isin` | `VARCHAR(12)` | No | 12-character alphanumeric ISIN. |
| `action_type` | `VARCHAR(30)` | No | Canonical action: `SPLIT`, `BONUS`, `CASH_DIVIDEND`, `RIGHTS`, `MERGER`, `DEMERGER`, `DELISTING`. |
| `announcement_timestamp` | `TIMESTAMP` | Yes | Announcement broadcast timestamp (UTC ISO 8601). |
| `ex_date` | `DATE` | No | Ex-date of entitlement. |
| `record_date` | `DATE` | Yes | Record date for entitlement verification. |
| `effective_date` | `DATE` | No | Effective session date of adjustment. |
| `ratio_numerator` | `DECIMAL(12,6)` | Yes | Entitlement numerator (e.g. 1.0 for 1:1 bonus). |
| `ratio_denominator` | `DECIMAL(12,6)` | Yes | Entitlement denominator (e.g. 1.0 for 1:1 bonus). |
| `cash_amount` | `DECIMAL(18,4)` | Yes | Cash dividend or distribution per share in INR. |
| `currency` | `VARCHAR(3)` | No | Currency code (strictly `INR`). |
| `old_identifier` | `VARCHAR(50)` | Yes | Identifier prior to restructuring. |
| `new_identifier` | `VARCHAR(50)` | Yes | Identifier following restructuring. |
| `source_timestamp` | `TIMESTAMP` | No | Official circular broadcast timestamp (UTC ISO 8601). |
| `source_identifier` | `VARCHAR(100)` | No | Source authority identifier. |
| `source_document_identifier` | `VARCHAR(100)` | Yes | Circular reference identifier. |
| `revision_status` | `VARCHAR(20)` | No | `ORIGINAL`, `REVISED`, `CANCELLED`. |
| `row_hash` | `CHAR(64)` | No | Deterministic SHA-256 canonical row hash. |

### 4.3 Governance Policy for Complex Actions
Complex corporate restructurings (demergers with spin-offs, unlisted entity allocations, debt-for-equity swaps) require flagging with `CORPORATE_ACTION_REVIEW_REQUIRED` and remain subject to manual governance review before inclusion in target return calculation.

---

## 5. Table D: Historical Point-in-Time Sector Classification (Resolves BLK-04)

### 5.1 Purpose & Reclassification Timing Invariant
Sector-relative targets ($R_{i, 20d} - R_{\text{sector}, 20d}$) and portfolio concentration limits ($\le 2500\text{ bps}$) mandate genuine point-in-time sector mappings. Modern static sector mappings must NEVER be applied retrospectively.

### 5.2 Required Schema & Field Specifications

| Field Name | Type | Nullable | Description / Invariants |
|---|---|---|---|
| `symbol` | `VARCHAR(20)` | No | NSE equity ticker symbol. |
| `isin` | `VARCHAR(12)` | No | 12-character alphanumeric ISIN. |
| `classification_standard` | `VARCHAR(30)` | No | Standard taxonomy: `AMFI_MACRO_SECTOR`, `NSE_SECTORAL`, `GICS`. |
| `sector_code` | `VARCHAR(30)` | No | Canonical sector code (e.g. `IT`, `FINANCIAL_SERVICES`). |
| `sector_name` | `VARCHAR(100)` | No | Full sector name. |
| `industry_code` | `VARCHAR(30)` | Yes | Granular industry classification code. |
| `industry_name` | `VARCHAR(100)` | Yes | Full industry name. |
| `effective_from` | `DATE` | No | Session date classification became active. |
| `effective_to` | `DATE` | Yes | Expiry date of classification (`NULL` if active). |
| `source_timestamp` | `TIMESTAMP` | No | Publication dissemination timestamp (UTC ISO 8601). |
| `ingestion_timestamp` | `TIMESTAMP` | No | Ingestion timestamp (UTC ISO 8601). |
| `source_identifier` | `VARCHAR(100)` | No | Source classification provider. |
| `row_hash` | `CHAR(64)` | No | Deterministic SHA-256 canonical row hash. |

### 5.3 Provider Verification Questions (Fail-Closed Gate)
A provider must explicitly clarify in writing:
1. Are historical sector reclassifications retained as distinct temporal intervals?
2. Has the sector taxonomy structure changed over 2014–2025, and are historical codes preserved?
3. Were historical sector assignments restated retrospectively to match modern business segments?
4. Are official source publication timestamps (`broadCastDate` / circular date) available?
*If point-in-time sector history cannot be acquired, BLK-04 remains active and sector-relative targets remain blocked.*

---

## 6. Table E: Security Identifier Master & Entity Cross-Reference

### 6.1 Purpose & Permanent Entity Resolution
Securities frequently alter ticker symbols, transfer across exchange series, or undergo restructuring. The security master provides a permanent internal surrogate key (`sec_uid`) linking all historical representations.

### 6.2 Required Schema & Field Specifications

| Field Name | Type | Nullable | Description / Invariants |
|---|---|---|---|
| `sec_uid` | `VARCHAR(32)` | No | Permanent internal surrogate security identifier. |
| `current_symbol` | `VARCHAR(20)` | No | Most recent or final active ticker symbol. |
| `historical_symbol` | `VARCHAR(20)` | No | Ticker symbol active during validity window. |
| `isin` | `VARCHAR(12)` | No | ISIN active during validity window. |
| `security_name` | `VARCHAR(150)` | No | Entity legal name. |
| `exchange_series` | `VARCHAR(5)` | No | Trading series (`EQ`, etc.). |
| `listing_date` | `DATE` | No | Initial exchange listing date. |
| `delisting_date` | `DATE` | Yes | Delisting date (`NULL` if active). |
| `former_symbol` | `VARCHAR(20)` | Yes | Preceding ticker symbol (if renamed). |
| `new_symbol` | `VARCHAR(20)` | Yes | Subsequent ticker symbol (if renamed). |
| `effective_from` | `DATE` | No | Effective date of mapping window. |
| `effective_to` | `DATE` | Yes | Expiry date of mapping window (`NULL` if active). |
| `corporate_action_linkage` | `VARCHAR(50)` | Yes | Corporate action identifier explaining mapping transition. |
| `row_hash` | `CHAR(64)` | No | Deterministic SHA-256 canonical row hash. |

---

## 7. Procurement Quality Safeguards

1. **Zero Data Imputation:** Missing sessions, turnover, or prices must never be interpolated or backfilled.
2. **Fail-Closed on Unknown Provenance:** Records with ambiguous timing, unverified circulars, or missing ISINs must fail closed to exclusion ledgers.
3. **Audit Conservation:** Every raw record received must map deterministically to either an accepted canonical table or an append-only rejection ledger.
4. **License Pre-Verification:** No data file may be ingested without an executed written agreement affirming quantitative research and derived analytics rights.
