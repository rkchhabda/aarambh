"""Production inference API: Ensemble (XGB + RF + LR) + 200-day SMA regime.

POST /v1/signal {"ticker": "RELIANCE.NS"} -> {signal, confidence, regime, timestamp}
No API key required (defaults to pro tier).
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
# Paths and constants
# ------------------------------------------------------------
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(WORKSPACE, "service", "models")

# Nifty 100 tickers (with .NS suffix for Yahoo Finance)
# Removed delisted/invalid: ZOMATO, TATAMOTORS, ADANITRANS, GMRINFRA, LTIM, MCDOWELL-N, PEL
TICKERS = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BPCL.NS", "BHARTIARTL.NS",
    "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DIVISLAB.NS", "DRREDDY.NS",
    "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS",
    "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS",
    "M&M.NS", "MARUTI.NS", "NESTLEIND.NS", "NTPC.NS", "ONGC.NS",
    "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SBIN.NS", "SUNPHARMA.NS",
    "TCS.NS", "TATACONSUM.NS", "TATASTEEL.NS", "TECHM.NS",
    "TITAN.NS", "ULTRACEMCO.NS", "UPL.NS", "WIPRO.NS", "ADANIGREEN.NS",
    "AMBUJACEM.NS", "APOLLOTYRE.NS", "ASHOKLEY.NS", "ASTRAL.NS",
    "AUROPHARMA.NS", "BALKRISIND.NS", "BANDHANBNK.NS", "BANKBARODA.NS", "BEL.NS",
    "BHEL.NS", "BIOCON.NS", "BOSCHLTD.NS", "CANBK.NS", "CHOLAFIN.NS",
    "COLPAL.NS", "CONCOR.NS", "CROMPTON.NS", "CUMMINSIND.NS", "DABUR.NS",
    "DALBHARAT.NS", "DEEPAKNTR.NS", "DLF.NS", "EDELWEISS.NS", "EMAMILTD.NS",
    "ENDURANCE.NS", "ESCORTS.NS", "EXIDEIND.NS", "FEDERALBNK.NS", "GAIL.NS",
    "GLENMARK.NS", "GODREJCP.NS", "GODREJPROP.NS", "GRANULES.NS",
    "HAVELLS.NS", "HINDPETRO.NS", "ICICIGI.NS", "ICICIPRULI.NS", "IDEA.NS",
    "IDFCFIRSTB.NS", "IGL.NS", "INDIGO.NS", "INDUSTOWER.NS", "JINDALSTEL.NS",
    "JUBLFOOD.NS", "LICHSGFIN.NS", "LUPIN.NS", "MARICO.NS",
    "MAXHEALTH.NS", "MFSL.NS", "MOTHERSON.NS", "MPHASIS.NS",
    "MRF.NS", "MUTHOOTFIN.NS", "NAUKRI.NS", "NAVINFLUOR.NS", "NBCC.NS",
    "NMDC.NS", "OBEROIRLTY.NS", "PAGEIND.NS", "PERSISTENT.NS",
    "PETRONET.NS", "PFC.NS", "PIDILITIND.NS", "PIIND.NS", "PNB.NS",
    "POLYCAB.NS", "PVRINOX.NS", "RAMCOCEM.NS", "RBLBANK.NS", "RECLTD.NS",
    "SAIL.NS", "SHREECEM.NS", "SIEMENS.NS", "SRF.NS", "SYNGENE.NS",
    "TATACHEM.NS", "TATACOMM.NS", "TATAPOWER.NS", "TORNTPHARM.NS", "TORNTPOWER.NS",
    "TRENT.NS", "TVSMOTOR.NS", "UBL.NS", "UNIONBANK.NS", "VBL.NS",
    "VEDL.NS", "VOLTAS.NS", "WHIRLPOOL.NS", "ZYDUSLIFE.NS"
]
SEQ_LEN = 32

# Feature list must match what you used for training the ensemble
FEATURES = ["ret_1", "ret_5", "ret_10", "log_vol_chg", "rsi_14", "macd",
            "bb_pos", "atr_14", "obv_slope", "sma_ratio", "rvol_5", "rvol_20"]

app = FastAPI(title="Quant Signal API (Ensemble - Nifty 100)", version="3.0.0")

# ------------------------------------------------------------
# Mount static files for web portal (at /app to avoid API conflicts)
# ------------------------------------------------------------
possible_static_dirs = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "static"),
    os.path.join(os.getcwd(), "service", "static"),
    "/opt/render/project/src/service/static",
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
    
    if len(available_models) == 1:
        ensemble_models = available_models
    elif len(available_models) > 1:
        ensemble_models = available_models
    else:
        ensemble_models = {}
        print("[WARN] No ensemble models found.")
    
    _LOADED = True
    print(f"[OK] Ensemble ready with {len(ensemble_models)} base model(s)")

_ensure_loaded()

# ------------------------------------------------------------
# Data fetching and feature engineering (yfinance for Indian stocks)
# ------------------------------------------------------------
def fetch_history(ticker: str) -> pd.DataFrame:
    """Fetch historical data with retries and session handling for Render compatibility."""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    
    # Create session with retry strategy
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    # Try yfinance with session
    try:
        df = yf.download(ticker, period="2y", interval="1d",
                         auto_adjust=False, progress=False, threads=False, session=session)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
    except Exception as e:
        print(f"yfinance download error: {e}")
        df = pd.DataFrame()
    
    # Fallback: try 5y period
    if df is None or df.empty:
        try:
            df = yf.download(ticker, period="5y", interval="1d",
                             auto_adjust=False, progress=False, threads=False, session=session)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
        except Exception:
            df = pd.DataFrame()
    
    # Fallback: try with different parameters
    if df is None or df.empty:
        try:
            df = yf.download(ticker, start="2022-01-01", end=None,
                             interval="1d", auto_adjust=False, progress=False, threads=False, session=session)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
        except Exception:
            df = pd.DataFrame()
    
    if df is None or df.empty:
        raise ValueError(f"No data returned for {ticker} - check symbol or network")
    
    df = df.reset_index().rename(columns={"Date": "timestamps"})
    df["timestamps"] = pd.to_datetime(df["timestamps"])
    df.columns = [c.lower() for c in df.columns]
    
    if df.empty or len(df) < 50:
        raise ValueError(f"Insufficient data for {ticker}: {len(df)} rows")
    
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
        "meta_loaded": meta_model is not None,
        "supported_tickers": len(TICKERS)
    }

# ------------------------------------------------------------
# SIGNAL ENDPOINT (no API key required, defaults to pro tier)
# ------------------------------------------------------------
@app.post("/v1/signal")
def signal(req: SignalRequest, x_api_key: str = Header(default="")):
    # No API key required - default to pro tier (no delay)
    tier = "pro"
    delay_hours = 0

    ticker = req.ticker.upper()
    if ticker not in TICKERS:
        raise HTTPException(status_code=404, detail=f"Ticker not supported: {ticker}. Use format: RELIANCE.NS")

    # Fetch and compute features
    try:
        raw = fetch_history(ticker)
        df = compute_features(raw)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Market data failure: {e}")

    if len(df) < SEQ_LEN + 210:
        raise HTTPException(status_code=503, detail="Insufficient history")

    # Regime filter (200-day SMA)
    row = df.iloc[-1]
    close, sma200 = float(row["close"]), float(row["sma_200"])
    above_sma = bool(close > sma200)

    # Get features for the last row
    feature_row = df[FEATURES].iloc[-1].values.astype(np.float32).reshape(1, -1)

    # Predict with ensemble
    if ensemble_models is None or meta_model is None:
        raise HTTPException(status_code=503, detail="Ensemble models not loaded.")

    model_names = list(ensemble_models.keys())
    
    if len(model_names) == 1:
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

    # Apply regime filter (long-only: BUY only if above SMA and prob > 0.5)
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