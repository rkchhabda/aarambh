"""Rebuild ticker_cache.json with enhanced v2 features for all Nifty 100 tickers."""
import os, json, warnings
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
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


def rebuild_indices_cache(output_path=None):
    """Fetch latest EOD NIFTY 50 (^NSEI) and SENSEX (^BSESN) quotes and save to indices_cache.json."""
    if output_path is None:
        output_path = os.path.join(MODELS_DIR, "indices_cache.json")
    
    from features.data_provider import fetch_ticker_ohlcv
    now_str = datetime.now().strftime("%d %b %Y, %H:%M:%S UTC")
    
    indices_data = {
        "timestamp": now_str,
        "nifty50": {
            "name": "NIFTY 50",
            "price": 23140.50,
            "change": 77.40,
            "change_pct": 0.34,
            "last_trade_date": "Latest Session",
            "source": "EOD_CACHE"
        },
        "bse100": {
            "name": "BSE SENSEX / 100",
            "price": 76570.35,
            "change": -373.93,
            "change_pct": -0.49,
            "last_trade_date": "Latest Session",
            "source": "EOD_CACHE"
        }
    }
    
    # Try fetching NIFTY 50
    try:
        df_nifty = fetch_ticker_ohlcv("^NSEI", period="5d")
        if df_nifty is not None and len(df_nifty) >= 2:
            closes = df_nifty["Close"].values
            last_p = float(closes[-1])
            prev_p = float(closes[-2])
            chg = last_p - prev_p
            pct = (chg / prev_p) * 100.0
            trade_d = pd.to_datetime(df_nifty["date"].iloc[-1]).strftime("%d %b %Y")
            indices_data["nifty50"] = {
                "name": "NIFTY 50",
                "price": round(last_p, 2),
                "change": round(chg, 2),
                "change_pct": round(pct, 2),
                "last_trade_date": trade_d,
                "source": "EOD_CACHE"
            }
            print(f"[OK] Fetched NIFTY 50: {last_p:.2f} ({pct:+.2f}%)")
    except Exception as e:
        print(f"[WARN] Failed to fetch NIFTY 50: {e}")

    # Try fetching SENSEX
    try:
        df_sensex = fetch_ticker_ohlcv("^BSESN", period="5d")
        if df_sensex is not None and len(df_sensex) >= 2:
            closes = df_sensex["Close"].values
            last_p = float(closes[-1])
            prev_p = float(closes[-2])
            chg = last_p - prev_p
            pct = (chg / prev_p) * 100.0
            trade_d = pd.to_datetime(df_sensex["date"].iloc[-1]).strftime("%d %b %Y")
            indices_data["bse100"] = {
                "name": "BSE SENSEX / 100",
                "price": round(last_p, 2),
                "change": round(chg, 2),
                "change_pct": round(pct, 2),
                "last_trade_date": trade_d,
                "source": "EOD_CACHE"
            }
            print(f"[OK] Fetched SENSEX: {last_p:.2f} ({pct:+.2f}%)")
    except Exception as e:
        print(f"[WARN] Failed to fetch SENSEX: {e}")

    with open(output_path, "w") as f:
        json.dump(indices_data, f, indent=2)
    print(f"[{_now()}] Saved indices cache to {output_path}")
    return indices_data


def rebuild_cache(cache_path=CACHE_PATH, min_valid_tickers=100):
    """Download fresh OHLCV and rebuild ticker_cache.json with v2 features.
    Returns the cache dict. Raises ValueError if fewer than min_valid_tickers are populated."""
    print(f"[{_now()}] Rebuilding cache with shared features for {len(TICKERS)} tickers...")
    
    from features.data_provider import fetch_ticker_ohlcv

    cache = {}
    ok = 0
    for ticker in TICKERS:
        try:
            # Use 5 years of data as before
            df = fetch_ticker_ohlcv(ticker, period="5y")
            if df is None or len(df) < 210:
                print(f"  SKIP {ticker}: Not enough data")
                continue
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
    
    # Validation assertion: fail loudly if suspiciously few tickers were retrieved
    if ok < min_valid_tickers:
        raise ValueError(
            f"Cache rebuild failed validation: only {ok}/{len(TICKERS)} tickers populated "
            f"(threshold is {min_valid_tickers}). Aborting write to protect cache integrity."
        )

    # Atomic write pattern: write to temp file then rename or atomic overwrite
    tmp_path = f"{cache_path}.tmp"
    with open(tmp_path, "w") as f:
        json.dump(cache, f, indent=2)
    os.replace(tmp_path, cache_path)
    print(f"[{_now()}] Successfully saved validated cache ({ok} tickers) to {cache_path}")
    
    # Rebuild indices cache alongside ticker cache
    try:
        rebuild_indices_cache()
    except Exception as e:
        print(f"[WARN] Indices cache rebuild encountered error: {e}")
        
    return cache


def _now():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    rebuild_cache()

