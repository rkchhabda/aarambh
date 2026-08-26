"""Strategy library: signal -> position -> PnL with costs and risk management.

Position sizing modes:
  - "binary":  +1 if p_up > thr_long, -1 if p_up < 1-thr_long (if shorting enabled), else 0
  - "linear":  pos = clip((p_up - 0.5) * k, -cap, cap); zero inside a neutral band
Risk overlay:
  - volatility targeting: pos *= clip(target_vol / realized_vol, 0, lev_cap)
Costs: cost_bps charged on |change in position| each day.
"""

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def build_positions(p_up, rvol, mode="binary", thr_long=0.55, allow_short=False,
                    k=4.0, band=0.02, cap=1.0, target_vol=None, lev_cap=1.5):
    p = np.asarray(p_up, float)
    n = len(p)
    if mode == "binary":
        pos = np.where(p > thr_long, 1.0, 0.0)
        if allow_short:
            pos = np.where(p < (1.0 - thr_long), -1.0, pos)
    else:  # linear
        raw = (p - 0.5) * k
        raw = np.where(np.abs(raw) < band, 0.0, raw)
        pos = np.clip(raw, -(cap if allow_short else 0.0), cap)

    if target_vol is not None and rvol is not None:
        rv = np.asarray(rvol, float)
        scale = np.clip(np.where(rv > 0, target_vol / rv, 1.0), 0.0, lev_cap)
        scale[rv <= 0] = 1.0
        pos = pos * scale
        pos = np.clip(pos, -(cap * lev_cap), cap * lev_cap)
    return pos


def backtest(pos, fwd_ret, cost_bps=5.0):
    """pos[i] held from close i to close i+1; earns fwd_ret[i]. Costs on turnover."""
    pos = np.asarray(pos, float)
    ret = np.asarray(fwd_ret, float)
    gross = pos[:-1] * ret[:-1]
    turnover = np.abs(np.diff(pos, prepend=0.0))
    costs = turnover[:-1] * cost_bps / 1e4
    net = gross - costs
    return net, turnover[:-1]


def perf_stats(daily_ret, exposure, benchmark=None):
    r = pd.Series(daily_ret)
    ann = r.mean() * TRADING_DAYS
    vol = r.std() * np.sqrt(TRADING_DAYS)
    sharpe = ann / vol if vol > 0 else 0.0
    equity = (1 + r).cumprod()
    dd = (equity / equity.cummax() - 1).min()
    active = exposure > 1e-8
    stats = {
        "total_return": float(equity.iloc[-1] - 1),
        "ann_return": float(ann),
        "ann_vol": float(vol),
        "sharpe": float(sharpe),
        "max_drawdown": float(dd),
        "exposure": float(exposure.mean()),
        "active_days_pct": float(active.mean() * 100),
        "win_rate_active": float((r[active] > 0).mean() * 100) if active.any() else float("nan"),
        "n_days": int(len(r)),
    }
    if benchmark is not None:
        b = pd.Series(benchmark)
        beq = (1 + b).cumprod()
        stats["bh_total_return"] = float(beq.iloc[-1] - 1)
        bvol = b.std() * np.sqrt(TRADING_DAYS)
        stats["bh_sharpe"] = float(b.mean() * TRADING_DAYS / bvol) if bvol > 0 else 0.0
        stats["bh_max_dd"] = float((beq / beq.cummax() - 1).min())
    return stats
