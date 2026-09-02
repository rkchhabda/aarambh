"""Production inference API: Ensemble (XGB + RF + LR) + 200-day SMA regime.

POST /v1/signal {"ticker": "RELIANCE.NS"} -> {signal, confidence, regime, timestamp}
No API key required (defaults to pro tier).
"""

import os
import sys
import json
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import ta
import joblib
import requests
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel

from service.database import init_db
from service.ratelimit import RateLimitMiddleware
from service.routes_auth import router as auth_router
from service.routes_watchlist import router as watchlist_router
from service.routes_portfolio import router as portfolio_router
from service.routes_scanner import router as scanner_router
from service.routes_signals import router as signals_router
from service.routes_alerts import router as alerts_router
from service.routes_admin import router as admin_router

# Load portal HTML at import time (file-based, works everywhere)
def _load_portal_html():
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html"),
        os.path.join(os.getcwd(), "service", "static", "index.html"),
        "/opt/render/project/src/service/static/index.html",
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    return "<h1>Portal not found</h1>"

PORTAL_HTML = _load_portal_html()

# ------------------------------------------------------------
# Paths and constants
# ------------------------------------------------------------
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(WORKSPACE, "service", "models")

# Ensure repo root is importable so `features.*` and `rebuild_cache_v2` resolve
# regardless of the working directory the service is started from.
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

import threading
try:
    from rebuild_cache_v2 import rebuild_cache
except Exception as _imp_err:
    print(f"[WARN] cache auto-refresh unavailable: {_imp_err}")
    rebuild_cache = None

CACHE_REFRESH_HOURS = float(os.environ.get("CACHE_REFRESH_HOURS", "24"))

# Nifty 100 tickers — single source of truth (train == serve).
from features.universe import TICKERS

SEQ_LEN = 32

# Feature list must match what you used for training the ensemble (v2: 10 features, 5d horizon)
FEATURES = ["bb_pos", "macd", "obv_slope", "sma_ratio", "cci", "ret_10",
            "williams_r", "rsi_14", "atr_14", "roc_10"]

# Decision threshold, tuned on validation (stored in features.json by retrain_v2.py).
# High confidence is required for the signal to carry a positive return edge.
_THRESHOLD = 0.5
_manifest_path = os.path.join(MODELS_DIR, "features.json")
if os.path.exists(_manifest_path):
    try:
        with open(_manifest_path) as f:
            _manifest = json.load(f)
        _THRESHOLD = float(_manifest.get("threshold", 0.5))
    except Exception:
        pass

app = FastAPI(title="Aarambh_Quant Signals", version="5.0.0",
              description="Evidence-based quantitative market intelligence for Indian equities")

# ─── Middleware ───────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)

# ─── Database ────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup_init():
    init_db()
    print("[OK] Database initialized")

# ─── Register Routers ────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(watchlist_router)
app.include_router(portfolio_router)
app.include_router(scanner_router)
app.include_router(signals_router)
app.include_router(alerts_router)
app.include_router(admin_router)

# ------------------------------------------------------------
# Serve portal directly from Python (no StaticFiles needed)
# ------------------------------------------------------------
@app.get("/")
def root():
    return RedirectResponse(url="/app/")

@app.get("/app/", response_class=HTMLResponse)
@app.get("/app", response_class=HTMLResponse)
def serve_portal():
    return HTMLResponse(content=PORTAL_HTML)

# ------------------------------------------------------------
# Load Ensemble Models
# ------------------------------------------------------------
ensemble_models = None
meta_model = None
scaler = None
_LOADED = False

def _ensure_loaded():
    global ensemble_models, meta_model, scaler, _LOADED
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

    # Feature scaler (trained alongside the ensemble; LR base needs it).
    scaler_path = os.path.join(MODELS_DIR, "scaler.pkl")
    if os.path.exists(scaler_path):
        scaler = joblib.load(scaler_path)
        print("[OK] Loaded feature scaler")
    else:
        print("[WARN] scaler.pkl not found - serving unscaled features")
    
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
# Feature-schema assertion (fail loudly on train/serve skew)
# ------------------------------------------------------------
def _assert_feature_schema():
    manifest_path = os.path.join(MODELS_DIR, "features.json")
    if not os.path.exists(manifest_path):
        print("[WARN] features.json manifest missing - cannot assert feature parity.")
        return
    with open(manifest_path) as f:
        manifest = json.load(f)
    expected = manifest.get("features", [])
    if expected and expected != FEATURES:
        raise RuntimeError(
            f"Feature schema mismatch! Model trained on {expected}, "
            f"service serves {FEATURES}. Retrain or fix FEATURES."
        )
    print(f"[OK] Feature schema verified ({len(FEATURES)} features, horizon={manifest.get('horizon')})")

_assert_feature_schema()

# ------------------------------------------------------------
# Background cache auto-refresh (keeps live signals current)
# ------------------------------------------------------------
_MIN_TICKERS = 40  # never replace cache with fewer tickers than this

def _refresh_cache_loop():
    # Wait before first refresh so the service can serve from committed cache.
    time.sleep(60)
    while True:
        try:
            new_cache = rebuild_cache()
            if new_cache and len(new_cache) >= _MIN_TICKERS:
                global _TICKER_CACHE
                _TICKER_CACHE = new_cache
                print(f"[OK] Auto-refreshed ticker cache ({len(new_cache)} tickers)")
            else:
                print(f"[WARN] Cache refresh returned only {len(new_cache or {})} tickers — keeping old cache")
        except Exception as e:
            print(f"[WARN] Cache refresh failed: {e}")
        time.sleep(CACHE_REFRESH_HOURS * 3600)

if rebuild_cache is not None:
    threading.Thread(target=_refresh_cache_loop, daemon=True).start()
    print(f"[OK] Cache auto-refresh scheduled every {CACHE_REFRESH_HOURS}h (first run on boot)")

# ------------------------------------------------------------
# Data fetching - use cached features (no live API calls)
# ------------------------------------------------------------
# Load ticker cache at startup
_CACHE_PATH = os.path.join(MODELS_DIR, "ticker_cache.json")
_TICKER_CACHE = {}

def _load_cache():
    global _TICKER_CACHE
    if os.path.exists(_CACHE_PATH):
        with open(_CACHE_PATH) as f:
            _TICKER_CACHE = json.load(f)
        print(f"[OK] Loaded ticker cache: {len(_TICKER_CACHE)} tickers")
    else:
        print("[WARN] Ticker cache not found")

_load_cache()

def fetch_cached_features(ticker: str) -> dict:
    """Get cached features and market data for a ticker."""
    if not _TICKER_CACHE:
        _load_cache()
    
    if ticker not in _TICKER_CACHE:
        raise ValueError(f"No cached data for {ticker}")
    
    return _TICKER_CACHE[ticker]

class SignalRequest(BaseModel):
    ticker: str

# ------------------------------------------------------------
# HEALTH ENDPOINT
# ------------------------------------------------------------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_type": "ensemble v2 (XGB + RF + LR + meta, 5d horizon)",
        "models_loaded": list(ensemble_models.keys()) if ensemble_models else [],
        "meta_loaded": meta_model is not None,
        "supported_tickers": len(TICKERS),
        "features": len(FEATURES),
        "horizon": "5d",
        "threshold": _THRESHOLD
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

    # Get cached features and market data
    try:
        cached = fetch_cached_features(ticker)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Market data failure: {e}")

    close = cached["close"]
    sma200 = cached["sma_200"]
    above_sma = cached["above_sma"]
    features = cached["features"]

    # Build feature row for ensemble
    feature_row = np.array([[features[f] for f in FEATURES]], dtype=np.float32)
    if scaler is not None:
        feature_row = scaler.transform(feature_row)

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

    # Apply regime filter (long-only: BUY only if above SMA and prob > threshold)
    signal_value = "BUY" if (final_prob > _THRESHOLD and above_sma) else "HOLD"

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