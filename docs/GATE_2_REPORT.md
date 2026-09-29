# Phase 6 — Gate 2: First Model Walk-Forward Evaluation Report

**Governing Documents:**  
- [`docs/RESEARCH_PREREGISTRATION.md`](docs/RESEARCH_PREREGISTRATION.md) (Signed 27.09.2026)  
- [`docs/RESEARCH_PREREGISTRATION_AMENDMENT_1.md`](docs/RESEARCH_PREREGISTRATION_AMENDMENT_1.md) (Signed 29.09.2026)  
**Milestone:** Gate 2 (Month 2 milestone per Amendment 1 Section G)  
**Dataset Scope:** **Development data strictly** (`2016-09-26` to `2025-09-16`). Windows A and B remain sealed in external vault and were not accessed.  
**Loading Mechanism:** Exclusively via [`scripts/phase6/data_loader.py`](scripts/phase6/data_loader.py).  
**Execution Script:** [`scripts/phase6/train_gate2_model.py`](scripts/phase6/train_gate2_model.py)  
**Artifact:** [`phase6_artifacts/gate2_results.json`](phase6_artifacts/gate2_results.json)  

---

## 1. Executive Summary: Null Result on Isolated Relative Features

Gate 2 evaluated whether the three Month 1 cross-sectional relative return features (`relative_ret_5d`, `relative_ret_5d_vs_index`, and `sector_rank_pct`) in isolation provide any directional predictability for 5-day forward price returns.

- **Primary Result:** Across 3 sequential expanding walk-forward folds, the models achieved a **mean validation AUC of 0.4997** (Logistic Regression) and **0.5016** (Shallow XGBoost).
- **Conclusion:** **Null result.** The three cross-sectional return features in isolation have **zero predictive power** above a coin flip for 5-day directional returns.
- **Pre-Registration Handling:** Per Section 8 of the pre-registration, this null result is recorded plainly as a legitimate, complete outcome.

---

## 2. Critical Methodological Disclaimer on Feature Coefficients

The Gate 2 Logistic Regression models exhibited consistent coefficient signs across the 3 folds ($\beta < 0$ for `relative_ret_5d` and $\beta > 0$ for `relative_ret_5d_vs_index`). Despite intuitive economic labels that could be applied (e.g., "intra-sector reversal vs universe momentum"), **these signs do NOT constitute evidence of a real relationship**:

1. **Zero Discriminative Power (AUC = 0.500):** On validation data, the models fail to separate positive and negative forward returns. A model with an AUC of 0.500 has zero ranking edge; coefficient signs in such a model are descriptive artifacts of the training sample fit, not predictive alpha.
2. **Dependent Training Folds (Expanding Window):** The 3 walk-forward folds share 80–90% of their training data (Fold 1 has 200,048 samples; Fold 2 expands to 232,754; Fold 3 expands to 265,460). Consistent signs across expanding folds are heavily autocorrelated estimates on the same underlying history, **not independent statistical replications**.
3. **Magnitudes Within Noise Range:** The standardized coefficients ($\beta \approx -0.086$ and $+0.047$) are small and fall entirely within the expected random noise band for large financial samples ($N > 200,000$).
4. **Disqualification from Future Feature Selection:** These three relative return features carry **zero weight** into Gate 3 feature selection, Gate 4 model freezing, or any narrative claiming "signals that showed early promise."

---

## 3. Walk-Forward Fold Boundaries

To ensure complete temporal separation and zero label leakage within the development period (`2016-09-26` to `2025-09-16`), 3 expanding folds were established with an **embargo / purge gap of exactly 10 trading days** before each validation period:

| Fold | Training Period | Trading Days | Purge Gap (10 Days) | Validation Period | Trading Days | Validation Observations |
|---|---|---|---|---|---|---|
| **Fold 1** | 2016-10-26 to 2022-10-14 | 1,477 | 2022-10-17 to 2022-10-31 | **2022-11-01 to 2023-10-13** | 237 | 32,706 |
| **Fold 2** | 2016-10-26 to 2023-09-28 | 1,714 | 2023-09-29 to 2023-10-13 | **2023-10-16 to 2024-10-03** | 237 | 32,706 |
| **Fold 3** | 2016-10-26 to 2024-09-18 | 1,951 | 2024-09-19 to 2024-10-03 | **2024-10-04 to 2025-09-16** | 237 | 32,705 |

*Total development observations evaluated: 299,545 clean rows across 138 universe tickers.*

---

## 4. Performance Metrics

### A. AUC Summary

| Architecture | Fold 1 Train | Fold 1 Val | Fold 2 Train | Fold 2 Val | Fold 3 Train | Fold 3 Val | **Mean Train** | **Mean Val** |
|---|---|---|---|---|---|---|---|---|
| **Logistic Regression** | 0.5183 | 0.4959 | 0.5152 | 0.4930 | 0.5124 | 0.5103 | **0.5153** | **0.4997** |
| **Shallow XGBoost** (depth 3) | 0.5308 | 0.4973 | 0.5273 | 0.5015 | 0.5260 | 0.5059 | **0.5280** | **0.5016** |

### B. Feature Coefficients & Importances

#### Logistic Regression Standardized Coefficients ($\beta$)
- `relative_ret_5d`: Fold 1 = -0.1072, Fold 2 = -0.0834, Fold 3 = -0.0684 (Mean: **-0.0863**)
- `relative_ret_5d_vs_index`: Fold 1 = +0.0660, Fold 2 = +0.0432, Fold 3 = +0.0312 (Mean: **+0.0468**)
- `sector_rank_pct`: Fold 1 = -0.0197, Fold 2 = -0.0145, Fold 3 = -0.0086 (Mean: **-0.0143**)

#### Shallow XGBoost Feature Gain
- `relative_ret_5d`: 43.2%
- `relative_ret_5d_vs_index`: 29.9%
- `sector_rank_pct`: 26.9%

---

## 5. Calibration Decile Tables (Logistic Regression)

Validation decile analysis confirms a complete lack of monotonicity and discriminative separation:

```
Fold 1 (Val Base Rate = 0.5485, Brier = 0.2486)
Decile |  Count  | Pred Prob | Actual Rate |  Diff
-------+---------+-----------+-------------+--------
   1   |    3271 |  0.4998   |   0.5390    | -0.0392
   2   |    3271 |  0.5111   |   0.5472    | -0.0362
   3   |    3270 |  0.5159   |   0.5529    | -0.0370
   4   |    3271 |  0.5196   |   0.5610    | -0.0414
   5   |    3270 |  0.5229   |   0.5554    | -0.0325
   6   |    3271 |  0.5260   |   0.5549    | -0.0289
   7   |    3270 |  0.5293   |   0.5523    | -0.0230
   8   |    3271 |  0.5329   |   0.5533    | -0.0205
   9   |    3270 |  0.5374   |   0.5492    | -0.0118
  10   |    3271 |  0.5478   |   0.5194    | +0.0284  (Inversion: highest predicted prob has lowest hit rate)

Fold 2 (Val Base Rate = 0.5811, Brier = 0.2465)
Decile |  Count  | Pred Prob | Actual Rate |  Diff
-------+---------+-----------+-------------+--------
   1   |    3271 |  0.5060   |   0.5827    | -0.0767
   2   |    3271 |  0.5170   |   0.5830    | -0.0660
   3   |    3270 |  0.5215   |   0.5893    | -0.0678
   4   |    3271 |  0.5247   |   0.5763    | -0.0516
   5   |    3270 |  0.5276   |   0.6015    | -0.0739
   6   |    3271 |  0.5305   |   0.5888    | -0.0583
   7   |    3270 |  0.5333   |   0.5758    | -0.0425
   8   |    3271 |  0.5367   |   0.5787    | -0.0421
   9   |    3270 |  0.5408   |   0.5731    | -0.0323
  10   |    3271 |  0.5504   |   0.5616    | -0.0112  (Completely flat hit rate across all deciles)

Fold 3 (Val Base Rate = 0.4836, Brier = 0.2524)
Decile |  Count  | Pred Prob | Actual Rate |  Diff
-------+---------+-----------+-------------+--------
   1   |    3271 |  0.5187   |   0.4974    | +0.0213
   2   |    3270 |  0.5268   |   0.4599    | +0.0669
   3   |    3271 |  0.5303   |   0.4766    | +0.0537
   4   |    3270 |  0.5329   |   0.4670    | +0.0659
   5   |    3271 |  0.5351   |   0.4723    | +0.0628
   6   |    3270 |  0.5372   |   0.4920    | +0.0452
   7   |    3270 |  0.5394   |   0.4752    | +0.0641
   8   |    3271 |  0.5418   |   0.4815    | +0.0603
   9   |    3270 |  0.5451   |   0.5000    | +0.0451
  10   |    3271 |  0.5529   |   0.5142    | +0.0387
```

---

## 6. Audit of Historical Failure Patterns
1. **Probability Collapse:** Confirmed. Standard deviation of probabilities is $\approx 0.012$. The models output the base rate with negligible spread.
2. **Agreement with Prior Findings:** Confirms the 309,739-observation historical technical indicator analysis: short-term market momentum and relative moves do not generate directional alpha on a 5-day horizon without external information.
3. **Blinding Integrity:** Windows A and B remain 100% sealed in external archives. Gate 2 was conducted exclusively on development data through `data_loader.py`.
