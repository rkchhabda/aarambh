"""Production inference API: Ensemble (XGB + RF + LR) + 200-day SMA regime.

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
import joblib
import yfinance as yf
from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

# ------------------------------------------------------------
# SAFE IMPORT for keys.py (fallback if missing or broken)
# ------------------------------------------------------------
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from keys import validate_api_key, get_tier, TIERS  # noqa: E402
except (ImportError, NameError, AttributeError):
    def validate_api_key(key):
        return {"tier": "free"} if key else None
    def get_tier(key):
        return "free"
    TIERS = {
        "free": {"delay_hours": 0, "name": "Free"},
        "pro": {"delay_hours": 0, "name": "Pro"}
    }
    print("[WARN] keys.py not found — using dummy fallback.")

# ------------------------------------------------------------
# Paths and constants
# ------------------------------------------------------------
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(WORKSPACE, "service", "models")

# US tickers for ensemble model
TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
SEQ_LEN = 32

# Feature list must match what you used for training the ensemble
FEATURES = ["ret_1", "ret_5", "ret_10", "log_vol_chg", "rsi_14", "macd",
            "bb_pos", "atr_14", "obv_slope", "sma_ratio", "rvol_5", "rvol_20"]

app = FastAPI(title="Quant Signal API (Ensemble)", version="2.0.0")

# ------------------------------------------------------------
# Mount static files for web portal (at /app to avoid API conflicts)
# Try multiple paths for local vs Render deployment
# ------------------------------------------------------------
possible_static_dirs = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "static"),  # Local: service/static
    os.path.join(os.getcwd(), "service", "static"),                      # Render: repo_root/service/static
    "/opt/render/project/src/service/static",                            # Render absolute path
]
static_dir = None
for d in possible_static_dirs:
    if os.path.exists(d):
        static_dir = d
        break

if static_dir:
    app.mount("/app", StaticFiles(directory=static_dir, html=True), name="static")
    print(f"[INFO] Mounted static files from: {static_dir}")
else:
    print("[WARN] Static directory not found in any expected location")

# Redirect root to /app
@app.get("/")
def root():
    return RedirectResponse(url="/app/")

# ------------------------------------------------------------
# Load Ensemble Models
# ------------------------------------------------------------
ensemble_models = None
meta_model = None
_LOADED = False

def _ensure_loaded():
    global ensemble_models, meta_model, _LOADED
    if _LOADED:
        return

    # Check which model files exist (match actual file names)
    model_file_map = {
        "xgb": "xgboost.pkl",
        "rf": "randomforest.pkl",
        "lr": "logisticregression.pkl",
    }
    available_models = {}
    for name, filename in model_file_map.items():
        path = os.path.join(MODELS_DIR, filename)
        if os.path.exists(path):
            available_models[name] = joblib.load(path)
            print(f"[OK] Loaded {name}")

    meta_path = os.path.join(MODELS_DIR, "meta_model.pkl")
    if not os.path.exists(meta_path):
        print("[WARN] Meta model not found.")
        _LOADED = True
        return

    meta_model = joblib.load(meta_path)
    
    # If we have multiple base models, use stacking. If only one, use it directly.
    if len(available_models) == 1:
        # Single model - meta_model is actually the base model
        ensemble_models = available_models
    elif len(available_models) > 1:
        # Multiple models - use stacking
        ensemble_models = available_models
    else:
        ensemble_models = {}
        print("[WARN] No ensemble models found.")
    
    _LOADED = True
    print(f"[OK] Ensemble ready with {len(ensemble_models)} base model(s)")

_ensure_loaded()

# ------------------------------------------------------------
# Data fetching and feature engineering (yfinance for US stocks)
# ------------------------------------------------------------
def fetch_history(ticker: str) -> pd.DataFrame:
    df = yf.download(ticker, period="2y", interval="1d",
                     auto_adjust=False, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index().rename(columns={"Date": "timestamps"})
    df["timestamps"] = pd.to_datetime(df["timestamps"])
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

# ------------------------------------------------------------
# HEALTH ENDPOINT
# ------------------------------------------------------------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_type": "ensemble (XGB + RF + LR + meta)",
        "models_loaded": list(ensemble_models.keys()) if ensemble_models else [],
        "meta_loaded": meta_model is not None
    }

# ------------------------------------------------------------
# SIGNAL ENDPOINT (uses ensemble)
# ------------------------------------------------------------
@app.post("/v1/signal")
def signal(req: SignalRequest, x_api_key: str = Header(default="")):
    # 1. Authenticate
    tier_info = validate_api_key(x_api_key)
    if tier_info is None:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    tier = get_tier(x_api_key)
    delay_hours = TIERS[tier]["delay_hours"]
    if delay_hours:
        raise HTTPException(
            status_code=403,
            detail=f"Tier '{tier}' receives signals with a {delay_hours}h delay."
        )

    ticker = req.ticker.upper()
    if ticker not in TICKERS:
        raise HTTPException(status_code=404, detail=f"Ticker not supported: {ticker}")

    # 2. Fetch and compute features
    try:
        raw = fetch_history(ticker)
        df = compute_features(raw)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Market data failure: {e}")

    if len(df) < SEQ_LEN + 210:
        raise HTTPException(status_code=503, detail="Insufficient history")

    # 3. Regime filter (200-day SMA)
    row = df.iloc[-1]
    close, sma200 = float(row["close"]), float(row["sma_200"])
    above_sma = bool(close > sma200)

    # 4. Get features for the last row
    #    Ensemble uses the LAST ROW features, not a sequence
    feature_row = df[FEATURES].iloc[-1].values.astype(np.float32).reshape(1, -1)

    # 5. Predict with ensemble
    if ensemble_models is None or meta_model is None:
        raise HTTPException(status_code=503, detail="Ensemble models not loaded.")

    # Check if we're using stacking (multiple base models) or single model
    model_names = list(ensemble_models.keys())
    
    if len(model_names) == 1:
        # Single model case - meta_model IS the base model
        model = ensemble_models[model_names[0]]
        try:
            if hasattr(model, "predict_proba"):
                final_prob = model.predict_proba(feature_row)[0][1]
            else:
                final_prob = model.predict(feature_row)[0]
        except Exception as e:
            print(f"Error with {model_names[0]}: {e}")
            final_prob = 0.5
    else:
        # Stacking case - multiple base models
        proba = []
        for name, model in ensemble_models.items():
            try:
                if hasattr(model, "predict_proba"):
                    p = model.predict_proba(feature_row)[0][1]
                else:
                    p = model.predict(feature_row)[0]
                proba.append(p)
            except Exception as e:
                print(f"Error with {name}: {e}")
                proba.append(0.5)
        
        stacked_input = np.array(proba).reshape(1, -1)
        final_prob = meta_model.predict_proba(stacked_input)[0][1]

    # 6. Apply regime filter (long-only: BUY only if above SMA and prob > 0.5)
    signal_value = "BUY" if (final_prob > 0.5 and above_sma) else "HOLD"

    return {
        "ticker": ticker,
        "signal": signal_value,
        "confidence": round(float(final_prob), 4),
        "regime": "BULL" if above_sma else "BEAR",
        "price": round(close, 2),
        "sma_200": round(sma200, 2),
        "tier": tier,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)