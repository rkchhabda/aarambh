"""Backtest endpoint — run historical signal-based backtests with configurable parameters."""

import os
import json
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/backtest", tags=["backtest"])

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "multi",
)


class BacktestRequest(BaseModel):
    ticker: str = "RELIANCE.NS"
    start_date: str | None = None  # ISO format
    end_date: str | None = None
    threshold: float = 0.65
    holding_period: int = 5  # days
    cost_bps: float = 20  # transaction cost in basis points


def _load_ticker_data(ticker: str) -> pd.DataFrame | None:
    """Load historical data for a ticker from cache or data files."""
    cache_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "service", "models", "ticker_cache.json",
    )
    # Try to reconstruct from cache features + close
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            cache = json.load(f)
        if ticker in cache:
            # We only have latest snapshot, not history
            # For backtest we need historical data
            pass

    # Try to load from yfinance (cached locally)
    ticker_file = os.path.join(DATA_DIR, f"{ticker}.csv")
    if os.path.exists(ticker_file):
        df = pd.read_csv(ticker_file)
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
        elif "date" in df.columns:
            df["Date"] = pd.to_datetime(df["date"])
            df = df.rename(columns={"date": "Date"})
        return df

    return None


def _compute_backtest_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all features needed for backtest from raw OHLCV."""
    import ta

    # Normalize column names (handle both cases)
    df = df.copy()
    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if cl == "close":
            col_map[c] = "Close"
        elif cl == "high":
            col_map[c] = "High"
        elif cl == "low":
            col_map[c] = "Low"
        elif cl == "volume":
            col_map[c] = "Volume"
        elif cl in ("date", "timestamps"):
            col_map[c] = "Date"
    df = df.rename(columns=col_map)

    c = df["Close"].values
    h = df["High"].values
    l = df["Low"].values
    v = df["Volume"].values
    cs = pd.Series(c, index=df.index)
    hs = pd.Series(h, index=df.index)
    ls = pd.Series(l, index=df.index)
    vs = pd.Series(v, index=df.index)

    feat = pd.DataFrame(index=df.index)
    feat["bb_pos"] = ((cs - ta.volatility.BollingerBands(cs, window=20).bollinger_mavg()) /
                      (ta.volatility.BollingerBands(cs, window=20).bollinger_wband() + 1e-10)).values
    feat["macd"] = ta.trend.MACD(cs).macd_diff().values
    feat["obv_slope"] = ta.volume.OnBalanceVolumeIndicator(cs, vs).on_balance_volume().diff(5).values
    sma_20 = ta.trend.SMAIndicator(cs, window=20).sma_indicator()
    feat["sma_ratio"] = (cs / sma_20 - 1).values
    feat["cci"] = ta.trend.CCIIndicator(hs, ls, cs, window=20).cci().values
    feat["ret_10"] = cs.pct_change(10).values
    feat["williams_r"] = ta.momentum.WilliamsRIndicator(hs, ls, cs, lbp=14).williams_r().values
    feat["rsi_14"] = ta.momentum.RSIIndicator(cs, window=14).rsi().values
    feat["atr_14"] = (ta.volatility.AverageTrueRange(hs, ls, cs, window=14).average_true_range() / cs).values
    feat["roc_10"] = ta.momentum.ROCIndicator(cs, window=10).roc().values

    feat["Close"] = c
    feat["SMA200"] = cs.rolling(200).mean().values
    feat["above_sma"] = (cs > cs.rolling(200).mean()).values

    # Forward returns
    feat["fwd_ret_1d"] = cs.pct_change(1).shift(-1).values
    feat["fwd_ret_5d"] = cs.pct_change(5).shift(-5).values
    feat["fwd_ret_20d"] = cs.pct_change(20).shift(-20).values

    return feat


def _run_backtest(
    df: pd.DataFrame,
    threshold: float = 0.65,
    holding_period: int = 5,
    cost_bps: float = 20,
    start_date: str = None,
    end_date: str = None,
) -> dict:
    """Run backtest using ensemble model predictions on historical features."""
    from service.app import FEATURES, ensemble_models, meta_model, scaler

    if ensemble_models is None or meta_model is None:
        raise HTTPException(status_code=503, detail="Models not loaded")

    # Compute features
    bt_df = _compute_backtest_features(df)

    # Filter by date range
    if "Date" in bt_df.columns:
        bt_df["Date"] = pd.to_datetime(bt_df["Date"], errors="coerce")
        if start_date:
            bt_df = bt_df[bt_df["Date"] >= pd.to_datetime(start_date)]
        if end_date:
            bt_df = bt_df[bt_df["Date"] <= pd.to_datetime(end_date)]

    # Drop rows with NaN features
    valid_mask = bt_df[FEATURES].notna().all(axis=1) & bt_df["above_sma"].notna()
    bt_df = bt_df[valid_mask].copy()

    if len(bt_df) < 10:
        return {"error": "Insufficient data for backtest", "trades": 0}

    # Get model predictions
    feature_rows = bt_df[FEATURES].values.astype(np.float32)
    if scaler is not None:
        feature_rows = scaler.transform(feature_rows)

    predictions = []
    for name, model in ensemble_models.items():
        try:
            if hasattr(model, "predict_proba"):
                preds = model.predict_proba(feature_rows)[:, 1]
            else:
                preds = model.predict(feature_rows)
            predictions.append(preds)
        except Exception:
            predictions.append(np.full(len(feature_rows), 0.5))

    # Stack and get meta-learner predictions
    if len(predictions) > 1:
        stacked = np.column_stack(predictions)
        final_probs = meta_model.predict_proba(stacked)[:, 1]
    else:
        final_probs = predictions[0]

    bt_df["prob"] = final_probs

    # Generate signals
    cost = cost_bps / 10000
    bt_df["signal"] = np.where(
        (bt_df["prob"] > threshold) & (bt_df["above_sma"]),
        "BUY", "HOLD"
    )

    # Calculate returns per trade
    trades = []
    equity = 1.0
    equity_curve = [equity]
    in_trade = False
    trade_entry_idx = None

    for i in range(len(bt_df)):
        row = bt_df.iloc[i]

        if row["signal"] == "BUY" and not in_trade:
            in_trade = True
            trade_entry_idx = i
        elif in_trade:
            days_held = i - trade_entry_idx
            if days_held >= holding_period:
                # Exit trade
                fwd_ret = row.get("fwd_ret_5d", 0)
                if pd.isna(fwd_ret):
                    fwd_ret = 0
                net_ret = fwd_ret - cost
                equity *= (1 + net_ret)

                entry_price = bt_df.iloc[trade_entry_idx]["Close"]
                exit_price = row["Close"]
                trades.append({
                    "entry_date": str(bt_df.iloc[trade_entry_idx].get("Date", "")),
                    "exit_date": str(row.get("Date", "")),
                    "entry_price": round(float(entry_price), 2),
                    "exit_price": round(float(exit_price), 2),
                    "return_pct": round(float(net_ret * 100), 2),
                    "holding_days": days_held,
                })
                in_trade = False
                trade_entry_idx = None

        equity_curve.append(equity)

    # Compute metrics
    if trades:
        returns = [t["return_pct"] / 100 for t in trades]
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r <= 0]
        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0
        profit_factor = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else float("inf")

        # Max drawdown
        eq = np.array(equity_curve)
        peak = np.maximum.accumulate(eq)
        dd = (eq - peak) / peak
        max_dd = float(dd.min()) * 100

        # Sharpe (simplified)
        daily_rets = np.diff(eq) / eq[:-1]
        sharpe = (np.mean(daily_rets) / np.std(daily_rets) * np.sqrt(252)) if np.std(daily_rets) > 0 else 0

        total_return = (equity - 1) * 100
        n_years = len(bt_df) / 252
        cagr = ((equity ** (1 / max(n_years, 0.01))) - 1) * 100 if n_years > 0 else 0
    else:
        avg_win = avg_loss = profit_factor = max_dd = sharpe = total_return = cagr = 0
        wins = losses = []

    return {
        "ticker": bt_df.iloc[0].get("ticker", "UNKNOWN") if "ticker" in bt_df.columns else "UNKNOWN",
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate_pct": round(len(wins) / max(len(trades), 1) * 100, 1),
        "avg_win_pct": round(float(avg_win * 100), 2),
        "avg_loss_pct": round(float(avg_loss * 100), 2),
        "profit_factor": round(float(profit_factor), 2),
        "total_return_pct": round(float(total_return), 2),
        "cagr_pct": round(float(cagr), 2),
        "max_drawdown_pct": round(float(max_dd), 2),
        "sharpe_ratio": round(float(sharpe), 3),
        "holding_period_days": holding_period,
        "threshold": threshold,
        "cost_bps": cost_bps,
        "data_points": len(bt_df),
        "date_range": {
            "start": str(bt_df.iloc[0].get("Date", "")) if len(bt_df) > 0 else "",
            "end": str(bt_df.iloc[-1].get("Date", "")) if len(bt_df) > 0 else "",
        },
        "trades": trades[:50],  # Limit to first 50 for response size
        "equity_curve": [round(float(x), 4) for x in equity_curve[::max(1, len(equity_curve)//200)]],
    }


@router.post("/run")
def run_backtest(req: BacktestRequest):
    """Run a historical backtest for a ticker with configurable parameters."""
    ticker = req.ticker.upper()

    df = _load_ticker_data(ticker)
    if df is None or len(df) < 250:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient historical data for {ticker}. Need at least 250 data points. Available tickers: AAPL, AMZN, GOOGL, MSFT, TSLA.",
        )

    return _run_backtest(
        df,
        threshold=req.threshold,
        holding_period=req.holding_period,
        cost_bps=req.cost_bps,
        start_date=req.start_date,
        end_date=req.end_date,
    )


@router.get("/tickers")
def available_backtest_tickers():
    """List tickers with sufficient historical data for backtesting."""
    tickers = []
    if os.path.exists(DATA_DIR):
        for f in os.listdir(DATA_DIR):
            if f.endswith(".csv"):
                ticker = f.replace(".csv", "")
                path = os.path.join(DATA_DIR, f)
                try:
                    df = pd.read_csv(path)
                    if len(df) >= 250:
                        tickers.append({
                            "ticker": ticker,
                            "data_points": len(df),
                            "start": str(df.iloc[0].get("Date", df.iloc[0].get("date", ""))),
                            "end": str(df.iloc[-1].get("Date", df.iloc[-1].get("date", ""))),
                        })
                except Exception:
                    pass
    return {"tickers": tickers, "count": len(tickers)}
