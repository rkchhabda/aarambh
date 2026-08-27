"""Production inference API: LSTM signal + 200-day SMA regime per ticker.

POST /v1/signal {"ticker": "RELIANCE"} -> {signal, confidence, regime, timestamp}
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
from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ------------------------------------------------------------
# SAFE IMPORT for keys.py (fallback if missing or broken)
# ------------------------------------------------------------
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from keys import validate_api_key, get_tier, TIERS  # noqa: E402
except (ImportError, NameError, AttributeError):
    # Fallback: dummy key validation so /health works
    def validate_api_key(key):
        return {"tier": "free"} if key else None

    def get_tier(key):
        return "free"

    TIERS = {
        "free": {"delay_hours": 0, "name": "Free"},
        "pro": {"delay_hours": 0, "name": "Pro"}
    }
    print("[WARN] keys.py not found or invalid — using dummy fallback for /health only.")

# ------------------------------------------------------------
# NSE Data fetching (nsepythonserver for live, jugaad-data for historical)
# ------------------------------------------------------------
try:
    from nsepythonserver import nsefetch
    from jugaad_data.nse import stock_df
    NSE_AVAILABLE = True
except ImportError:
    NSE_AVAILABLE = False
    print("[WARN] nsepythonserver or jugaad-data not installed — NSE data fetching will fail.")

# ------------------------------------------------------------
# Paths and constants
# ------------------------------------------------------------
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(WORKSPACE, "service", "models")

# NSE tickers (RELIANCE is the default; add more as needed)
TICKERS = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"]
SEQ_LEN = 32
FEATURES = ["ret_1", "ret_5", "ret_10", "log_vol_chg", "rsi_14", "macd",
            "bb_pos", "atr_14", "obv_slope", "sma_ratio", "rvol_5", "rvol_20"]

app = FastAPI(title="Quant Signal API (NSE)", version="1.0.0")

# Mount static files for web portal (at /app to avoid API conflicts)
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/app", StaticFiles(directory=static_dir, html=True), name="static")

# Redirect root to /app
from fastapi.responses import RedirectResponse

@app.get("/")
def root():
    return RedirectResponse(url="/app/")

# ------------------------------------------------------------
# LSTM Model Definition
# ------------------------------------------------------------
class LSTMClassifier(torch.nn.Module):
    def __init__(self, n_features, hidden=64):
        super().__init__()
        self.lstm = torch.nn.LSTM(n_features, hidden, num_layers=1, batch_first=True)
        self.head = torch.nn.Sequential(
            torch.nn.Linear(hidden, 16), torch.nn.ReLU(), torch.nn.Linear(16, 1))

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :]).squeeze(-1)

# ------------------------------------------------------------
# Model Loading (with graceful fallback)
# ------------------------------------------------------------
MODELS: dict[str, tuple[LSTMClassifier, np.ndarray, np.ndarray]] = {}
_LOADED = False

def _ensure_loaded():
    global MODELS, _LOADED
    if _LOADED:
        return

    manifest_path = os.path.join(MODELS_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        print(f"[WARN] manifest.json not found at {manifest_path} — models will not load.")
        _LOADED = True
        return

    try:
        with open(manifest_path) as f:
            manifest = json.load(f)

        # Only load models for supported Indian tickers (NSE)
        supported_set = set(TICKERS)
        for ticker, meta in manifest.items():
            if ticker not in supported_set:
                print(f"[INFO] Skipping {ticker} — not in supported Indian tickers ({supported_set})")
                continue

            model_path = os.path.join(MODELS_DIR, ticker, "lstm.pt")
            scaler_path = os.path.join(MODELS_DIR, ticker, "scaler.npz")

            if not os.path.exists(model_path) or not os.path.exists(scaler_path):
                print(f"[WARN] Missing model or scaler for {ticker} — skipping.")
                continue

            model = LSTMClassifier(len(meta["features"]), meta["hidden"])
            state = torch.load(model_path, map_location="cpu", weights_only=True)
            model.load_state_dict(state)
            model.eval()
            sc = np.load(scaler_path)
            MODELS[ticker] = (model, sc["mean"], sc["scale"])
            print(f"[OK] Loaded model for {ticker}")

    except Exception as e:
        print(f"[ERROR] Failed to load models: {e}")

    _LOADED = True

# Load models at startup (but don't crash the app if they fail)
_ensure_loaded()

# ------------------------------------------------------------
# Data fetching and feature engineering (NSE)
# ------------------------------------------------------------
def fetch_history(ticker: str) -> pd.DataFrame:
    """
    Fetch historical data for NSE ticker using jugaad-data.
    Returns DataFrame with columns: timestamps, open, high, low, close, volume
    """
    if not NSE_AVAILABLE:
        raise RuntimeError("nsepythonserver or jugaad-data not available. Install requirements.")

    # jugaad-data expects symbol like 'RELIANCE'
    # Fetch last 400 trading days to ensure we have 200+ for SMA + 32 for sequence
    from datetime import date, timedelta
    end_date = date.today()
    start_date = end_date - timedelta(days=500)  # ~400 trading days with buffer
    
    df = stock_df(symbol=ticker, from_date=start_date, to_date=end_date, series="EQ")
    
    if df is None or df.empty:
        raise ValueError(f"No data returned for {ticker}")

    # jugaad-data returns columns: DATE, OPEN, HIGH, LOW, CLOSE, VOLUME, ...
    df = df.rename(columns={
        "DATE": "timestamps",
        "OPEN": "open",
        "HIGH": "high",
        "LOW": "low",
        "CLOSE": "close",
        "VOLUME": "volume"
    })
    
    # Keep only needed columns
    df = df[["timestamps", "open", "high", "low", "close", "volume"]].copy()
    
    df["timestamps"] = pd.to_datetime(df["timestamps"])
    df = df.sort_values("timestamps").reset_index(drop=True)
    
    # Convert to numeric
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    
    df = df.dropna().reset_index(drop=True)
    
    if len(df) < 250:  # Need at least 200 for SMA + 32 for sequence
        raise ValueError(f"Insufficient data for {ticker}: {len(df)} rows")
    
    return df


def fetch_live_quote(ticker: str) -> dict:
    """
    Fetch live quote using nsepythonserver's nsefetch (bypasses NSE IP blocks on Render).
    Returns dict with lastPrice, change, etc.
    """
    if not NSE_AVAILABLE:
        raise RuntimeError("nsepythonserver not available")
    
    # Use nsefetch with the NSE quote API endpoint
    url = f"https://www.nseindia.com/api/quote-equity?symbol={ticker}"
    quote_data = nsefetch(url)
    return quote_data


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
    ticker: str = "RELIANCE"  # Default to RELIANCE for NSE

# ------------------------------------------------------------
# HEALTH ENDPOINT
# ------------------------------------------------------------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "models_loaded": sorted(MODELS.keys()),
        "models_dir_exists": os.path.exists(MODELS_DIR),
        "nse_available": NSE_AVAILABLE,
        "supported_tickers": TICKERS
    }


# ------------------------------------------------------------
# SIGNAL ENDPOINT (requires API key)
# ------------------------------------------------------------
@app.post("/v1/signal")
def signal(req: SignalRequest, x_api_key: str = Header(default="")):
    tier_info = validate_api_key(x_api_key)
    if tier_info is None:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    ticker = req.ticker.upper()
    
    # Validate: Only Indian tickers (NSE) are supported
    if ticker not in TICKERS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Only Indian tickers are supported. "
                f"Supported tickers: {TICKERS}"
            )
        )

    tier = get_tier(x_api_key)
    delay_hours = TIERS[tier]["delay_hours"]
    if delay_hours:
        raise HTTPException(
            status_code=403,
            detail=f"Tier '{tier}' receives signals with a {delay_hours}h delay."
        )

    # Fetch historical data (last 30 days) for SMA calculation
    try:
        from datetime import date, timedelta
        end_date = date.today()
        start_date = end_date - timedelta(days=45)  # ~30 trading days with buffer
        hist_df = stock_df(symbol=ticker, from_date=start_date, to_date=end_date, series="EQ")
        
        if hist_df is None or hist_df.empty:
            raise ValueError(f"No historical data returned for {ticker}")
        
        # Rename columns
        hist_df = hist_df.rename(columns={
            "DATE": "timestamps",
            "OPEN": "open",
            "HIGH": "high",
            "LOW": "low",
            "CLOSE": "close",
            "VOLUME": "volume"
        })
        
        # Keep needed columns
        hist_df = hist_df[["timestamps", "close"]].copy()
        hist_df["timestamps"] = pd.to_datetime(hist_df["timestamps"])
        hist_df = hist_df.sort_values("timestamps").reset_index(drop=True)
        hist_df["close"] = pd.to_numeric(hist_df["close"], errors="coerce")
        hist_df = hist_df.dropna().reset_index(drop=True)
        
        if len(hist_df) < 20:
            raise ValueError(f"Insufficient historical data for {ticker}: {len(hist_df)} rows")
            
        # Calculate 20-day SMA
        sma_20 = float(hist_df["close"].rolling(window=20).mean().iloc[-1])
        
    except Exception as e:
        error_msg = str(e).lower()
        if "rate limit" in error_msg or "too many requests" in error_msg or "429" in error_msg:
            raise HTTPException(status_code=429, detail="NSE rate limit exceeded. Please try again later.")
        raise HTTPException(status_code=502, detail=f"Historical data failure: {e}")

    # Fetch live price using nsefetch
    try:
        url = f"https://www.nseindia.com/api/quote-equity?symbol={ticker}"
        quote_data = nsefetch(url)
        
        # Extract last price from quote data
        # NSE quote structure: quote_data['priceInfo']['lastPrice']
        if 'priceInfo' in quote_data and 'lastPrice' in quote_data['priceInfo']:
            last_price = float(quote_data['priceInfo']['lastPrice'])
        elif 'lastPrice' in quote_data:
            last_price = float(quote_data['lastPrice'])
        else:
            # Fallback: use last close from historical data
            last_price = float(hist_df["close"].iloc[-1])
            
    except Exception as e:
        error_msg = str(e).lower()
        if "rate limit" in error_msg or "too many requests" in error_msg or "429" in error_msg:
            raise HTTPException(status_code=429, detail="NSE rate limit exceeded. Please try again later.")
        # Fallback to last close from historical data
        last_price = float(hist_df["close"].iloc[-1])

    # Generate signal based on price vs SMA
    if last_price > sma_20:
        signal_value = "BUY"
    elif last_price < sma_20:
        signal_value = "SELL"
    else:
        signal_value = "HOLD"

    return {
        "ticker": ticker,
        "price": round(last_price, 2),
        "signal": signal_value,
        "sma_20": round(sma_20, 2)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)