"""
COVID & Long-Horizon (10-Year) Stress Test on Nifty 100 Equities.
Tests:
1. Pure 200-SMA regime filter (long if Close > SMA200, flat otherwise).
2. COVID Crash window (2020-01-01 to 2020-04-30) and Full COVID Year (2020-01-01 to 2020-12-31).
3. Pre-COVID Bull/Consolidation (2017-08-01 to 2019-12-31).
4. Post-COVID Bull & Late Cycle (2021-01-01 to 2026-08-27).
5. Full 9-Year Cycle (2017-08-01 to 2026-08-27).
6. Metrics: Total Return, Ann Return, Max Drawdown, Sharpe, Sortino, Calmar, Ulcer Index.
7. Rolling 126-day windows across the full 9-year dataset with distinct market drawdown event clustering.
8. Cost tiers: 0 bps, 5 bps, 15 bps.
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
sys.path.insert(0, BASE_DIR)

DATA_FILE = os.path.join(BASE_DIR, "data", "multi", "historical_10y_raw.csv")
OUT_FILE = os.path.join(BASE_DIR, "scripts", "verification", "covid_stress_test_results.json")

def compute_drawdown_series(returns):
    eq = np.cumprod(1.0 + returns)
    cummax = np.maximum.accumulate(eq)
    dd = (eq / cummax) - 1.0
    return eq, dd

def compute_sortino(returns, mar=0.0):
    excess = returns - (mar / 252.0)
    downside = excess[excess < 0]
    if len(downside) == 0:
        return 0.0
    downside_dev = np.sqrt(np.mean(downside ** 2)) * np.sqrt(252.0)
    ann_excess = np.mean(excess) * 252.0
    return float(ann_excess / downside_dev) if downside_dev > 1e-8 else 0.0

def compute_calmar(ann_ret_pct, max_dd_pct):
    mdd_abs = abs(max_dd_pct)
    if mdd_abs < 1e-4:
        return 0.0
    return float(ann_ret_pct / mdd_abs)

def compute_ulcer_index(dd_series):
    dd_pct = dd_series * 100.0
    return float(np.sqrt(np.mean(dd_pct ** 2)))

def analyze_recovery(returns):
    eq, dd = compute_drawdown_series(returns)
    underwater = dd < -0.0001
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
    
    sortino = compute_sortino(r)
    calmar = compute_calmar(ann_ret, max_dd)
    ulcer = compute_ulcer_index(dd)
    
    active = daily_exp > 1e-6
    win_rate = (r[active] > 0).mean() * 100.0 if active.sum() > 0 else 0.0
    exposure = np.mean(daily_exp) * 100.0
    trades = int(np.sum(trade_counts))
    
    rec_metrics = analyze_recovery(r)
    
    return {
        "total_ret_pct": round(float(total_ret), 2),
        "ann_ret_pct": round(float(ann_ret), 2),
        "sharpe": round(float(sharpe), 3),
        "sortino": round(float(sortino), 3),
        "calmar": round(float(calmar), 3),
        "ulcer_index": round(float(ulcer), 3),
        "max_dd_pct": round(float(max_dd), 2),
        "win_rate_pct": round(float(win_rate), 2),
        "trade_count": trades,
        "avg_exposure_pct": round(float(exposure), 2),
        **rec_metrics
    }

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
    daily_turnover = pos_diff.sum(axis=1) / N
    
    trade_counts = (pos_diff > 0.5).sum(axis=1)
    
    daily_gross = (pos_mat * ret_mat).sum(axis=1) / N
    cost_drag = daily_turnover * (cost_bps / 10000.0)
    daily_net = daily_gross - cost_drag
    daily_exp = pos_mat.mean(axis=1)
    
    return calc_stats(daily_net.values, daily_exp.values, trade_counts.values)

def main():
    print("=" * 80)
    print("COVID-19 & 10-YEAR EXTENDED DRAWDOWN STRESS TEST")
    print("=" * 80)
    
    if not os.path.exists(DATA_FILE):
        print(f"ERROR: {DATA_FILE} does not exist. Run backfill first.")
        sys.exit(1)
        
    print(f"[1] Loading raw 10-year data from {DATA_FILE}...")
    df_raw = pd.read_csv(DATA_FILE)
    print(f"    Loaded {len(df_raw)} rows, {df_raw['ticker'].nunique()} tickers.")
    print(f"    Date span: {df_raw['date'].min()} to {df_raw['date'].max()}")
    
    print("[2] Computing continuous 200-day SMA and next-day returns per ticker...")
    records = []
    for ticker, group in df_raw.groupby("ticker", sort=False):
        group = group.sort_values("date").reset_index(drop=True)
        c = group["Close"]
        sma_200 = c.rolling(200).mean().values
        fwd_1d = (c.shift(-1) / c - 1.0).values
        d_vals = group["date"].values
        t_vals = group["ticker"].values
        for i in range(len(group)):
            records.append((t_vals[i], d_vals[i], sma_200[i], fwd_1d[i], c.iloc[i]))
            
    df = pd.DataFrame(records, columns=["ticker", "date", "sma_200", "fwd_ret_1d", "Close"])
    
    all_dates = sorted(df["date"].unique())
    # 200 sessions warmup
    post_warmup_dates = all_dates[200:]
    df_active = df[df["date"].isin(post_warmup_dates)].copy()
    df_active["above_sma200"] = df_active["Close"] > df_active["sma_200"]
    
    earliest_trading_date = post_warmup_dates[0]
    latest_trading_date = post_warmup_dates[-1]
    print(f"    Post-warmup span: {earliest_trading_date} to {latest_trading_date} ({len(post_warmup_dates)} trading sessions)")
    
    # Define test windows
    covid_crash_dates = [d for d in post_warmup_dates if "2020-01-01" <= d <= "2020-04-30"]
    covid_full_dates = [d for d in post_warmup_dates if "2020-01-01" <= d <= "2020-12-31"]
    pre_covid_dates = [d for d in post_warmup_dates if d < "2020-01-01"]
    post_covid_dates = [d for d in post_warmup_dates if d >= "2021-01-01"]
    
    named_windows = [
        ("COVID Crash Window [2020-01-01 -> 2020-04-30]", covid_crash_dates),
        ("COVID Full Year (Crash + Rebound) [2020-01-01 -> 2020-12-31]", covid_full_dates),
        ("Pre-COVID Bull/Consolidation [2017-08 -> 2019-12-31]", pre_covid_dates),
        ("Post-COVID Bull & Late Cycle [2021-01-01 -> 2026-08-27]", post_covid_dates),
        ("Full Extended 9-Year Cycle [2017-08 -> 2026-08-27]", post_warmup_dates),
    ]
    
    results = {
        "metadata": {
            "script": "covid_stress_test.py",
            "timestamp": datetime.now().isoformat(),
            "target_universe": "Nifty 100 Indian Equities",
            "tickers_count": int(df_active["ticker"].nunique()),
            "earliest_raw_date": df_raw["date"].min(),
            "earliest_trading_date": earliest_trading_date,
            "latest_trading_date": latest_trading_date,
            "total_trading_days": len(post_warmup_dates),
            "covid_covered": True,
            "cost_tiers": ["0bps", "5bps", "15bps"]
        },
        "windows": {}
    }
    
    print("\n" + "=" * 80)
    print("WINDOW RESULTS SUMMARY")
    print("=" * 80)
    
    for w_name, w_dates in named_windows:
        if not w_dates:
            continue
        df_sub = df_active[df_active["date"].isin(w_dates)]
        bh = simulate(df_sub, use_filter=False, cost_bps=0.0)
        rf_0 = simulate(df_sub, use_filter=True, cost_bps=0.0)
        rf_5 = simulate(df_sub, use_filter=True, cost_bps=5.0)
        rf_15 = simulate(df_sub, use_filter=True, cost_bps=15.0)
        
        dd_ratio_15 = round(abs(bh["max_dd_pct"]) / abs(rf_15["max_dd_pct"]), 3) if abs(rf_15["max_dd_pct"]) > 1e-4 else 0.0
        
        results["windows"][w_name] = {
            "start_date": w_dates[0],
            "end_date": w_dates[-1],
            "trading_sessions": len(w_dates),
            "dd_reduction_ratio_15bps": dd_ratio_15,
            "buy_and_hold": bh,
            "regime_filter_0bps": rf_0,
            "regime_filter_5bps": rf_5,
            "regime_filter_15bps": rf_15
        }
        
        print(f"\n>>> {w_name}")
        print(f"    Sessions: {len(w_dates)} | Span: {w_dates[0]} to {w_dates[-1]}")
        print(f"    Buy & Hold    : Ret={bh['total_ret_pct']}%, MaxDD={bh['max_dd_pct']}%, Sharpe={bh['sharpe']}, Sortino={bh['sortino']}, Calmar={bh['calmar']}, Ulcer={bh['ulcer_index']}")
        print(f"    Regime (0bps) : Ret={rf_0['total_ret_pct']}%, MaxDD={rf_0['max_dd_pct']}%, Sharpe={rf_0['sharpe']}, Sortino={rf_0['sortino']}, Calmar={rf_0['calmar']}, Ulcer={rf_0['ulcer_index']}")
        print(f"    Regime (5bps) : Ret={rf_5['total_ret_pct']}%, MaxDD={rf_5['max_dd_pct']}%, Sharpe={rf_5['sharpe']}, Sortino={rf_5['sortino']}, Calmar={rf_5['calmar']}, Ulcer={rf_5['ulcer_index']}")
        print(f"    Regime (15bps): Ret={rf_15['total_ret_pct']}%, MaxDD={rf_15['max_dd_pct']}%, Sharpe={rf_15['sharpe']}, Sortino={rf_15['sortino']}, Calmar={rf_15['calmar']}, Ulcer={rf_15['ulcer_index']}")
        print(f"    --> DD Reduction Ratio (15bps): {dd_ratio_15}x")

    # Rolling window analysis across 9 years: 126-day window, 21-day step
    print("\n" + "=" * 80)
    print("ROLLING 126-DAY WINDOW ANALYSIS (9-YEAR SPAN)")
    print("=" * 80)
    
    W_LEN = 126
    W_STEP = 21
    rolling_rows = []
    
    for start_i in range(0, len(post_warmup_dates) - W_LEN + 1, W_STEP):
        w_d = post_warmup_dates[start_i:start_i + W_LEN]
        df_sub = df_active[df_active["date"].isin(w_d)]
        bh_w = simulate(df_sub, use_filter=False, cost_bps=0.0)
        rf_w = simulate(df_sub, use_filter=True, cost_bps=15.0)
        
        bh_dd = bh_w["max_dd_pct"]
        rf_dd = rf_w["max_dd_pct"]
        ratio = round(abs(bh_dd) / abs(rf_dd), 4) if abs(rf_dd) > 1e-4 else 1.0
        
        rolling_rows.append({
            "start": w_d[0],
            "end": w_d[-1],
            "bh_max_dd_pct": bh_dd,
            "rf_max_dd_pct": rf_dd,
            "bh_total_ret_pct": bh_w["total_ret_pct"],
            "rf_total_ret_pct": rf_w["total_ret_pct"],
            "bh_sharpe": bh_w["sharpe"],
            "rf_sharpe": rf_w["sharpe"],
            "bh_sortino": bh_w["sortino"],
            "rf_sortino": rf_w["sortino"],
            "bh_calmar": bh_w["calmar"],
            "rf_calmar": rf_w["calmar"],
            "bh_ulcer": bh_w["ulcer_index"],
            "rf_ulcer": rf_w["ulcer_index"],
            "dd_reduction_ratio": ratio,
            "filter_reduces_drawdown": abs(rf_dd) < abs(bh_dd)
        })
        
    ratios = [r["dd_reduction_ratio"] for r in rolling_rows]
    reduces = [r["filter_reduces_drawdown"] for r in rolling_rows]
    
    # Distinct Drawdown Event Clustering:
    # Cluster windows that share the identical (bh_max_dd_pct, rf_max_dd_pct)
    clusters = {}
    for i, w in enumerate(rolling_rows):
        key = (w["bh_max_dd_pct"], w["rf_max_dd_pct"])
        if key not in clusters:
            clusters[key] = []
        clusters[key].append(i + 1)
        
    rolling_summary = {
        "total_rolling_windows": len(rolling_rows),
        "distinct_dd_value_pairs": len(clusters),
        "dd_ratio_mean": round(float(np.mean(ratios)), 4),
        "dd_ratio_median": round(float(np.median(ratios)), 4),
        "dd_ratio_std": round(float(np.std(ratios)), 4),
        "dd_ratio_min": round(float(np.min(ratios)), 4),
        "dd_ratio_max": round(float(np.max(ratios)), 4),
        "dd_ratio_p25": round(float(np.percentile(ratios, 25)), 4),
        "dd_ratio_p75": round(float(np.percentile(ratios, 75)), 4),
        "windows_filter_reduces_dd": int(sum(reduces)),
        "pct_filter_reduces_dd": round(float(np.mean(reduces) * 100.0), 2)
    }
    
    results["rolling_window_analysis"] = {
        "summary": rolling_summary,
        "distinct_event_clusters": [
            {
                "window_indices": idxs,
                "window_count": len(idxs),
                "bh_max_dd_pct": key[0],
                "rf_max_dd_pct": key[1],
                "dd_reduction_ratio": round(abs(key[0]) / abs(key[1]), 4) if abs(key[1]) > 1e-4 else 1.0,
                "span_start": rolling_rows[idxs[0] - 1]["start"],
                "span_end": rolling_rows[idxs[-1] - 1]["end"]
            }
            for key, idxs in clusters.items()
        ],
        "all_windows": rolling_rows
    }
    
    print(f"Total rolling windows: {len(rolling_rows)}")
    print(f"Distinct drawdown value pairs: {len(clusters)}")
    print(f"DD Ratio - Mean: {rolling_summary['dd_ratio_mean']}, Median: {rolling_summary['dd_ratio_median']}, Min: {rolling_summary['dd_ratio_min']}, Max: {rolling_summary['dd_ratio_max']}")
    print(f"Filter reduces DD in: {rolling_summary['windows_filter_reduces_dd']} / {len(rolling_rows)} ({rolling_summary['pct_filter_reduces_dd']}%)")
    
    with open(OUT_FILE, "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"\n[OK] Results written to {OUT_FILE}")

if __name__ == "__main__":
    main()
