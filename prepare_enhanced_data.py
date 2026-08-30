"""
Enhanced Multi-Ticker Data v2 - Batch Download
Uses yfinance batch download for speed.
"""
import os, warnings, json, time
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, ta, yfinance as yf

BASE = os.path.dirname(os.path.abspath(__file__))
MULTI_DIR = os.path.join(BASE, "data", "multi")
os.makedirs(MULTI_DIR, exist_ok=True)

# Single source of truth for features (must match the live service).
from features.indicators import compute_features, ALL_FEATURES

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

def main():
    t0 = time.time()
    print("=" * 60)
    print("ENHANCED DATA v2 - BATCH DOWNLOAD")
    print(f"Tickers: {len(TICKERS)} | Features: {len(ALL_FEATURES)}")
    print("=" * 60)

    # Batch download tickers
    print("Batch downloading tickers...")
    data = yf.download(TICKERS, period="5y", interval="1d", group_by="ticker",
                       progress=True, threads=True)

    # Also download Nifty 50 for sector-relative
    print("Downloading Nifty 50 index...")
    nifty = yf.download("^NSEI", period="5y", interval="1d", progress=False, auto_adjust=True)
    if isinstance(nifty.columns, pd.MultiIndex):
        nifty.columns = nifty.columns.get_level_values(0)
    nifty = nifty.reset_index()
    nifty.columns = [c.capitalize() for c in nifty.columns]
    if "Date" in nifty.columns:
        nifty.rename(columns={"Date": "date"}, inplace=True)
    idx_ret = nifty.set_index("date")["Close"].pct_change()

    # Process each ticker
    all_frames = []
    ok, fail = 0, 0

    for ticker in TICKERS:
        try:
            df = data[ticker].dropna()
            if len(df) < 250:
                fail += 1
                continue

            df2 = df.reset_index()
            if isinstance(df2.columns, pd.MultiIndex):
                df2.columns = df2.columns.get_level_values(0)
            df2.columns = [c.capitalize() for c in df2.columns]
            if "Date" in df2.columns:
                df2.rename(columns={"Date": "date"}, inplace=True)

            feat = compute_features(df2, idx_ret)
            feat["ticker"] = ticker

            # Drop rows with NaN in features
            feat_valid = feat[ALL_FEATURES].notna().all(axis=1)
            feat = feat[feat_valid].copy()

            if len(feat) < 100:
                fail += 1
                continue

            all_frames.append(feat)
            ok += 1
        except Exception as e:
            print(f"  FAIL {ticker}: {e}")
            fail += 1

    print(f"\nFetched: {ok} ok, {fail} failed ({time.time()-t0:.0f}s)")

    big = pd.concat(all_frames, ignore_index=True).sort_values("date").reset_index(drop=True)
    print(f"Total rows: {len(big)}")

    # Targets at different horizons
    for horizon, days in {"1d": 1, "3d": 3, "5d": 5}.items():
        big[f"target_{horizon}"] = (big["Close"].shift(-days) > big["Close"]).astype(int)

    # Drop last N rows (where targets are NaN)
    big = big.dropna(subset=["target_1d", "target_3d", "target_5d"]).reset_index(drop=True)
    print(f"After target cleanup: {len(big)} rows")

    # Time split: 70/15/15
    n = len(big)
    tr_end = int(n * 0.70)
    va_end = int(n * 0.85)
    train = big.iloc[:tr_end].copy()
    val = big.iloc[tr_end:va_end].copy()
    test = big.iloc[va_end:].copy()

    print(f"Train: {len(train)} | Val: {len(val)} | Test: {len(test)}")
    for name, split in [("Train", train), ("Val", val), ("Test", test)]:
        d1 = split["target_1d"].value_counts(normalize=True)
        print(f"  {name} 1d: UP={d1.get(1,0):.3f} DOWN={d1.get(0,0):.3f}")

    # Save per-horizon
    for horizon in ["1d", "3d", "5d"]:
        tc = f"target_{horizon}"
        save_cols = ["date", "ticker", "Close"] + ALL_FEATURES + [tc]
        for name, split in [("train", train), ("val", val), ("test", test)]:
            out = os.path.join(MULTI_DIR, f"{name}_multi_v2_{horizon}.csv")
            split[save_cols].rename(columns={tc: "target"}).to_csv(out, index=False)
        print(f"Saved {horizon} datasets")

    # Feature importance
    print("\n--- Feature Importance (1d target) ---")
    from xgboost import XGBClassifier
    X_tr = train[ALL_FEATURES].fillna(0).values
    y_tr = train["target_1d"].values
    xgb = XGBClassifier(n_estimators=100, max_depth=5, random_state=42,
                        eval_metric="logloss", verbosity=0, n_jobs=-1)
    xgb.fit(X_tr, y_tr)
    imp = pd.Series(xgb.feature_importances_, index=ALL_FEATURES).sort_values(ascending=False)
    for feat, score in imp.items():
        print(f"  {feat:25s} {score:.4f}")

    print(f"\nTotal time: {time.time()-t0:.0f}s")
    print("DONE")


if __name__ == "__main__":
    main()
