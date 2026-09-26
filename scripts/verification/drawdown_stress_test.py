"""
Long-Horizon Drawdown & Regime Filter Stress Test on Nifty 100 Equities.

Tests:
1. Pure 200-SMA regime filter (long if Close > SMA200, flat otherwise) across 1,006 post-warmup trading sessions (2022-08-04 to 2026-08-27, ~4.06 years).
2. Four non-overlapping ~1-year windows:
   - Window 1: 2022-08-04 to 2023-08-08 (251 sessions) - 2022/2023 consolidation & breakout
   - Window 2: 2023-08-09 to 2024-08-14 (251 sessions) - 2023/2024 massive Indian bull run
   - Window 3: 2024-08-16 to 2025-08-20 (251 sessions) - Late cycle / all-time-high rally & correction
   - Window 4: 2025-08-21 to 2026-08-27 (253 sessions) - 2025/2026 sideways chop & correction
3. Full multi-year period (2022-08-04 to 2026-08-27, 1006 sessions).
4. Cycle recovery metrics: peak-to-peak return, max drawdown, time to recover (underwater duration in trading days).
5. Cost tiers: 0 bps (frictionless baseline), 5 bps (institutional), and 15 bps (retail).
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"

import sys
import json
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data", "multi")
OUT_DIR = os.path.join(BASE_DIR, "scripts", "verification")

def compute_drawdown_series(returns):
    eq = np.cumprod(1.0 + returns)
    cummax = np.maximum.accumulate(eq)
    dd = (eq / cummax) - 1.0
    return eq, dd

def analyze_recovery(returns):
    """
    Computes peak-to-peak metrics:
    - Maximum drawdown duration (longest streak in days from peak until new high)
    - Average drawdown duration
    - Total days spent in drawdown (>1% underwater)
    """
    eq, dd = compute_drawdown_series(returns)
    underwater = dd < -0.0001
    
    # Calculate duration of every drawdown episode
    durations = []
    current_dur = 0
    for is_under in underwater:
        if is_under:
            current_dur += 1
        else:
            if current_dur > 0:
                durations.append(current_dur)
            current_dur = 0
    if current_dur > 0:
        durations.append(current_dur)
        
    max_recovery_days = max(durations) if durations else 0
    avg_recovery_days = float(np.mean(durations)) if durations else 0.0
    pct_time_underwater = float(np.mean(underwater) * 100.0)
    
    return {
        "max_drawdown_duration_days": int(max_recovery_days),
        "avg_drawdown_duration_days": round(avg_recovery_days, 1),
        "pct_time_underwater": round(pct_time_underwater, 1)
    }

def calc_stats(daily_net, daily_exp, trade_counts):
    r = daily_net.copy()
    valid = ~np.isnan(r)
    r = r[valid]
    daily_exp = daily_exp[valid]
    
    eq, dd = compute_drawdown_series(r)
    total_ret = (eq[-1] - 1.0) * 100.0 if len(eq) > 0 else 0.0
    ann_ret = np.mean(r) * 252.0 * 100.0
    vol = np.std(r) * np.sqrt(252.0)
    sharpe = (ann_ret / 100.0) / vol if vol > 1e-8 else 0.0
    max_dd = np.min(dd) * 100.0 if len(dd) > 0 else 0.0
    
    active = daily_exp > 1e-6
    win_rate = (r[active] > 0).mean() * 100.0 if active.sum() > 0 else 0.0
    exposure = np.mean(daily_exp) * 100.0
    trades = int(np.sum(trade_counts))
    
    rec_metrics = analyze_recovery(r)
    
    return {
        "total_ret_pct": round(float(total_ret), 2),
        "ann_ret_pct": round(float(ann_ret), 2),
        "sharpe": round(float(sharpe), 3),
        "max_dd_pct": round(float(max_dd), 2),
        "win_rate_pct": round(float(win_rate), 2),
        "trade_count": trades,
        "avg_exposure_pct": round(float(exposure), 2),
        **rec_metrics
    }

def main():
    print("=" * 90)
    print("PART 1: STRESS-TESTING THE 200-SMA REGIME FILTER DRAWDOWN CLAIM")
    print("=" * 90)
    
    # 1. Load data
    print("[1] Loading all historical splits for 138 Nifty 100 tickers...")
    cols = ["date", "ticker", "Close"]
    t_hist = pd.read_csv(os.path.join(DATA_DIR, "train_multi_v2_5d.csv"), usecols=cols)
    v_hist = pd.read_csv(os.path.join(DATA_DIR, "val_multi_v2_5d.csv"), usecols=cols)
    te_hist = pd.read_csv(os.path.join(DATA_DIR, "test_multi_v2_5d.csv"), usecols=cols)
    
    full_hist = pd.concat([t_hist, v_hist, te_hist], ignore_index=True)
    full_hist = full_hist.sort_values(["ticker", "date"]).reset_index(drop=True)
    
    print("[2] Computing continuous 200-day SMA and next-day returns per ticker...")
    records = []
    for ticker, group in full_hist.groupby("ticker", sort=False):
        group = group.copy()
        c = group["Close"]
        sma_200 = c.rolling(200).mean().values
        fwd_1d = (c.shift(-1) / c - 1.0).values
        d_vals = group["date"].values
        t_vals = group["ticker"].values
        for i in range(len(group)):
            records.append((t_vals[i], d_vals[i], sma_200[i], fwd_1d[i], c.iloc[i]))
            
    df = pd.DataFrame(records, columns=["ticker", "date", "sma_200", "fwd_ret_1d", "Close"])
    
    # Filter to post-warmup dates (where 200 SMA has formed)
    all_dates = sorted(df["date"].unique())
    post_warmup_dates = all_dates[200:]
    df_active = df[df["date"].isin(post_warmup_dates)].copy()
    df_active["above_sma200"] = df_active["Close"] > df_active["sma_200"]
    
    print(f"    Full Evaluated Span: {post_warmup_dates[0]} to {post_warmup_dates[-1]}")
    print(f"    Total Sessions: {len(post_warmup_dates)}, Universe: {df_active['ticker'].nunique()} tickers")
    
    # Split into 4 non-overlapping ~1-year windows (approx 251 trading days per year)
    w1_dates = post_warmup_dates[0:251]
    w2_dates = post_warmup_dates[251:502]
    w3_dates = post_warmup_dates[502:753]
    w4_dates = post_warmup_dates[753:]
    
    windows = [
        ("Window 1 (2022-2023 Consolidation)", w1_dates),
        ("Window 2 (2023-2024 Bull Rally)", w2_dates),
        ("Window 3 (2024-2025 Market Peak)", w3_dates),
        ("Window 4 (2025-2026 Late Cycle Chop)", w4_dates),
        ("Full Multi-Year Cycle (2022-2026)", post_warmup_dates),
    ]
    
    def simulate(df_sub, use_filter=True, cost_bps=15.0):
        df_s = df_sub.copy()
        if use_filter:
            df_s["pos"] = df_s["above_sma200"].astype(float)
        else:
            df_s["pos"] = 1.0
            
        pos_mat = df_s.pivot(index="date", columns="ticker", values="pos").fillna(0.0)
        ret_mat = df_s.pivot(index="date", columns="ticker", values="fwd_ret_1d").fillna(0.0)
        
        idx = pos_mat.index.intersection(ret_mat.index)
        pos_mat = pos_mat.loc[idx]
        ret_mat = ret_mat.loc[idx]
        
        N = pos_mat.shape[1]
        pos_diff = pos_mat.diff().abs()
        pos_diff.iloc[0] = pos_mat.iloc[0].abs()
        
        daily_trades = (pos_diff > 0.0).sum(axis=1).values
        daily_gross = (pos_mat * ret_mat).sum(axis=1) / N
        daily_costs = (pos_diff.sum(axis=1) * (cost_bps / 10000.0)) / N
        daily_net = daily_gross - daily_costs
        daily_exp = pos_mat.mean(axis=1)
        
        return calc_stats(daily_net.values, daily_exp.values, daily_trades)

    all_window_results = {}
    
    print("\n[3] Running Simulation across all 4 Non-Overlapping Windows + Full Cycle...")
    for win_name, win_d in windows:
        sub = df_active[df_active["date"].isin(win_d)]
        start_d, end_d = win_d[0], win_d[-1]
        lbl = f"{win_name} [{start_d} -> {end_d}]"
        
        # Benchmark
        bh_stats = simulate(sub, use_filter=False, cost_bps=0.0)
        
        # Regime Filter at 0 bps, 5 bps, 15 bps
        rf_0bps = simulate(sub, use_filter=True, cost_bps=0.0)
        rf_5bps = simulate(sub, use_filter=True, cost_bps=5.0)
        rf_15bps = simulate(sub, use_filter=True, cost_bps=15.0)
        
        all_window_results[lbl] = {
            "buy_and_hold": bh_stats,
            "regime_filter_0bps": rf_0bps,
            "regime_filter_5bps": rf_5bps,
            "regime_filter_15bps": rf_15bps,
        }

    # Print Table
    print("\n" + "=" * 115)
    print(f"{'WINDOW & SCENARIO':<52} {'Return%':>8} {'Sharpe':>7} {'MaxDD%':>8} {'Win%':>6} {'Exp%':>6} {'MaxDD Dur':>10} {'Underwater%':>12}")
    print("-" * 115)
    
    for lbl, data in all_window_results.items():
        bh = data["buy_and_hold"]
        rf15 = data["regime_filter_15bps"]
        rf5 = data["regime_filter_5bps"]
        
        print(f"--- {lbl} ---")
        print(f"  {'Buy & Hold Benchmark (Equal-Weight)':<50} {bh['total_ret_pct']:>8.2f} {bh['sharpe']:>7.3f} {bh['max_dd_pct']:>8.2f} {bh['win_rate_pct']:>6.1f} {bh['avg_exposure_pct']:>6.1f} {bh['max_drawdown_duration_days']:>9d}d {bh['pct_time_underwater']:>11.1f}%")
        print(f"  {'Regime Filter (SMA200) @ 5bps cost':<50} {rf5['total_ret_pct']:>8.2f} {rf5['sharpe']:>7.3f} {rf5['max_dd_pct']:>8.2f} {rf5['win_rate_pct']:>6.1f} {rf5['avg_exposure_pct']:>6.1f} {rf5['max_drawdown_duration_days']:>9d}d {rf5['pct_time_underwater']:>11.1f}%")
        print(f"  {'Regime Filter (SMA200) @ 15bps retail cost':<50} {rf15['total_ret_pct']:>8.2f} {rf15['sharpe']:>7.3f} {rf15['max_dd_pct']:>8.2f} {rf15['win_rate_pct']:>6.1f} {rf15['avg_exposure_pct']:>6.1f} {rf15['max_drawdown_duration_days']:>9d}d {rf15['pct_time_underwater']:>11.1f}%")
        
        dd_ratio = abs(bh['max_dd_pct']) / (abs(rf15['max_dd_pct']) + 1e-6)
        print(f"  >> Drawdown Reduction: {bh['max_dd_pct']:.2f}% vs {rf15['max_dd_pct']:.2f}% ({dd_ratio:.2f}x reduction) | Return: {bh['total_ret_pct']:+.2f}% vs {rf15['total_ret_pct']:+.2f}%\n")
    print("=" * 115)
    
    out_payload = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "target_universe": "Nifty 100 Indian Equities",
            "tickers_count": df_active["ticker"].nunique(),
            "full_start_date": post_warmup_dates[0],
            "full_end_date": post_warmup_dates[-1],
            "total_trading_days": len(post_warmup_dates),
        },
        "windows": all_window_results
    }
    
    out_file = os.path.join(OUT_DIR, "drawdown_stress_test_results.json")
    with open(out_file, "w") as f:
        json.dump(out_payload, f, indent=2)
    print(f"\n[OK] Complete results artifact saved to: {out_file}")

if __name__ == "__main__":
    main()
