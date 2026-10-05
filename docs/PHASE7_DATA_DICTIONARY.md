# Phase 7 — Data Dictionary & Schema Specifications

**Repository:** GaurviDEEP
**Working Branch:** `phase7-research`
**Governing Document:** [`docs/PHASE7_RESEARCH_PREREGISTRATION.md`](PHASE7_RESEARCH_PREREGISTRATION.md)
**Standard Environment:** Python 3.12 (`.venv-phase7`)
**Status Date:** 2026-10-05

---

## 1. General Data Invariants & Standards

1. **Timestamp Representation:**
   - All internal date-time fields must use **ISO 8601 UTC** (`YYYY-MM-DDTHH:MM:SSZ`).
   - Daily trading session dates must be formatted as **ISO 8601 calendar strings** (`YYYY-MM-DD`).
   - Conversion to Indian Standard Time (IST, UTC+05:30) occurs strictly at display boundaries.
2. **Timing Integrity & Audited Timestamps:**
   - Every fundamental observation must record:
     - `effective_date`: First trading session date where the disclosure was known before market open.
     - `source_timestamp`: Original filing timestamp recorded by the exchange.
     - `first_seen_timestamp`: Timestamp when the observation was first ingested.
   - If `source_timestamp` occurs after NSE market close (15:30 IST), `effective_date` must advance to $T+1$.
3. **Identifier Standards:**
   - NSE Equity Symbols: Uppercase string without exchange suffixes (e.g. `RELIANCE`, `TCS`, `INFY`).
   - ISIN: 12-character alphanumeric code (e.g. `INE002A01018`).

---

## 2. Market Data & Pricing Tables

### Table: `market_daily_ohlcv`
Daily unadjusted and adjusted pricing data for eligible equity securities.

| Column Name | Data Type | Nullable | Units / Format | Description |
|---|---|---|---|---|
| `date` | `DATE` | No | `YYYY-MM-DD` | Trading session date |
| `symbol` | `VARCHAR(20)` | No | Uppercase string | NSE equity ticker symbol |
| `open` | `FLOAT` | No | INR | Session opening price |
| `high` | `FLOAT` | No | INR | Session high price |
| `low` | `FLOAT` | No | INR | Session low price |
| `close` | `FLOAT` | No | INR | Session closing price |
| `volume` | `BIGINT` | No | Shares | Total traded volume (number of shares) |
| `traded_value` | `FLOAT` | No | INR | Total daily traded value (turnover) |
| `split_adj_factor` | `FLOAT` | No | Ratio ($\ge 1.0$) | Cumulative factor for splits and bonus shares |
| `div_adj_factor` | `FLOAT` | No | Ratio ($\ge 1.0$) | Cumulative factor for cash dividend reinvestment |
| `adj_close` | `FLOAT` | No | INR | Total-return adjusted closing price |
| `vwap` | `FLOAT` | Yes | INR | Volume-weighted average session price |

---

## 3. Universe & Corporate Action Tables

### Table: `pit_nifty500_membership`
Point-in-Time constituent additions and deletions for Nifty 500.

| Column Name | Data Type | Nullable | Units / Format | Description |
|---|---|---|---|---|
| `effective_date` | `DATE` | No | `YYYY-MM-DD` | First trading day the change was active |
| `symbol` | `VARCHAR(20)` | No | Uppercase string | NSE symbol being added or removed |
| `action` | `VARCHAR(10)` | No | `ADD` / `REMOVE` | Membership transition event |
| `circular_number` | `VARCHAR(50)` | Yes | String | Exchange circular or notice reference |
| `source_timestamp` | `TIMESTAMP` | No | UTC ISO 8601 | Announcement dissemination timestamp |
| `ingestion_timestamp` | `TIMESTAMP` | No | UTC ISO 8601 | Audit log ingestion timestamp |

### Table: `corporate_actions`
Verified corporate action adjustments for equity securities.

| Column Name | Data Type | Nullable | Units / Format | Description |
|---|---|---|---|---|
| `symbol` | `VARCHAR(20)` | No | Uppercase string | NSE ticker symbol |
| `ex_date` | `DATE` | No | `YYYY-MM-DD` | Ex-action trading date |
| `record_date` | `DATE` | Yes | `YYYY-MM-DD` | Record date for entitlement |
| `action_type` | `VARCHAR(20)` | No | `SPLIT`/`BONUS`/`DIVIDEND` | Nature of corporate action |
| `multiplier` | `FLOAT` | No | Ratio | Quantity multiplier (e.g. 2.0 for 1:1 bonus) |
| `cash_amount` | `FLOAT` | Yes | INR | Cash dividend per share (if dividend) |
| `source_timestamp` | `TIMESTAMP` | No | UTC ISO 8601 | Broadcast date of corporate announcement |

### Table: `sector_classification_pit`
Historical point-in-time AMFI/NSE sector and industry mapping.

| Column Name | Data Type | Nullable | Units / Format | Description |
|---|---|---|---|---|
| `symbol` | `VARCHAR(20)` | No | Uppercase string | NSE ticker symbol |
| `sector` | `VARCHAR(50)` | No | String | Major sector (e.g. Basic Materials, Technology) |
| `industry` | `VARCHAR(100)` | No | String | Sub-industry classification |
| `valid_from` | `DATE` | No | `YYYY-MM-DD` | Effective date of classification |
| `valid_to` | `DATE` | Yes | `YYYY-MM-DD` | Expiry date (null if currently active) |

---

## 4. Fundamental Disclosures (SUE & Accounting)

### Table: `fundamental_disclosures`
Verified quarterly financial statement disclosures.

| Column Name | Data Type | Nullable | Units / Format | Description |
|---|---|---|---|---|
| `symbol` | `VARCHAR(20)` | No | Uppercase string | NSE ticker symbol |
| `period_end_date` | `DATE` | No | `YYYY-MM-DD` | Quarter end date (e.g. 2024-03-31) |
| `broadcast_date` | `TIMESTAMP` | No | UTC ISO 8601 | Official exchange broadcast timestamp |
| `effective_date` | `DATE` | No | `YYYY-MM-DD` | First trading day available prior to open |
| `nature` | `VARCHAR(20)` | No | `STANDALONE`/`CONSOLIDATED` | Reporting scope |
| `pat` | `FLOAT` | No | INR Crores | Profit After Tax |
| `eps_nominal` | `FLOAT` | No | INR | Unadjusted diluted EPS reported |
| `eps_adjusted` | `FLOAT` | No | INR | Split-adjusted diluted EPS |
| `eps_yoy_delta` | `FLOAT` | Yes | INR | $EPS_{t} - EPS_{t-4}$ (adjusted) |
| `sue` | `FLOAT` | Yes | Standardized units | $\frac{\Delta EPS}{\sigma(\Delta EPS)}$ (Standardized Unexpected Earnings) |

---

## 5. Target Variables

### `target_20d_sector_relative`
- **Definition:** 20-trading-day forward total return of security $i$ from $t+1$ to $t+20$, minus the 20-trading-day total return of its assigned sector benchmark.
- **Execution Assumption:** Next-session executable price ($t+1$ open or volume-weighted price).
- **Formula:**
  $$\text{target\_20d\_sector\_relative}_{i, t} = \frac{P_{i, t+20}^{\text{exec}} - P_{i, t+1}^{\text{exec}}}{P_{i, t+1}^{\text{exec}}} - R_{S(i)}(t+1 \to t+20)$$
- **Physical Isolation:** Exists exclusively in target datasets; forbidden in any feature matrix.

### `target_60d_residual`
- **Definition:** 60-trading-day forward return of security $i$ from $t+1$ to $t+60$, minus estimated trailing beta multiplied by market total return.
- **Formula:**
  $$\text{target\_60d\_residual}_{i, t} = R_{i}(t+1 \to t+60) - \hat{\beta}_{i, t} \cdot R_{\text{market}}(t+1 \to t+60)$$

---

## 6. Permitted Feature Variables

| Feature Name | Family | Lookback | Description | Formula / Source |
|---|---|---|---|---|
| `mom_12m_minus_1m` | Momentum | 252 days | 12-month return excluding latest 21 days | $\frac{P_{t-21}}{P_{t-252}} - 1$ |
| `mom_6m_sector_rel` | Momentum | 126 days | 6-month excess return over sector benchmark | $R_{i}(t-126 \to t-1) - R_{S(i)}(t-126 \to t-1)$ |
| `mom_3m_residual` | Momentum | 63 days | 3-month residual return net of market beta | $R_{i}(t-63 \to t-1) - \hat{\beta} \cdot R_m$ |
| `distance_52w_high` | Momentum | 252 days | Percentage distance from 52-week peak close | $\frac{P_{i, t} - \max_{252}(P_i)}{\max_{252}(P_i)}$ |
| `mom_consistency` | Momentum | 252 days | Fraction of positive calendar months over trailing year | $\frac{1}{12}\sum_{m=1}^{12} \mathbb{I}(R_m > 0)$ |
| `vol_confirmed_mom` | Momentum | 63 days | 63-day price return multiplied by volume trend ratio | $R_{63} \cdot \frac{\text{SMA}_{20}(V)}{\text{SMA}_{63}(V)}$ |
| `sue_zscore` | Fundamentals | 8 quarters | Standardized unexpected earnings | $\frac{EPS_{\text{adj}, t} - EPS_{\text{adj}, t-4}}{\text{std}_{8}(\Delta EPS)}$ |

---

## 7. Python Canonical Data Contracts (`phase7.data.contracts`)

Implemented as immutable, frozen dataclasses with strict type validation, `Decimal` precision for financial values, timezone-aware UTC `datetime` objects, and deterministic SHA-256 row hashing.

### 7.1 Core Enumerations

1. **`TradedValueStatus`:**
   - `REPORTED`: Exchange-reported turnover in INR.
   - `ESTIMATED_CLOSE_X_VOLUME`: Estimated product of Close and Volume (prohibited for primary liquidity gate).
   - `UNAVAILABLE`: Missing turnover.
2. **`PriceAdjustmentState`:**
   - `UNADJUSTED`: Raw exchange prices.
   - `SPLIT_AND_BONUS_ADJUSTED`: Adjusted for stock splits and bonus issues.
   - `TOTAL_RETURN_ADJUSTED`: Adjusted for splits, bonuses, and cash dividend reinvestment.
3. **`CorporateActionType`:**
   - `SPLIT`, `BONUS`, `CASH_DIVIDEND`, `SPECIAL_DIVIDEND`, `RIGHTS_ISSUE`, `SPINOFF`, `AMALGAMATION`, `FACE_VALUE_SPLIT`.
4. **`ExclusionReason`:**
   - `NOT_IN_PIT_UNIVERSE`: Security was not an active constituent of Nifty 500 on date $t$.
   - `INSUFFICIENT_HISTORY`: Less than 252 trading sessions of verified history prior to date $t$.
   - `BELOW_TURNOVER_THRESHOLD`: 60-day median daily traded value strictly below INR 10 crore.
   - `BELOW_PRICE_THRESHOLD`: Previous close strictly below INR 20.00 (penny stock filter).
   - `TRADING_SUSPENDED`: Security subject to regulatory, GSM/ASM, or exchange trading halt on date $t$.
   - `MISSING_PRICE_DATA`: Required price observations absent on date $t$.
   - `CIRCUIT_FILTER_LOCKED`: Security hit daily price band circuit filter preventing trading execution.
   - `UNVERIFIED_CORPORATE_ACTION`: Unresolved corporate action lacking verified adjustment multiplier.

### 7.2 Dataclass Schema Specifications

1. **`DailyPriceRecord`:**
   - Natural Key: `(symbol, date, adjustment_state)`
   - Fields: `symbol` (str), `isin` (str, 12-char), `date` (date), `open` (Decimal), `high` (Decimal), `low` (Decimal), `close` (Decimal), `volume` (int), `traded_value` (Decimal), `traded_value_status` (TradedValueStatus), `split_adj_factor` (Decimal), `div_adj_factor` (Decimal), `adjustment_state` (PriceAdjustmentState), `vwap` (Optional[Decimal]), `source_timestamp` (datetime, UTC), `row_hash` (str).
2. **`PITMembershipRecord`:**
   - Natural Key: `(symbol, effective_date, action)`
   - Fields: `symbol` (str), `isin` (str), `effective_date` (date), `action` (str: `ADD`/`REMOVE`), `circular_number` (Optional[str]), `source_timestamp` (datetime, UTC), `ingestion_timestamp` (datetime, UTC), `row_hash` (str).
3. **`PITSectorClassificationRecord`:**
   - Natural Key: `(symbol, valid_from)`
   - Fields: `symbol` (str), `isin` (str), `sector` (str), `industry` (str), `valid_from` (date), `valid_to` (Optional[date]), `source_timestamp` (datetime, UTC), `row_hash` (str).
4. **`CorporateActionRecord`:**
   - Natural Key: `(symbol, ex_date, action_type)`
   - Fields: `symbol` (str), `isin` (str), `ex_date` (date), `record_date` (Optional[date]), `action_type` (CorporateActionType), `multiplier` (Decimal), `cash_amount` (Decimal), `reference_price` (Optional[Decimal]), `source_timestamp` (datetime, UTC), `row_hash` (str).
5. **`EligibilitySuspensionRecord`:**
   - Natural Key: `(symbol, suspension_start)`
   - Fields: `symbol` (str), `isin` (str), `suspension_start` (date), `suspension_end` (Optional[date]), `reason` (str), `source_timestamp` (datetime, UTC), `row_hash` (str).
6. **`PITFinancialStatementRecord`:**
   - Natural Key: `(symbol, period_end_date, nature)`
   - Fields: `symbol` (str), `isin` (str), `period_end_date` (date), `broadcast_timestamp` (datetime, UTC), `effective_date` (date), `nature` (str: `STANDALONE`/`CONSOLIDATED`), `pat` (Decimal), `eps_nominal` (Decimal), `eps_adjusted` (Decimal), `row_hash` (str).
7. **`EligibleSecurityRecord`:**
   - Fields: `symbol` (str), `isin` (str), `sector` (str), `close` (Decimal), `median_daily_traded_value_60d` (Decimal), `history_days` (int).
8. **`PITUniverseSnapshot`:**
   - Fields: `as_of_date` (date), `eligible_securities` (Tuple[EligibleSecurityRecord, ...]), `excluded_securities` (Dict[str, Tuple[ExclusionReason, ...]]), `universe_hash` (str), `is_real_data_blocked` (bool), `source_row_count` (int).

### 7.3 Row Hash Determination

The deterministic SHA-256 row hash is computed as:
$$\text{row\_hash} = \text{SHA256}\left(\sum_{k \in \text{sorted}(\text{keys})} k + \text{"="} + \text{normalize}(v) + \text{";"}\right)$$
where `row_hash` is excluded from the input dictionary, dates are formatted `YYYY-MM-DD`, UTC datetimes are formatted `YYYY-MM-DDTHH:MM:SSZ`, Decimals are string-normalized, and floats/integers are strictly represented.
