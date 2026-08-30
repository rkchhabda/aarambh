# GaurviDEEP — Improvement Plan

Analysis of the ensemble pipeline (training → Optuna tuning → evaluation → live
FastAPI service). Findings are grouped by priority.

---

## 🔴 P0 — Correctness (live predictions are silently wrong)

### 1. `obv_slope` train/serve skew (critical)
The feature is computed **differently** at training time vs. inference time, so the
model receives a value it never saw during training.

| Stage | File | Definition |
|-------|------|------------|
| Training | `prepare_enhanced_data.py` (`compute_features`) | `obv_slope = obv.diff(5)` → `OBV[t] − OBV[t−5]` |
| Serving | `rebuild_cache_v2.py:48` (`compute_v2_features`) | `np.polyfit(x, y, 1)[0]` → linear-regression slope of OBV over last 10 points |

**Impact:** every live `/v1/signal` prediction for the `obv_slope` input is
garbage. Accuracy on the test set looks fine because eval uses the training
definition; production does not.

**Fix:**
- Create `features/indicators.py` exporting a single `compute_features(df, index_returns=None)`.
- Import it in `prepare_enhanced_data.py`, `rebuild_cache_v2.py` (and any other
  caller) so there is exactly **one** implementation.
- Add a unit test asserting training features == serving features for a fixed
  input row.

### 2. Three divergent feature implementations
There are four overlapping definitions of "features":
- `build_ensemble.py` → 12 features, **1d** target, hardcoded Windows path
- `prepare_multiticker_data.py` → 12 features, **next-day** target
- `prepare_enhanced_data.py` → 27 features, 1d/3d/5d targets
- `rebuild_cache_v2.py` → 10 features (for serving)

**Fix:** all scripts import the shared module from #1. Delete or archive the
legacy `build_ensemble.py` (see P2 #10).

---

## 🟠 P1 — Methodology / honest metrics

### 3. Proper stacking for the meta-model
`retrain_v2.py` trains the meta-model (`LogisticRegression`) on predictions from a
**single** validation fold. This overfits the meta-learner and makes the reported
ensemble accuracy optimistic.

**Fix:** generate **out-of-fold (OOF)** predictions for the base models via
cross-validation on the training set, then fit the meta-model on those OOF
probabilities. Evaluate on a held-out test set the meta-model never saw.

### 4. Report baselines and ranking metrics
`eval_v2.py` reports only accuracy (73.7% test / 71.8% WF). Without context this
is not interpretable.

**Fix:** always print:
- Majority-class baseline accuracy (and class balance for the chosen horizon)
- A naive momentum baseline (e.g. "predict up if `ret_5 > 0`")
- `AUC`, `F1`, `precision/recall` (not just accuracy)
- Brier score is already printed — keep it.

### 5. Trading backtest (the actual product goal)
It is a *signal* product; accuracy ≠ profit. There is no transaction-cost-aware
evaluation of the BUY/HOLD signals.

**Fix:** add `backtest.py` that, on the test / walk-forward period:
- Acts on `signal == "BUY"` only (respecting the SMA200 regime gate)
- Applies realistic costs (brokerage + slippage, e.g. 0.1–0.3% per trade)
- Reports total return, hit-rate, Sharpe, max drawdown, and compares to a
  buy-and-hold benchmark.

---

## 🟡 P2 — Robustness / quality

### 6. Scale features for the LR models
`LogisticRegression` with L1 penalty is scale-sensitive. Inputs `roc_10`,
`atr_14`, `rsi_14`, `williams_r`, `cci` have very different magnitudes, so the L1
penalty is applied unevenly across features.

**Fix:** wrap the base LR and the meta LR in a `StandardScaler` (fit on training
data only). XGB/RF are scale-invariant and need no scaling.

### 7. Do not hardcode threshold / regime gate
The decision uses a fixed `0.5` cut-off (`service/app.py:248`) and a hardcoded
SMA200 gate. Neither is validated.

**Fix:** tune the probability threshold and the regime-gate rule on the validation
set / walk-forward to optimize F1 or backtest return, then persist the chosen
values.

### 8. `retrain_v2.py` hardcodes the 10 features
`retrain_v2.py` defines `FEATURES` literally instead of reading
`cfg['features']` from `best_params.json`. If feature selection changes during
tuning, retrain silently mismatches eval.

**Fix:** `FEATURES = cfg['features']` (already available in the same file).

### 9. `ticker_cache.json` is a stale one-off snapshot
Last rebuilt 29-Aug. Live signals use stale prices, and the SMA200 regime gate
drifts as the market moves.

**Fix:** schedule `rebuild_cache_v2.py` (cron / worker) so cached features and
SMA200 stay current. Optionally fetch live data on demand with a short cache TTL.

### 10. Legacy `build_ensemble.py`
Uses a hardcoded absolute Windows path (`C:\Users\r_chh\...`) and is stale 1d /
12-feature code that contradicts the v2 5d / 10-feature pipeline. Risk of being
run by mistake.

**Fix:** archive under `legacy/` or delete; reference the shared module instead.

### 11. Version the feature schema
Nothing asserts that the served features match what the model was trained on.

**Fix:** write a `service/models/features.json` manifest (feature list + version)
when training, and at API startup assert
`FEATURES == manifest['features']`. Fail loudly on mismatch instead of serving
wrong predictions.

---

## Suggested implementation order
1. **#1 + #11** — shared feature module + startup schema assertion (stops silent wrong predictions).
2. **#2 + #10** — delete legacy code, unify callers.
3. **#3 + #4 + #5** — fix stacking, add baselines/AUC, add backtest (validate real value).
4. **#6 + #7 + #8 + #9** — scaling, threshold tuning, config-driven features, cache refresh.
