"""Rebuild ticker_cache.json with enhanced v2 features for all Nifty 100 tickers."""
import os, json, warnings
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, yfinance as yf, ta
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE, "service", "models")
CACHE_PATH = os.path.join(MODELS_DIR, "ticker_cache.json")

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

def compute_v2_features(df):
    """Compute v2 features needed for inference."""
    c = df["Close"]
    h = df["High"]
    l = df["Low"]
    v = df["Volume"]

    features = {}
    # bb_pos
    bb = ta.volatility.BollingerBands(c, window=20)
    bb_high = bb.bollinger_hband().iloc[-1]
    bb_low = bb.bollinger_lband().iloc[-1]
    bb_mid = bb.bollinger_mavg().iloc[-1]
    bb_w = bb.bollinger_wband().iloc[-1]
    features["bb_pos"] = ((c.iloc[-1] - bb_mid) / (bb_w + 1e-10))

    # macd
    macd_ind = ta.trend.MACD(c)
    features["macd"] = macd_ind.macd_diff().iloc[-1]

    # obv_slope
    obv = ta.volume.OnBalanceVolumeIndicator(c, v).on_balance_volume()
    if len(obv) >= 10:
        x = np.arange(10)
        y = obv.iloc[-10:].values
        features["obv_slope"] = np.polyfit(x, y, 1)[0]
    else:
        features["obv_slope"] = 0

    # sma_ratio
    sma_20 = ta.trend.SMAIndicator(c, window=20).sma_indicator()
    features["sma_ratio"] = (c.iloc[-1] / sma_20.iloc[-1] - 1) if sma_20.iloc[-1] > 0 else 0

    # cci
    features["cci"] = ta.trend.CCIIndicator(h, l, c, window=20).cci().iloc[-1]

    # ret_10
    features["ret_10"] = c.pct_change(10).iloc[-1]

    # williams_r
    features["williams_r"] = ta.momentum.WilliamsRIndicator(h, l, c, lbp=14).williams_r().iloc[-1]

    # rsi_14
    features["rsi_14"] = ta.momentum.RSIIndicator(c, window=14).rsi().iloc[-1]

    # atr_14
    atr = ta.volatility.AverageTrueRange(h, l, c, window=14).average_true_range()
    features["atr_14"] = (atr.iloc[-1] / c.iloc[-1]) if c.iloc[-1] > 0 else 0

    # roc_10
    features["roc_10"] = ta.momentum.ROCIndicator(c, window=10).roc().iloc[-1]

    # SMA 200 for regime filter
    sma_200 = c.rolling(200).mean().iloc[-1]

    return features, float(c.iloc[-1]), float(sma_200)

print(f"Rebuilding cache with v2 features for {len(TICKERS)} tickers...")
data = yf.download(TICKERS, period="5y", group_by="ticker", progress=True, threads=True)

cache = {}
ok = 0
for ticker in TICKERS:
    try:
        df = data[ticker].dropna()
        if len(df) < 210:
            continue
        features, close, sma200 = compute_v2_features(df)
        cache[ticker] = {
            "features": features,
            "close": close,
            "sma_200": sma200,
            "above_sma": bool(close > sma200)
        }
        ok += 1
    except Exception as e:
        print(f"  FAIL {ticker}: {e}")

print(f"Done: {ok}/{len(TICKERS)}")
with open(CACHE_PATH, "w") as f:
    json.dump(cache, f, indent=2)
print(f"Saved to {CACHE_PATH}")
