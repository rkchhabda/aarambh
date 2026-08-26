"""Production inference API: LSTM signal + 200-day SMA regime per ticker.

POST /v1/signal {"ticker": "AAPL"} -> {signal, confidence, regime, timestamp}
Requires X-API-Key header (see keys.py for tier management).
"""

import os
import sys
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import ta
import torch
import yfinance as yf
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from keys import validate_api_key, get_tier, TIERS  # noqa: E402

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # GaurviDEEP/
MODELS_DIR = os.path.join(WORKSPACE, "service", "models")
TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
SEQ_LEN = 32
FEATURES = ["ret_1", "ret_5", "ret_10", "log_vol_chg", "rsi_14", "macd",
            "bb_pos", "atr_14", "obv_slope", "sma_ratio", "rvol_5", "rvol_20"]

app = FastAPI(title="Quant Signal API", version="1.0.0")


class LSTMClassifier(torch.nn.Module):
    def __init__(self, n_features, hidden=64):
        super().__init__()
        self.lstm = torch.nn.LSTM(n_features, hidden, num_layers=1, batch_first=True)
        self.head = torch.nn.Sequential(
            torch.nn.Linear(hidden, 16), torch.nn.ReLU(), torch.nn.Linear(16, 1))

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :]).squeeze(-1)


MODELS: dict[str, tuple[LSTMClassifier, np.ndarray, np.ndarray]] = {}
_LOADED = False


def _ensure_loaded():
    global _LOADED
    if _LOADED:
        return
    with open(os.path.join(MODELS_DIR, "manifest.json")) as f:
        manifest = json.load(f)
    for ticker, meta in manifest.items():
        model = LSTMClassifier(len(meta["features"]), meta["hidden"])
        state = torch.load(os.path.join(MODELS_DIR, ticker, "lstm.pt"),
                           map_location="cpu", weights_only=True)
        model.load_state_dict(state)
        model.eval()
        sc = np.load(os.path.join(MODELS_DIR, ticker, "scaler.npz"))
        MODELS[ticker] = (model, sc["mean"], sc["scale"])
    _LOADED = True


# load immediately so MODELS is ready for direct imports
_ensure_loaded()


def fetch_history(ticker: str) -> pd.DataFrame:
    df = yf.download(ticker, period="2y", interval="1d",
                     auto_adjust=False, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index().rename(columns={"Date": "timestamps"})
    df["timestamps"] = pd.to_datetime(df["timestamps"])
    # normalize column names to lowercase
    df.columns = [c.lower() for c in df.columns]
    return df.sort_values("timestamps").reset_index(drop=True)


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    df["ret_1"] = df["close"].pct_change()
    df["ret_5"] = df["close"].pct_change(5)
    df["ret_10"] = df["close"].pct_change(10)
    df["log_vol_chg"] = np.log(df["volume"] + 1).diff()
    df["rsi_14"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    df["macd"] = ta.trend.MACD(df["close"]).macd_diff()
    bb = ta.volatility.BollingerBands(df["close"], window=20)
    df["bb_pos"] = (df["close"] - bb.bollinger_mavg()) / bb.bollinger_wband()
    df["atr_14"] = ta.volatility.AverageTrueRange(
        df["high"], df["low"], df["close"], window=14).average_true_range() / df["close"]
    df["obv_slope"] = ta.volume.OnBalanceVolumeIndicator(
        df["close"], df["volume"]).on_balance_volume().diff(5)
    df["sma_ratio"] = df["close"] / ta.trend.SMAIndicator(df["close"], window=20).sma_indicator() - 1
    df["rvol_5"] = df["ret_1"].rolling(5).std()
    df["rvol_20"] = df["ret_1"].rolling(20).std()
    df["sma_200"] = ta.trend.SMAIndicator(df["close"], window=200).sma_indicator()
    return df


class SignalRequest(BaseModel):
    ticker: str


@app.get("/health")
def health():
    return {"status": "ok", "models_loaded": sorted(MODELS.keys())}


@app.post("/v1/signal")
def signal(req: SignalRequest, x_api_key: str = Header(default="")):
    tier_info = validate_api_key(x_api_key)
    if tier_info is None:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    ticker = req.ticker.upper()
    if ticker not in TICKERS:
        raise HTTPException(status_code=404, detail=f"Ticker not supported: {ticker}")

    tier = get_tier(x_api_key)
    delay_hours = TIERS[tier]["delay_hours"]
    if delay_hours:
        raise HTTPException(
            status_code=403,
            detail=f"Tier '{tier}' receives signals with a {delay_hours}h delay. "
                   f"Upgrade to Pro for real-time access.")

    try:
        raw = fetch_history(ticker)
        df = compute_features(raw)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Market data failure: {e}")

    if len(df) < SEQ_LEN + 210:
        raise HTTPException(status_code=503, detail="Insufficient history")

    row = df.iloc[-1]
    close, sma200 = float(row["close"]), float(row["sma_200"])
    above_sma = bool(close > sma200)

    feats = df[FEATURES].iloc[-SEQ_LEN:].values.astype(np.float32)
    mean, scale = MODELS[ticker][1], MODELS[ticker][2]
    feats = (feats - mean) / scale
    feats = feats.astype(np.float32)
    model = MODELS[ticker][0]
    with torch.no_grad():
        logit = model(torch.from_numpy(feats[np.newaxis]))
        p_up = float(torch.sigmoid(logit).item())

    # Scenario 2/2b rules: long-only + 200-day SMA regime filter
    signal_value = "BUY" if (p_up > 0.5 and above_sma) else "HOLD"

    return {
        "ticker": ticker,
        "signal": signal_value,
        "confidence": round(p_up, 4),
        "regime": "BULL" if above_sma else "BEAR",
        "price": round(close, 2),
        "sma_200": round(sma200, 2),
        "tier": tier,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
