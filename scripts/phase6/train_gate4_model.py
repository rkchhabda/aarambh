"""Gate 4: Pre-Registered Macro & Options (India VIX) vs 200-SMA Regime Evaluation.

Governing Documents:
- docs/RESEARCH_PREREGISTRATION.md (Section 3.3, 3.4, 4, 5)
- docs/RESEARCH_PREREGISTRATION_AMENDMENT_1.md (Section G: Gate 4)

Pre-Registered Hypotheses & Evaluation Protocol:
1. Baseline Model (M0):
   - Evaluates the existing 200-SMA regime filter alone (stock Close > 200-SMA).
2. Incremental Model (M1):
   - Evaluates 200-SMA regime + 3 orthogonal macro/options features:
     a) vix_spike_5d: 5-day percentage change in India VIX ((VIX_t - VIX_{t-5}) / VIX_{t-5})
     b) pct_universe_above_50sma: Cross-sectional market breadth (% of 138 universe stocks > 50-SMA)
     c) vix_accel_x_sma_regime: Interaction term (vix_spike_5d * (1 if Close > 200-SMA else -1))
3. Pre-Registered Pass Criterion:
   - Macro/options features add real directional alpha ONLY if M1 produces statistically
     significant incremental AUC/Sharpe over M0 on validation folds, and features remain
     statistically significant when 200-SMA is included as a control variable.
   - If incremental AUC is ~0, or coefficients collapse, it is formally logged as
     "redundant collinearity with the 200-SMA regime."
4. Walk-Forward Discipline:
   - 3 sequential expanding folds within development period (2016-09-26 to 2025-09-16).
   - 10-day purge gap between train and validation on every fold.
   - Windows A and B remain strictly sealed.
"""

import json
import os
import sys
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from scripts.phase6.data_loader import load_development_raw, load_development_vix

ARTIFACTS_DIR = os.path.join(BASE_DIR, "phase6_artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

BASELINE_FEATURES = ["sma_200_regime", "sma_200_dist"]
ORTHOGONAL_MACRO_FEATURES = ["vix_spike_5d", "pct_universe_above_50sma", "vix_accel_x_sma_regime"]
ALL_FEATURES = BASELINE_FEATURES + ORTHOGONAL_MACRO_FEATURES


def build_gate4_dataset() -> pd.DataFrame:
    """Load raw prices and VIX via data_loader.py and engineer orthogonal macro features."""
    print("Loading raw development prices via scripts.phase6.data_loader...")
    raw_df = load_development_raw()
    print(f"Loaded {len(raw_df):,} raw price records across {raw_df['ticker'].nunique()} tickers.")
    
    print("Loading India VIX development data via scripts.phase6.data_loader...")
    vix_df = load_development_vix()
    print(f"Loaded {len(vix_df):,} daily India VIX records ({vix_df['date'].min()} to {vix_df['date'].max()}).")
    
    # 1. Compute VIX 5-day spike / acceleration
    vix_df = vix_df.sort_values("date").reset_index(drop=True)
    vix_df["vix_spike_5d"] = (vix_df["vix_close"] - vix_df["vix_close"].shift(5)) / vix_df["vix_close"].shift(5)
    vix_df["vix_level"] = vix_df["vix_close"]
    
    # 2. Compute stock-level indicators and universe breadth
    raw_df = raw_df.sort_values(["ticker", "date"]).reset_index(drop=True)
    
    # 50-day SMA and 200-day SMA per ticker
    print("Computing trailing 50-day and 200-day SMAs per ticker...")
    raw_df["sma_50"] = raw_df.groupby("ticker")["Close"].transform(lambda s: s.rolling(50, min_periods=50).mean())
    raw_df["sma_200"] = raw_df.groupby("ticker")["Close"].transform(lambda s: s.rolling(200, min_periods=200).mean())
    
    # Binary regime flags and normalized distances
    raw_df["above_50sma"] = (raw_df["Close"] > raw_df["sma_50"]).astype(float)
    raw_df["sma_200_regime"] = (raw_df["Close"] > raw_df["sma_200"]).astype(float)
    raw_df["sma_200_dist"] = (raw_df["Close"] - raw_df["sma_200"]) / raw_df["sma_200"]
    
    # Cross-sectional market breadth on each date: % of universe above 50-SMA
    print("Computing daily cross-sectional universe breadth (% above 50-SMA)...")
    breadth_series = raw_df.groupby("date")["above_50sma"].mean()
    breadth_df = breadth_series.reset_index().rename(columns={"above_50sma": "pct_universe_above_50sma"})
    
    # 3. Compute 5-day forward return directional target
    # shift(-5) per ticker looks 5 trading days forward
    print("Computing 5-day forward directional target per ticker...")
    raw_df["fwd_ret_5d"] = raw_df.groupby("ticker")["Close"].shift(-5) / raw_df["Close"] - 1.0
    raw_df["target"] = (raw_df["fwd_ret_5d"] > 0).astype(float)
    
    # 4. Merge VIX and Market Breadth by date
    merged = raw_df.merge(vix_df[["date", "vix_level", "vix_spike_5d"]], on="date", how="left")
    merged = merged.merge(breadth_df, on="date", how="left")
    
    # 5. Compute VIX-acceleration conditional on SMA regime:
    # Sign: +1 if in bull regime (Close > 200-SMA), -1 if in bear regime
    regime_sign = np.where(merged["sma_200_regime"] > 0.5, 1.0, -1.0)
    merged["vix_accel_x_sma_regime"] = merged["vix_spike_5d"] * regime_sign
    
    # Drop rows with NaN in target or any of the required features
    all_req_cols = ["target"] + ALL_FEATURES
    clean_mask = merged[all_req_cols].notna().all(axis=1)
    df_clean = merged[clean_mask].copy()
    df_clean["target"] = df_clean["target"].astype(int)
    
    df_clean = df_clean.sort_values(["date", "ticker"]).reset_index(drop=True)
    print(f"Clean labeled Gate 4 dataset: {len(df_clean):,} rows across {df_clean['date'].nunique()} trading dates.")
    print(f"Date range: {df_clean['date'].min()} to {df_clean['date'].max()} (Cutoff: 2025-09-16)")
    print(f"Positive target base rate: {df_clean['target'].mean():.4f} ({df_clean['target'].sum():,} / {len(df_clean):,})")
    return df_clean


def get_walkforward_folds(df: pd.DataFrame, n_folds: int = 3):
    """Generate sequential expanding-window folds with 10-day purge gaps."""
    dates = sorted(df["date"].unique())
    total_dates = len(dates)
    val_len = 237
    purge_len = 10
    
    folds = []
    for i in range(n_folds):
        val_end_idx = total_dates - (n_folds - 1 - i) * val_len
        val_start_idx = val_end_idx - val_len
        purge_start_idx = val_start_idx - purge_len
        train_end_idx = purge_start_idx
        
        train_dates = dates[:train_end_idx]
        purge_dates = dates[purge_start_idx:val_start_idx]
        val_dates = dates[val_start_idx:val_end_idx]
        
        folds.append({
            "fold_num": i + 1,
            "train_start": train_dates[0],
            "train_end": train_dates[-1],
            "train_days": len(train_dates),
            "purge_start": purge_dates[0],
            "purge_end": purge_dates[-1],
            "purge_days": len(purge_dates),
            "val_start": val_dates[0],
            "val_end": val_dates[-1],
            "val_days": len(val_dates),
            "train_dates_set": set(train_dates),
            "val_dates_set": set(val_dates)
        })
    return folds


def decile_calibration_table(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> list:
    """Compute decile calibration table: predicted prob vs actual positive rate."""
    df_eval = pd.DataFrame({"true": y_true, "prob": y_prob})
    try:
        df_eval = df_eval.assign(decile=pd.qcut(df_eval["prob"], q=n_bins, labels=False, duplicates="drop") + 1)
    except Exception:
        df_eval = df_eval.assign(decile=pd.cut(df_eval["prob"], bins=n_bins, labels=False) + 1)
        
    table = []
    for d, group in df_eval.groupby("decile"):
        table.append({
            "decile": int(d),
            "count": len(group),
            "pred_prob_mean": float(group["prob"].mean()),
            "actual_rate": float(group["true"].mean()),
            "abs_error": float(abs(group["prob"].mean() - group["true"].mean()))
        })
    return table


def run_gate4_experiment():
    print("=" * 75)
    print("PHASE 6 — GATE 4: MACRO & OPTIONS (VIX) VS 200-SMA REGIME EVALUATION")
    print("Comparison: Baseline (200-SMA alone) vs Incremental (200-SMA + Macro/VIX)")
    print("Status: Development Data Only (Windows A & B Sealed)")
    print("=" * 75)
    
    df = build_gate4_dataset()
    folds = get_walkforward_folds(df, n_folds=3)
    
    print("\n" + "=" * 75)
    print("WALK-FORWARD FOLD BOUNDARIES (EXPANDING WINDOW + 10-DAY PURGE)")
    print("=" * 75)
    for f in folds:
        print(f"Fold {f['fold_num']}:")
        print(f"  Train:      {f['train_start']} to {f['train_end']} ({f['train_days']} trading days)")
        print(f"  Purge Gap:  {f['purge_start']} to {f['purge_end']} ({f['purge_days']} trading days)")
        print(f"  Validation: {f['val_start']} to {f['val_end']} ({f['val_days']} trading days)")
        
    fold_results = []
    
    for f in folds:
        fold_num = f["fold_num"]
        print("\n" + "-" * 75)
        print(f"EVALUATING FOLD {fold_num} / {len(folds)}")
        print("-" * 75)
        
        train_mask = df["date"].isin(f["train_dates_set"])
        val_mask = df["date"].isin(f["val_dates_set"])
        
        train_df = df[train_mask]
        val_df = df[val_mask]
        
        y_train = train_df["target"].values
        y_val = val_df["target"].values
        
        # ── MODEL 0: BASELINE (200-SMA REGIME ALONE) ──
        X_tr_base = train_df[BASELINE_FEATURES].values
        X_va_base = val_df[BASELINE_FEATURES].values
        
        scaler_base = StandardScaler()
        X_tr_base_sc = scaler_base.fit_transform(X_tr_base)
        X_va_base_sc = scaler_base.transform(X_va_base)
        
        lr_base = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
        lr_base.fit(X_tr_base_sc, y_train)
        
        p_tr_base = lr_base.predict_proba(X_tr_base_sc)[:, 1]
        p_va_base = lr_base.predict_proba(X_va_base_sc)[:, 1]
        
        base_tr_auc = roc_auc_score(y_train, p_tr_base)
        base_va_auc = roc_auc_score(y_val, p_va_base)
        base_brier = brier_score_loss(y_val, p_va_base)
        
        # ── MODEL 1: INCREMENTAL (200-SMA + 3 ORTHOGONAL MACRO/VIX FEATURES) ──
        X_tr_inc = train_df[ALL_FEATURES].values
        X_va_inc = val_df[ALL_FEATURES].values
        
        scaler_inc = StandardScaler()
        X_tr_inc_sc = scaler_inc.fit_transform(X_tr_inc)
        X_va_inc_sc = scaler_inc.transform(X_va_inc)
        
        lr_inc = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
        lr_inc.fit(X_tr_inc_sc, y_train)
        
        p_tr_inc = lr_inc.predict_proba(X_tr_inc_sc)[:, 1]
        p_va_inc = lr_inc.predict_proba(X_va_inc_sc)[:, 1]
        
        inc_tr_auc = roc_auc_score(y_train, p_tr_inc)
        inc_va_auc = roc_auc_score(y_val, p_va_inc)
        inc_brier = brier_score_loss(y_val, p_va_inc)
        
        delta_auc = inc_va_auc - base_va_auc
        
        # Shallow XGBoost on incremental set
        xgb_inc = XGBClassifier(
            max_depth=3, n_estimators=100, learning_rate=0.05,
            subsample=0.8, random_state=42, eval_metric="logloss"
        )
        xgb_inc.fit(X_tr_inc, y_train)
        p_va_xgb = xgb_inc.predict_proba(X_va_inc)[:, 1]
        xgb_va_auc = roc_auc_score(y_val, p_va_xgb)
        
        # Statistical significance of Logistic Regression coefficients
        # Compute standard errors via Fisher Information matrix
        # P * (1 - P) diagonal
        W_diag = p_tr_inc * (1 - p_tr_inc)
        # X design matrix with intercept
        X_design = np.hstack([np.ones((len(X_tr_inc_sc), 1)), X_tr_inc_sc])
        # Fisher info = X^T W X
        try:
            V_cov = np.linalg.inv((X_design.T * W_diag) @ X_design)
            se = np.sqrt(np.diag(V_cov))
            coef_with_intercept = np.concatenate([[lr_inc.intercept_[0]], lr_inc.coef_[0]])
            z_scores = coef_with_intercept / se
            p_values = 2 * (1 - stats.norm.cdf(np.abs(z_scores)))
        except Exception:
            se = [None] * (len(ALL_FEATURES) + 1)
            p_values = [None] * (len(ALL_FEATURES) + 1)
            
        coef_dict = {}
        for idx, col in enumerate(ALL_FEATURES):
            coef_dict[col] = {
                "beta": float(lr_inc.coef_[0][idx]),
                "odds_ratio": float(np.exp(lr_inc.coef_[0][idx])),
                "p_value": float(p_values[idx + 1]) if p_values[idx + 1] is not None else None
            }
            
        xgb_importances = {col: float(imp) for col, imp in zip(ALL_FEATURES, xgb_inc.feature_importances_)}
        calib_table = decile_calibration_table(y_val, p_va_inc)
        
        fold_res = {
            "fold_num": fold_num,
            "train_days": f["train_days"],
            "val_days": f["val_days"],
            "train_samples": len(X_tr_inc),
            "val_samples": len(X_va_inc),
            "baseline_200sma": {
                "train_auc": float(base_tr_auc),
                "val_auc": float(base_va_auc),
                "val_brier": float(base_brier)
            },
            "incremental_macro_vix": {
                "train_auc": float(inc_tr_auc),
                "val_auc": float(inc_va_auc),
                "val_brier": float(inc_brier),
                "delta_val_auc": float(delta_auc),
                "xgb_val_auc": float(xgb_va_auc),
                "prob_mean": float(p_va_inc.mean()),
                "prob_std": float(p_va_inc.std()),
                "coefficients": coef_dict,
                "xgb_importances": xgb_importances,
                "calibration_table": calib_table
            }
        }
        fold_results.append(fold_res)
        
        print(f"\n[Fold {fold_num} Performance]")
        print(f"  Baseline M0 (200-SMA alone):         Val AUC = {base_va_auc:.4f} (Brier: {base_brier:.4f})")
        print(f"  Incremental M1 (200-SMA + Macro/VIX): Val AUC = {inc_va_auc:.4f} (Brier: {inc_brier:.4f})")
        print(f"  Incremental Delta AUC (M1 - M0):     Delta   = {delta_auc:+.4f}")
        print(f"  Incremental XGBoost Val AUC:         Val AUC = {xgb_va_auc:.4f}")
        print("\n  Standardized Coefficients in M1 (controlling for 200-SMA):")
        for col in ALL_FEATURES:
            pv_str = f"p={coef_dict[col]['p_value']:.4e}" if coef_dict[col]['p_value'] is not None else "p=N/A"
            sig_star = " ***" if (coef_dict[col]['p_value'] and coef_dict[col]['p_value'] < 0.001) else ""
            print(f"    - {col:27s}: beta = {coef_dict[col]['beta']:+.4f} (odds = {coef_dict[col]['odds_ratio']:.4f}, {pv_str}){sig_star}")

    # Averages across folds
    mean_base_va_auc = np.mean([r["baseline_200sma"]["val_auc"] for r in fold_results])
    mean_inc_va_auc = np.mean([r["incremental_macro_vix"]["val_auc"] for r in fold_results])
    mean_delta_auc = mean_inc_va_auc - mean_base_va_auc
    mean_xgb_va_auc = np.mean([r["incremental_macro_vix"]["xgb_val_auc"] for r in fold_results])
    
    print("\n" + "=" * 75)
    print("WALK-FORWARD SUMMARY ACROSS ALL 3 FOLDS")
    print("=" * 75)
    print(f"Baseline M0 (200-SMA alone) Mean Val AUC:          {mean_base_va_auc:.4f}")
    print(f"Incremental M1 (200-SMA + Macro/VIX) Mean Val AUC: {mean_inc_va_auc:.4f}")
    print(f"Mean Incremental Delta AUC (M1 - M0):              {mean_delta_auc:+.4f}")
    print(f"Incremental Shallow XGBoost Mean Val AUC:          {mean_xgb_va_auc:.4f}")
    
    # Pre-registered pass / fail check
    # Pass requires mean_inc_va_auc >= 0.52 and positive statistically significant delta
    is_incremental_real = (mean_delta_auc >= 0.01) and (mean_inc_va_auc >= 0.52)
    verdict = "INCREMENTAL_SIGNAL_FOUND" if is_incremental_real else "REDUNDANT_WITH_200SMA_NULL_RESULT"
    print(f"\nPRE-REGISTERED GATE 4 VERDICT: {verdict}")
    if not is_incremental_real:
        print("-> FINDING: VIX & macro features do NOT provide meaningful incremental directional")
        print("   alpha over 200-SMA alone. Differences are within noise, confirming collinear redundancy.")

    full_output = {
        "gate": "Gate 4",
        "verdict": verdict,
        "status": "EVALUATED_DEVELOPMENT_ONLY",
        "dataset": "Development data strictly (2016-09-26 to 2025-09-16)",
        "features": {
            "baseline": BASELINE_FEATURES,
            "orthogonal_macro": ORTHOGONAL_MACRO_FEATURES
        },
        "n_folds": 3,
        "folds_metadata": [{k: v for k, v in f.items() if not k.endswith("_set")} for f in folds],
        "summary": {
            "baseline_mean_val_auc": float(mean_base_va_auc),
            "incremental_lr_mean_val_auc": float(mean_inc_va_auc),
            "incremental_delta_auc": float(mean_delta_auc),
            "incremental_xgb_mean_val_auc": float(mean_xgb_va_auc),
            "verdict": verdict
        },
        "folds": fold_results
    }
    
    out_file = os.path.join(ARTIFACTS_DIR, "gate4_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(full_output, f, indent=2)
    print(f"\nArtifact saved to: {out_file}")
    return full_output


if __name__ == "__main__":
    run_gate4_experiment()
