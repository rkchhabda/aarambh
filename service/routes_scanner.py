"""Market scanner route — filter and sort Nifty 100 tickers by signal/score/risk."""

import json
import os
from fastapi import APIRouter, Query

router = APIRouter(prefix="/scanner", tags=["scanner"])

_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "service", "models", "ticker_cache.json",
)

# Ticker name map (from the HTML portal's hardcoded list)
TICKER_NAMES = {
    "ADANIENT.NS": "Adani Enterprises", "ADANIPORTS.NS": "Adani Ports", "APOLLOHOSP.NS": "Apollo Hospitals",
    "ASIANPAINT.NS": "Asian Paints", "AXISBANK.NS": "Axis Bank", "BAJAJ-AUTO.NS": "Bajaj Auto",
    "BAJFINANCE.NS": "Bajaj Finance", "BAJAJFINSV.NS": "Bajaj Finserv", "BPCL.NS": "BPCL",
    "BHARTIARTL.NS": "Bharti Airtel", "BRITANNIA.NS": "Britannia", "CIPLA.NS": "Cipla",
    "COALINDIA.NS": "Coal India", "DIVISLAB.NS": "Divi's Labs", "DRREDDY.NS": "Dr. Reddy's",
    "EICHERMOT.NS": "Eicher Motors", "GRASIM.NS": "Grasim", "HCLTECH.NS": "HCL Tech",
    "HDFCBANK.NS": "HDFC Bank", "HDFCLIFE.NS": "HDFC Life", "HEROMOTOCO.NS": "Hero Moto",
    "HINDALCO.NS": "Hindalco", "HINDUNILVR.NS": "HUL", "ICICIBANK.NS": "ICICI Bank",
    "ITC.NS": "ITC", "INDUSINDBK.NS": "IndusInd Bank", "INFY.NS": "Infosys",
    "JSWSTEEL.NS": "JSW Steel", "KOTAKBANK.NS": "Kotak Bank", "LT.NS": "L&T",
    "M&M.NS": "M&M", "MARUTI.NS": "Maruti", "NESTLEIND.NS": "Nestle", "NTPC.NS": "NTPC",
    "ONGC.NS": "ONGC", "POWERGRID.NS": "Power Grid", "RELIANCE.NS": "Reliance",
    "SBILIFE.NS": "SBI Life", "SBIN.NS": "SBI", "SUNPHARMA.NS": "Sun Pharma",
    "TCS.NS": "TCS", "TATACONSUM.NS": "Tata Consumer", "TATASTEEL.NS": "Tata Steel",
    "TECHM.NS": "Tech Mahindra", "TITAN.NS": "Titan", "ULTRACEMCO.NS": "UltraTech",
    "UPL.NS": "UPL", "WIPRO.NS": "Wipro", "ADANIGREEN.NS": "Adani Green",
    "AMBUJACEM.NS": "Ambuja Cement", "APOLLOTYRE.NS": "Apollo Tyres", "ASHOKLEY.NS": "Ashok Leyland",
    "ASTRAL.NS": "Astral", "AUROPHARMA.NS": "Aurobindo Pharma", "BALKRISIND.NS": "Balkrishna Ind",
    "BANDHANBNK.NS": "Bandhan Bank", "BANKBARODA.NS": "Bank of Baroda", "BEL.NS": "BEL",
    "BHEL.NS": "BHEL", "BIOCON.NS": "Biocon", "BOSCHLTD.NS": "Bosch", "CANBK.NS": "Canara Bank",
    "CHOLAFIN.NS": "Chola Finance", "COLPAL.NS": "Colgate", "CONCOR.NS": "Concor",
    "CROMPTON.NS": "Crompton", "CUMMINSIND.NS": "Cummins", "DABUR.NS": "Dabur",
    "DALBHARAT.NS": "Dalmia Bharat", "DEEPAKNTR.NS": "Deepak Nitrite", "DLF.NS": "DLF",
    "EDELWEISS.NS": "Edelweiss", "EMAMILTD.NS": "Emami", "ENDURANCE.NS": "Endurance",
    "ESCORTS.NS": "Escorts", "EXIDEIND.NS": "Exide", "FEDERALBNK.NS": "Federal Bank",
    "GAIL.NS": "GAIL", "GLENMARK.NS": "Glenmark", "GODREJCP.NS": "Godrej Consumer",
    "GODREJPROP.NS": "Godrej Properties", "GRANULES.NS": "Granules", "HAVELLS.NS": "Havells",
    "HINDPETRO.NS": "Hind Petro", "ICICIGI.NS": "ICICI GI", "ICICIPRULI.NS": "ICICI Pru",
    "IDEA.NS": "Vodafone Idea", "IDFCFIRSTB.NS": "IDFC First Bank", "IGL.NS": "IGL",
    "INDIGO.NS": "IndiGo", "INDUSTOWER.NS": "Indus Towers", "JINDALSTEL.NS": "Jindal Steel",
    "JUBLFOOD.NS": "Jubilant Food", "LICHSGFIN.NS": "LIC HFL", "LUPIN.NS": "Lupin",
    "MARICO.NS": "Marico", "MAXHEALTH.NS": "Max Healthcare", "MFSL.NS": "Max Financial",
    "MOTHERSON.NS": "Motherson", "MPHASIS.NS": "Mphasis", "MRF.NS": "MRF",
    "MUTHOOTFIN.NS": "Muthoot Finance", "NAUKRI.NS": "Info Edge", "NAVINFLUOR.NS": "Navin Fluorine",
    "NBCC.NS": "NBCC", "NMDC.NS": "NMDC", "OBEROIRLTY.NS": "Oberoi Realty",
    "PAGEIND.NS": "Page Industries", "PERSISTENT.NS": "Persistent", "PETRONET.NS": "Petronet LNG",
    "PFC.NS": "PFC", "PIDILITIND.NS": "Pidilite", "PIIND.NS": "PI Industries",
    "PNB.NS": "PNB", "POLYCAB.NS": "Polycab", "PVRINOX.NS": "PVR Inox",
    "RAMCOCEM.NS": "Ramco Cement", "RBLBANK.NS": "RBL Bank", "RECLTD.NS": "RECL",
    "SAIL.NS": "SAIL", "SHREECEM.NS": "Shree Cement", "SIEMENS.NS": "Siemens",
    "SRF.NS": "SRF", "SYNGENE.NS": "Syngene", "TATACHEM.NS": "Tata Chemicals",
    "TATACOMM.NS": "Tata Comm", "TATAPOWER.NS": "Tata Power", "TORNTPHARM.NS": "Torrent Pharma",
    "TORNTPOWER.NS": "Torrent Power", "TRENT.NS": "Trent", "TVSMOTOR.NS": "TVS Motor",
    "UBL.NS": "UBL", "UNIONBANK.NS": "Union Bank", "VBL.NS": "Varun Beverages",
    "VEDL.NS": "Vedanta", "VOLTAS.NS": "Voltas", "WHIRLPOOL.NS": "Whirlpool",
    "ZYDUSLIFE.NS": "Zydus Lifesciences",
}


def _load_cache():
    if not os.path.exists(_CACHE_PATH):
        return {}
    with open(_CACHE_PATH) as f:
        return json.load(f)


def _compute_score(features: dict, above_sma: bool) -> int:
    """Quick quant score from cached features."""
    score = 50
    if above_sma:
        score += 15
    rsi = features.get("rsi_14", 50)
    if 40 <= rsi <= 60:
        score += 5
    elif rsi > 60:
        score += 10
    elif rsi < 30:
        score -= 5
    macd = features.get("macd", 0)
    if macd > 0:
        score += 10
    else:
        score -= 5
    ret10 = features.get("ret_10", 0)
    if ret10 > 0.03:
        score += 10
    elif ret10 > 0:
        score += 5
    elif ret10 < -0.03:
        score -= 10
    elif ret10 < 0:
        score -= 5
    return max(0, min(100, score))


def _risk_label(features: dict) -> str:
    atr = features.get("atr_14", 0.02)
    rvol = abs(features.get("ret_10", 0))
    if atr > 0.03 or rvol > 0.05:
        return "High"
    elif atr > 0.02 or rvol > 0.03:
        return "Medium"
    return "Low"


def _momentum_label(features: dict) -> str:
    ret10 = features.get("ret_10", 0)
    roc = features.get("roc_10", 0)
    combined = (ret10 * 0.5 + roc / 100 * 0.5)
    if combined > 0.03:
        return "Strong Positive"
    elif combined > 0:
        return "Positive"
    elif combined > -0.03:
        return "Neutral"
    elif combined > -0.05:
        return "Negative"
    return "Strong Negative"


@router.get("")
def scan_tickers(
    signal: str | None = Query(None, description="BUY|HOLD"),
    min_score: int | None = Query(None, ge=0, le=100),
    risk: str | None = Query(None, description="Low|Medium|High"),
    momentum: str | None = Query(None),
    above_sma: bool | None = Query(None),
    sort_by: str = Query("score", description="score|confidence|ticker"),
    order: str = Query("desc", description="asc|desc"),
):
    cache = _load_cache()
    results = []

    for ticker, data in cache.items():
        features = data.get("features", {})
        above = data.get("above_sma", False)
        close = data.get("close", 0)
        sma200 = data.get("sma_200", 0)
        score = _compute_score(features, above)
        risk_label = _risk_label(features)
        mom_label = _momentum_label(features)

        # Ensemble probability proxy (from features)
        prob = 0.5
        if above:
            prob += 0.1
        if features.get("macd", 0) > 0:
            prob += 0.1
        if features.get("rsi_14", 50) > 55:
            prob += 0.05
        prob = min(0.95, max(0.05, prob))
        sig = "BUY" if (prob > 0.65 and above) else "HOLD"

        entry = {
            "ticker": ticker,
            "name": TICKER_NAMES.get(ticker, ticker.replace(".NS", "")),
            "signal": sig,
            "confidence": round(prob, 4),
            "price": round(close, 2),
            "sma_200": round(sma200, 2),
            "regime": "BULL" if above else "BEAR",
            "score": score,
            "risk": risk_label,
            "momentum": mom_label,
        }

        # Apply filters
        if signal and entry["signal"] != signal.upper():
            continue
        if min_score is not None and score < min_score:
            continue
        if risk and entry["risk"] != risk:
            continue
        if momentum and entry["momentum"] != momentum:
            continue
        if above_sma is not None and above != above_sma:
            continue

        results.append(entry)

    # Sort
    reverse = order == "desc"
    if sort_by == "score":
        results.sort(key=lambda x: x["score"], reverse=reverse)
    elif sort_by == "confidence":
        results.sort(key=lambda x: x["confidence"], reverse=reverse)
    elif sort_by == "ticker":
        results.sort(key=lambda x: x["ticker"], reverse=reverse)

    # Summary stats
    buy_count = sum(1 for r in results if r["signal"] == "BUY")
    hold_count = sum(1 for r in results if r["signal"] == "HOLD")
    bull_count = sum(1 for r in results if r["regime"] == "BULL")
    bear_count = sum(1 for r in results if r["regime"] == "BEAR")

    return {
        "total": len(results),
        "buy_count": buy_count,
        "hold_count": hold_count,
        "bull_count": bull_count,
        "bear_count": bear_count,
        "advance_decline": round(bull_count / max(bear_count, 1), 2),
        "tickers": results,
    }
