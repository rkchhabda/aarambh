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

ALL_FEATURES = [
    "ret_1", "ret_5", "ret_10", "log_vol_chg", "rsi_14", "macd",
    "bb_pos", "atr_14", "obv_slope", "sma_ratio", "rvol_5", "rvol_20",
    "stoch_k", "stoch_d", "cci", "williams_r", "roc_10",
    "adx", "aroon_up", "aroon_down", "sma_5_20_cross",
    "mfi", "volume_sma_ratio",
    "price_vs_high20", "price_vs_low20",
    "ret_20", "rvol_10",
]

def compute_features(df, index_returns=None):
    """Compute 27 features from single-ticker OHLCV."""
    c, h, l, v = df["Close"].values, df["High"].values, df["Low"].values, df["Volume"].values
    cs = pd.Series(c, index=df.index)
    hs = pd.Series(h, index=df.index)
    ls = pd.Series(l, index=df.index)
    vs = pd.Series(v, index=df.index)
    dates = df["date"].values

    feat = {}
    # Original 12
    feat["ret_1"] = cs.pct_change(1).values
    feat["ret_5"] = cs.pct_change(5).values
    feat["ret_10"] = cs.pct_change(10).values
    feat["log_vol_chg"] = np.log(vs + 1).diff().values
    feat["rsi_14"] = ta.momentum.RSIIndicator(cs, window=14).rsi().values
    macd_ind = ta.trend.MACD(cs)
    feat["macd"] = macd_ind.macd_diff().values
    bb = ta.volatility.BollingerBands(cs, window=20)
    feat["bb_pos"] = ((cs - bb.bollinger_mavg()) / (bb.bollinger_wband() + 1e-10)).values
    atr = ta.volatility.AverageTrueRange(hs, ls, cs, window=14)
    feat["atr_14"] = (atr.average_true_range() / cs).values
    obv = ta.volume.OnBalanceVolumeIndicator(cs, vs).on_balance_volume()
    feat["obv_slope"] = obv.diff(5).values
    sma_20 = ta.trend.SMAIndicator(cs, window=20).sma_indicator()
    feat["sma_ratio"] = (cs / sma_20 - 1).values
    feat["rvol_5"] = cs.pct_change().rolling(5).std().values
    feat["rvol_20"] = cs.pct_change().rolling(20).std().values

    # New momentum
    stoch = ta.momentum.StochasticOscillator(hs, ls, cs, window=14, smooth_window=3)
    feat["stoch_k"] = stoch.stoch().values
    feat["stoch_d"] = stoch.stoch_signal().values
    feat["cci"] = ta.trend.CCIIndicator(hs, ls, cs, window=20).cci().values
    feat["williams_r"] = ta.momentum.WilliamsRIndicator(hs, ls, cs, lbp=14).williams_r().values
    feat["roc_10"] = ta.momentum.ROCIndicator(cs, window=10).roc().values

    # New trend
    adx_ind = ta.trend.ADXIndicator(hs, ls, cs, window=14)
    feat["adx"] = adx_ind.adx().values
    aroon = ta.trend.AroonIndicator(hs, ls, window=25)
    feat["aroon_up"] = aroon.aroon_up().values
    feat["aroon_down"] = aroon.aroon_down().values
    sma_5 = cs.rolling(5).mean()
    feat["sma_5_20_cross"] = ((sma_5 - sma_20) / (sma_20 + 1e-10)).values

    # New volume
    feat["mfi"] = ta.volume.MFIIndicator(hs, ls, cs, vs, window=14).money_flow_index().values
    vol_sma_20 = vs.rolling(20).mean()
    feat["volume_sma_ratio"] = (vs / (vol_sma_20 + 1)).values

    # New regime
    high_20 = hs.rolling(20).max()
    low_20 = ls.rolling(20).min()
    feat["price_vs_high20"] = ((cs - high_20) / (high_20 + 1e-10)).values
    feat["price_vs_low20"] = ((cs - low_20) / (low_20 + 1e-10)).values

    # Multi-timeframe
    feat["ret_20"] = cs.pct_change(20).values
    feat["rvol_10"] = cs.pct_change().rolling(10).std().values

    # Sector-relative
    if index_returns is not None:
        ir = pd.Series(index_returns).reindex(pd.Series(dates)).values
        ret5 = feat["ret_5"]
        ret20 = feat["ret_20"]
        ir5 = pd.Series(ir).rolling(5).sum().values
        ir20 = pd.Series(ir).rolling(20).sum().values
        feat["relative_ret_5"] = ret5 - ir5
        feat["relative_ret_20"] = ret20 - ir20
    else:
        feat["relative_ret_5"] = np.zeros(len(df))
        feat["relative_ret_20"] = np.zeros(len(df))

    out = pd.DataFrame(feat, index=df.index)
    out["date"] = dates
    out["Close"] = c
    return out


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
