"""Detailed signal endpoint — full factor analysis, quant score, risk metrics, history."""

import json
import os
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/v1", tags=["signals-detail"])

MODELS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "service", "models",
)

# Feature categories for factor analysis
FACTOR_GROUPS = {
    "Trend": ["sma_ratio", "macd", "bb_pos"],
    "Momentum": ["rsi_14", "williams_r", "roc_10", "cci"],
    "Volatility": ["atr_14"],
    "Volume": ["obv_slope"],
    "Returns": ["ret_10"],
}

FACTOR_DESCRIPTIONS = {
    "sma_ratio": "Price vs 20-day SMA — positive means uptrend",
    "macd": "MACD histogram — positive means bullish momentum",
    "bb_pos": "Bollinger Band position — higher means overbought territory",
    "rsi_14": "14-day RSI — >70 overbought, <30 oversold",
    "williams_r": "Williams %R — momentum oscillator",
    "roc_10": "10-day Rate of Change — price momentum",
    "cci": "Commodity Channel Index — trend strength",
    "atr_14": "Average True Range — volatility measure",
    "obv_slope": "On-Balance Volume slope — volume trend",
    "ret_10": "10-day return — recent price performance",
}


def _compute_factor_score(name: str, value: float) -> float:
    """Score a single factor 0-100 based on its typical range."""
    if name == "rsi_14":
        if 40 <= value <= 60:
            return 60
        elif 60 < value <= 70:
            return 75
        elif value > 70:
            return 50  # overbought
        elif 30 <= value < 40:
            return 55
        else:
            return 30  # oversold
    elif name == "macd":
        if value > 0.5:
            return 85
        elif value > 0:
            return 70
        elif value > -0.5:
            return 40
        else:
            return 20
    elif name == "sma_ratio":
        if value > 0.05:
            return 90
        elif value > 0.02:
            return 75
        elif value > 0:
            return 60
        elif value > -0.02:
            return 40
        else:
            return 20
    elif name == "bb_pos":
        if value > 2:
            return 40  # overbought
        elif value > 0:
            return 70
        elif value > -2:
            return 50
        else:
            return 30
    elif name == "cci":
        if value > 100:
            return 80
        elif value > 0:
            return 65
        elif value > -100:
            return 45
        else:
            return 25
    elif name == "williams_r":
        if value > -20:
            return 45  # overbought
        elif value > -50:
            return 70
        elif value > -80:
            return 55
        else:
            return 35  # oversold
    elif name == "roc_10":
        if value > 5:
            return 85
        elif value > 2:
            return 70
        elif value > 0:
            return 55
        elif value > -2:
            return 40
        else:
            return 20
    elif name == "atr_14":
        if value > 0.03:
            return 30  # high risk
        elif value > 0.02:
            return 50
        else:
            return 75  # low risk
    elif name == "obv_slope":
        if value > 100000:
            return 85
        elif value > 0:
            return 65
        elif value > -100000:
            return 40
        else:
            return 20
    elif name == "ret_10":
        if value > 0.05:
            return 85
        elif value > 0.02:
            return 70
        elif value > 0:
            return 55
        elif value > -0.02:
            return 40
        else:
            return 20
    return 50


def _compute_quant_score(features: dict, above_sma: bool) -> dict:
    """Compute Aarambh Quant Score (0-100) with component breakdown."""
    factor_scores = {}
    for group, feat_names in FACTOR_GROUPS.items():
        group_scores = []
        for fname in feat_names:
            val = features.get(fname, 0)
            score = _compute_factor_score(fname, val)
            factor_scores[fname] = {
                "value": round(val, 4),
                "score": round(score, 1),
                "description": FACTOR_DESCRIPTIONS.get(fname, ""),
                "group": group,
            }
            group_scores.append(score)

    # Group averages
    group_scores_map = {}
    for group, feat_names in FACTOR_GROUPS.items():
        scores = [factor_scores[f]["score"] for f in feat_names if f in factor_scores]
        group_scores_map[group] = round(sum(scores) / len(scores), 1) if scores else 50

    # Regime bonus
    regime_score = 75 if above_sma else 35
    group_scores_map["Regime"] = regime_score

    # Model agreement (proxy: if all features point same direction)
    trend_up = sum(1 for f in ["sma_ratio", "macd", "rsi_14"] if features.get(f, 0) > 0)
    agreement_score = 40 + trend_up * 15
    group_scores_map["Agreement"] = min(100, agreement_score)

    # Weighted average
    weights = {
        "Trend": 0.20,
        "Momentum": 0.20,
        "Volatility": 0.10,
        "Volume": 0.10,
        "Returns": 0.15,
        "Regime": 0.15,
        "Agreement": 0.10,
    }
    total = sum(group_scores_map.get(g, 50) * w for g, w in weights.items())
    total = max(0, min(100, round(total)))

    if total >= 70:
        label = "Strong"
        color = "#22c55e"
    elif total >= 55:
        label = "Healthy"
        color = "#84cc16"
    elif total >= 40:
        label = "Neutral"
        color = "#eab308"
    else:
        label = "Risk Elevated"
        color = "#ef4444"

    return {
        "score": total,
        "label": label,
        "color": color,
        "components": group_scores_map,
        "factors": factor_scores,
    }


def _compute_risk_metrics(features: dict, close: float) -> dict:
    """Compute risk metrics from features."""
    atr = features.get("atr_14", 0.02)
    rvol = abs(features.get("ret_10", 0))

    if atr > 0.03 or rvol > 0.05:
        risk_level = "High"
        risk_color = "#ef4444"
    elif atr > 0.02 or rvol > 0.03:
        risk_level = "Medium"
        risk_color = "#eab308"
    else:
        risk_level = "Low"
        risk_color = "#22c55e"

    # ATR-based stop loss estimate
    atr_pct = atr * 100
    stop_loss_pct = round(atr_pct * 2, 2)

    return {
        "risk_level": risk_level,
        "risk_color": risk_color,
        "atr_pct": round(atr_pct, 2),
        "volatility_regime": "High" if atr > 0.03 else ("Medium" if atr > 0.02 else "Low"),
        "stop_loss_estimate_pct": stop_loss_pct,
    }


class DetailedSignalRequest(BaseModel):
    ticker: str


@router.post("/signal/detailed")
def detailed_signal(req: DetailedSignalRequest):
    """Full signal analysis with quant score, factor breakdown, risk metrics."""
    from service.app import TICKERS, FEATURES, _THRESHOLD, ensemble_models, meta_model, scaler, fetch_cached_features

    ticker = req.ticker.upper()
    if ticker not in TICKERS:
        raise HTTPException(status_code=404, detail=f"Ticker not supported: {ticker}")

    try:
        cached = fetch_cached_features(ticker)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Market data failure: {e}")

    close = cached["close"]
    sma200 = cached["sma_200"]
    above_sma = cached["above_sma"]
    features = cached["features"]

    # Build feature row
    feature_row = np.array([[features[f] for f in FEATURES]], dtype=np.float32)
    if scaler is not None:
        feature_row = scaler.transform(feature_row)

    # Predict
    if ensemble_models is None or meta_model is None:
        raise HTTPException(status_code=503, detail="Ensemble models not loaded.")

    model_names = list(ensemble_models.keys())
    base_probas = {}
    for name, model in ensemble_models.items():
        try:
            if hasattr(model, "predict_proba"):
                p = model.predict_proba(feature_row)[0][1]
            else:
                p = model.predict(feature_row)[0]
            base_probas[name] = round(float(p), 4)
        except Exception as e:
            base_probas[name] = 0.5

    if len(model_names) > 1:
        stacked_input = np.array(list(base_probas.values())).reshape(1, -1)
        final_prob = meta_model.predict_proba(stacked_input)[0][1]
    else:
        final_prob = list(base_probas.values())[0]

    signal_value = "BUY" if (final_prob > _THRESHOLD and above_sma) else "HOLD"

    # Quant score
    quant = _compute_quant_score(features, above_sma)

    # Risk metrics
    risk = _compute_risk_metrics(features, close)

    # Factor analysis
    factor_analysis = {}
    for group, feat_names in FACTOR_GROUPS.items():
        group_data = []
        for fname in feat_names:
            if fname in quant["factors"]:
                group_data.append({
                    "name": fname,
                    "value": quant["factors"][fname]["value"],
                    "score": quant["factors"][fname]["score"],
                    "description": quant["factors"][fname]["description"],
                })
        factor_analysis[group] = group_data

    # Daily change estimate (from ret_10 proxy)
    ret_10 = features.get("ret_10", 0)
    daily_change_pct = round((ret_10 / 10) * 100, 2) if ret_10 else 0

    # Price vs SMA distances
    sma_distance_pct = round(((close - sma200) / sma200) * 100, 2) if sma200 else 0

    from datetime import datetime, timezone
    return {
        "ticker": ticker,
        "signal": signal_value,
        "confidence": round(float(final_prob), 4),
        "regime": "BULL" if above_sma else "BEAR",
        "price": round(close, 2),
        "sma_200": round(sma200, 2),
        "sma_distance_pct": sma_distance_pct,
        "daily_change_pct": daily_change_pct,
        "threshold": _THRESHOLD,
        "quant_score": quant,
        "risk": risk,
        "factor_analysis": factor_analysis,
        "model_predictions": base_probas,
        "model_count": len(model_names),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
