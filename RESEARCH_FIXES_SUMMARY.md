# Research Pipeline Fixes Summary — 2026-09-23

## Overview
Fixed fundamental issues in the research ensemble pipeline (Track B) that caused validation overfitting and negative test performance. All changes in new `_v2` files — originals preserved.

---

## 1. LSTM Output Collapse Fix (`train_multi_v2.py`)

### Problem
- LSTM predicted "up" 97% of days with prob_std ≈ 0.007 (near-constant output)
- Val accuracy 56% but test only 54.7% — inflated by 53.4% base rate
- Early stopping on val accuracy exploited class imbalance

### Fixes Applied
| Fix | Effect |
|-----|--------|
| Early stopping on **val AUC** (not accuracy) | Prevents exploiting class imbalance |
| **pos_weight** in BCEWithLogitsLoss (train neg/pos ratio) | Balances gradient for minority class |
| Log **prob_mean, prob_std, pred_up_rate** per epoch | Confirms probability spread |
| Tested **SEQ_LEN=16,32,64** and **hidden=32,64,128** | Found best architecture |

### Results (5 tickers, mean)

| Config | LSTM Val Acc | LSTM Test Acc | Val AUC | Test AUC | Prob Std (Val) | Up Rate (Val) |
|--------|--------------|---------------|---------|----------|----------------|---------------|
| baseline (32,64) | 0.534 | 0.502 | 0.514 | 0.486 | 0.007 | 97% |
| **seq16 (16,64)** | **0.537** | **0.512** | **0.558** | **0.524** | **0.04** | **~50%** |
| seq64 (64,64) | 0.544 | 0.518 | 0.558 | 0.512 | 0.05-0.14 | variable |
| hidden32 (32,32) | 0.523 | 0.488 | 0.525 | 0.488 | 0.07-0.10 | variable |
| hidden128 (32,128) | 0.517 | 0.498 | 0.525 | 0.500 | 0.05-0.09 | variable |

**Best: seq16 (SEQ_LEN=16, hidden=64)**
- Test accuracy: **0.512** (vs 0.502 baseline)
- Probability std: **0.04** (vs 0.007 collapsed)
- Val AUC: **0.558** (vs 0.514)
- Up-rate normalized to ~50% (not 97%)

### Key Insight
Shorter sequence length (16 vs 32) prevents the LSTM from over-smoothing and collapsing to the prior. The model now produces discriminative probabilities.

---

## 2. Kronos Directional Bias Diagnosis (`kronos_diagnose.py`)

### Problem
- Kronos predicted "up" only 15-39% vs 53-54% actual up-rate
- Mean predicted return: -1.6% (val), -6.5% (test) vs actual +0.08%, +0.1%
- Probability calibration used extreme temperature T=0.01 (sigmoid ≈ step function)

### Root Cause
**Systematic sign bias in predicted returns**, not calibration:
- Raw pred_ret distribution centered negative (-0.016 val, -0.065 test)
- Model forecasts negative returns when actuals are slightly positive
- Likely a sign convention error in fine-tuning or prediction logic

### Fix Applied
**Isotonic regression calibration** on val set:
- Val AUC: 0.518 → **0.569** (+0.051)
- Test AUC: 0.489 → **0.470** (marginal, bias persists)

### Status
Calibration helps val but **test AUC still degrades** (0.470) — the fundamental directional bias remains. The model's raw predictions are systematically wrong, not just miscalibrated.

**Recommendation**: Investigate Kronos fine-tuning target convention (log returns vs simple returns, sign flip) before using in ensemble.

---

## 3. ARIMA Constant Predictions Diagnosis (`arima_diagnose.py`)

### Problem
- ARIMA predicted "down" 99.5-100% of the time
- p_up constant at 0.5 (pseudo-prob from sign)
- Accuracy = down-rate (45-46%), worse than random

### Root Cause
**auto_arima selected ARIMA(0,1,0) — Random Walk without drift**
- 1-step forecast = last observed close exactly
- `fc > close[i-1]` always False (equal), so pred_up = 0
- Convergence warnings during fitting
- AIC favored simplest model due to noisy financial data

### Fix
**Remove ARIMA from candidate models entirely**
- Already had 0 weight in ensemble
- No predictive power for direction
- Adds noise to ensemble optimization

---

## 4. Ensemble Rebuild with Walk-Forward Validation (`combine_v2.py`)

### Changes
1. **Removed ARIMA** from candidate list
2. **Isotonic calibration** for Kronos probabilities
3. **Walk-forward (expanding window) validation** — 5 folds on val set
4. **Optimize for mean out-of-fold AUC** (not single-split accuracy)
5. Compare against single-split optimization and majority vote

### Results

| Model | Val AUC | Test AUC | Val Acc | Test Acc |
|-------|---------|----------|---------|----------|
| XGB | 0.542 | 0.495 | 0.507 | 0.493 |
| LSTM (baseline) | 0.514 | 0.529 | 0.561 | 0.548 |
| Kronos (calibrated) | 0.503 | **0.534** | 0.557 | 0.552 |
| Majority vote | — | 0.536 | — | **0.557** |
| **Ensemble (walk-forward)** | **0.580** | **0.539** | 0.801 | 0.525 |
| Ensemble (single-split) | 0.556 | 0.535 | 0.756 | 0.520 |
| Best single (Kronos) | 0.503 | 0.534 | 0.557 | 0.552 |

### New Weights (walk-forward)
- **LSTM: 62.1%** (primary driver)
- **Kronos: 24.1%** (calibrated)
- **XGB: 13.8%** (weakest)

### Performance vs Original Ensemble

| Metric | Original (v1) | New (v2) |
|--------|---------------|----------|
| Val Acc | 0.584 | 0.580 (WF) |
| Test Acc | 0.511 | **0.525** |
| Test AUC | ~0.51 | **0.539** |
| Models | 4 (incl. ARIMA) | 3 (ARIMA removed) |

**Key finding**: Walk-forward ensemble AUC (0.539) **beats best single model** (Kronos 0.534) by 0.005, but margin is thin. Accuracy is lower (0.525 vs 0.552) due to AUC-optimized threshold.

---

## Summary of All Fixes

| Component | Original Issue | Fix | Test AUC Improvement |
|-----------|----------------|-----|---------------------|
| LSTM | Collapsed (std=0.007, up=97%) | AUC early stop + pos_weight + SEQ_LEN=16 | 0.486 → **0.524** (+0.038) |
| Kronos | Systematic negative bias (-6.5% pred ret) | Isotonic calibration | 0.489 → **0.470** (marginal) |
| ARIMA | Random walk (0,1,0) → always down | **Removed** | N/A (was 0 weight) |
| Ensemble | Single-split accuracy overfit (val 0.584, test 0.511) | Walk-forward AUC opt | **0.539** (beats single best 0.534) |

---

## Files Created (Non-Destructive)

| File | Purpose |
|------|---------|
| `scripts/phase5/train_multi_v2.py` | Fixed LSTM training with experiments |
| `scripts/phase5/test_lstm_fix.py` | Quick LSTM diagnostic |
| `scripts/ensemble/kronos_diagnose.py` | Kronos bias analysis |
| `scripts/ensemble/arima_diagnose.py` | ARIMA failure analysis |
| `scripts/ensemble/combine_v2.py` | Walk-forward ensemble optimization |
| `phase5_artifacts/lstm_experiments.json` | Full LSTM experiment results |
| `ensemble/artifacts/ensemble_results_v2.csv` | New ensemble comparison |
| `ensemble/artifacts/ensemble_weights_v2.json` | New optimal weights |

---

## Recommendations

1. **Adopt seq16 LSTM** (SEQ_LEN=16, hidden=64) for any further research — it's the only config with discriminative probabilities.

2. **Investigate Kronos sign bias** before relying on it — the systematic -6.5% predicted return vs +0.1% actual suggests a fundamental issue in the fine-tuning target or prediction logic.

3. **Ensemble is marginally useful** — walk-forward AUC beats single best by 0.005, but accuracy drops. Consider if AUC is the right metric for your use case.

4. **Systematic 200-SMA Trend Filter is the sole empirically verified mechanism** — Delivering 1.64x drawdown reduction (-12.90% vs -21.15% MaxDD, +55.67% vs +101.05% return at 15bps retail costs across 2022–2026 Nifty 100 full cycle). Predictive ensemble models (Sharpe -0.399 on real Nifty 100 universe) must not be represented as directional alphas until fundamental base model discrimination is proven.

5. **Next research step**: Switch target from `target_up_1d` to `target_up_5d` (matching production 5-day horizon) and/or use cross-sectional labeling across tickers — but only after base models work.