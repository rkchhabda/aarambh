"""
Extended Drawdown & Regime Filter Stress Test — v2
====================================================
Extends drawdown_stress_test.py with:

  1. Sortino ratio, Calmar ratio, Ulcer Index added to all summaries.
  2. Rolling overlapping-window analysis (6-month windows, stepped monthly)
     — distribution of drawdown-reduction ratios across all windows,
       plus % of windows where filter helps vs hurts on drawdown.
  3. SMA parameter sensitivity: 150-day, 200-day, 250-day compared
     across the full cycle at 15 bps retail cost.
  4. Data-availability report (earliest date, COVID coverage check).

All results: no rounding in a favorable direction.
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
OUT_DIR  = os.path.join(BASE_DIR, "scripts", "verification")


# ── Core metrics ──────────────────────────────────────────────────────────────

def compute_equity_dd(returns):
    eq = np.cumprod(1.0 + returns)
    cummax = np.maximum.accumulate(eq)
    dd = (eq / cummax) - 1.0
    return eq, dd


def sortino_ratio(returns, ann_factor=252.0, mar=0.0):
    r = returns[~np.isnan(returns)]
    if len(r) == 0:
        return 0.0
    ann_ret = np.mean(r) * ann_factor
    downside = r[r < mar] - mar
    if len(downside) == 0:
        return float('inf') if ann_ret > 0 else 0.0
    dd_std = np.sqrt(np.mean(downside ** 2)) * np.sqrt(ann_factor)
    return float((ann_ret - mar * ann_factor) / dd_std) if dd_std > 1e-10 else 0.0


def calmar_ratio(returns, ann_factor=252.0):
    r = returns[~np.isnan(returns)]
    if len(r) == 0:
        return 0.0
    ann_ret = np.mean(r) * ann_factor
    _, dd = compute_equity_dd(r)
    max_dd = abs(np.min(dd)) if len(dd) > 0 else 1e-10
    return float(ann_ret / max_dd) if max_dd > 1e-10 else 0.0


def ulcer_index(returns):
    r = returns[~np.isnan(returns)]
    if len(r) == 0:
        return 0.0
    _, dd = compute_equity_dd(r)
    return float(np.sqrt(np.mean((dd * 100.0) ** 2)))


def analyze_recovery(returns):
    eq, dd = compute_equity_dd(returns)
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
    return {
        "max_drawdown_duration_days": int(max(durations)) if durations else 0,
        "avg_drawdown_duration_days": round(float(np.mean(durations)), 1) if durations else 0.0,
        "pct_time_underwater": round(float(np.mean(underwater) * 100.0), 1),
    }


def calc_stats(daily_net, daily_exp, trade_counts):
    r = daily_net.copy()
    valid = ~np.isnan(r)
    r = r[valid]
    daily_exp = daily_exp[valid]

    eq, dd = compute_equity_dd(r)
    total_ret  = (eq[-1] - 1.0) * 100.0 if len(eq) > 0 else 0.0
    ann_ret    = np.mean(r) * 252.0 * 100.0
    vol        = np.std(r) * np.sqrt(252.0)
    sharpe     = (ann_ret / 100.0) / vol if vol > 1e-8 else 0.0
    max_dd     = np.min(dd) * 100.0 if len(dd) > 0 else 0.0

    active   = daily_exp > 1e-6
    win_rate = (r[active] > 0).mean() * 100.0 if active.sum() > 0 else 0.0
    exposure = np.mean(daily_exp) * 100.0
    trades   = int(np.sum(trade_counts))

    rec = analyze_recovery(r)

    return {
        "total_ret_pct":    round(float(total_ret), 2),
        "ann_ret_pct":      round(float(ann_ret), 2),
        "sharpe":           round(float(sharpe), 3),
        "sortino":          round(sortino_ratio(r), 3),
        "calmar":           round(calmar_ratio(r), 3),
        "ulcer_index":      round(ulcer_index(r), 3),
        "max_dd_pct":       round(float(max_dd), 2),
        "win_rate_pct":     round(float(win_rate), 2),
        "trade_count":      trades,
        "avg_exposure_pct": round(float(exposure), 2),
        **rec,
    }


# ── Simulation engine ─────────────────────────────────────────────────────────

def simulate(df_sub, use_filter=True, cost_bps=15.0, sma_col="above_sma200"):
    df_s = df_sub.copy()
    df_s["pos"] = df_s[sma_col].astype(float) if use_filter else 1.0

    pos_mat = df_s.pivot(index="date", columns="ticker", values="pos").fillna(0.0)
    ret_mat = df_s.pivot(index="date", columns="ticker", values="fwd_ret_1d").fillna(0.0)

    idx = pos_mat.index.intersection(ret_mat.index)
    pos_mat = pos_mat.loc[idx]
    ret_mat = ret_mat.loc[idx]

    N = pos_mat.shape[1]
    pos_diff = pos_mat.diff().abs()
    pos_diff.iloc[0] = pos_mat.iloc[0].abs()

    daily_trades = (pos_diff > 0.0).sum(axis=1).values
    daily_gross  = (pos_mat * ret_mat).sum(axis=1) / N
    daily_costs  = (pos_diff.sum(axis=1) * (cost_bps / 10000.0)) / N
    daily_net    = daily_gross - daily_costs
    daily_exp    = pos_mat.mean(axis=1)

    return calc_stats(daily_net.values, daily_exp.values, daily_trades)


def print_row(label, s):
    print(f"  {label:<52} Ret:{s['total_ret_pct']:>7.2f}%  "
          f"Sh:{s['sharpe']:>6.3f}  So:{s['sortino']:>6.3f}  "
          f"Ca:{s['calmar']:>6.3f}  UI:{s['ulcer_index']:>6.2f}  "
          f"MaxDD:{s['max_dd_pct']:>7.2f}%  Exp:{s['avg_exposure_pct']:>5.1f}%")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():

    # ── PART 0: Data availability ─────────────────────────────────────────────
    print("=" * 100)
    print("PART 0: DATA AVAILABILITY AUDIT")
    print("=" * 100)

    cols = ["date", "ticker", "Close"]
    t_hist  = pd.read_csv(os.path.join(DATA_DIR, "train_multi_v2_5d.csv"), usecols=cols)
    v_hist  = pd.read_csv(os.path.join(DATA_DIR, "val_multi_v2_5d.csv"),   usecols=cols)
    te_hist = pd.read_csv(os.path.join(DATA_DIR, "test_multi_v2_5d.csv"),  usecols=cols)

    full_hist = pd.concat([t_hist, v_hist, te_hist], ignore_index=True)
    full_hist = full_hist.sort_values(["ticker", "date"]).reset_index(drop=True)

    all_raw_dates = sorted(full_hist["date"].unique())
    print(f"  Earliest raw date on disk : {all_raw_dates[0]}")
    print(f"  Latest raw date on disk   : {all_raw_dates[-1]}")
    print(f"  Total raw calendar dates  : {len(all_raw_dates)}")
    print(f"  Tickers in universe       : {full_hist['ticker'].nunique()}")
    print(f"  200-day warmup consumed   : first 200 unique dates")
    post_warmup_dates = all_raw_dates[200:]
    print(f"  Earliest post-warmup date : {post_warmup_dates[0]}  (true earliest usable date)")
    print()

    covid_start = "2020-02-01"
    covid_end   = "2020-04-30"
    covid_in_data = any(covid_start <= d <= covid_end for d in all_raw_dates)
    print(f"  COVID window ({covid_start} to {covid_end}) in data: {covid_in_data}")
    if not covid_in_data:
        print(f"  *** COVID period NOT covered. Earliest raw data is {all_raw_dates[0]}. ***")
        print(f"  *** COVID extension would require sourcing ~4 years of additional Nifty 100 OHLCV. ***")
    print()

    # ── Build master df with all 3 SMA columns ────────────────────────────────
    print("[1] Computing 150/200/250-day SMAs and forward returns per ticker...")
    records = []
    for ticker, group in full_hist.groupby("ticker", sort=False):
        group = group.copy()
        c = group["Close"]
        sma_150 = c.rolling(150).mean().values
        sma_200 = c.rolling(200).mean().values
        sma_250 = c.rolling(250).mean().values
        fwd_1d  = (c.shift(-1) / c - 1.0).values
        d_vals  = group["date"].values
        for i in range(len(group)):
            records.append((
                ticker, d_vals[i],
                sma_150[i], sma_200[i], sma_250[i],
                fwd_1d[i], float(c.iloc[i])
            ))

    df = pd.DataFrame(records, columns=[
        "ticker", "date", "sma_150", "sma_200", "sma_250", "fwd_ret_1d", "Close"
    ])

    # Use 250-day warmup so all three SMAs are valid
    post_warmup_250 = all_raw_dates[250:]
    df_active = df[df["date"].isin(post_warmup_250)].copy()
    df_active["above_sma150"] = df_active["Close"] > df_active["sma_150"]
    df_active["above_sma200"] = df_active["Close"] > df_active["sma_200"]
    df_active["above_sma250"] = df_active["Close"] > df_active["sma_250"]

    all_dates = sorted(df_active["date"].unique())
    print(f"  Post-warmup span (SMA250 baseline): {all_dates[0]} to {all_dates[-1]} ({len(all_dates)} sessions)\n")

    # ── PART 1: Full-cycle + 4 windows with extended metrics ──────────────────
    print("=" * 100)
    print("PART 1: FULL-CYCLE + WINDOWS — SHARPE / SORTINO / CALMAR / ULCER INDEX")
    print("=" * 100)

    w1_dates = all_dates[0:251]
    w2_dates = all_dates[251:502]
    w3_dates = all_dates[502:753]
    w4_dates = all_dates[753:]

    windows = [
        ("Window 1 (2022-2023 Consolidation)",   w1_dates),
        ("Window 2 (2023-2024 Bull Rally)",       w2_dates),
        ("Window 3 (2024-2025 Market Peak)",      w3_dates),
        ("Window 4 (2025-2026 Late Cycle Chop)",  w4_dates),
        ("Full Multi-Year Cycle (2022-2026)",     all_dates),
    ]

    all_window_results = {}

    for win_name, win_d in windows:
        sub = df_active[df_active["date"].isin(win_d)]
        start_d, end_d = win_d[0], win_d[-1]
        lbl = f"{win_name} [{start_d} -> {end_d}]"

        bh    = simulate(sub, use_filter=False, cost_bps=0.0)
        rf_0  = simulate(sub, use_filter=True,  cost_bps=0.0,  sma_col="above_sma200")
        rf_5  = simulate(sub, use_filter=True,  cost_bps=5.0,  sma_col="above_sma200")
        rf_15 = simulate(sub, use_filter=True,  cost_bps=15.0, sma_col="above_sma200")

        all_window_results[lbl] = {
            "buy_and_hold":        bh,
            "regime_filter_0bps":  rf_0,
            "regime_filter_5bps":  rf_5,
            "regime_filter_15bps": rf_15,
        }

        dd_ratio = abs(bh["max_dd_pct"]) / (abs(rf_15["max_dd_pct"]) + 1e-6)
        print(f"\n--- {lbl} ---")
        print_row("Buy & Hold Benchmark",          bh)
        print_row("Regime Filter SMA200 @ 0bps",   rf_0)
        print_row("Regime Filter SMA200 @ 5bps",   rf_5)
        print_row("Regime Filter SMA200 @ 15bps",  rf_15)
        print(f"  >> DD Reduction: {bh['max_dd_pct']:.2f}% -> {rf_15['max_dd_pct']:.2f}% "
              f"({dd_ratio:.2f}x) | Return: {bh['total_ret_pct']:+.2f}% vs {rf_15['total_ret_pct']:+.2f}%")

    # ── PART 2: Rolling windows ───────────────────────────────────────────────
    print("\n" + "=" * 100)
    print("PART 2: ROLLING 6-MONTH WINDOWS (stepped monthly) — DD-REDUCTION DISTRIBUTION")
    print("=" * 100)

    WINDOW_DAYS = 126
    STEP_DAYS   = 21

    rolling_results = []
    start_idx = 0
    while start_idx + WINDOW_DAYS <= len(all_dates):
        win_d = all_dates[start_idx : start_idx + WINDOW_DAYS]
        sub   = df_active[df_active["date"].isin(win_d)]
        bh    = simulate(sub, use_filter=False, cost_bps=0.0)
        rf_15 = simulate(sub, use_filter=True,  cost_bps=15.0, sma_col="above_sma200")

        bh_dd  = abs(bh["max_dd_pct"])
        rf_dd  = abs(rf_15["max_dd_pct"])
        ratio  = bh_dd / (rf_dd + 1e-6)

        rolling_results.append({
            "start":                  win_d[0],
            "end":                    win_d[-1],
            "bh_max_dd_pct":          round(bh["max_dd_pct"], 3),
            "rf_max_dd_pct":          round(rf_15["max_dd_pct"], 3),
            "bh_total_ret_pct":       round(bh["total_ret_pct"], 3),
            "rf_total_ret_pct":       round(rf_15["total_ret_pct"], 3),
            "dd_reduction_ratio":     round(ratio, 4),
            "filter_reduces_drawdown": bool(bh_dd > rf_dd),
        })
        start_idx += STEP_DAYS

    ratios  = np.array([r["dd_reduction_ratio"] for r in rolling_results])
    helps   = np.array([r["filter_reduces_drawdown"] for r in rolling_results])
    n_total = len(rolling_results)
    n_helps = int(helps.sum())
    pct_help = n_helps / n_total * 100.0

    print(f"\n  Total rolling windows : {n_total}  ({WINDOW_DAYS}-day, {STEP_DAYS}-day step)")
    print(f"  Span: {rolling_results[0]['start']} to {rolling_results[-1]['end']}")
    print(f"\n  DD-Reduction Ratio (BH_MaxDD / Filter_MaxDD @ 15bps retail):")
    print(f"    Mean   : {np.mean(ratios):.4f}")
    print(f"    Median : {np.median(ratios):.4f}")
    print(f"    Std    : {np.std(ratios):.4f}")
    print(f"    Min    : {np.min(ratios):.4f}")
    print(f"    Max    : {np.max(ratios):.4f}")
    print(f"    p25    : {np.percentile(ratios, 25):.4f}")
    print(f"    p75    : {np.percentile(ratios, 75):.4f}")
    print(f"\n  Windows filter REDUCES drawdown : {n_helps}/{n_total} = {pct_help:.1f}%")
    print(f"  Windows filter INCREASES drawdown: {n_total-n_helps}/{n_total} = {100.0-pct_help:.1f}%")

    sorted_rr = sorted(rolling_results, key=lambda x: x["dd_reduction_ratio"])
    print(f"\n  Worst 5 windows (filter least effective):")
    for rr in sorted_rr[:5]:
        print(f"    {rr['start']} -> {rr['end']}  BH:{rr['bh_max_dd_pct']:>7.2f}%  "
              f"Filter:{rr['rf_max_dd_pct']:>7.2f}%  Ratio:{rr['dd_reduction_ratio']:.3f}  "
              f"BH-Ret:{rr['bh_total_ret_pct']:>+7.2f}%  Filter-Ret:{rr['rf_total_ret_pct']:>+7.2f}%")
    print(f"\n  Best 5 windows (filter most effective):")
    for rr in sorted_rr[-5:][::-1]:
        print(f"    {rr['start']} -> {rr['end']}  BH:{rr['bh_max_dd_pct']:>7.2f}%  "
              f"Filter:{rr['rf_max_dd_pct']:>7.2f}%  Ratio:{rr['dd_reduction_ratio']:.3f}  "
              f"BH-Ret:{rr['bh_total_ret_pct']:>+7.2f}%  Filter-Ret:{rr['rf_total_ret_pct']:>+7.2f}%")

    # ── PART 3: SMA sensitivity ───────────────────────────────────────────────
    print("\n" + "=" * 100)
    print("PART 3: SMA PARAMETER SENSITIVITY — 150 / 200 / 250 DAY (FULL CYCLE, 15bps)")
    print("=" * 100)

    full_sub = df_active[df_active["date"].isin(all_dates)]
    bh_full  = simulate(full_sub, use_filter=False, cost_bps=0.0)

    print(f"\n  Full cycle: {all_dates[0]} -> {all_dates[-1]}  ({len(all_dates)} sessions)")
    print(f"\n  {'Config':<15} {'Ret%':>8}  {'Sharpe':>7}  {'Sortino':>8}  "
          f"{'Calmar':>7}  {'UI':>6}  {'MaxDD%':>8}  {'Exp%':>6}  {'DD-Ratio vs BH':>15}")
    print(f"  {'-'*95}")
    print(f"  {'Buy & Hold':<15} {bh_full['total_ret_pct']:>8.2f}  {bh_full['sharpe']:>7.3f}  "
          f"{bh_full['sortino']:>8.3f}  {bh_full['calmar']:>7.3f}  "
          f"{bh_full['ulcer_index']:>6.2f}  {bh_full['max_dd_pct']:>8.2f}  "
          f"{bh_full['avg_exposure_pct']:>5.1f}%  {'baseline':>15}")

    sma_sensitivity_results = {}
    for sma_name, sma_col in [("SMA-150", "above_sma150"), ("SMA-200", "above_sma200"), ("SMA-250", "above_sma250")]:
        s = simulate(full_sub, use_filter=True, cost_bps=15.0, sma_col=sma_col)
        dd_ratio = abs(bh_full["max_dd_pct"]) / (abs(s["max_dd_pct"]) + 1e-6)
        s["dd_reduction_ratio_vs_bh"] = round(dd_ratio, 3)
        sma_sensitivity_results[sma_name] = s
        print(f"  {sma_name:<15} {s['total_ret_pct']:>8.2f}  {s['sharpe']:>7.3f}  "
              f"{s['sortino']:>8.3f}  {s['calmar']:>7.3f}  "
              f"{s['ulcer_index']:>6.2f}  {s['max_dd_pct']:>8.2f}  "
              f"{s['avg_exposure_pct']:>5.1f}%  {dd_ratio:>14.3f}x")

    # ── Save ──────────────────────────────────────────────────────────────────
    out_payload = {
        "metadata": {
            "script":               "drawdown_stress_test_v2.py",
            "timestamp":            datetime.now().isoformat(),
            "target_universe":      "Nifty 100 Indian Equities",
            "tickers_count":        df_active["ticker"].nunique(),
            "earliest_raw_date":    all_raw_dates[0],
            "earliest_usable_date": all_dates[0],
            "latest_date":          all_dates[-1],
            "total_trading_days":   len(all_dates),
            "covid_in_data":        covid_in_data,
            "covid_note":           (
                "COVID window (2020-02-01 to 2020-04-30) NOT in dataset. "
                "Earliest raw data: " + all_raw_dates[0] + ". "
                "Coverage starts post-COVID. Extension requires sourcing additional history."
            ) if not covid_in_data else "COVID period covered.",
            "new_metrics":          ["sortino", "calmar", "ulcer_index"],
        },
        "extended_windows": all_window_results,
        "rolling_window_analysis": {
            "config": {
                "window_trading_days": WINDOW_DAYS,
                "step_trading_days":   STEP_DAYS,
                "total_windows":       n_total,
                "cost_bps":            15,
                "sma_period":          200,
            },
            "summary": {
                "dd_ratio_mean":   round(float(np.mean(ratios)), 4),
                "dd_ratio_median": round(float(np.median(ratios)), 4),
                "dd_ratio_std":    round(float(np.std(ratios)), 4),
                "dd_ratio_min":    round(float(np.min(ratios)), 4),
                "dd_ratio_max":    round(float(np.max(ratios)), 4),
                "dd_ratio_p25":    round(float(np.percentile(ratios, 25)), 4),
                "dd_ratio_p75":    round(float(np.percentile(ratios, 75)), 4),
                "windows_filter_reduces_drawdown": n_helps,
                "windows_filter_increases_drawdown": n_total - n_helps,
                "pct_filter_reduces_drawdown": round(pct_help, 2),
            },
            "all_windows": rolling_results,
        },
        "sma_sensitivity": {
            "config":       {"cost_bps": 15, "period": "full_cycle"},
            "buy_and_hold": bh_full,
            **sma_sensitivity_results,
        },
    }

    out_file = os.path.join(OUT_DIR, "drawdown_stress_test_v2_results.json")
    with open(out_file, "w") as f:
        json.dump(out_payload, f, indent=2)
    print(f"\n[OK] Artifact saved: {out_file}")
    print("=" * 100)


if __name__ == "__main__":
    main()
