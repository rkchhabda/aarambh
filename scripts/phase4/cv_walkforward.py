"""Expanding-window walk-forward evaluation of trading strategies.

Hyperparameters are re-chosen at each fold boundary using ONLY the expanding
training prefix (Sharpe net of costs). The out-of-sample blocks are stitched
into one honest equity curve per signal.
"""

import json
import os
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from strategy_lib import build_positions, backtest, perf_stats

WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ART = os.path.join(WORKSPACE, "ensemble", "artifacts")
OUT = os.path.join(WORKSPACE, "phase4_artifacts")
COST_BPS = 5.0
TRAIN_MIN = 110          # first fold trains on days [0:110)
N_BLOCKS = 5             # OOS blocks covering days 110..441


def load_signal_matrix():
    df = pd.read_csv(os.path.join(ART, "features.csv"), parse_dates=["timestamps"])
    ret_by_ts = df.set_index(df["timestamps"].dt.strftime("%Y-%m-%d"))["next_ret"]
    rvol_by_ts = df.set_index(df["timestamps"].dt.strftime("%Y-%m-%d"))["rvol_20"]

    signals = {}
    for m in ["xgb", "lstm", "kronos"]:
        with open(os.path.join(ART, f"{m}_preds.json")) as f:
            d = json.load(f)
        ts, p, y = [], [], []
        for split in ["val", "test"]:                      # chronological order
            ts += d[split]["timestamps"]; p += d[split]["p_up"]; y += d[split]["actual"]
        signals[m] = pd.DataFrame({"p_up": p, "target_up": y,
                                   "fwd_ret": [ret_by_ts[t] for t in ts],
                                   "rvol": [rvol_by_ts[t] for t in ts]}, index=ts)

    # combined signals
    signals["lstm+kronos"] = (signals["lstm"]["p_up"] + signals["kronos"]["p_up"]) / 2
    signals["xgb+lstm+kronos"] = (signals["xgb"]["p_up"] + signals["lstm"]["p_up"]
                                  + signals["kronos"]["p_up"]) / 3
    for name in ["lstm+kronos", "xgb+lstm+kronos"]:
        base = signals["lstm"].copy()
        base["p_up"] = signals[name].values
        signals[name] = base
    return signals


GRID = []
for thr in [0.50, 0.525, 0.55, 0.575, 0.60]:
    for tv in [None, 0.010, 0.015]:
        GRID.append({"mode": "binary", "thr_long": thr, "allow_short": False,
                     "target_vol": tv})
for k in [3.0, 5.0, 8.0]:
    for tv in [None, 0.010, 0.015]:
        GRID.append({"mode": "linear", "k": k, "band": 0.02, "cap": 1.0,
                     "allow_short": True, "target_vol": tv})


def prefix_sharpe(sig, params, end):
    p = sig["p_up"].values[:end]
    rv = sig["rvol"].values[:end]
    pos = build_positions(p, rv, **params)
    fwd = sig["fwd_ret"].values[:end]
    net, expo = backtest(pos, fwd, COST_BPS)
    if len(net) < 10 or net.std() == 0:
        return -9.9
    r = pd.Series(net)
    ann = r.mean() * 252
    v = r.std() * np.sqrt(252)
    s = ann / v if v > 0 else -9.9
    # penalize zero-exposure degenerate solutions
    if exposure_fraction(pos[:-1]) < 0.05:
        s -= 1.0
    return float(s)


def exposure_fraction(pos):
    return float(np.mean(np.abs(pos) > 1e-8)) if len(pos) else 0.0


def main():
    os.makedirs(OUT, exist_ok=True)
    signals = load_signal_matrix()
    n = len(signals["lstm"])
    bounds = np.linspace(TRAIN_MIN, n, N_BLOCKS + 1).astype(int)
    print(f"Walk-forward: {n} days | folds: ", list(zip(bounds[:-1], bounds[1:])))

    all_results = {}
    curves = {}

    for name, sig in signals.items():
        oos_net, oos_expo, oos_bh, chosen = [], [], [], []
        for b0, b1 in zip(bounds[:-1], bounds[1:]):
            scores = [(prefix_sharpe(sig, g, b0), i) for i, g in enumerate(GRID)]
            best_i = max(scores)[1]
            best_params = GRID[best_i]
            chosen.append({**best_params, "train_prefix_sharpe": round(max(scores)[0], 3)})

            pos = build_positions(sig["p_up"].values[b0:b1], sig["rvol"].values[b0:b1],
                                  **best_params)
            net, expo = backtest(pos, sig["fwd_ret"].values[b0:b1], COST_BPS)
            bh = (sig["fwd_ret"].values[b0:b1])[:-1]
            oos_net.append(net); oos_expo.append(expo); oos_bh.append(bh)

        net = np.concatenate(oos_net)
        expo = np.concatenate(oos_expo)
        bh = np.concatenate(oos_bh)
        stats = perf_stats(net, expo, benchmark=bh)
        stats["signal"] = name
        all_results[name] = {"stats": stats, "chosen": chosen}
        curves[name] = (1 + pd.Series(net)).cumprod()
        print(f"\n=== {name} ===")
        for k_, v_ in stats.items():
            print(f"  {k_:>16}: {v_:.4f}" if isinstance(v_, float) else f"  {k_:>16}: {v_}")
        print(f"  chosen params per fold: {[c['mode'] + ('/thr=' + str(c.get('thr_long')) if c['mode']=='binary' else '/k=' + str(c.get('k'))) + ('/vt=' + str(c['target_vol'])) for c in chosen]}")

    # Buy & hold full-span reference
    bh_full = np.concatenate([sig_fwd[:-1] for sig_fwd in
                              [signals["lstm"]["fwd_ret"].values[110:]]])
    print(f"\nBuy&hold same span: total={((1+pd.Series(bh_full)).prod()-1)*100:.2f}% "
          f"sharpe={pd.Series(bh_full).mean()*252/(pd.Series(bh_full).std()*np.sqrt(252)):.3f}")

    res_df = pd.DataFrame([{**v["stats"]} for v in all_results.values()])
    res_df.to_csv(os.path.join(OUT, "walkforward_results.csv"), index=False)
    with open(os.path.join(OUT, "walkforward_chosen_params.json"), "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    plt.figure(figsize=(11, 6))
    for name, eq in curves.items():
        plt.plot(eq.values, label=name)
    plt.plot((1 + pd.Series(bh_full)).cumprod().values, "--k", label="buy&hold", alpha=0.7)
    plt.title("Stitched out-of-sample equity (net of 5bps costs)")
    plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(OUT, "equity_curves.png"), dpi=120)
    print(f"\nSaved results -> {OUT}")


if __name__ == "__main__":
    main()
