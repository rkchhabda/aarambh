# Phase 6 — Gate 4: Options & Macro (India VIX) vs 200-SMA Regime Evaluation Report

**Governing Documents:**  
- [`docs/RESEARCH_PREREGISTRATION.md`](docs/RESEARCH_PREREGISTRATION.md) (Section 3.3, 3.4, 4, 5)  
- [`docs/RESEARCH_PREREGISTRATION_AMENDMENT_1.md`](docs/RESEARCH_PREREGISTRATION_AMENDMENT_1.md) (Section G: Gate 4)  
**Milestone:** Gate 4 (Options/Macro features, model refinement, and freeze evaluation)  
**Dataset Scope:** **Development data strictly** (`2016-09-26` to `2025-09-16`). Windows A and B remain sealed in external vault and were not accessed.  
**Loading Mechanism:** Exclusively via [`scripts/phase6/data_loader.py`](scripts/phase6/data_loader.py).  
**Execution Script:** [`scripts/phase6/train_gate4_model.py`](scripts/phase6/train_gate4_model.py)  
**Artifact:** [`phase6_artifacts/gate4_results.json`](phase6_artifacts/gate4_results.json)  

---

## 1. Executive Summary: Redundant Collinearity & Null Directional Edge

Gate 4 evaluated whether incorporating options-implied volatility (`^INDIAVIX`) and market-wide breadth (`% of universe > 50-SMA`) on top of the established 200-SMA regime filter provides genuine, incremental 5-day forward directional alpha.

- **Pre-Registered Baseline (M0):** 200-SMA regime alone (`sma_200_regime`, `sma_200_dist`).
- **Pre-Registered Incremental Model (M1):** 200-SMA regime + 3 orthogonal macro/options features (`vix_spike_5d`, `pct_universe_above_50sma`, and interaction term `vix_accel_x_sma_regime`).
- **Primary Finding:** Across 3 sequential expanding walk-forward folds within the development period:
  - **Baseline M0 Mean Validation AUC:** **0.4870**
  - **Incremental M1 (Logistic Regression) Mean Validation AUC:** **0.5055** ($\Delta = +0.0185$)
  - **Incremental M1 (Shallow XGBoost) Mean Validation AUC:** **0.5093**
- **Sub-period Stability Failure:** In **2 out of 3 validation folds**, the incremental model produced a validation AUC **below 0.5000** (Fold 1: $0.4883$; Fold 3: $0.4881$).
- **Formal Verdict:** **REDUNDANT_WITH_200SMA_NULL_RESULT.** Adding India VIX and cross-sectional market breadth does **not** manufacture a robust directional edge on a 5-day horizon.

---

## 2. Pre-Training Hypothesis Audit & Theoretical Interpretation

Before training, the pre-registered question was posed:  
*"Is the hypothesis that VIX/macro adds directional signal on top of what SMA regime already provides, or is there risk of just re-discovering a weaker version of the same thing?"*

The empirical walk-forward results provide a definitive answer:
1. **The Collinearity Trap Confirmed:** In the baseline model (M0), simply trading in the direction of the 200-SMA produced a negative/flat mean validation AUC ($0.4870$), largely because buying extended stocks in late 2024–2025 suffered sharp mean-reversions (Fold 3 Val AUC = $0.4560$).
2. **Opposing Coefficient Cancellation:** In the incremental model (M1), `vix_spike_5d` ($\beta \approx -0.051$) and the interaction term `vix_accel_x_sma_regime` ($\beta \approx +0.052$) have nearly identical opposite magnitudes. When a stock is above its 200-SMA, the two terms cancel out ($\text{net } \beta \approx +0.001$), meaning **VIX spikes provide zero incremental predictive signal during bull regimes**.
3. **Regime Inconsistency:** The only validation fold where macro features produced an AUC $>0.50$ was Fold 2 (Val AUC = $0.5400$, Oct 2023 to Oct 2024), a period characterized by an uninterrupted macro rally across the Indian market. In the other two years (Fold 1: choppy market, Fold 3: late-cycle consolidation), the model failed completely ($\text{AUC} < 0.49$).

---

## 3. Walk-Forward Fold Boundaries (Within Development Period)

The dataset contains **272,374 clean observation rows** across **2,001 trading dates** (2017-07-17 to 2025-09-16, requiring 200 days of trailing history for SMA calculation).  
Each validation fold contains **237 trading days (~1 year)** separated by a **10-trading-day purge gap**:

| Fold | Training Period | Training Days | Purge Gap (10 Days) | Validation Period | Validation Days | Val Observations |
|---|---|---|---|---|---|---|
| **Fold 1** | 2017-07-17 to 2022-10-07 | 1,280 days | 2022-10-10 to 2022-10-21 | **2022-10-24 to 2023-10-09** | 237 days | 32,706 rows |
| **Fold 2** | 2017-07-17 to 2023-09-22 | 1,517 days | 2023-09-25 to 2023-10-09 | **2023-10-10 to 2024-09-30** | 237 days | 32,706 rows |
| **Fold 3** | 2017-07-17 to 2024-09-16 | 1,754 days | 2024-09-17 to 2024-09-30 | **2024-10-01 to 2025-09-16** | 237 days | 32,705 rows |

---

## 4. Performance Metrics & Comparative Table

### A. AUC Comparison: Baseline (M0) vs Incremental (M1)

| Split / Model | Fold 1 Val AUC | Fold 2 Val AUC | Fold 3 Val AUC | **Mean Validation AUC** |
|---|---|---|---|---|
| **M0: 200-SMA Baseline Alone (LR)** | 0.4972 | 0.5078 | 0.4560 | **0.4870** |
| **M1: Incremental (200-SMA + Macro/VIX LR)** | 0.4883 | 0.5400 | 0.4881 | **0.5055** |
| **Delta ($\Delta \text{AUC} = \text{M1} - \text{M0}$)** | **-0.0089** | **+0.0322** | **+0.0321** | **+0.0185** |
| **M1: Incremental Shallow XGBoost (depth 3)** | 0.4944 | 0.5178 | 0.5156 | **0.5093** |

*Key Takeaway:* While M1 technically shows a $+0.0185$ delta over the degraded M0 baseline, the absolute validation AUC is **only 0.5055 (LR) and 0.5093 (XGBoost)**, which is far below the pre-registered threshold ($\text{AUC} \ge 0.56$).

---

### B. Standardized Logistic Regression Coefficients in Incremental Model (M1)

*Evaluated with 200-SMA included as a control variable:*

| Feature | Fold 1 $\beta$ ($p$-value) | Fold 2 $\beta$ ($p$-value) | Fold 3 $\beta$ ($p$-value) | Interpretation |
|---|---|---|---|---|
| `sma_200_regime` (Control) | -0.0012 ($p=0.87$) | -0.0001 ($p=0.99$) | +0.0099 ($p=0.08$) | Statistically insignificant once short-term volatility is present |
| `sma_200_dist` (Control) | +0.0064 ($p=0.36$) | -0.0034 ($p=0.59$) | +0.0067 ($p=0.25$) | Statistically insignificant |
| `vix_spike_5d` | **-0.0512** ($p < 10^{-10}$) | **-0.0529** ($p < 10^{-10}$) | **-0.0495** ($p < 10^{-10}$) | Stable negative baseline coefficient |
| `pct_universe_above_50sma` | **-0.0352** ($p < 10^{-10}$) | **-0.0176** ($p = 2\times 10^{-4}$) | **-0.0290** ($p < 10^{-10}$) | High market breadth slightly reduces 5-day forward return probability |
| `vix_accel_x_sma_regime` | **+0.0558** ($p < 10^{-10}$) | **+0.0474** ($p < 10^{-10}$) | **+0.0514** ($p < 10^{-10}$) | Offsets `vix_spike_5d` during bull regime ($+0.0558 - 0.0512 \approx 0$) |

---

## 5. Pre-Registration Section 1 Criteria Audit

| Section 1 Criterion | Pre-Registered Threshold | Gate 4 Observed Result | Verdict |
|---|---|---|---|
| **Validation AUC** | $\ge 0.56$, lower 95% CI $\ge 0.53$ | **0.5055** (LR), **0.5093** (XGBoost) | **FAIL** |
| **Stability** | At least 3 of 4 non-overlapping test sub-periods satisfy criterion | 2 of 3 validation folds have $\text{AUC} < 0.5000$ | **FAIL** |
| **Incremental Alpha over 200-SMA** | Statistically and economically significant increase | Mean Val AUC remains $\approx 0.50$ | **FAIL** |
| **Out-of-sample Discipline** | Windows A and B untouched | Windows A & B remain sealed in external vault | **PASS** |

---

## 6. Synthesis Across Gates 1, 2, 3, and 4

At the conclusion of the Development Phase (Gates 1–4):
1. **Gate 1 (Cross-Sectional Features):** Relative return and sector percentile features engineered.
2. **Gate 2 (First Model):** Three relative features in isolation yielded **Val AUC = 0.5000**. Null result.
3. **Gate 3 (Fundamental Data):** Point-in-time compliant 10-year fundamental dataset was **not sourced** (free sources violate PIT; commercial providers require institutional licensing).
4. **Gate 4 (Options & Macro Features):** India VIX and cross-sectional universe breadth yielded **Mean Val AUC = 0.5055**, failing Section 1 criteria and showing extreme instability across market sub-periods.

**Overall Development Phase Conclusion:**  
No combination of technical indicators (309,739 observations), cross-sectional relative features (Gate 2), or macro/options volatility signals (Gate 4) has cleared the pre-registered threshold ($\text{AUC} \ge 0.56$) on development data. In accordance with Section 8 of `RESEARCH_PREREGISTRATION.md`, this is an honest, complete null finding on short-term (5-day) directional alpha for this universe.
