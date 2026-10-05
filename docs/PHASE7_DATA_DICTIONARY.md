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
