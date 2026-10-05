# Phase 7 — Candidate Model Card Template

**Model Identifier:** `[e.g. M7-LGBM-RANK-01]`
**Model Family:** `[Baselines | Linear | Tree | Ranking]`
**Preregistration Version:** `1.0.0`
**Evaluation Date:** `[YYYY-MM-DD]`
**Author / Evaluator:** Lead Quantitative Research Engineer
**Git Checkpoint Hash:** `[40-character SHA]`

---

## 1. Model Overview & Theoretical Motivation
- **Architecture Description:** `[e.g. LightGBM LambdaRank with pairwise ranking objective]`
- **Hypothesis ID:** `[e.g. H-MOM-SUE-01]`
- **Economic Rationale:** `[Why this model family is expected to rank equities by 20-day sector-relative return]`
- **Hyperparameter Specification:**
  ```yaml
  model_params:
    learning_rate: 0.03
    max_depth: 3
    num_leaves: 7
    subsample: 0.8
    colsample_bytree: 0.8
    min_child_samples: 50
    random_state: 42
  ```

---

## 2. Training Data, Universe & Preprocessing
- **Investable Universe:** Point-in-time liquid Nifty 500 (Price $\ge$ INR 20, 60d MDTV $\ge$ INR 10 cr).
- **Temporal Span:** `[Start Date] to [End Date]` across 10 expanding walk-forward folds.
- **Total Training Observations ($N$):** `[Total rows across folds]`
- **Purge & Embargo Applied:** Purge = 20 trading days; Embargo = 5 trading days.
- **Fold-Local Preprocessing:** `[StandardScaler / Winsorization fitted strictly on fold training data]`
- **Feature Set Evaluated:**
  1. `mom_12m_minus_1m`
  2. `mom_6m_sector_rel`
  3. `mom_3m_residual`
  4. `distance_52w_high`
  5. `mom_consistency`
  6. `sue_zscore`

---

## 3. Walk-Forward Predictive Performance (Gate 2)

| Metric | Target Threshold | Observed Value | Gate Status |
|---|---|---|---|
| **Mean 20-Day Rank IC** | $\ge +0.030$ | `[0.0XXX]` | `[PASS / FAIL]` |
| **Median Rank IC** | $> +0.015$ | `[0.0XXX]` | `[PASS / FAIL]` |
| **Positive Monthly IC %** | $\ge 60.0\%$ | `[XX.X%]` | `[PASS / FAIL]` |
| **Positive Windows Count** | $\ge 8 / 10$ | `[X / 10]` | `[PASS / FAIL]` |
| **Stationary Bootstrap 95% CI** | Lower Bound $> 0$ | `[Lower, Upper]` | `[PASS / FAIL]` |
| **Quintile Return Spread (Q5 - Q1)** | Positive & Monotonic | `[+X.XX% / Monotonic: Yes/No]` | `[PASS / FAIL]` |

### Window-by-Window Validation IC Breakdown
| Window | Training Range | Validation Range | Val Obs ($N$) | Realized Rank IC | Realized Spread |
|---|---|---|---|---|---|
| Fold 1 | `YYYY-MM-DD` to `YYYY-MM-DD` | `YYYY-MM-DD` to `YYYY-MM-DD` | `XX,XXX` | `0.0XXX` | `+X.XX%` |
| Fold 2 | `YYYY-MM-DD` to `YYYY-MM-DD` | `YYYY-MM-DD` to `YYYY-MM-DD` | `XX,XXX` | `0.0XXX` | `+X.XX%` |
| ... | ... | ... | ... | ... | ... |
| Fold 10 | `YYYY-MM-DD` to `YYYY-MM-DD` | `YYYY-MM-DD` to `YYYY-MM-DD` | `XX,XXX` | `0.0XXX` | `+X.XX%` |

---

## 4. Economic Portfolio Performance (Gate 2)

Evaluated on Top-20 Long-Only Equal-Weighted portfolio with weekly rebalancing, 500 bps stock cap, 2500 bps sector cap, and next-session ($t+1$) execution.

| Metric | Threshold | 25 bps Base Cost | 50 bps Conservative | 75 bps Stress Cost | Status |
|---|---|---|---|---|---|
| **Net Sharpe Ratio** | $\ge 0.80$ (at base) | `[X.XX]` | `[X.XX]` | `[X.XX]` | `[PASS/FAIL]` |
| **Sortino Ratio** | $\ge 1.00$ | `[X.XX]` | `[X.XX]` | `[X.XX]` | `[PASS/FAIL]` |
| **Maximum Drawdown** | $\le 20.0\%$ | `[-XX.X%]` | `[-XX.X%]` | `[-XX.X%]` | `[PASS/FAIL]` |
| **Calmar Ratio** | $\ge 0.50$ | `[X.XX]` | `[X.XX]` | `[X.XX]` | `[PASS/FAIL]` |
| **Excess Return Windows** | $\ge 7 / 10$ | `[X / 10]` | `[X / 10]` | `[X / 10]` | `[PASS/FAIL]` |
| **Monthly One-Way Turnover**| $\le 40.0\%$ | `[XX.X%]` | `[XX.X%]` | `[XX.X%]` | `[PASS/FAIL]` |
| **Median Holding Period** | $\ge 20$ days | `[XX days]` | `[XX days]` | `[XX days]` | `[PASS/FAIL]` |

---

## 5. Robustness & Anti-Overfitting Audit (Gate 3)

| Robustness Dimension | Pre-Registered Standard | Observed Result | Status |
|---|---|---|---|
| **Regime Consistency** | Positive Rank IC in $\ge 4 / 6$ regimes | `[X / 6 regimes positive]` | `[PASS/FAIL]` |
| **Sector Breadth** | Positive IC in $\ge 60\%$ major sectors | `[XX.X% sectors positive]` | `[PASS/FAIL]` |
| **Sector Concentration** | Max single sector alpha contribution $\le 35\%$ | `[XX.X% by Sector]` | `[PASS/FAIL]` |
| **Temporal Concentration**| Max single calendar year alpha contribution $\le 40\%$ | `[XX.X% by Year]` | `[PASS/FAIL]` |
| **Jackknife: Drop Best Month** | Net Sharpe remains positive | `[Net Sharpe = X.XX]` | `[PASS/FAIL]` |
| **Jackknife: Drop Top 5 Trades** | Net Sharpe remains positive | `[Net Sharpe = X.XX]` | `[PASS/FAIL]` |
| **Deflated Sharpe Ratio (DSR)** | Probability $\ge 90.0\%$ | `[XX.X%]` | `[PASS/FAIL]` |
| **Prob. of Backtest Overfitting (PBO)** | Estimated via CSCV | `[XX.X%]` | `[REPORTED]` |

---

## 6. Gating Verdict & Sign-Off

- **Gate 1 Data Integrity:** `[PASS / FAIL]`
- **Gate 2 Development Validation:** `[PASS / FAIL]`
- **Gate 3 Robustness Audit:** `[PASS / FAIL]`
- **Overall Model Verdict:**
  `[ ] ADVANCE_TO_FREEZE`
  `[ ] SCREENING_UTILITY_ONLY`
  `[ ] VALID_NULL_RESULT`
  `[ ] DISQUALIFIED`

**Sign-off:**
`Lead Quantitative Research Engineer: _______________________ Date: _________`
`Research Governance Officer:         _______________________ Date: _________`
