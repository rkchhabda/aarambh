"""
Verification backtest engine for Track A Ensemble on Nifty 100 universe.
Runs cleanly on Python 3.14 + Windows:
- Keeps date as string (avoids Python 3.14 pandas to_datetime C-level crash)
- Sets n_jobs=1 on scikit-learn models (avoids multiprocessing deadlock)
- Suppresses ChainedAssignmentError warnings
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"

import sys
import json
import warnings
warnings.filterwarnings("ignore")
import joblib
import numpy as np
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS_DIR = os.path.join(BASE_DIR, "service", "models")
DATA_DIR = os.path.join(BASE_DIR, "data", "multi")
OUT_DIR = os.path.join(BASE_DIR, "scripts", "verification")

def main():
    print("=" * 85)
    print("TRACK A ENSEMBLE VERIFICATION BACKTEST ON NIFTY 100 UNIVERSE")
    print("=" * 85)
    
    # 1. Load models
    print("[1] Loading production model artifacts from service/models/...")
    with open(os.path.join(MODELS_DIR, "features.json")) as f:
        manifest = json.load(f)
    features = manifest["features"]
    manifest_threshold = manifest.get("threshold", 0.55)
    
    xgb = joblib.load(os.path.join(MODELS_DIR, "xgboost.pkl"))
    rf = joblib.load(os.path.join(MODELS_DIR, "randomforest.pkl"))
    rf.n_jobs = 1
    lr = joblib.load(os.path.join(MODELS_DIR, "logisticregression.pkl"))
    lr.n_jobs = 1
    meta = joblib.load(os.path.join(MODELS_DIR, "meta_model.pkl"))
    meta.n_jobs = 1
    scaler = joblib.load(os.path.join(MODELS_DIR, "scaler.pkl"))
    
    print(f"    Features ({len(features)}): {features}")
    print(f"    Manifest Threshold: {manifest_threshold}")
    
    # 2. Load historical series to compute true rolling 200-SMA
    print("[2] Loading continuous historical prices for 200-day SMA regime filter...")
    cols = ["date", "ticker", "Close"]
    t_hist = pd.read_csv(os.path.join(DATA_DIR, "train_multi_v2_5d.csv"), usecols=cols)
    v_hist = pd.read_csv(os.path.join(DATA_DIR, "val_multi_v2_5d.csv"), usecols=cols)
    te_hist = pd.read_csv(os.path.join(DATA_DIR, "test_multi_v2_5d.csv"), usecols=cols)
    
    full_hist = pd.concat([t_hist, v_hist, te_hist], ignore_index=True)
    full_hist = full_hist.sort_values(["ticker", "date"]).reset_index(drop=True)
    
    print("    Computing rolling 200-day SMA and 1-day forward returns per ticker...")
    sma_records = []
    for ticker, group in full_hist.groupby("ticker", sort=False):
        group = group.copy()
        c_series = group["Close"]
        sma_200 = c_series.rolling(200).mean().values
        fwd_1d = (c_series.shift(-1) / c_series - 1.0).values
        d_vals = group["date"].values
        t_vals = group["ticker"].values
        for i in range(len(group)):
            sma_records.append((t_vals[i], d_vals[i], sma_200[i], fwd_1d[i]))
            
    sma_df = pd.DataFrame(sma_records, columns=["ticker", "date", "sma_200", "fwd_ret_1d"])
    
    # 3. Load full test split
    print("[3] Loading held-out test split data...")
    test_df = pd.read_csv(os.path.join(DATA_DIR, "test_multi_v2_5d.csv"))
    
    test_df = pd.merge(test_df, sma_df, on=["ticker", "date"], how="left")
    test_df["above_sma200"] = test_df["Close"] > test_df["sma_200"]
    
    # Generate ensemble predictions
    print("[4] Generating production ensemble predictions on test split...")
    X = test_df[features].fillna(0).values
    Xs = scaler.transform(X)
    p_xgb = xgb.predict_proba(Xs)[:, 1]
    p_rf = rf.predict_proba(Xs)[:, 1]
    p_lr = lr.predict_proba(Xs)[:, 1]
    stack = np.column_stack([p_xgb, p_rf, p_lr])
    test_df["p_meta"] = meta.predict_proba(stack)[:, 1]
    
    test_dates = sorted(test_df["date"].unique())
    n_days = len(test_dates)
    n_tickers = test_df["ticker"].nunique()
    print(f"    Test Range: {test_dates[0]} to {test_dates[-1]}")
    print(f"    Trading Sessions: {n_days}, Tickers: {n_tickers}, Total Test Rows: {len(test_df)}")
    
    def run_portfolio_sim(df_slice, thr, use_regime, cost_bps):
        df_s = df_slice.copy()
        if use_regime:
            df_s["pos"] = ((df_s["p_meta"] > thr) & (df_s["above_sma200"] == True)).astype(float)
        else:
            df_s["pos"] = (df_s["p_meta"] > thr).astype(float)
            
        pos_mat = df_s.pivot(index="date", columns="ticker", values="pos").fillna(0.0)
        ret_mat = df_s.pivot(index="date", columns="ticker", values="fwd_ret_1d").fillna(0.0)
        
        idx = pos_mat.index.intersection(ret_mat.index)
        pos_mat = pos_mat.loc[idx]
        ret_mat = ret_mat.loc[idx]
        
        N = pos_mat.shape[1]
        
        pos_diff = pos_mat.diff().abs()
        pos_diff.iloc[0] = pos_mat.iloc[0].abs()
        daily_trades = int((pos_diff > 0.0).sum().sum())
        
        daily_gross = (pos_mat * ret_mat).sum(axis=1) / N
        daily_costs = (pos_diff.sum(axis=1) * (cost_bps / 10000.0)) / N
        daily_net = daily_gross - daily_costs
        daily_exp = pos_mat.mean(axis=1)
        
        r = daily_net.values
        valid = ~np.isnan(r)
        r = r[valid]
        daily_exp = daily_exp.values[valid]
        
        eq = np.cumprod(1.0 + r)
        total_ret = (eq[-1] - 1.0) * 100.0 if len(eq) > 0 else 0.0
        ann_ret = np.mean(r) * 252.0 * 100.0
        vol = np.std(r) * np.sqrt(252.0)
        sharpe = (ann_ret / 100.0) / vol if vol > 1e-8 else 0.0
        
        cummax = np.maximum.accumulate(eq)
        dd = (eq / cummax) - 1.0
        max_dd = np.min(dd) * 100.0 if len(dd) > 0 else 0.0
        
        active = daily_exp > 1e-6
        win_rate = (r[active] > 0).mean() * 100.0 if active.sum() > 0 else 0.0
        exposure = np.mean(daily_exp) * 100.0
        
        return {
            "total_ret_pct": round(float(total_ret), 2),
            "ann_ret_pct": round(float(ann_ret), 2),
            "sharpe": round(float(sharpe), 3),
            "max_dd_pct": round(float(max_dd), 2),
            "win_rate_pct": round(float(win_rate), 2),
            "trade_count": daily_trades,
            "avg_exposure_pct": round(float(exposure), 2)
        }

    def run_bh(df_slice):
        ret_mat = df_slice.pivot(index="date", columns="ticker", values="fwd_ret_1d").fillna(0.0)
        daily_ret = ret_mat.mean(axis=1).values
        valid = ~np.isnan(daily_ret)
        r = daily_ret[valid]
        
        eq = np.cumprod(1.0 + r)
        total_ret = (eq[-1] - 1.0) * 100.0 if len(eq) > 0 else 0.0
        ann_ret = np.mean(r) * 252.0 * 100.0
        vol = np.std(r) * np.sqrt(252.0)
        sharpe = (ann_ret / 100.0) / vol if vol > 1e-8 else 0.0
        
        cummax = np.maximum.accumulate(eq)
        dd = (eq / cummax) - 1.0
        max_dd = np.min(dd) * 100.0 if len(dd) > 0 else 0.0
        win_rate = (r > 0).mean() * 100.0
        
        return {
            "total_ret_pct": round(float(total_ret), 2),
            "ann_ret_pct": round(float(ann_ret), 2),
            "sharpe": round(float(sharpe), 3),
            "max_dd_pct": round(float(max_dd), 2),
            "win_rate_pct": round(float(win_rate), 2),
            "trade_count": ret_mat.shape[1],
            "avg_exposure_pct": 100.00
        }

    print("\n[5] Executing full test period backtests...")
    results = {}
    
    # Buy & Hold Benchmark
    results["Buy & Hold Benchmark (Equal-Weight Universe)"] = run_bh(test_df)
    
    # Scenarios across Regime Filter x Thresholds x Costs
    for reg in [True, False]:
        reg_name = "With Regime Filter (SMA200)" if reg else "No Regime Filter"
        for thr in [0.50, manifest_threshold]:
            for bps in [5.0, 15.0]:
                scen_name = f"Track A ({reg_name}, Thr={thr:.2f}, Cost={int(bps)}bps)"
                results[scen_name] = run_portfolio_sim(test_df, thr=thr, use_regime=reg, cost_bps=bps)

    print("\n[6] Executing 4-Period Chronological Walk-Forward Breakdown...")
    q_len = n_days // 4
    subperiods = [
        ("Sub-Period 1 (Q1)", test_dates[0:q_len]),
        ("Sub-Period 2 (Q2)", test_dates[q_len:2*q_len]),
        ("Sub-Period 3 (Q3)", test_dates[2*q_len:3*q_len]),
        ("Sub-Period 4 (Q4)", test_dates[3*q_len:]),
    ]
    
    subperiod_results = {}
    for name, q_dates in subperiods:
        q_slice = test_df[test_df["date"].isin(q_dates)]
        d_start = q_dates[0]
        d_end = q_dates[-1]
        
        strat_q = run_portfolio_sim(q_slice, thr=0.55, use_regime=True, cost_bps=15.0)
        bh_q = run_bh(q_slice)
        
        subperiod_results[f"{name} [{d_start} -> {d_end}] Track A (Thr=0.55, 15bps)"] = strat_q
        subperiod_results[f"{name} [{d_start} -> {d_end}] Buy & Hold Benchmark"] = bh_q

    print("\n" + "=" * 105)
    print(f"{'SCENARIO':<58} {'Return%':>8} {'Sharpe':>7} {'MaxDD%':>8} {'WinRate%':>9} {'Trades':>7} {'Exp%':>7}")
    print("-" * 105)
    for name, s in results.items():
        print(f"{name:<58} {s['total_ret_pct']:>8.2f} {s['sharpe']:>7.3f} {s['max_dd_pct']:>8.2f} {s['win_rate_pct']:>9.2f} {s['trade_count']:>7d} {s['avg_exposure_pct']:>7.2f}")
    print("-" * 105)
    for name, s in subperiod_results.items():
        print(f"{name:<58} {s['total_ret_pct']:>8.2f} {s['sharpe']:>7.3f} {s['max_dd_pct']:>8.2f} {s['win_rate_pct']:>9.2f} {s['trade_count']:>7d} {s['avg_exposure_pct']:>7.2f}")
    print("=" * 105)
    
    out_payload = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "target_universe": "Nifty 100 Indian Equities",
            "tickers_count": n_tickers,
            "test_start_date": test_dates[0],
            "test_end_date": test_dates[-1],
            "trading_days": n_days,
            "features": features,
            "manifest_threshold": manifest_threshold
        },
        "scenarios": results,
        "subperiods": subperiod_results
    }
    
    out_file = os.path.join(OUT_DIR, "backtest_results.json")
    with open(out_file, "w") as f:
        json.dump(out_payload, f, indent=2)
    print(f"\n[OK] Results successfully saved to: {out_file}")

if __name__ == "__main__":
    main()
