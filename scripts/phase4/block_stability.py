"""Per-block stability analysis for the LSTM deployment path."""

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from strategy_lib import build_positions, backtest, perf_stats
from cv_walkforward import load_signal_matrix, GRID, prefix_sharpe, COST_BPS, TRAIN_MIN, N_BLOCKS

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "phase4_artifacts")


def main():
    signals = load_signal_matrix()
    sig = signals["lstm"]
    n = len(sig)
    bounds = np.linspace(TRAIN_MIN, n, N_BLOCKS + 1).astype(int)

    print("LSTM per-block OOS detail (params chosen on expanding prefix):")
    rows = []
    cum = 1.0
    for b0, b1 in zip(bounds[:-1], bounds[1:]):
        best_i = max((prefix_sharpe(sig, g, b0), i) for i, g in enumerate(GRID))[1]
        params = GRID[best_i]
        pos = build_positions(sig["p_up"].values[b0:b1], sig["rvol"].values[b0:b1], **params)
        net, expo = backtest(pos, sig["fwd_ret"].values[b0:b1], COST_BPS)
        s = perf_stats(net, expo)
        cum *= (1 + s["total_return"])
        ts = sig.index[b0]
        rows.append({"block": f"{ts}", "params": str(params),
                     "oos_ret_pct": round(s["total_return"] * 100, 2),
                     "sharpe": round(s["sharpe"], 2),
                     "maxdd_pct": round(s["max_drawdown"] * 100, 2),
                     "active_pct": round(s["active_days_pct"], 1),
                     "win_rate": round(s["win_rate_active"], 1)})
        print(f"  {rows[-1]}")

    # Deployment config = last prefix choice, hypothetical full-OOS application
    best_i = max((prefix_sharpe(sig, g, bounds[1]), i) for i, g in enumerate(GRID))[1]
    pos = build_positions(sig["p_up"].values, sig["rvol"].values, **GRID[best_i])
    pos[:bounds[1]] = 0.0                       # no trading before first OOS block
    net, expo = backtest(pos, sig["fwd_ret"].values, COST_BPS)
    net[:bounds[1] - 1] = 0.0
    s = perf_stats(net, expo)
    print("\nLSTM 'deployed from day 110' full-span stats:")
    for k, v in s.items():
        print(f"  {k:>16}: {v:.4f}" if isinstance(v, float) else f"  {k:>16}: {v}")

    pd.DataFrame(rows).to_csv(os.path.join(OUT, "lstm_block_stability.csv"), index=False)
    print(f"\nSaved -> {os.path.join(OUT, 'lstm_block_stability.csv')}")


if __name__ == "__main__":
    main()
