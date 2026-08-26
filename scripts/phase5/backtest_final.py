"""Phase 5 backtests: regime filter, long/short/flat with short stop-loss,
slippage stress regimes, and the final Go/No-Go comparison."""

import json
import os

import numpy as np
import pandas as pd

TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
ART = "phase5_artifacts"
COST_BPS = {"ideal": 5.0, "retail": 15.0, "high_vol": 30.0}


def strategy_positions(df, mode):
    """Vectorized rules -> target positions per day (decided at close t).
    modes: phase4_long | pooled_long | regime_long | ls_regime"""
    p = df["p_lstm"].values
    above = df["above_sma200"].values.astype(bool)

    if mode == "phase4_long":
        return (p > 0.5).astype(float)

    if mode == "regime_long":
        return ((p > 0.5) & above).astype(float)

    if mode == "ls_regime":
        pos = np.zeros(len(p))
        in_short_stop = False
        cooldown = 0
        entry = None
        for t in range(len(p)):
            if cooldown > 0:
                cooldown -= 1
            # stop-loss management for an open short (checked at close t)
            if pos[t - 1] < 0 if t > 0 else False:
                if df["close"].iloc[t] > entry * 1.05:
                    in_short_stop = True
                    cooldown = 5          # 5-day short ban after stop-out
            if in_short_stop:
                pos[t] = 0.0
                if cooldown == 0:
                    in_short_stop = False
                continue
            if p[t] > 0.55 and above[t]:
                pos[t] = 1.0
                entry = None
            elif p[t] < 0.45 and not above[t]:
                pos[t] = -1.0
                entry = df["close"].iloc[t]
            else:
                pos[t] = 0.0
                entry = None
        return pos

    raise ValueError(mode)


def apply_short_stops(pos, closes):
    """Enforce exit-at-stop inside the position vector (stateful pass)."""
    pos = pos.copy()
    entry = None
    stopped = False
    cooldown = 0
    for t in range(len(pos)):
        if cooldown > 0:
            cooldown -= 1
        if pos[t] < 0:
            if entry is None:
                entry = closes[t]
            elif closes[t] > entry * 1.05:
                pos[t] = 0.0                     # forced cover at close t
                entry = None
                cooldown = 5
                continue
        else:
            entry = None
    return pos


def bt(pos, fwd_ret, cost_bps):
    gross = pos * fwd_ret
    turn = np.abs(np.diff(np.concatenate([[0.0], pos])))   # len == len(pos)
    costs = turn * cost_bps / 1e4
    net = gross - costs
    return net


def stats(net, pos):
    r = pd.Series(net)
    eq = (1 + r).cumprod()
    active = np.abs(pos) > 1e-8
    ann = r.mean() * 252
    vol = r.std() * np.sqrt(252)
    return {
        "total_ret_pct": round((eq.iloc[-1] - 1) * 100, 2),
        "ann_ret_pct": round(ann * 100, 2),
        "sharpe": round(float(ann / vol), 3) if vol > 0 else 0.0,
        "max_dd_pct": round(float((eq / eq.cummax() - 1).min()) * 100, 2),
        "win_rate_pct": round(float((r[active[:len(r)]] > 0).mean() * 100), 2) if active.any() else float("nan"),
        "exposure_pct": round(float(active.mean() * 100), 2),
    }


def load_all():
    frames = {}
    for t in TICKERS:
        df = pd.read_csv(os.path.join(ART, f"preds_{t}.csv"))
        frames[t] = df[df.split == "test"].reset_index(drop=True)   # trade TEST only
    n = min(len(v) for v in frames.values())
    return {t: v.iloc[-n:].reset_index(drop=True) for t, v in frames.items()}, n


def main():
    data, n_days = load_all()
    print(f"Test span: {n_days} days per ticker "
          f"({data['AAPL']['timestamps'].iloc[0]} -> {data['AAPL']['timestamps'].iloc[-1]})\n")

    # ---------- Portfolio-level strategies ----------
    def portfolio(mode, cost_bps, use_stops=True):
        nets = []
        exposures = []
        for t, df in data.items():
            pos = strategy_positions(df, mode)
            if use_stops and mode == "ls_regime":
                pos = apply_short_stops(pos, df["close"].values)
            nets.append(bt(pos, df["fwd_ret"].values, cost_bps))
            exposures.append(pos)
        port_net = pd.DataFrame(nets).T.mean(axis=1).values       # equal-weight
        port_pos = pd.DataFrame(exposures).T.mean(axis=1).values
        return port_net, port_pos

    results = {}

    # Scenario 1: Phase 4 style - AAPL only, long-only, no filter, 5 bps
    df = data["AAPL"]
    pos = strategy_positions(df, "phase4_long")
    s1 = stats(bt(pos, df["fwd_ret"].values, 5.0), pos)
    results["1_phase4_aapl_long_only_5bps"] = s1

    # Scenario 2: multi-ticker pooled long-only (p>0.5), 5 bps
    net, expo = portfolio("phase4_long", 5.0)
    results["2_multiticker_long_only_5bps"] = stats(net, expo)

    # Scenario 2b: multi-ticker regime-filtered long-only @5bps
    net, expo = portfolio("regime_long", 5.0)
    results["2b_multiticker_regime_long_5bps"] = stats(net, expo)

    # Scenario 3 (+Task 5 stress): L/S/F with regime filter + stops, 5/15/30 bps
    for label, bps in COST_BPS.items():
        net, expo = portfolio("ls_regime", bps)
        results[f"3_ls_regime_{label}_{int(bps)}bps"] = stats(net, expo)

    bh = pd.DataFrame([df["fwd_ret"].values for df in data.values()]).T.mean(axis=1)
    results["benchmark_buyhold_portfolio"] = {
        "total_ret_pct": round(((1 + bh).prod() - 1) * 100, 2),
        "sharpe": round(float(bh.mean() * 252 / (bh.std() * np.sqrt(252))), 3),
        "max_dd_pct": round(float((((1 + bh).cumprod() / (1 + bh).cumprod().cummax()) - 1).min()) * 100, 2),
    }

    print("=" * 78)
    print(f"{'SCENARIO':<42} {'Ret%':>8} {'Sharpe':>7} {'MaxDD%':>8} {'Win%':>7} {'Exp%':>6}")
    print("-" * 78)
    for name, s in results.items():
        wr = s.get("win_rate_pct", float("nan"))
        ex = s.get("exposure_pct", 100.0)
        print(f"{name:<42} {s['total_ret_pct']:>8} {s['sharpe']:>7} "
              f"{s['max_dd_pct']:>8} {wr:>7} {ex:>6}")
    print("=" * 78)

    # ---------- Go/No-Go logic ----------
    final = results["3_ls_regime_retail_15bps"]
    verdict_sharpe_ok = final["sharpe"] >= 0.3
    verdict_dd_ok = final["max_dd_pct"] >= -25.0
    go = verdict_sharpe_ok and verdict_dd_ok
    print("\nGO/NO-GO CRITERIA (under 15 bps):")
    print(f"  Sharpe {final['sharpe']} >= 0.3 ?      {'PASS' if verdict_sharpe_ok else 'FAIL'}")
    print(f"  MaxDD   {final['max_dd_pct']}% >= -25% ?  {'PASS' if verdict_dd_ok else 'FAIL'}")
    print(f"\n  VERDICT: {'GO - deploy to paper trading' if go else 'NO-GO - redesign needed'}")

    with open(os.path.join(ART, "final_report.json"), "w") as f:
        json.dump({"results": results, "verdict": "GO" if go else "NO-GO",
                   "n_test_days": int(n_days)}, f, indent=2)
    print(f"\nSaved -> {os.path.join(ART, 'final_report.json')}")


if __name__ == "__main__":
    main()
