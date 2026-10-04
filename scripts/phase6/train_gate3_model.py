"""Gate 3: Pre-Registered Fundamental (SUE) vs Technical Alpha Evaluation.

Governing Documents:
- docs/RESEARCH_PREREGISTRATION.md (Section 1, 3.2, 4, 5, 6)
- docs/RESEARCH_PREREGISTRATION_AMENDMENT_1.md (Section G: Gate 3)
- docs/GATE_3_SOURCING_REPORT.md (Sections 7, 8.5)

Pre-Registered Hypotheses & Protocol:
1. Evaluation Universe:
   - 133 tickers with valid XBRL quarterly disclosures.
   - 5 tickers excluded entirely per pre-registration decision in Section 8.5:
     HDFCLIFE.NS, SBILIFE.NS, ICICIGI.NS, ICICIPRULI.NS, NESTLEIND.NS.
2. Development Window:
   - Narrowed window: 2018-01-01 to 2025-09-16 (development cutoff).
   - Windows A & B remain strictly sealed.
3. Feature Sets Evaluated:
   - M0 (Cross-Sectional Baseline): relative_ret_5d, relative_ret_5d_vs_index, sector_rank_pct
   - M1 (Incremental Fundamental): M0 features + sue (Standardized Unexpected Earnings)
   - M_SUE (Pure Fundamental Factor): sue alone
4. Fold-Specific Winsorization (Zero Lookahead Discipline):
   - SUE is winsorized at 1st and 99th percentiles computed STRICTLY on each fold's train split.
   - Validation split is clipped using the training fold's thresholds.
5. Models & Evaluation:
   - Logistic Regression (L2 regularized) + Shallow XGBoost (max_depth=3).
   - 3 sequential expanding walk-forward folds with 10-day purge gaps.
   - Validation AUC, Brier Score, and 5-day Backtest Sharpe net of 15 bps round-trip transaction costs.
   - Section 1 Criteria Table & Welch's t-test vs. Buy & Hold.
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

from scripts.phase6.data_loader import load_development_features
from features.universe import TICKERS

ARTIFACTS_DIR = os.path.join(BASE_DIR, "phase6_artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

SUE_CSV = os.path.join(BASE_DIR, "data", "fundamentals", "sue_features_quarterly.csv")
EXCLUDED_TICKERS = {"HDFCLIFE.NS", "SBILIFE.NS", "ICICIGI.NS", "ICICIPRULI.NS", "NESTLEIND.NS"}

BASELINE_FEATURES = ["relative_ret_5d", "relative_ret_5d_vs_index", "sector_rank_pct"]
INCREMENTAL_FEATURES = BASELINE_FEATURES + ["sue"]
SUE_ONLY_FEATURES = ["sue"]


def build_gate3_dataset() -> pd.DataFrame:
    """Load development relative features and merge point-in-time quarterly SUE."""
    print("Loading development features strictly through scripts.phase6.data_loader...")
    # Development window: 2018-01-01 to 2025-09-16
    df = load_development_features(start_date="2018-01-01", end_date="2025-09-16")
    
    # Exclude the 5 tickers without compliant depth per Section 8.5
    df = df[~df["ticker"].isin(EXCLUDED_TICKERS)].copy()
    print(f"Loaded {len(df):,} daily feature records across {df['ticker'].nunique()} tickers (2018–2025).")

    # Load SUE quarterly records
    sue_df = pd.read_csv(SUE_CSV)
    sue_df = sue_df[~sue_df["ticker"].isin(EXCLUDED_TICKERS)].copy()
    sue_df = sue_df[sue_df["sue"].notna()][["ticker", "effective_date", "sue"]].copy()
    sue_df = sue_df.rename(columns={"effective_date": "date"})
    sue_df = sue_df.sort_values(["ticker", "date"]).reset_index(drop=True)
    print(f"Loaded {len(sue_df):,} usable quarterly SUE records across {sue_df['ticker'].nunique()} tickers.")

    # Sort daily df strictly chronologically per ticker
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    # Merge SUE into daily trading series point-in-time
    # Merge on ticker and date, then forward-fill SUE per ticker
    merged = pd.merge(df, sue_df, on=["ticker", "date"], how="left")
    merged = merged.sort_values(["ticker", "date"]).reset_index(drop=True)
    merged["sue"] = merged.groupby("ticker")["sue"].ffill()

    # Compute 5-day forward return: (Close_{t+5} - Close_t) / Close_t
    merged["fwd_ret_5d"] = merged.groupby("ticker")["Close"].shift(-5) / merged["Close"] - 1.0

    # Require non-null observable forward return, valid active SUE feature, and baseline features
    # NOTE: fwd_ret_5d must be strictly non-null BEFORE computing target, otherwise the final 5
    # trading days (unobservable future return past cutoff) produce NaN > 0 => False => 0.0,
    # corrupting Fold 3 with 665 artificial zero targets and NaN forward returns.
    req_cols = ["fwd_ret_5d", "sue"] + BASELINE_FEATURES
    clean_mask = merged[req_cols].notna().all(axis=1)
    df_clean = merged[clean_mask].copy()
    df_clean["target"] = (df_clean["fwd_ret_5d"] > 0).astype(int)

    df_clean = df_clean.sort_values(["date", "ticker"]).reset_index(drop=True)
    print(f"Clean labeled Gate 3 dataset: {len(df_clean):,} rows across {df_clean['date'].nunique()} trading dates.")
    print(f"Date range: {df_clean['date'].min()} to {df_clean['date'].max()} ({df_clean['ticker'].nunique()} tickers)")
    print(f"Positive target base rate: {df_clean['target'].mean():.4f} ({df_clean['target'].sum():,} / {len(df_clean):,})")
    return df_clean


def get_walkforward_folds(df: pd.DataFrame, n_folds: int = 3):
    """Generate sequential expanding-window folds with 10-day purge gaps."""
    dates = sorted(df["date"].unique())
    total_dates = len(dates)

    # 3 folds: ~240 trading days (~1 year) per validation fold
    val_len = 240
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


def run_gate3_experiment():
    print("=" * 70)
    print("PHASE 6 — GATE 3: FUNDAMENTAL (SUE) WALK-FORWARD ALPHA EVALUATION")
    print("Scope: Development Data Only (2018-01-01 to 2025-09-16)")
    print("Excluded Tickers (5):", sorted(list(EXCLUDED_TICKERS)))
    print("=" * 70)

    df = build_gate3_dataset()
    folds = get_walkforward_folds(df, n_folds=3)

    print("\n" + "=" * 70)
    print("WALK-FORWARD FOLD BOUNDARIES (EXPANDING WINDOW + 10-DAY PURGE)")
    print("=" * 70)
    for f in folds:
        print(f"Fold {f['fold_num']}:")
        print(f"  Train:      {f['train_start']} to {f['train_end']} ({f['train_days']} trading days)")
        print(f"  Purge Gap:  {f['purge_start']} to {f['purge_end']} ({f['purge_days']} trading days)")
        print(f"  Validation: {f['val_start']} to {f['val_end']} ({f['val_days']} trading days)")

    fold_evaluations = []

    for f in folds:
        fold_num = f["fold_num"]
        print("\n" + "-" * 70)
        print(f"EVALUATING FOLD {fold_num} / {len(folds)}")
        print("-" * 70)

        train_mask = df["date"].isin(f["train_dates_set"])
        val_mask = df["date"].isin(f["val_dates_set"])

        train_df = df[train_mask].copy()
        val_df = df[val_mask].copy()

        y_train = train_df["target"].values
        y_val = val_df["target"].values
        fwd_ret_val = val_df["fwd_ret_5d"].values

        # ── FOLD-SPECIFIC WINSORIZATION OF SUE (STRICT ZERO LOOKAHEAD) ──
        p01 = train_df["sue"].quantile(0.01)
        p99 = train_df["sue"].quantile(0.99)
        print(f"Fold {fold_num} Train SUE Winsorization Bounds: [{p01:.4f}, {p99:.4f}]")

        train_df["sue_win"] = train_df["sue"].clip(lower=p01, upper=p99)
        val_df["sue_win"] = val_df["sue"].clip(lower=p01, upper=p99)

        # ── 1. MODEL 0: BASELINE CROSS-SECTIONAL FEATURES ──
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

        # ── 2. MODEL 1: INCREMENTAL FUNDAMENTAL (BASELINE + SUE) ──
        inc_cols = BASELINE_FEATURES + ["sue_win"]
        X_tr_inc = train_df[inc_cols].values
        X_va_inc = val_df[inc_cols].values

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
        p_tr_xgb = xgb_inc.predict_proba(X_tr_inc)[:, 1]
        p_va_xgb = xgb_inc.predict_proba(X_va_inc)[:, 1]
        xgb_tr_auc = roc_auc_score(y_train, p_tr_xgb)
        xgb_va_auc = roc_auc_score(y_val, p_va_xgb)

        # ── 3. MODEL SUE-ONLY (STANDALONE FUNDAMENTAL FACTOR) ──
        X_tr_sue = train_df[["sue_win"]].values
        X_va_sue = val_df[["sue_win"]].values
        scaler_sue = StandardScaler()
        X_tr_sue_sc = scaler_sue.fit_transform(X_tr_sue)
        X_va_sue_sc = scaler_sue.transform(X_va_sue)

        lr_sue = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
        lr_sue.fit(X_tr_sue_sc, y_train)
        p_va_sue = lr_sue.predict_proba(X_va_sue_sc)[:, 1]
        sue_only_auc = roc_auc_score(y_val, p_va_sue)

        # Statistical significance of Logistic Regression coefficients (Fisher Information)
        W_diag = p_tr_inc * (1 - p_tr_inc)
        X_design = np.hstack([np.ones((len(X_tr_inc_sc), 1)), X_tr_inc_sc])
        try:
            V_cov = np.linalg.inv((X_design.T * W_diag) @ X_design)
            se = np.sqrt(np.diag(V_cov))
            coef_with_intercept = np.concatenate([[lr_inc.intercept_[0]], lr_inc.coef_[0]])
            z_scores = coef_with_intercept / se
            p_values = 2 * (1 - stats.norm.cdf(np.abs(z_scores)))
        except Exception:
            se = [None] * (len(inc_cols) + 1)
            p_values = [None] * (len(inc_cols) + 1)

        coef_dict = {}
        for idx, col in enumerate(inc_cols):
            coef_dict[col] = {
                "beta": float(lr_inc.coef_[0][idx]),
                "odds_ratio": float(np.exp(lr_inc.coef_[0][idx])),
                "p_value": float(p_values[idx + 1]) if p_values[idx + 1] is not None else None
            }

        # ── 4. BACKTEST SHARPE RATIO & ECONOMIC SIGNIFICANCE ──
        # Strategy: Buy top quintile / top decile of predicted probability
        # Holding period: 5 trading days. Cost deduction: 15 bps (0.0015) round trip
        cost_bps = 0.0015
        
        # Benchmark Buy & Hold on same validation fold
        bh_rets = fwd_ret_val
        bh_mean = np.mean(bh_rets)
        bh_std = np.std(bh_rets)
        bh_sharpe = (bh_mean / bh_std) * np.sqrt(252 / 5) if bh_std > 0 else 0.0

        # Model Strategy: Long when P > top 20% threshold of validation predictions
        top20_thresh = np.percentile(p_va_inc, 80)
        strat_mask = p_va_inc >= top20_thresh
        strat_rets = fwd_ret_val[strat_mask] - cost_bps
        strat_mean = np.mean(strat_rets) if len(strat_rets) > 0 else 0.0
        strat_std = np.std(strat_rets) if len(strat_rets) > 0 else 0.0
        strat_sharpe = (strat_mean / strat_std) * np.sqrt(252 / 5) if strat_std > 0 else 0.0

        # Welch's t-test strategy vs Buy & Hold
        t_stat, p_val_welch = stats.ttest_ind(strat_rets, bh_rets, equal_var=False)

        # Cohen's d effect size
        pooled_std = np.sqrt((strat_std**2 + bh_std**2) / 2) if (strat_std + bh_std) > 0 else 1.0
        cohens_d = (strat_mean - bh_mean) / pooled_std

        print(f"\n[Fold {fold_num} Performance]")
        print(f"  M0 Baseline (Cross-Sectional): Val AUC = {base_va_auc:.4f} | Brier = {base_brier:.4f}")
        print(f"  M1 Incremental (+ SUE):         Val AUC = {inc_va_auc:.4f} | Delta AUC = {delta_auc:+.4f}")
        print(f"  M_SUE Standalone (SUE only):    Val AUC = {sue_only_auc:.4f}")
        print(f"  XGBoost Incremental (+ SUE):    Val AUC = {xgb_va_auc:.4f}")
        print(f"  Strategy Sharpe (net 15bps):    {strat_sharpe:.4f} vs Buy&Hold: {bh_sharpe:.4f}")
        print(f"  Welch's t-test p-value:         {p_val_welch:.4e} | Cohen's d: {cohens_d:+.4f}")
        print("  Logistic Regression Coefficients:")
        for col in inc_cols:
            p_str = f"p={coef_dict[col]['p_value']:.4e}" if coef_dict[col]['p_value'] else "p=N/A"
            print(f"    - {col:25s}: beta = {coef_dict[col]['beta']:+.4f} | {p_str}")

        fold_res = {
            "fold_num": fold_num,
            "train_days": f["train_days"],
            "val_days": f["val_days"],
            "train_samples": len(X_tr_inc),
            "val_samples": len(X_va_inc),
            "winsorization_bounds": {"p01": float(p01), "p99": float(p99)},
            "baseline_m0": {"train_auc": float(base_tr_auc), "val_auc": float(base_va_auc), "brier": float(base_brier)},
            "incremental_m1": {
                "train_auc": float(inc_tr_auc), "val_auc": float(inc_va_auc), "delta_auc": float(delta_auc),
                "xgb_val_auc": float(xgb_va_auc), "brier": float(inc_brier),
                "coefficients": coef_dict
            },
            "standalone_sue": {"val_auc": float(sue_only_auc)},
            "economic_metrics": {
                "strategy_sharpe_net": float(strat_sharpe),
                "buy_and_hold_sharpe": float(bh_sharpe),
                "delta_sharpe": float(strat_sharpe - bh_sharpe),
                "cohens_d": float(cohens_d),
                "welch_t_stat": float(t_stat) if pd.notna(t_stat) else None,
                "welch_p_val": float(p_val_welch) if pd.notna(p_val_welch) else None
            },
            "calibration_table": decile_calibration_table(y_val, p_va_inc)
        }
        fold_evaluations.append(fold_res)

    # Aggregate Walk-Forward Summary
    m0_mean_val_auc = np.mean([f["baseline_m0"]["val_auc"] for f in fold_evaluations])
    m1_mean_val_auc = np.mean([f["incremental_m1"]["val_auc"] for f in fold_evaluations])
    m1_mean_train_auc = np.mean([f["incremental_m1"]["train_auc"] for f in fold_evaluations])
    xgb_mean_val_auc = np.mean([f["incremental_m1"]["xgb_val_auc"] for f in fold_evaluations])
    sue_mean_val_auc = np.mean([f["standalone_sue"]["val_auc"] for f in fold_evaluations])
    delta_mean_auc = m1_mean_val_auc - m0_mean_val_auc

    mean_strat_sharpe = np.mean([f["economic_metrics"]["strategy_sharpe_net"] for f in fold_evaluations])
    mean_bh_sharpe = np.mean([f["economic_metrics"]["buy_and_hold_sharpe"] for f in fold_evaluations])
    mean_cohens_d = np.mean([f["economic_metrics"]["cohens_d"] for f in fold_evaluations])

    # 95% Confidence Interval for Mean Val AUC
    val_aucs = [f["incremental_m1"]["val_auc"] for f in fold_evaluations]
    auc_ci_lower = float(np.mean(val_aucs) - 1.96 * (np.std(val_aucs) / np.sqrt(len(val_aucs))))
    auc_ci_upper = float(np.mean(val_aucs) + 1.96 * (np.std(val_aucs) / np.sqrt(len(val_aucs))))

    print("\n" + "=" * 70)
    print("GATE 3 WALK-FORWARD SUMMARY ACROSS ALL 3 FOLDS")
    print("=" * 70)
    print(f"M0 Baseline (Cross-Sectional): Mean Val AUC = {m0_mean_val_auc:.4f}")
    print(f"M1 Incremental (+ SUE):        Mean Val AUC = {m1_mean_val_auc:.4f} (95% CI: [{auc_ci_lower:.4f}, {auc_ci_upper:.4f}])")
    print(f"  Delta AUC over Baseline:     {delta_mean_auc:+.4f}")
    print(f"M_SUE Standalone (SUE only):   Mean Val AUC = {sue_mean_val_auc:.4f}")
    print(f"XGBoost Incremental (+ SUE):   Mean Val AUC = {xgb_mean_val_auc:.4f}")
    print(f"\nEconomic Significance:")
    print(f"  Strategy Sharpe (net 15bps): {mean_strat_sharpe:.4f}")
    print(f"  Buy & Hold Sharpe:           {mean_bh_sharpe:.4f}")
    print(f"  Cohen's d Effect Size:       {mean_cohens_d:+.4f}")

    # Section 1 Criteria Check
    pass_auc = (m1_mean_val_auc >= 0.56) and (auc_ci_lower >= 0.53)
    pass_sharpe = (mean_strat_sharpe >= 0.8) and (mean_strat_sharpe > mean_bh_sharpe)
    pass_cohen = mean_cohens_d >= 0.10
    pass_stability = all(f["incremental_m1"]["val_auc"] > 0.50 for f in fold_evaluations)
    gate3_verdict = "PASS" if (pass_auc and pass_sharpe and pass_cohen and pass_stability) else "NULL / NO EDGE"

    print("\n" + "=" * 70)
    print("SECTION 1 PRE-REGISTRATION CRITERIA AUDIT TABLE")
    print("=" * 70)
    print(f"1. Validation AUC >= 0.56 (95% CI lower >= 0.53): {m1_mean_val_auc:.4f} [{auc_ci_lower:.4f}, {auc_ci_upper:.4f}] -> {'PASS' if pass_auc else 'FAIL'}")
    print(f"2. Net Sharpe >= 0.8 & > Buy&Hold:                {mean_strat_sharpe:.4f} vs {mean_bh_sharpe:.4f} -> {'PASS' if pass_sharpe else 'FAIL'}")
    print(f"3. Economic Effect Size Cohen's d >= 0.10:        {mean_cohens_d:+.4f} -> {'PASS' if pass_cohen else 'FAIL'}")
    print(f"4. Stability across folds:                        {[round(f['incremental_m1']['val_auc'], 4) for f in fold_evaluations]} -> {'PASS' if pass_stability else 'FAIL'}")
    print(f"\nGATE 3 OVERALL VERDICT: {gate3_verdict}")

    full_results = {
        "gate": "Gate 3",
        "timestamp": "2026-09-30",
        "universe_size": 133,
        "excluded_tickers": list(EXCLUDED_TICKERS),
        "development_window": "2018-01-01 to 2025-09-16",
        "baseline_features": BASELINE_FEATURES,
        "incremental_features": INCREMENTAL_FEATURES,
        "folds": fold_evaluations,
        "summary": {
            "m0_baseline_mean_val_auc": float(m0_mean_val_auc),
            "m1_incremental_mean_val_auc": float(m1_mean_val_auc),
            "m1_incremental_mean_train_auc": float(m1_mean_train_auc),
            "delta_mean_val_auc": float(delta_mean_auc),
            "m_sue_standalone_mean_val_auc": float(sue_mean_val_auc),
            "xgb_incremental_mean_val_auc": float(xgb_mean_val_auc),
            "auc_95_ci_lower": float(auc_ci_lower),
            "auc_95_ci_upper": float(auc_ci_upper),
            "strategy_sharpe_net": float(mean_strat_sharpe),
            "buy_and_hold_sharpe": float(mean_bh_sharpe),
            "mean_cohens_d": float(mean_cohens_d),
            "section_1_criteria": {
                "auc_threshold_met": bool(pass_auc),
                "sharpe_threshold_met": bool(pass_sharpe),
                "effect_size_met": bool(pass_cohen),
                "stability_met": bool(pass_stability),
                "overall_verdict": gate3_verdict
            }
        }
    }

    out_file = os.path.join(ARTIFACTS_DIR, "gate3_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(full_results, f, indent=2)
    print(f"\nGate 3 results artifact saved to: {out_file}")
    return full_results


if __name__ == "__main__":
    run_gate3_experiment()
