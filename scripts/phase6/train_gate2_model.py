"""Gate 2: First Model Iteration on Month 1 Cross-Sectional Features.

Pre-Registration Context:
- Governing Document: docs/RESEARCH_PREREGISTRATION.md & docs/RESEARCH_PREREGISTRATION_AMENDMENT_1.md
- Gate: Gate 2 (Month 2 milestone per Amendment 1 Section G)
- Scope: Development data only (2016-09-26 to 2025-09-16).
- Windows A and B are SEALED and NOT touched.
- Data Loading: Exclusively via scripts.phase6.data_loader.
- Features: ONLY relative_ret_5d, relative_ret_5d_vs_index, sector_rank_pct.
- Models: Logistic Regression (L2 regularized) + Shallow XGBoost (max_depth=3).
- Split: 3 sequential walk-forward expanding folds with 10-day purge gaps.
"""

import json
import os
import sys
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from scripts.phase6.data_loader import load_development_features

ARTIFACTS_DIR = os.path.join(BASE_DIR, "phase6_artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

FEATURE_COLS = ["relative_ret_5d", "relative_ret_5d_vs_index", "sector_rank_pct"]


def build_labeled_dataset() -> pd.DataFrame:
    """Load development features via data loader and compute 5-day directional target."""
    print("Loading development features strictly through scripts.phase6.data_loader...")
    df = load_development_features()
    print(f"Loaded {len(df):,} raw development rows across {df['ticker'].nunique()} tickers.")
    
    # Sort strictly chronologically per ticker
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)
    
    # Compute 5-day forward return: (Close_{t+5} - Close_t) / Close_t
    # shift(-5) per ticker looks 5 trading days forward
    df["fwd_ret_5d"] = df.groupby("ticker")["Close"].shift(-5) / df["Close"] - 1.0
    
    # Binary classification target: 1 if positive return, 0 otherwise
    df["target"] = (df["fwd_ret_5d"] > 0).astype(float)
    
    # Drop rows where target is NaN (last 5 trading days per ticker) or any feature is NaN
    valid_mask = df["target"].notna() & df[FEATURE_COLS].notna().all(axis=1)
    df_clean = df[valid_mask].copy()
    df_clean["target"] = df_clean["target"].astype(int)
    
    # Sort by date for walk-forward time splits
    df_clean = df_clean.sort_values(["date", "ticker"]).reset_index(drop=True)
    print(f"Clean labeled dataset: {len(df_clean):,} rows from {df_clean['date'].min()} to {df_clean['date'].max()}.")
    print(f"Overall positive base rate: {df_clean['target'].mean():.4f} ({df_clean['target'].sum():,} / {len(df_clean):,})")
    return df_clean


def get_walkforward_folds(df: pd.DataFrame, n_folds: int = 3):
    """Generate sequential expanding-window folds with 10-day purge gaps."""
    dates = sorted(df["date"].unique())
    total_dates = len(dates)
    
    # 3 folds: ~237 trading days (~1 year) per validation fold
    # 10 trading days purge gap before each validation fold
    val_len = 237
    purge_len = 10
    
    folds = []
    for i in range(n_folds):
        # i=0: fold 1; i=1: fold 2; i=2: fold 3 (ending at latest date)
        # Offset from end
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
    # Use qcut with duplicates='drop'
    try:
        df_eval["decile"] = pd.qcut(df_eval["prob"], q=n_bins, labels=False, duplicates="drop") + 1
    except Exception:
        df_eval["decile"] = pd.cut(df_eval["prob"], bins=n_bins, labels=False) + 1
        
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


def run_gate2_experiment():
    print("=" * 70)
    print("PHASE 6 — GATE 2: FIRST MODEL WALK-FORWARD EVALUATION")
    print("Features in Scope: ONLY relative_ret_5d, relative_ret_5d_vs_index, sector_rank_pct")
    print("Status: Development Data Only (Windows A & B Sealed)")
    print("=" * 70)
    
    df = build_labeled_dataset()
    folds = get_walkforward_folds(df, n_folds=3)
    
    print("\n" + "=" * 70)
    print("WALK-FORWARD FOLD BOUNDARIES (EXPANDING WINDOW + 10-DAY PURGE)")
    print("=" * 70)
    for f in folds:
        print(f"Fold {f['fold_num']}:")
        print(f"  Train:      {f['train_start']} to {f['train_end']} ({f['train_days']} trading days)")
        print(f"  Purge Gap:  {f['purge_start']} to {f['purge_end']} ({f['purge_days']} trading days)")
        print(f"  Validation: {f['val_start']} to {f['val_end']} ({f['val_days']} trading days)")
    
    lr_results = []
    xgb_results = []
    
    for f in folds:
        fold_num = f["fold_num"]
        print("\n" + "-" * 70)
        print(f"TRAINING FOLD {fold_num} / {len(folds)}")
        print("-" * 70)
        
        train_mask = df["date"].isin(f["train_dates_set"])
        val_mask = df["date"].isin(f["val_dates_set"])
        
        train_df = df[train_mask]
        val_df = df[val_mask]
        
        X_train_raw = train_df[FEATURE_COLS].values
        y_train = train_df["target"].values
        X_val_raw = val_df[FEATURE_COLS].values
        y_val = val_df["target"].values
        
        print(f"Train samples: {len(X_train_raw):,} (Base rate: {y_train.mean():.4f})")
        print(f"Val samples:   {len(X_val_raw):,} (Base rate: {y_val.mean():.4f})")
        
        # Standardize features (fitted strictly on train fold)
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train_raw)
        X_val_scaled = scaler.transform(X_val_raw)
        
        # ── 1. LOGISTIC REGRESSION ──
        lr = LogisticRegression(penalty="l2", C=1.0, max_iter=1000, random_state=42)
        lr.fit(X_train_scaled, y_train)
        
        lr_train_prob = lr.predict_proba(X_train_scaled)[:, 1]
        lr_val_prob = lr.predict_proba(X_val_scaled)[:, 1]
        
        lr_train_auc = roc_auc_score(y_train, lr_train_prob)
        lr_val_auc = roc_auc_score(y_val, lr_val_prob)
        lr_brier = brier_score_loss(y_val, lr_val_prob)
        lr_calib = decile_calibration_table(y_val, lr_val_prob)
        
        lr_coefs = {col: float(coef) for col, coef in zip(FEATURE_COLS, lr.coef_[0])}
        lr_odds = {col: float(np.exp(coef)) for col, coef in zip(FEATURE_COLS, lr.coef_[0])}
        
        lr_fold_res = {
            "fold_num": fold_num,
            "train_days": f["train_days"],
            "val_days": f["val_days"],
            "train_samples": len(X_train_raw),
            "val_samples": len(X_val_raw),
            "train_base_rate": float(y_train.mean()),
            "val_base_rate": float(y_val.mean()),
            "train_auc": float(lr_train_auc),
            "val_auc": float(lr_val_auc),
            "val_brier": float(lr_brier),
            "prob_mean": float(lr_val_prob.mean()),
            "prob_std": float(lr_val_prob.std()),
            "prob_min": float(lr_val_prob.min()),
            "prob_max": float(lr_val_prob.max()),
            "intercept": float(lr.intercept_[0]),
            "coefficients": lr_coefs,
            "odds_ratios": lr_odds,
            "calibration_table": lr_calib
        }
        lr_results.append(lr_fold_res)
        
        print(f"\n[Logistic Regression - Fold {fold_num}]")
        print(f"  Train AUC: {lr_train_auc:.4f} | Val AUC: {lr_val_auc:.4f} | Brier: {lr_brier:.4f}")
        print(f"  Probabilities: mean={lr_val_prob.mean():.4f}, std={lr_val_prob.std():.4f}, min={lr_val_prob.min():.4f}, max={lr_val_prob.max():.4f}")
        print("  Standardized Coefficients:")
        for col in FEATURE_COLS:
            print(f"    - {col:25s}: beta = {lr_coefs[col]:+.4f} (odds ratio = {lr_odds[col]:.4f})")
            
        # ── 2. SHALLOW XGBOOST ──
        xgb = XGBClassifier(
            max_depth=3,
            n_estimators=100,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=1.0,
            random_state=42,
            eval_metric="logloss"
        )
        xgb.fit(X_train_raw, y_train)
        
        xgb_train_prob = xgb.predict_proba(X_train_raw)[:, 1]
        xgb_val_prob = xgb.predict_proba(X_val_raw)[:, 1]
        
        xgb_train_auc = roc_auc_score(y_train, xgb_train_prob)
        xgb_val_auc = roc_auc_score(y_val, xgb_val_prob)
        xgb_brier = brier_score_loss(y_val, xgb_val_prob)
        xgb_calib = decile_calibration_table(y_val, xgb_val_prob)
        
        xgb_importances = {col: float(imp) for col, imp in zip(FEATURE_COLS, xgb.feature_importances_)}
        
        xgb_fold_res = {
            "fold_num": fold_num,
            "train_days": f["train_days"],
            "val_days": f["val_days"],
            "train_samples": len(X_train_raw),
            "val_samples": len(X_val_raw),
            "train_auc": float(xgb_train_auc),
            "val_auc": float(xgb_val_auc),
            "val_brier": float(xgb_brier),
            "prob_mean": float(xgb_val_prob.mean()),
            "prob_std": float(xgb_val_prob.std()),
            "prob_min": float(xgb_val_prob.min()),
            "prob_max": float(xgb_val_prob.max()),
            "feature_importances": xgb_importances,
            "calibration_table": xgb_calib
        }
        xgb_results.append(xgb_fold_res)
        
        print(f"\n[Shallow XGBoost - Fold {fold_num}]")
        print(f"  Train AUC: {xgb_train_auc:.4f} | Val AUC: {xgb_val_auc:.4f} | Brier: {xgb_brier:.4f}")
        print(f"  Probabilities: mean={xgb_val_prob.mean():.4f}, std={xgb_val_prob.std():.4f}, min={xgb_val_prob.min():.4f}, max={xgb_val_prob.max():.4f}")
        print("  Feature Importances (gain):")
        for col in FEATURE_COLS:
            print(f"    - {col:25s}: {xgb_importances[col]:.4f}")

    # Compute averages
    lr_mean_val_auc = np.mean([r["val_auc"] for r in lr_results])
    lr_mean_train_auc = np.mean([r["train_auc"] for r in lr_results])
    xgb_mean_val_auc = np.mean([r["val_auc"] for r in xgb_results])
    xgb_mean_train_auc = np.mean([r["train_auc"] for r in xgb_results])
    
    print("\n" + "=" * 70)
    print("WALK-FORWARD SUMMARY ACROSS ALL 3 FOLDS")
    print("=" * 70)
    print(f"Logistic Regression: Mean Train AUC = {lr_mean_train_auc:.4f} | Mean Val AUC = {lr_mean_val_auc:.4f}")
    for r in lr_results:
        print(f"  Fold {r['fold_num']}: Train AUC = {r['train_auc']:.4f}, Val AUC = {r['val_auc']:.4f}, Prob Std = {r['prob_std']:.4f}")
        
    print(f"\nShallow XGBoost:     Mean Train AUC = {xgb_mean_train_auc:.4f} | Mean Val AUC = {xgb_mean_val_auc:.4f}")
    for r in xgb_results:
        print(f"  Fold {r['fold_num']}: Train AUC = {r['train_auc']:.4f}, Val AUC = {r['val_auc']:.4f}, Prob Std = {r['prob_std']:.4f}")

    # Save summary artifact
    full_output = {
        "gate": "Gate 2",
        "dataset": "Development data strictly (2016-09-26 to 2025-09-16)",
        "features": FEATURE_COLS,
        "n_folds": 3,
        "folds_metadata": [{k: v for k, v in f.items() if not k.endswith("_set")} for f in folds],
        "logistic_regression": {
            "mean_train_auc": float(lr_mean_train_auc),
            "mean_val_auc": float(lr_mean_val_auc),
            "folds": lr_results
        },
        "xgboost": {
            "mean_train_auc": float(xgb_mean_train_auc),
            "mean_val_auc": float(xgb_mean_val_auc),
            "folds": xgb_results
        }
    }
    
    out_file = os.path.join(ARTIFACTS_DIR, "gate2_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(full_output, f, indent=2)
    print(f"\nArtifact saved to: {out_file}")
    
    return full_output


if __name__ == "__main__":
    run_gate2_experiment()
