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
   - ISIN: 12-character alphanumeric code (e.g. `INE002A01018`). Enforced strictly as ISIN structural-format validation via regex `^[A-Z]{2}[A-Z0-9]{9}[0-9]$` (two-letter country code, nine alphanumeric characters, and one trailing numeric check character). Full ISO 6166 check-digit computation is not claimed or performed.

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

## 7. Python Canonical Data Contracts (`phase7.data.contracts` & `phase7.data.universe`)

Implemented as immutable, frozen dataclasses with strict type validation, `Decimal` precision for financial values, timezone-aware UTC `datetime` objects, and deterministic SHA-256 row hashing.

### 7.1 Core Governance Principles
- **Legacy Universe Boundary:** The static legacy universe is prohibited as a Phase 7 universe provider and protected by automated boundary tests.
- **Sector Classification Standard:** Static current sector mappings may be used only in explicitly labelled synthetic tests or non-historical display contexts. Historical sector-relative research fails closed without valid point-in-time sector classification.

### 7.2 Core Enumerations

1. **`TradedValueStatus`:**
   - `EXCHANGE_REPORTED`: Official exchange-reported turnover in INR. Derivation method must be empty.
   - `DERIVED_FROM_PRICE_VOLUME`: Derived turnover with recorded derivation method. Deriving from Close alone is strictly prohibited.
   - `MISSING`: Turnover missing from exchange feed (traded value must be zero).
   - `INVALID`: Unparseable or corrupt turnover value (traded value must be zero).

2. **`PriceAdjustmentState`:**
   - `RAW`: Raw unadjusted exchange prices.
   - `SPLIT_ADJUSTED`: Adjusted for splits and bonus shares.
   - `TOTAL_RETURN_ADJUSTED`: Adjusted for splits, bonuses, and cash dividend reinvestment.
   - `UNKNOWN`: Unverified adjustment state (fails closed).

3. **`CorporateActionType`:**
   - Canonical categories: `SPLIT`, `BONUS`, `CASH_DIVIDEND`, `RIGHTS`, `MERGER`, `DEMERGER`, `SYMBOL_CHANGE`, `DELISTING`.
   - Source aliases normalized via `canonicalize_corporate_action_type()`:
     - `RIGHTS_ISSUE` $\to$ `RIGHTS`
     - `AMALGAMATION` $\to$ `MERGER`
     - `SPINOFF` $\to$ `DEMERGER`
     - `FACE_VALUE_SPLIT` $\to$ `SPLIT`
   - Ambiguous actions (`RIGHTS`, `MERGER`, `DEMERGER`, `SYMBOL_CHANGE`, `DELISTING`) route to `MANUAL_REVIEW` pending explicit research policy.

4. **`ExclusionReason`:**
   - Canonical enumeration:
     - `NOT_IN_PIT_UNIVERSE`: Security was not an active constituent of Nifty 500 on prediction date.
     - `MISSING_MEMBERSHIP_HISTORY`: Security lacks point-in-time constituent membership records.
     - `MISSING_ISIN`: Security record lacks valid 12-character ISIN.
     - `BELOW_MIN_PRICE`: Closing price strictly below INR 20.00 minimum threshold.
     - `INSUFFICIENT_HISTORY`: Less than 252 valid trading session observations prior to prediction date.
     - `MISSING_PRICE_HISTORY`: No price records available for candidate security.
     - `MISSING_LIQUIDITY_HISTORY`: Insufficient turnover observations (< 60 sessions) or missing values for MDTV.
     - `BELOW_MIN_LIQUIDITY`: 60-day median daily traded value strictly below INR 10 crore.
     - `MISSING_SECTOR_CLASSIFICATION`: Security lacks valid point-in-time AMFI/NSE sector mapping.
     - `CONFLICTING_SECTOR_CLASSIFICATION`: Multiple conflicting sector classifications effective on prediction date.
     - `SUSPENDED`: Security subject to active regulatory trading suspension on prediction date.
     - `PROLONGED_NON_TRADING`: Trading suspended due to prolonged lack of trades / liquidity.
     - `RESTRICTED_SECURITY`: Security on surveillance or restricted list (GSM/ASM stages).
     - `INVALID_CORPORATE_ACTION_HISTORY`: Unresolved or inconsistent corporate action adjustments.
     - `UNKNOWN_POINT_IN_TIME_STATUS`: Security status indeterminate at prediction timestamp.
     - `DUPLICATE_SECURITY_RECORD`: Conflicting price/liquidity records on same trading date.
     - `FUTURE_DATA_DETECTED`: Source timestamp is in the future relative to prediction timestamp.
     - `DATA_VALIDATION_FAILURE`: Security-level input records failed structural or schema validation rules.
   - Compatibility aliases supported: `BELOW_TURNOVER_THRESHOLD`, `BELOW_PRICE_THRESHOLD`, `TRADING_SUSPENDED`, `MISSING_PRICE_DATA`, `UNVERIFIED_CORPORATE_ACTION`, `CIRCUIT_FILTER_LOCKED`.
   - **Architectural Distinction:** `ExclusionReason.DATA_VALIDATION_FAILURE` operates strictly at the individual security level and is NOT aliased to `UNKNOWN_POINT_IN_TIME_STATUS`. In contrast, `UniverseBuildStatus.DATA_VALIDATION_FAILURE` operates at the dataset-wide build execution level.

5. **`UniverseBuildStatus`:**
   - `SUCCESS`: Investable universe constructed with $\ge 1$ eligible security.
   - `BLOCKED_MISSING_MEMBERSHIP`: Missing historical constituent membership records (BLK-01).
   - `BLOCKED_MISSING_PRICE_LIQUIDITY`: Missing historical OHLCV and traded value records (BLK-02).
   - `BLOCKED_MISSING_SECTOR_HISTORY`: Missing historical point-in-time sector classifications (BLK-04).
   - `VALID_EMPTY_UNIVERSE`: All datasets present, point-in-time validation succeeded, but 0 securities passed active eligibility filters.
   - `DATA_VALIDATION_FAILURE`: Fatal dataset-wide or configuration-level validation error occurred during build execution. Distinct from security-level exclusion.
   - `BLOCKED`: Documented compatibility alias mapping to `BLOCKED_MISSING_MEMBERSHIP`.
   - Property `is_real_data_blocked`: Boolean flag returning `True` for all `BLOCKED_MISSING_*` states.

### 7.3 Dataclass Schema Specifications

1. **`DailyPriceRecord`:**
   - Fields: `trading_date` (date), `symbol` (str), `isin` (str, 12-char), `open` (Decimal), `high` (Decimal), `low` (Decimal), `close` (Decimal), `volume` (int), `traded_value_inr` (Decimal), `traded_value_status` (TradedValueStatus), `price_adjustment_state` (PriceAdjustmentState), `source_timestamp` (datetime, UTC), `ingestion_timestamp` (datetime, UTC), `source_identifier` (str), `adjusted_close` (Optional[Decimal]), `traded_value_derivation_method` (Optional[str]), `row_hash` (str).
2. **`PITMembershipRecord`:**
   - Fields: `index_code` (str), `symbol` (str), `isin` (str), `effective_from` (date), `effective_to` (Optional[date]), `source_timestamp` (datetime, UTC), `ingestion_timestamp` (datetime, UTC), `source_identifier` (str), `circular_reference` (Optional[str]), `row_hash` (str).
3. **`PITMembershipEventRecord`:**
   - Fields: `index_code` (str), `symbol` (str), `isin` (str), `event_type` (str: `ADD`/`REMOVE`), `effective_date` (date), `source_timestamp` (datetime, UTC), `ingestion_timestamp` (datetime, UTC), `source_identifier` (str), `circular_reference` (Optional[str]), `row_hash` (str).
4. **`PITSectorClassificationRecord`:**
   - Fields: `symbol` (str), `isin` (str), `sector_code` (str), `effective_from` (date), `effective_to` (Optional[date]), `source_timestamp` (datetime, UTC), `ingestion_timestamp` (datetime, UTC), `source_identifier` (str), `industry_code` (Optional[str]), `sub_industry_code` (Optional[str]), `row_hash` (str).
5. **`CorporateActionAdjustmentRecord`:**
   - Fields: `action_id` (str), `symbol` (str), `isin` (str), `action_type` (CorporateActionType), `ex_date` (date), `record_date` (Optional[date]), `split_factor` (Decimal), `bonus_ratio_numerator` (Decimal), `bonus_ratio_denominator` (Decimal), `dividend_amount_inr` (Decimal), `total_return_factor` (Decimal), `source_timestamp` (datetime, UTC), `ingestion_timestamp` (datetime, UTC), `source_identifier` (str), `row_hash` (str).
6. **`EligibilitySuspensionRecord`:**
   - Fields: `symbol` (str), `isin` (str), `status` (EligibilityStatus), `effective_from` (date), `effective_to` (Optional[date]), `source_timestamp` (datetime, UTC), `ingestion_timestamp` (datetime, UTC), `source_identifier` (str), `reason` (Optional[str]), `row_hash` (str).
7. **`UniverseBuildResult`:**
   - Fields: `prediction_timestamp` (datetime, UTC), `prediction_date` (date), `eligible_symbols` (List[str]), `eligible_isins` (List[str]), `exclusions` (Dict[str, List[ExclusionReason]]), `evidence` (Dict[str, Dict[str, Any]]), `universe_hash` (str), `status` (UniverseBuildStatus), `config_version` (str), `dataset_version` (str), `blockers` (List[str]), `warnings` (List[str]).

### 7.4 Row Hash Determination

The deterministic SHA-256 row hash is computed as:
$$\text{row\_hash} = \text{SHA256}\left(\text{JSON}_{\text{canonical}}\left(\{\text{sorted\_keys}\} \setminus \{\text{"row\_hash"}\}\right)\right)$$
where dates are formatted `YYYY-MM-DD`, UTC datetimes are formatted `YYYY-MM-DDTHH:MM:SSZ`, Decimals are string-normalized, symbols/ISINs are uppercased, and values are serialized with sort keys and compact separators.

---

## 8. Phase 7 Target Engine Contracts and Specifications (Milestone 3)

### 8.1 Target Variable Formulas

1. **20-Trading-Day Sector-Relative Forward Target (`target_20d_sector_relative`):**
   $$R_{\text{stock}, t+1 \to t+20} = \frac{P_{\text{stock}, t+20}}{P_{\text{stock}, t+1}} - 1$$
   $$R_{\text{sector}, t+1 \to t+20} = \frac{P_{\text{sector}, t+20}}{P_{\text{sector}, t+1}} - 1$$
   $$y_{i, t}^{\text{20d\_sector\_rel}} = R_{\text{stock}, t+1 \to t+20} - R_{\text{sector}, t+1 \to t+20}$$
   - Execution lag: $T+1$ trading day entry ($t+1$). Same-day entry at $t$ is strictly prohibited.
   - Horizon: Exactly 20 trading sessions counted sequentially (exchange holidays and weekends skipped).
   - Point-in-Time Sector: Sector benchmark must match the point-in-time sector code valid at prediction instant $t$ ($t \in [\text{effective\_from}, \text{effective\_to})$ with $\text{source\_timestamp} \le t$).

2. **60-Trading-Day Beta-Adjusted Residual Forward Target (`target_60d_residual`):**
   $$R_{\text{stock}, t+1 \to t+60} = \frac{P_{\text{stock}, t+60}}{P_{\text{stock}, t+1}} - 1$$
   $$R_{\text{market}, t+1 \to t+60} = \frac{P_{\text{market}, t+60}}{P_{\text{market}, t+1}} - 1$$
   $$y_{i, t}^{\text{60d\_residual}} = R_{\text{stock}, t+1 \to t+60} - \left(\beta_{i, \le t} \cdot R_{\text{market}, t+1 \to t+60}\right)$$
   - Beta estimate provenance: Beta estimate must be pre-calculated using data strictly up to $t$ ($\text{estimation\_end\_timestamp} \le t$). Future beta leaks fail closed (`FUTURE_BETA_DETECTED`).
   - Preservation: Stock return, benchmark return, beta, and residual target are stored separately in the target record.

### 8.2 Enumerations

1. **`TargetStatus` (`str, Enum`):**
   - `VALID`: Successfully computed target satisfying all point-in-time and boundary requirements.
   - `INVALID`: Excluded due to terminal event, data truncation, or integrity failure.
   - `BLOCKED`: Blocked due to missing upstream point-in-time datasets (e.g. PIT sector classification).

2. **`TargetReasonCode` (`str, Enum`):**
   - `MISSING_ENTRY_PRICE`: Missing price observation on session $t+1$.
   - `MISSING_EXIT_PRICE`: Missing price observation on session $t+H$.
   - `INSUFFICIENT_FORWARD_OBSERVATIONS`: Dataset truncated before horizon session $t+H$ is reached.
   - `SUSPENDED_DURING_HORIZON`: Active trading suspension or restriction during $[t+1, t+H]$.
   - `DELISTED_DURING_HORIZON`: Delisting effective during $[t+1, t+H]$.
   - `CORPORATE_ACTION_REVIEW_REQUIRED`: Complex restructuring (merger, demerger, rights) or invalid factor during horizon.
   - `MISSING_PIT_SECTOR`: No point-in-time sector classification covering $t$.
   - `CONFLICTING_PIT_SECTOR`: Conflicting overlapping sector classifications active at $t$.
   - `FUTURE_SECTOR_DETECTED`: Sector classification record exists only after prediction instant $t$.
   - `MISSING_BENCHMARK`: Missing benchmark price or return on stock entry or exit date.
   - `INVALID_BENCHMARK`: Mismatched benchmark identifier or invalid return structure.
   - `INVALID_BETA`: Missing, non-finite, or security-mismatched beta input record.
   - `FUTURE_BETA_DETECTED`: Beta estimation window ends strictly after prediction instant $t$.
   - `INVALID_ADJUSTMENT_STATE`: Price series does not satisfy required total-return adjustment state.
   - `DATA_VALIDATION_FAILURE`: Structural validation or identity mismatch failure.
   - `SAME_DAY_ENTRY_PROHIBITED`: Prohibited attempt to enter on prediction date $t$.
   - `DUPLICATE_DATE_OBSERVATION`: Multiple observations for the same security on the same trading date.

### 8.3 Dataclass Schema Specifications

1. **`TargetSpecificationRecord`:**
   - Fields: `target_name` (str), `target_version` (str), `horizon_trading_days` (int), `execution_lag_trading_days` (int), `entry_price_field` (str), `exit_price_field` (str), `return_type` (str), `benchmark_type` (str), `adjustment_state_requirement` (PriceAdjustmentState), `missing_terminal_policy` (str), `suspension_policy` (str), `delisting_policy` (str), `created_timestamp` (datetime, UTC), `specification_hash` (str).
2. **`PredictionEventRecord`:**
   - Fields: `prediction_timestamp` (datetime, UTC), `prediction_trading_date` (date), `symbol` (str), `isin` (str), `universe_hash` (str), `dataset_version` (str), `source_cutoff_timestamp` (datetime, UTC), `target_specification_hash` (str), `row_hash` (str).
3. **`ForwardPriceObservationRecord`:**
   - Fields: `trading_date` (date), `symbol` (str), `isin` (str), `price` (Decimal), `adjustment_state` (PriceAdjustmentState), `source_timestamp` (datetime, UTC), `source_identifier` (str), `row_hash` (str).
4. **`SectorBenchmarkObservationRecord`:**
   - Fields: `sector_code` (str), `trading_date` (date), `benchmark_identifier` (str), `price` (Optional[Decimal]), `return_value` (Optional[Decimal]), `adjustment_state` (PriceAdjustmentState), `source_timestamp` (datetime, UTC), `dataset_version` (str), `row_hash` (str).
5. **`BetaInputRecord`:**
   - Fields: `symbol` (str), `isin` (str), `beta` (Decimal), `estimation_end_timestamp` (datetime, UTC), `estimation_method` (str), `benchmark_identifier` (str), `dataset_version` (str), `row_hash` (str).
6. **`TargetResultRecord`:**
   - Fields: `target_name` (str), `target_version` (str), `prediction_timestamp` (datetime, UTC), `symbol` (str), `isin` (str), `horizon_trading_days` (int), `entry_date` (Optional[date]), `exit_date` (Optional[date]), `stock_total_return` (Optional[Decimal]), `benchmark_total_return` (Optional[Decimal]), `beta_used` (Optional[Decimal]), `target_value` (Optional[Decimal]), `target_status` (TargetStatus), `invalid_reason_codes` (List[TargetReasonCode]), `source_dataset_versions` (Dict[str, str]), `target_hash` (str).
7. **`TargetAuditRecord`:**
   - Fields: `input_record_count` (int), `accepted_target_count` (int), `rejected_target_count` (int), `blocked_target_count` (int), `future_data_count` (int), `missing_entry_count` (int), `missing_exit_count` (int), `adjustment_state_failure_count` (int), `suspension_count` (int), `delisting_count` (int), `invalid_beta_count` (int), `overlapping_label_count` (int), `target_specification_hash` (str), `dataset_version` (str), `failure_reasons_summary` (Dict[str, int]), `audit_notes` (List[str]).
   - Governance invariant: Excludes all investment performance metrics (Sharpe, Sortino, Alpha, Rank IC, Drawdown). Strictly restricted to data quality, integrity, and temporal leakage verification.
