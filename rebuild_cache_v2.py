"""Rebuild ticker_cache.json with enhanced v2 features for all Nifty 100 tickers."""
import os, json, warnings
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, yfinance as yf
from datetime import datetime, timedelta

# Single source of truth for features (must match training).
from features.indicators import compute_inference_features
# Single source of truth for the tradable universe (train == serve).
from features.universe import TICKERS

BASE = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE, "service", "models")
CACHE_PATH = os.path.join(MODELS_DIR, "ticker_cache.json")

# Features used by the deployed ensemble (must match features.json / best_params.json).
MANIFEST_PATH = os.path.join(MODELS_DIR, "features.json")
if os.path.exists(MANIFEST_PATH):
    try:
        with open(MANIFEST_PATH) as f:
            INFERENCE_FEATURES = json.load(f).get("features", [
                "bb_pos", "macd", "obv_slope", "sma_ratio", "cci", "ret_10",
                "williams_r", "rsi_14", "atr_14", "roc_10"
            ])
    except Exception:
        INFERENCE_FEATURES = ["bb_pos", "macd", "obv_slope", "sma_ratio", "cci", "ret_10", "williams_r", "rsi_14", "atr_14", "roc_10"]
else:
    INFERENCE_FEATURES = [
        "bb_pos", "macd", "obv_slope", "sma_ratio", "cci", "ret_10",
        "williams_r", "rsi_14", "atr_14", "roc_10",
    ]


def _to_frame(df):
    """Normalize a yfinance ticker frame to the columns compute_features expects."""
    df = df.reset_index()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.capitalize() for c in df.columns]
    if "Date" in df.columns:
        df.rename(columns={"Date": "date"}, inplace=True)
    return df


def rebuild_cache(cache_path=CACHE_PATH):
    """Download fresh OHLCV and rebuild ticker_cache.json with v2 features.
    Returns the cache dict. Safe to call from a background thread."""
    print(f"[{_now()}] Rebuilding cache with shared features for {len(TICKERS)} tickers...")
    data = yf.download(TICKERS, period="5y", group_by="ticker", progress=False, threads=True)

    cache = {}
    ok = 0
    for ticker in TICKERS:
        try:
            raw = data[ticker].dropna()
            if len(raw) < 210:
                continue
            df = _to_frame(raw)
            features, close, sma200 = compute_inference_features(df, INFERENCE_FEATURES)
            cache[ticker] = {
                "features": features,
                "close": close,
                "sma_200": sma200,
                "above_sma": bool(close > sma200)
            }
            ok += 1
        except Exception as e:
            print(f"  FAIL {ticker}: {e}")

    print(f"[{_now()}] Done: {ok}/{len(TICKERS)}")
    with open(cache_path, "w") as f:
        json.dump(cache, f, indent=2)
    print(f"[{_now()}] Saved to {cache_path}")
    return cache


def _now():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    rebuild_cache()
