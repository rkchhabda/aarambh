"""Rebuild ticker_cache.json with fresh data for all Nifty 100 tickers."""
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

FEATURES = ["ret_1", "ret_5", "ret_10", "log_vol_chg", "rsi_14", "macd",
            "bb_pos", "atr_14", "obv_slope", "sma_ratio", "rvol_5", "rvol_20"]

def compute_features(df):
    """Compute feature vector from OHLCV data."""
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    vol = df["Volume"]

    features = {}
    features["ret_1"] = close.pct_change(1).iloc[-1]
    features["ret_5"] = close.pct_change(5).iloc[-1]
    features["ret_10"] = close.pct_change(10).iloc[-1]
    features["log_vol_chg"] = np.log(vol.iloc[-1] / vol.iloc[-6:].mean()) if vol.iloc[-6:].mean() > 0 else 0

    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
    features["rsi_14"] = rsi.iloc[-1]

    macd_ind = ta.trend.MACD(close)
    features["macd"] = macd_ind.macd_diff().iloc[-1]

    bb = ta.volatility.BollingerBands(close, window=20)
    bb_high = bb.bollinger_hband().iloc[-1]
    bb_low = bb.bollinger_lband().iloc[-1]
    features["bb_pos"] = ((close.iloc[-1] - bb_low) / (bb_high - bb_low) * 100) if (bb_high - bb_low) > 0 else 50

    atr = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()
    features["atr_14"] = (atr.iloc[-1] / close.iloc[-1]) if close.iloc[-1] > 0 else 0

    obv = ta.volume.OnBalanceVolumeIndicator(close, vol).on_balance_volume()
    if len(obv) >= 10:
        x = np.arange(10)
        y = obv.iloc[-10:].values
        slope = np.polyfit(x, y, 1)[0]
        features["obv_slope"] = slope
    else:
        features["obv_slope"] = 0

    sma50 = close.rolling(50).mean().iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1]
    features["sma_ratio"] = (sma50 / sma200 - 1) if sma200 > 0 else 0

    rv = vol.pct_change().rolling(5).std().iloc[-1]
    features["rvol_5"] = rv if not np.isnan(rv) else 0
    rv20 = vol.pct_change().rolling(20).std().iloc[-1]
    features["rvol_20"] = rv20 if not np.isnan(rv20) else 0

    return features, float(close.iloc[-1]), float(sma200)

print(f"Fetching data for {len(TICKERS)} tickers...")
end = datetime.now()
start = end - timedelta(days=400)

# Batch download
data = yf.download(TICKERS, start=start, end=end, group_by="ticker", progress=True, threads=True)

cache = {}
ok = 0
fail = 0

for ticker in TICKERS:
    try:
        if len(TICKERS) == 1:
            df = data
        else:
            df = data[ticker].dropna()
        
        if len(df) < 210:
            print(f"  SKIP {ticker}: only {len(df)} rows")
            fail += 1
            continue
        
        features, close, sma200 = compute_features(df)
        above_sma = close > sma200
        
        cache[ticker] = {
            "features": features,
            "close": close,
            "sma_200": sma200,
            "above_sma": bool(above_sma)
        }
        ok += 1
        if ok % 20 == 0:
            print(f"  {ok}/{len(TICKERS)} done...")
    except Exception as e:
        print(f"  FAIL {ticker}: {e}")
        fail += 1

print(f"\nDone: {ok} ok, {fail} failed")
with open(CACHE_PATH, "w") as f:
    json.dump(cache, f, indent=2)
print(f"Saved to {CACHE_PATH}")
