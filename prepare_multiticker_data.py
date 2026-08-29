"""
TASK 1: Prepare Multi-Ticker Data for Optuna Hyperparameter Tuning

Fetches 5 years of daily data for all Nifty 100 tickers via yfinance,
generates the standard 12 features, stacks everything into one DataFrame,
and splits into train (70%) / val (15%) / test (15%) by time.
"""
import os
import sys
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import ta
import yfinance as yf

# ============================================================
# CONFIG
# ============================================================
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MULTI_DIR = os.path.join(DATA_DIR, "multi")
os.makedirs(MULTI_DIR, exist_ok=True)

YEARS_BACK = 5

NIFTY_100 = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "KOTAKBANK.NS",
    "LT.NS", "WIPRO.NS", "HCLTECH.NS", "ASIANPAINT.NS", "MARUTI.NS",
    "TITAN.NS", "BAJFINANCE.NS", "NTPC.NS", "ONGC.NS", "POWERGRID.NS",
    "ULTRACEMCO.NS", "AXISBANK.NS", "ADANIPORTS.NS", "JSWSTEEL.NS",
    "TATASTEEL.NS", "TECHM.NS", "INDUSINDBK.NS", "HDFCLIFE.NS", "SBIN.NS",
    "BAJAJFINSV.NS", "HDFC.NS", "M&M.NS", "ADANIENT.NS", "COALINDIA.NS",
    "SUNPHARMA.NS", "TATAMOTORS.NS", "TATASTL.NS", "VEDL.NS", "HERO.NS",
    "BRITANNIA.NS", "GRASIM.NS", "APOLLOHOSP.NS", "CIPLA.NS", "DIVISLAB.NS",
    "DRREDDY.NS", "EICHERMOT.NS", "HINDALCO.NS", "INDIGO.NS", "PIDILITIND.NS",
    "SBILIFE.NS", "SHREECEM.NS", "SIEMENS.NS", "TATACONSUM.NS", "TATAPOWER.NS",
    "UPL.NS", "BAJAJ-AUTO.NS", "BHARATFORG.NS", "BOSCHLTD.NS", "COFORGE.NS",
    "DABUR.NS", "GODREJCP.NS", "HAVELS.NS", "IGL.NS", "JUBLFOOD.NS",
    "MARICO.NS", "MOTHERSUMI.NS", "PEL.NS", "PIIND.NS", "SRTRANSFIN.NS",
    "TORNTPHARM.NS", "VOLTAS.NS", "WHIRLPOOL.NS", "YESBANK.NS", "ZEEL.NS",
    "NHPC.NS", "PFC.NS", "RECLTD.NS", "SAIL.NS", "IDEA.NS",
    "BANKBARODA.NS", "CANBK.NS", "PNB.NS", "UNIONBANK.NS", "FEDERALBNK.NS",
    "IDFCFIRSTB.NS", "RBLBANK.NS", "MUTHOOTFIN.NS", "LUPIN.NS", "MANAPPURAM.NS",
    "PAGEIND.NS", "BANDHANBNK.NS", "GODREJPROP.NS", "DLF.NS", "PHOENIXLTD.NS",
    "PRESTIGE.NS", "SOBHA.NS", "OBEROIRLTY.NS", "SUNTV.NS", "TVSMOTOR.NS",
    "ASHOKLEY.NS", "ESCORTS.NS", "AMBUJACEM.NS", "ACC.NS", "RAMCOCEM.NS",
]
# Deduplicate while preserving order
NIFTY_100 = list(dict.fromkeys(NIFTY_100))

# ============================================================
# FEATURE ENGINEERING (same 12 features as inference)
# ============================================================
def add_features(df):
    """Add technical indicators to OHLCV data. Returns df with features + target."""
    df = df.copy()
    df = df.sort_values("date").reset_index(drop=True)

    c = df["Close"]
    h = df["High"]
    l = df["Low"]
    v = df["Volume"]

    # Returns
    df["ret_1"] = c.pct_change(1)
    df["ret_5"] = c.pct_change(5)
    df["ret_10"] = c.pct_change(10)

    # Volume change
    df["log_vol_chg"] = np.log(v + 1).diff()

    # RSI
    df["rsi_14"] = ta.momentum.RSIIndicator(c, window=14).rsi()

    # MACD (diff = macd line - signal line)
    macd = ta.trend.MACD(c)
    df["macd"] = macd.macd_diff()

    # Bollinger Bands position
    bb = ta.volatility.BollingerBands(c, window=20)
    df["bb_pos"] = (c - bb.bollinger_mavg()) / (bb.bollinger_wband() + 1e-10)

    # ATR (normalized by close)
    atr = ta.volatility.AverageTrueRange(h, l, c, window=14)
    df["atr_14"] = atr.average_true_range() / c

    # OBV slope
    obv = ta.volume.OnBalanceVolumeIndicator(c, v).on_balance_volume()
    df["obv_slope"] = obv.diff(5)

    # SMA ratio (close / SMA20 - 1)
    sma_20 = ta.trend.SMAIndicator(c, window=20).sma_indicator()
    df["sma_ratio"] = c / sma_20 - 1

    # Rolling volatility
    df["rvol_5"] = df["ret_1"].rolling(5).std()
    df["rvol_20"] = df["ret_1"].rolling(20).std()

    # Target: next-day direction (1 = up, 0 = down/flat)
    df["target"] = (c.shift(-1) > c).astype(int)

    return df


# ============================================================
# FETCH & BUILD
# ============================================================
def fetch_ticker(ticker, period=f"{YEARS_BACK}y"):
    """Download OHLCV from Yahoo Finance."""
    try:
        df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
        if df is None or len(df) < 100:
            print(f"  SKIP {ticker}: insufficient data ({len(df) if df is not None else 0} rows)")
            return None
        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.reset_index()
        # Standardize column names
        df.columns = [c.capitalize() if c != "Adj Close" else "Close" for c in df.columns]
        if "Date" in df.columns:
            df.rename(columns={"Date": "date"}, inplace=True)
        return df
    except Exception as e:
        print(f"  FAIL {ticker}: {e}")
        return None


def main():
    print("=" * 60)
    print("TASK 1: Prepare Multi-Ticker Data")
    print(f"Tickers: {len(NIFTY_100)} | Lookback: {YEARS_BACK} years")
    print("=" * 60)

    all_frames = []
    success = 0
    failed = []

    for i, ticker in enumerate(NIFTY_100):
        print(f"[{i+1}/{len(NIFTY_100)}] {ticker} ...", end=" ")
        raw = fetch_ticker(ticker)
        if raw is None:
            failed.append(ticker)
            continue

        feat = add_features(raw)
        feat["ticker"] = ticker

        # Keep only rows where all features are valid (drop first 30 rows warmup + last row target)
        feat_cols = ["ret_1", "ret_5", "ret_10", "log_vol_chg", "rsi_14", "macd",
                     "bb_pos", "atr_14", "obv_slope", "sma_ratio", "rvol_5", "rvol_20"]
        valid_mask = feat[feat_cols + ["target"]].notna().all(axis=1)
        feat = feat[valid_mask].copy()

        if len(feat) < 50:
            print(f"SKIP (only {len(feat)} valid rows)")
            failed.append(ticker)
            continue

        all_frames.append(feat)
        print(f"OK ({len(feat)} rows)")
        success += 1

    if not all_frames:
        print("\nERROR: No data fetched. Check network / yfinance.")
        sys.exit(1)

    # Stack all tickers
    big_df = pd.concat(all_frames, ignore_index=True)
    big_df = big_df.sort_values("date").reset_index(drop=True)

    print(f"\n{'='*60}")
    print(f"Total tickers fetched: {success}/{len(NIFTY_100)}")
    if failed:
        print(f"Failed: {failed}")
    print(f"Total rows: {len(big_df)}")
    print(f"Date range: {big_df['date'].min()} to {big_df['date'].max()}")
    print(f"Target distribution: {big_df['target'].value_counts().to_dict()}")

    # ============================================================
    # TIME-BASED SPLIT (no shuffling, no leakage)
    # ============================================================
    # Global time split: first 70% = train, next 15% = val, last 15% = test
    n = len(big_df)
    train_end = int(n * 0.70)
    val_end = int(n * 0.85)

    train_df = big_df.iloc[:train_end].copy()
    val_df = big_df.iloc[train_end:val_end].copy()
    test_df = big_df.iloc[val_end:].copy()

    print(f"\nSplit sizes:")
    print(f"  Train: {len(train_df)} rows ({train_df['date'].min()} to {train_df['date'].max()})")
    print(f"  Val:   {len(val_df)} rows ({val_df['date'].min()} to {val_df['date'].max()})")
    print(f"  Test:  {len(test_df)} rows ({test_df['date'].min()} to {test_df['date'].max()})")

    # Target distribution per split
    for name, split_df in [("Train", train_df), ("Val", val_df), ("Test", test_df)]:
        dist = split_df["target"].value_counts(normalize=True)
        print(f"  {name} target dist: UP={dist.get(1,0):.3f} DOWN={dist.get(0,0):.3f}")

    # ============================================================
    # SAVE
    # ============================================================
    feat_cols = ["ret_1", "ret_5", "ret_10", "log_vol_chg", "rsi_14", "macd",
                 "bb_pos", "atr_14", "obv_slope", "sma_ratio", "rvol_5", "rvol_20"]
    save_cols = ["date", "ticker", "Close"] + feat_cols + ["target"]

    for name, split_df in [("train", train_df), ("val", val_df), ("test", test_df)]:
        out_path = os.path.join(MULTI_DIR, f"{name}_multi.csv")
        split_df[save_cols].to_csv(out_path, index=False)
        print(f"Saved {out_path}")

    # Also save the full dataset for reference
    big_df[save_cols].to_csv(os.path.join(MULTI_DIR, "all_multi.csv"), index=False)

    print(f"\n{'='*60}")
    print("DONE. Files saved to data/multi/")
    print("=" * 60)


if __name__ == "__main__":
    main()
