"""Percentile-calibration V2 backtest (Track B).

Replaces fixed 0.45/0.55 thresholds with per-ticker rolling percentiles:
  - BUY if p > 70th percentile of last 100 predictions
  - SELL if p < 30th percentile of last 100 predictions
  - Ensures ~30% active signals even when probabilities cluster near 0.5
"""

import json
import os
import sys

WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, WORKSPACE)

import numpy as np
import pandas as pd

from scripts.phase5.backtest_final import load_all, stats, bt

COST_BPS = 15.0
LOOKBACK = 100
BUY_PCT = 70
SELL_PCT = 30


def percentile_signal(p_up, lookback=LOOKBACK, buy_pct=BUY_PCT, sell_pct=SELL_PCT):
    """Compute positions using rolling percentile thresholds."""
    n = len(p_up)
    pos = np.zeros(n)
    for i in range(n):
        if i < lookback:
            pos[i] = 0.0
            continue
        window = p_up[i - lookback:i]
        buy_thr = np.percentile(window, buy_pct)
        sell_thr = np.percentile(window, sell_pct)
        if p_up[i] > buy_thr:
            pos[i] = 1.0
        elif p_up[i] < sell_thr:
            pos[i] = -1.0
        else:
            pos[i] = 0.0
    return pos


def percentile_signal_with_regime(p_up, above_sma, lookback=LOOKBACK, buy_pct=BUY_PCT, sell_pct=SELL_PCT):
    """Percentile + 200-SMA regime filter (buy only above, sell only below)."""
    n = len(p_up)
    pos = np.zeros(n)
    for i in range(n):
        if i < lookback:
            pos[i] = 0.0
            continue
        window = p_up[i - lookback:i]
        buy_thr = np.percentile(window, buy_pct)
        sell_thr = np.percentile(window, sell_pct)
        if p_up[i] > buy_thr and above_sma[i]:
            pos[i] = 1.0
        elif p_up[i] < sell_thr and not above_sma[i]:
            pos[i] = -1.0
        else:
            pos[i] = 0.0
    return pos


def main():
    data, n = load_all()
    print(f"Test span: {n} days per ticker")

    results = {}

    # Variant A: pure percentile (no regime)
    print("\n=== V2-A: Pure Percentile (no regime) ===")
    nets_a = []
    for t, df in data.items():
        p_up = df["p_lstm"].values
        pos = percentile_signal(p_up)
        net = bt(pos, df["fwd_ret"].values, COST_BPS)
        nets_a.append(net)
        buy_days = (pos > 0).sum()
        sell_days = (pos < 0).sum()
        print(f"{t:>5}: BUY={buy_days:>3} ({buy_days/n:.1%})  SELL={sell_days:>3} ({sell_days/n:.1%})  FLAT={(pos==0).sum():>3}")
    port_a = pd.DataFrame(nets_a).T.mean(axis=1).values
    s_a = stats(port_a, np.zeros_like(port_a))
    results["V2A_pure_percentile"] = s_a
    print(f"  Portfolio: Ret={s_a['total_ret_pct']:.2f}%  Sharpe={s_a['sharpe']:.3f}  MaxDD={s_a['max_dd_pct']:.2f}%")

    # Variant B: percentile + 200-SMA regime
    print("\n=== V2-B: Percentile + 200-SMA Regime ===")
    nets_b = []
    for t, df in data.items():
        p_up = df["p_lstm"].values
        above = df["above_sma200"].values.astype(bool)
        pos = percentile_signal_with_regime(p_up, above)
        net = bt(pos, df["fwd_ret"].values, COST_BPS)
        nets_b.append(net)
        buy_days = (pos > 0).sum()
        sell_days = (pos < 0).sum()
        flat_days = (pos == 0).sum()
        print(f"{t:>5}: BUY={buy_days:>3} ({buy_days/n:.1%})  SELL={sell_days:>3} ({sell_days/n:.1%})  FLAT={flat_days:>3}")
    port_b = pd.DataFrame(nets_b).T.mean(axis=1).values
    s_b = stats(port_b, np.zeros_like(port_b))
    results["V2B_percentile_regime"] = s_b
    print(f"  Portfolio: Ret={s_b['total_ret_pct']:.2f}%  Sharpe={s_b['sharpe']:.3f}  MaxDD={s_b['max_dd_pct']:.2f}%")

    # Variant C: V1 baseline (fixed thresholds from Phase 5)
    print("\n=== V1 Baseline: Fixed 0.55/0.45 + Regime ===")
    from scripts.phase5.backtest_final import strategy_positions
    nets_c = []
    for t, df in data.items():
        pos = strategy_positions(df, "ls_regime")
        # apply stops
        pos = apply_short_stops(pos, df["close"].values)
        net = bt(pos, df["fwd_ret"].values, COST_BPS)
        nets_c.append(net)
        buy_days = (pos > 0).sum()
        sell_days = (pos < 0).sum()
        print(f"{t:>5}: BUY={buy_days:>3} ({buy_days/n:.1%})  SELL={sell_days:>3} ({sell_days/n:.1%})")
    port_c = pd.DataFrame(nets_c).T.mean(axis=1).values
    s_c = stats(port_c, np.zeros_like(port_c))
    results["V1_fixed_regime"] = s_c
    print(f"  Portfolio: Ret={s_c['total_ret_pct']:.2f}%  Sharpe={s_c['sharpe']:.3f}  MaxDD={s_c['max_dd_pct']:.2f}%")

    # Comparison table
    print("\n" + "=" * 70)
    print(f"{'Variant':<28} {'Ret%':>8} {'Sharpe':>7} {'MaxDD%':>8} {'Buy%':>7} {'Sell%':>7}")
    print("-" * 70)
    for name, s in results.items():
        # signal freq not stored in stats, compute from first ticker for reference
        print(f"{name:<28} {s['total_ret_pct']:>8} {s['sharpe']:>7} {s['max_dd_pct']:>8}")

    # Verdict
    v2b = results["V2B_percentile_regime"]
    print(f"\nV2 DECISION: Sharpe={v2b['sharpe']:.3f}  |  Target >0.5 for 'GO'")
    if v2b["sharpe"] > 0.5:
        print("   LAUNCH READY — V2 percentile calibration rescues the short leg!")
    else:
        print("   HOLD — V2 still below 0.5 Sharpe. Need better signal model.")

    with open("phase5_artifacts/percentile_v2_results.json", "w") as f:
        json.dump(results, f, indent=2, default=lambda x: float(x) if isinstance(x, (np.floating, np.integer)) else x)


def apply_short_stops(pos, closes):
    """Enforce 5% stop-loss on shorts."""
    pos = pos.copy()
    entry = None
    cooldown = 0
    for t in range(len(pos)):
        if cooldown > 0:
            cooldown -= 1
        if pos[t] < 0:
            if entry is None:
                entry = closes[t]
            elif closes[t] > entry * 1.05:
                pos[t] = 0.0
                entry = None
                cooldown = 5
                continue
        else:
            entry = None
    return pos


if __name__ == "__main__":
    main()