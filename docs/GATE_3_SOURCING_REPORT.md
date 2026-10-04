# Phase 6 — Gate 3: Fundamental Data Sourcing & Data Quality Audit

**Governing Documents:**  
- [`docs/RESEARCH_PREREGISTRATION.md`](docs/RESEARCH_PREREGISTRATION.md) (Section 3.2, 4, 6)  
- [`docs/RESEARCH_PREREGISTRATION_AMENDMENT_1.md`](docs/RESEARCH_PREREGISTRATION_AMENDMENT_1.md) (Section G: "Gate 3: Fundamental data integration (if sourced)")  
**Milestone:** Gate 3  
**Status:** In Progress — Descoping to Free Public NSE XBRL Fundamentals Build  
**Scope:** Narrowed Development Window (2018-01-01 to 2025-09-16) for fundamental/SUE models; full window (2016-09-26 to 2025-09-16) retained for other models. Windows A & B remain strictly sealed.  

---

## 1. Requirement & Governing Pre-Registration Standard

Per Section 3.2 and Section 6 of `docs/RESEARCH_PREREGISTRATION.md`:
> *"Fundamental data — quarterly earnings surprise (actual vs. estimate), balance sheet quality (debt/equity, interest coverage), valuation relative to sector (P/E, P/B percentile within sector). Requires a new data source."*  
> *"Sourcing (free vs. paid, coverage of the 138-ticker universe, historical depth available) should be reported before any modeling begins. Any new data source must be checked for the same point-in-time discipline already required elsewhere in this project — no fundamental data that wasn't actually available to a trader on that date (e.g., earnings reported with a lag must be timestamped to their actual release date, not the quarter-end date)."*

Furthermore, Amendment 1 Section G explicitly conditions this milestone:  
**"Gate 3: Fundamental data integration (if sourced) — Development data only."**

---

## 2. Commercial & Free Vendor Sourcing Audit (Pricing & Technical Depth)

A concrete pricing and coverage investigation was conducted across primary Indian financial data providers:

| Vendor / Provider | Tier / Product | Verified Pricing (Annual) | Historical Depth | Universe Coverage | Point-in-Time (PIT) Release Audit | Viability Verdict |
|---|---|---|---|---|---|---|
| **CMIE Prowess / Prowessdx** | Institutional / Prowess-IP on Web / Prowessdx | **Indicative, publicly unconfirmed:** ~₹3.30L – ₹3.52L + 18% GST (based on educational institutional tenders; CMIE does not publish list pricing; sold strictly via direct institutional sales contract. A direct formal quotation must be sought before informing any spending decision). | 10+ years (full 2016–2025 panel) | 100% of NSE/BSE listed universe | **Full PIT integrity.** Normalized standardized disclosures, actual board announcement timestamps, restatement tracking. | **Viable for future institutional licensing.** Currently not licensed for this project. |
| **Trendlyne** | StratQ (Professional) / GuruQ | **₹5,900/year** (StratQ) / **₹2,190/year** (GuruQ) | ~3–5 years historical ratios; 10y raw statements | 100% of Nifty universe | **Partial PIT.** Excel Connect / web data downloader allows CSV exports, but public developer API is unavailable for retail tiers; historical consensus forecast timestamps are restricted. | **Inexpensive research tool, but lacks automated programmatic PIT time-series API.** |
| **Screener.in** | Premium Tier | **₹4,999/year** (~$60 USD/yr) | 10+ years annual/quarterly statements | 100% of NSE/BSE listed universe | **Lacks precise historical PIT timestamps.** Early years (2016–2019) align primarily to fiscal quarter-ends rather than exact press release dates. | **Low cost for manual Excel exports, but requires manual PIT lag reconstruction.** |
| **Yahoo Finance API** | Free (`yfinance` / `quoteSummary`) | ₹0 (Free / Public) | ~4 to 8 trailing quarters only | Partial (~85% of 138 tickers) | **Fails PIT discipline completely.** Lacks historical announcement dates; unauthenticated endpoints rate-limited. | **REJECTED.** Severe lookahead risk and insufficient depth (<2 years vs. 9-year development requirement). |
| **NSE Corporate Disclosures** | Direct XBRL / Announcements | ₹0 (Free portal) | ~2–3 years readily structured; older filings heterogeneous | 100% of 138 tickers | Available in raw PDF/HTML/XBRL announcement metadata. | Requires custom multi-year extraction pipeline; no turnkey bulk PIT dataset available. | **REJECTED for automated use without custom pipeline.** |
| **Institutional Terminals** | Bloomberg / FactSet / S&P Capital IQ | **$12,000 – $30,000 USD/year** (~₹10 Lakhs – ₹25 Lakhs/yr) | 10+ years | 100% | Institutional-grade PIT point-in-time point data. | Cost-prohibitive for current research stage. |

---

## 3. Methodological & Point-in-Time (PIT) Integrity Analysis

Section 6 establishes a non-negotiable rule: **zero lookahead bias in fundamental data**. 

In Indian equities, quarterly financial results (Q1, Q2, Q3, Q4) are declared by companies via board meeting disclosures typically **15 to 45 calendar days after the quarter-end date**:
- *Example:* For Q3 ending December 31, 2023, Infosys disclosed earnings on January 11, 2024; Reliance disclosed on January 19, 2024; state-run banks disclosed in mid-February 2024.
- If a model assigns Q3 earnings, P/E, or debt ratios to any trading date between January 1 and the disclosure date, it introduces **severe lookahead bias (peeking up to 45 days into the future)**.
- Any pseudo-fundamental dataset that forward-fills numbers based on quarter-end dates would artificially inflate train/val performance, producing exactly the spurious alpha patterns that `RESEARCH_PREREGISTRATION.md` was enacted to prevent.

---

## 4. Gate 3 Sourcing Verdict

1. **Status:** **NOT SOURCED.** Free public sources do not possess the required 9-year point-in-time depth (2016–2025) for the 138-ticker universe.
2. **Honest Accounting:** In strict compliance with Amendment 1 Section G ("*Fundamental data integration (if sourced)*") and Section 8 ("*If the Result Is Null / What does not count as progress*"), we do not synthesize a synthetic, lookahead-contaminated fundamental dataset.
3. **Data Loader Safeguards Maintained:** No fundamental dataset was added to `data_loader.py` that would violate the development cutoff (`2025-09-16`). Windows A and B remain 100% sealed.

---

## 5. Protocol for Future Fundamental Ingestion (If Owner Sources Data)

If the owner obtains an institutional, point-in-time compliant historical fundamental export (e.g., from CMIE Prowess, FactSet, or Bloomberg), it can be integrated under the following schema:
- **Required Columns:** `date` (actual market disclosure date YYYY-MM-DD), `ticker` (e.g. `RELIANCE.NS`), `pe_ratio`, `pb_ratio`, `debt_to_equity`, `earnings_surprise_pct`.
- **Constraint:** Must strictly pass through [`scripts/phase6/data_loader.py`](scripts/phase6/data_loader.py) with the `date <= 2025-09-16` filter enforced.

---

## 6. Next Sequential Step: Gate 4 (Options & Macro Features)

Per Amendment 1 Section G:
- **Gate 4:** Options & Macro Features (India VIX level/term structure, 200-SMA market regime, universe breadth), model refinement, and final model **FREEZE**.
- Options and macro indicators (e.g. `^INDIAVIX`, Nifty 50 regime) have verified, point-in-time historical data readily accessible across the full 2016–2025 development window.

---

## 7. Pre-Registration Scope Change Addendum (Dated: 2026-09-30)

*Required by Section 3 of `RESEARCH_PREREGISTRATION.md`: "Anything not on this list requires updating this document with a dated, written rationale before being added."*

**Scope Change Decision:**
Gate 3's fundamental-features test uses a narrowed development window of 2018-01-01 to 2025-09-16 (instead of the full 2016-2025 window used elsewhere), because reliable point-in-time XBRL data does not exist before 2018 per the 5-ticker feasibility check. Pre-2018 legacy HTML filings are excluded entirely rather than scraped, since their reliability is unverified and scraping them was never approved. This narrowing is decided now, before any modeling, and applies ONLY to models that use fundamental/SUE features — models using other feature families keep the original 2016-2025 development window.

**Execution Constraints:**
1. **Source:** Free public NSE Corporate Filings archive only (`nsearchives.nseindia.com` via session-authenticated queries). BSE is excluded due to HTTP 403 bot-protection (no circumvention permitted).
2. **Corporate Action Adjustments:** Mandatory split and bonus adjustment engine applied retroactively to nominal historical EPS to eliminate artificial earnings shocks.
3. **Point-in-Time Enforcement:** All EPS/SUE values timestamped to actual exchange disclosure/broadcast timestamps (`broadCastDate`/`filingDate`), not accounting period-end dates.
4. **Development Only:** Cutoff strictly enforced at `2025-09-16`. Holdout Windows A & B remain untouched and sealed.

---

## 8. Gate 3 SUE Pipeline Implementation & Data Quality Audit (Steps 1–6)

**Execution Date:** 2026-09-30  
**Status:** Feature Pipeline Built & Audited — **Ready for Review (Zero Model Training Conducted)**  

### 8.1 Harvester & Universe Coverage (Step 1)
- **Harvester:** [`scripts/phase6/harvest_nse_metadata.py`](../scripts/phase6/harvest_nse_metadata.py) (throttled at ~1s/req using NSE corporate results API).
- **Universe Queried:** All 138 canonical tickers.
- **Total Filings Indexed:** 15,625 raw records across history.
- **Total Machine-Readable XBRL Instances Identified:** 6,730 instances (`.xml`).
- **Usable Tickers ($\ge 10$ Quarters):** **133 / 138 (96.4%)**.
- **Excluded Tickers ($< 10$ Quarters):** **5 tickers** flagged for exclusion:
  - `HDFCLIFE.NS` (0 quarters, IRDAI insurance format)
  - `SBILIFE.NS` (0 quarters, IRDAI insurance format)
  - `ICICIGI.NS` (0 quarters, IRDAI insurance format)
  - `ICICIPRULI.NS` (0 quarters, IRDAI insurance format)
  - `NESTLEIND.NS` (6 quarters, calendar fiscal year Jan–Dec, recent XBRL onboarding)

### 8.2 Multi-Taxonomy Parser & Standalone vs. Consolidated Resolution (Steps 2 & 3)
- **Script:** [`scripts/phase6/build_step2_step3_pipeline.py`](../scripts/phase6/build_step2_step3_pipeline.py)
- **Resolution Rule (Step 3):** Prefer Consolidated disclosures where filed; fall back to Standalone only when no Consolidated filing exists for that quarter. Latest broadcast timestamp selected for revisions.
- **Resolved Filings:** 3,550 unique quarterly filings across 134 active tickers:
  - Consolidated: **3,189 (89.8%)**
  - Standalone fallback: **361 (10.2%)**
- **Taxonomy Extraction Success (Step 2):**
  - Standard Ind-AS: 2,152 filings
  - Banking / NBFC taxonomy: 1,372 filings
  - Extraction Success Rate: **99.3% (3,524 / 3,550 valid basic EPS & PAT values extracted)**.

### 8.3 Corporate Action Adjustment Engine Validation (Step 4)
- **Engine:** [`scripts/phase6/corporate_action_engine.py`](../scripts/phase6/corporate_action_engine.py)
- **Archive Ingested:** 138 per-ticker corporate action histories from NSE (`/api/corporates-corporateActions`).
- **Total Split/Bonus Events Mapped:** 114 corporate action events.
- **Adjustment Formula:** For any filing with broadcast timestamp $t < T_{\text{ex}}$, $\text{EPS}_{\text{adj}} = \text{EPS}_{\text{nominal}} / \prod_{T_{\text{ex}} > t} M$.

#### Benchmark 1: Reliance Industries (`RELIANCE.NS`) — Oct 2024 1:1 Bonus

| Quarter End | Broadcast Timestamp | Nominal EPS | Adjustment Multiplier | Split-Adjusted EPS | Corporate Action Applied |
|---|---|---|---|---|---|
| `2023-12-31` | 2024-01-19 19:17:54 | ₹25.52 | 2.00x | **₹12.76** | BONUS 2.0x (2024-10-28) |
| `2024-03-31` | 2024-04-22 19:47:08 | ₹28.01 | 2.00x | **₹14.01** | BONUS 2.0x (2024-10-28) |
| `2024-06-30` | 2024-07-19 19:31:45 | ₹22.37 | 2.00x | **₹11.19** | BONUS 2.0x (2024-10-28) |
| `2024-09-30` | 2024-10-14 19:32:45 | ₹24.48 | 2.00x | **₹12.24** | BONUS 2.0x (2024-10-28) |
| `2024-12-31` | 2025-01-16 20:15:20 | ₹13.70 | 1.00x | **₹13.70** | None (Post-Bonus) |

*Validation:* Without adjustment, Q3 FY25 vs Q3 FY24 appeared as a catastrophic $-46.3\%$ collapse (₹13.70 vs ₹25.52). On the split-adjusted series, it correctly reflects **$+7.4\%$ YoY earnings growth** (₹13.70 vs ₹12.76).

#### Benchmark 2: Tata Steel (`TATASTEEL.NS`) — July 2022 10:1 Stock Split

| Quarter End | Broadcast Timestamp | Nominal EPS | Adjustment Multiplier | Split-Adjusted EPS | Corporate Action Applied |
|---|---|---|---|---|---|
| `2022-03-31` | 2022-05-03 20:22:54 | ₹79.91 | 10.00x | **₹7.99** | SPLIT 10.0x (2022-07-28) |
| `2022-06-30` | 2022-07-25 18:45:02 | ₹50.03 | 10.00x | **₹5.00** | SPLIT 10.0x (2022-07-28) |
| `2022-09-30` | 2022-10-31 17:48:41 | ₹1.24 | 1.00x | **₹1.24** | None (Post-Split) |

*Validation:* Eliminates artificial $-97.5\%$ drop from nominal ₹50.03 to ₹1.24.

### 8.4 SUE Feature Construction & Data Quality Report (Steps 5 & 6)
- **Script:** [`scripts/phase6/build_sue_feature.py`](../scripts/phase6/build_sue_feature.py)
- **Artifacts:**
  - Feature Dataset: [`data/fundamentals/sue_features_quarterly.csv`](../data/fundamentals/sue_features_quarterly.csv)
  - Summary JSON: [`data/fundamentals/gate3_sue_data_quality_summary.json`](../data/fundamentals/gate3_sue_data_quality_summary.json)
- **Formula:**
  $$\Delta \text{EPS}_t = \text{EPS}_{\text{adj}, t} - \text{EPS}_{\text{adj}, t-4}$$
  $$\text{SUE}_t = \frac{\Delta \text{EPS}_t}{\sigma_{\text{rolling}}(\Delta \text{EPS}_{t-k \dots t})}$$
  where $\sigma$ is computed over a rolling 8-quarter window (minimum 3 quarters required).
- **Point-in-Time Timestamp Rule:** Values assigned to exchange `broadCastDate`. If broadcast after market close ($\ge 15:30$), `effective_date` advances to next calendar trading session.

#### SUE Data Quality & Distribution Audit

| Metric | Value |
|---|---|
| **Total Universe Tickers** | 138 |
| **Tickers with Usable SUE Series** | **133 / 138 (96.4%)** |
| **Total Usable Quarterly SUE Observations** | **2,704** |
| **Quarters per Ticker (Mean / Median)** | **20.33 / 21.0** |
| **Quarters per Ticker (Min / Max)** | **9.0 / 23.0** |
| **SUE Mean / Std** | **+0.455 / 1.402** |
| **SUE Median (50th %ile)** | **+0.385** |
| **SUE Interquartile Range (25th – 75th %ile)** | **-0.261 to +1.247** |
| **SUE 1st / 99th Percentile** | **-2.517 / +3.611** |
| **SUE Min / Max** | **-16.705 / +16.854** |
| **Skewness / Kurtosis** | **-0.708 / 25.327** (heavy tails, suitable for winsorization / robust ranking) |

### 8.5 Pre-Modeling Governance Decisions (Dated: 2026-09-30)

*Required by Pre-Registration governance prior to launching Gate 3 model training.*

#### 1. Treatment of the 5 Excluded Tickers in Model Evaluation
- **Decided Rule:** The 5 tickers with insufficient historical XBRL depth (`HDFCLIFE.NS`, `SBILIFE.NS`, `ICICIGI.NS`, `ICICIPRULI.NS`, `NESTLEIND.NS`) are **excluded entirely from the Gate 3 SUE model training dataset, validation folds, and AUC / Sharpe evaluation metrics**.
- **Written Rationale:** Fundamental earnings surprise cannot be synthesized or imputed via fallback zero/median without injecting artificial noise that distorts sector ranking and gradient descent. Because the empirical question of Gate 3 is whether genuinely reported corporate earnings surprise delivers directional 5-day alpha, the evaluation must be conducted on the 133-ticker universe where genuine point-in-time XBRL disclosures exist. Any production system requiring all 138 tickers defaults to technical/macro models for the 5 excluded names.

#### 2. SUE Distribution Heavy Tails & Fold-Specific Winsorization Discipline
- **Risk Identification:** The observed SUE kurtosis of **25.33** confirms a heavy-tailed distribution driven by cyclical turnaround quarters (e.g. steel, energy, and commodities swinging between small losses and large gains). If unconstrained, extreme observations ($SUE \le -16.7$ or $\ge +16.8$) could disproportionately dominate logistic regression coefficients and tree split thresholds.
- **Enforced Winsorization Protocol:** SUE is winsorized at the 1st and 99th percentiles.
- **Strict Lookahead Safeguard:** The winsorization percentiles ($P_{01}$ and $P_{99}$) are **computed strictly on the training partition of each walk-forward fold**. The validation partition is then clipped using the training fold's thresholds. Computing global winsorization percentiles across the full 2018–2025 development window is strictly prohibited as a form of lookahead bias.

---

## 9. Gate 3 Model Training & Walk-Forward Alpha Evaluation

**Execution Date:** 2026-09-30  
**Artifacts Generated:**
- Model Training Script: [`scripts/phase6/train_gate3_model.py`](../scripts/phase6/train_gate3_model.py)
- Evaluation Metrics JSON: [`phase6_artifacts/gate3_results.json`](../phase6_artifacts/gate3_results.json)

### 9.1 Experimental Architecture & Pre-Registration Protocol

1. **Universe & Observation Window:**
   - 133 canonical universe tickers (5 tickers excluded per Section 8.5 pre-registration decision: `HDFCLIFE.NS`, `SBILIFE.NS`, `ICICIGI.NS`, `ICICIPRULI.NS`, `NESTLEIND.NS`).
   - Development window strictly bounded from `2018-01-01` to `2025-09-16` (1,883 trading days; 179,443 labeled ticker-day observations with observable 5-day forward horizons).
   - Test windows A & B remain untouched and sealed.
2. **Walk-Forward Cross-Validation Structure:**
   - Expanding window walk-forward validation across 3 chronological folds.
   - Validation block size: 240 trading days (~1 calendar year) per fold.
   - Zero lookahead: SUE 1st/99th percentile winsorization bounds ($P_{01}$, $P_{99}$) were computed strictly on the training partition of each fold and applied downstream to validation.
3. **Model Specifications:**
   - **Target:** `target_5d` (forward 5-day return > 0).
   - **M0 (Baseline):** Gate 2 Cross-Sectional Technical features (`relative_ret_5d`, `relative_ret_5d_vs_index`, `sector_rank_pct`).
   - **M1 (Incremental):** Baseline features + winsorized `sue`.
   - **M_SUE (Standalone):** Winsorized `sue` alone.
   - **XGBoost Incremental:** Non-linear boosted trees trained on M1 feature set.

---

### 9.2 Fold 3 Economic Simulation Anomaly: Root-Cause Investigation & Resolution

#### Investigation of the 0.0000 Sharpe Anomaly
During initial execution, Fold 3 returned `strategy_sharpe_net = 0.0000` and `buy_and_hold_sharpe = 0.0000` with Cohen's $d$ and Welch's $t$ marked `null` / `NaN`. An immediate code and data audit revealed the root cause:
- **Root Cause (Forward Return Horizon Edge Condition):**
  When computing forward returns on daily series via `shift(-5)`:
  $$\text{fwd\_ret\_5d}_t = \frac{\text{Close}_{t+5} - \text{Close}_t}{\text{Close}_t}$$
  the final 5 trading days of the development window (`2025-09-10` to `2025-09-16`) cannot observe a future 5-day close prior to the hard development cutoff date (`2025-09-16`), producing `NaN`.
- **Silent Cast Bug:**
  In pandas, evaluating `(np.nan > 0)` returns `False`, which `.astype(int)` silently cast to `0`. Consequently, `req_cols.notna().all()` checked `target` (valid `0`) rather than `fwd_ret_5d` (`NaN`), allowing 665 rows (5 trading days $\times$ 133 tickers) with unobservable future returns to persist into the dataset with an artificial loss label (`target = 0`).
- **Impact on Economic Simulation:**
  All 665 unobservable rows fell exclusively in Fold 3's validation window. In NumPy, calculating `np.mean()` or `np.std()` on an array containing `NaN` values propagates `NaN`. The defensive condition `if strat_std > 0` evaluated to `False` (since `NaN > 0` is `False`), silently defaulting the Sharpe ratios to `0.0000` and Welch's $t$-test to `null`.
- **Pipeline Correction:**
  In [`scripts/phase6/train_gate3_model.py`](../scripts/phase6/train_gate3_model.py), the dataset ingestion was patched to explicitly require `fwd_ret_5d.notna()` before generating `target`. All 665 rows whose 5-day horizon extended past the development cutoff were dropped, leaving 179,443 fully observable rows across 1,512 trading days.
- **Verification on AUC & Metrics:**
  - Fold 3 M0 Base AUC shifted from `0.5090` to **`0.5091`** (+0.0001).
  - Fold 3 M1 Incremental AUC shifted from `0.5088` to **`0.5090`** (+0.0002).
  - The 665 rows represented only 2.08% of Fold 3 validation data and had virtually zero impact on the discriminative ranking.
  - Fold 3's true economic metrics are now fully resolved: Buy & Hold Sharpe was **-0.1027** (reflecting a sideways/choppy market regime in late 2024–mid 2025), while the Model Strategy Sharpe was **+0.0496** ($\Delta \text{Sharpe} = +0.1523$, Welch $t = 1.494$, $p = 0.1351$, Cohen's $d = +0.0211$).

---

### 9.3 Empirical Results Across Walk-Forward Folds (Verified)

#### Walk-Forward Fold Performance Summary

| Fold | Train Window | Val Window | Train N | Val N | M0 Val AUC | M1 Val AUC | $\Delta$ AUC | Standalone SUE AUC | XGBoost M1 AUC | M1 Brier Score |
|---|---|---|---|---|---|---|---|---|---|---|
| **Fold 1** | Days 1–782 | Days 793–1032 | 82,467 | 31,920 | 0.4936 | 0.4961 | +0.0025 | 0.5058 | 0.4950 | 0.2471 |
| **Fold 2** | Days 1–1022 | Days 1033–1272 | 114,387 | 31,920 | 0.4945 | 0.4897 | -0.0049 | 0.4864 | 0.5002 | 0.2442 |
| **Fold 3** | Days 1–1262 | Days 1273–1512 | 146,307 | 31,920 | 0.5091 | 0.5090 | -0.0001 | 0.4976 | 0.4980 | 0.2539 |
| **Mean** | — | — | — | — | **0.4991** | **0.4983** | **-0.0008** | **0.4966** | **0.4977** | **0.2484** |

- **M1 Incremental AUC 95% Confidence Interval:** **[0.4892, 0.5074]** (centered squarely on 0.5000 random chance).
- **Incremental Predictive Value ($\Delta \text{AUC}$):** $-0.0008$ (zero measurable incremental value over technical features).
- **Standalone Fundamental Value:** SUE alone achieved a mean validation AUC of **0.4966**, indistinguishable from noise.
- **Non-Linear Interactions:** Non-linear modeling via XGBoost yielded a mean validation AUC of **0.4977**, confirming that non-linear feature interactions do not extract latent alpha.

#### Econometric & Model Stability (M1 Logistic Regression)

| Feature | Fold 1 $\beta$ ($p$-value) | Fold 2 $\beta$ ($p$-value) | Fold 3 $\beta$ ($p$-value) | Stability Assessment |
|---|---|---|---|---|
| `relative_ret_5d` | -0.1022 ($p < 10^{-9}$) | -0.0563 ($p < 10^{-4}$) | -0.0381 ($p = 0.0026$) | Consistently negative (mean-reverting) |
| `relative_ret_5d_vs_index` | +0.0755 ($p < 10^{-5}$) | +0.0283 ($p = 0.0429$) | +0.0118 ($p = 0.3409$) | Decaying positive relative strength |
| `sector_rank_pct` | -0.0191 ($p = 0.0138$) | -0.0101 ($p = 0.1251$) | -0.0011 ($p = 0.8568$) | Statistically insignificant in later folds |
| **`sue_win`** | **-0.0208 ($p = 0.0030$)** | **-0.0157 ($p = 0.0083$)** | **+0.0006 ($p = 0.9025$)** | **Unstable / Sign Inversion (Fails stability)** |

*Stability Analysis:* In Folds 1 and 2, the SUE coefficient was negative (positive surprises underperformed over 5 days, consistent with short-term post-earnings profit taking). In Fold 3, the sign flipped to positive and decayed to zero ($p = 0.9025$).

#### Economic Performance (Top-Quintile Long Strategy Net of 15 bps Roundtrip Friction)

| Fold | Strategy Net Sharpe | Buy & Hold Sharpe | Delta Sharpe | Welch $t$-statistic ($p$-value) | Cohen's $d$ |
|---|---|---|---|---|---|
| **Fold 1** | 0.4711 | 1.0207 | -0.5496 | $t = -4.30$ ($p < 0.0001$) | -0.0617 |
| **Fold 2** | 1.0632 | 1.4996 | -0.4364 | $t = -4.46$ ($p < 0.0001$) | -0.0612 |
| **Fold 3** | 0.0496 | -0.1027 | +0.1523 | $t = +1.49$ ($p = 0.1351$) | +0.0211 |
| **Mean** | **0.5280** | **0.8059** | **-0.2779** | — | **-0.0339** |

*Economic Analysis:* In Folds 1 and 2, the top-20% strategy significantly underperformed the passive buy-and-hold benchmark after standard 15 bps round-trip friction. In Fold 3, while the strategy slightly outperformed the negative market benchmark (-0.1027 vs +0.0496), the absolute Sharpe of 0.0496 falls far short of the 0.80 threshold and the Welch $t$-test confirms no statistically significant alpha ($p = 0.1351$).

---

### 9.4 Section 1 Pre-Registration Criteria Audit

*All criteria evaluated against the full 3-fold walk-forward validation series per pre-registration rules.*

| Criterion | Pre-Registered Requirement | Observed Result (3-Fold Mean & Fold Components) | Status |
|---|---|---|---|
| **1. Discriminative Power (AUC)** | Validation AUC $\ge 0.560$, 95% CI lower bound $\ge 0.530$ | **Mean: 0.4983** (95% CI: **[0.4892, 0.5074]**)<br>• Fold 1: `0.4961`<br>• Fold 2: `0.4897`<br>• Fold 3: `0.5090`<br>*Math:* $\frac{0.4961 + 0.4897 + 0.5090}{3} = 0.4983$ | **FAIL** |
| **2. Economic Performance (Sharpe)** | Net annualized Sharpe $\ge 0.80$ AND $>$ Buy & Hold | **Strategy Mean: 0.5280** vs **Buy & Hold Mean: 0.8059** ($\Delta = -0.2779$)<br>• Fold 1: `0.4711` vs `1.0207` ($\Delta = -0.5496$)<br>• Fold 2: `1.0632` vs `1.4996` ($\Delta = -0.4364$)<br>• Fold 3: `0.0496` vs `-0.1027` ($\Delta = +0.1523$)<br>*Math:* $\text{Strat} = \frac{0.4711 + 1.0632 + 0.0496}{3} = 0.5280$<br>*Math:* $\text{B&H} = \frac{1.0207 + 1.4996 - 0.1027}{3} = 0.8059$ | **FAIL** |
| **3. Effect Size (Cohen's $d$)** | Cohen's $d \ge 0.10$ vs Benchmark | **Mean: -0.0339** (Negative overall)<br>• Fold 1: `-0.0617`<br>• Fold 2: `-0.0612`<br>• Fold 3: `+0.0211`<br>*Math:* $\frac{-0.0617 - 0.0612 + 0.0211}{3} = -0.0339$ | **FAIL** |
| **4. Feature Stability** | Consistent sign & significance across folds | **Sign inverted** (Inconsistent across regimes)<br>• Fold 1: $\beta = -0.0208$ ($p = 0.0030$)<br>• Fold 2: $\beta = -0.0157$ ($p = 0.0083$)<br>• Fold 3: $\beta = +0.0006$ ($p = 0.9025$) | **FAIL** |
| **OVERALL GATE 3 VERDICT** | All 4 criteria must PASS | **0 of 4 Criteria Met** | **FAIL (NULL / NO EDGE)** |

---

### 9.5 Final Research Conclusion & Production Policy

1. **Empirical Finding:**
   - Standardized Unexpected Earnings (SUE) constructed from machine-readable exchange XBRL filings provides **no directional predictive power** ($\text{AUC} \approx 0.498$) for 5-day forward equity returns in the liquid Indian large/mid-cap universe over the 2018–2025 period.
   - SUE adds **zero incremental edge** ($\Delta \text{AUC} = -0.0008$) when added to existing cross-sectional price/momentum features.
2. **Pre-Registration Enforcement & Production Gate Policy:**
   - Per the governing principles in `docs/RESEARCH_PREREGISTRATION.md`, negative and null findings are documented transparently and respected without post-hoc rationalization.
   - SUE will **NOT** be included in the live production inference engine, feature pipeline, or model registry.
   - This prevents unnecessary pipeline complexity, eliminates fragile external XBRL parsing dependencies in production, and protects the system from out-of-sample overfitting.



