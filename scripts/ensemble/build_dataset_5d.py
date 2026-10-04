"""Build unified feature dataset with 5-day-ahead directional labels.

This creates features_5d.csv alongside the existing features.csv.
The 5-day target matches the production horizon (service/models uses 5-day).
"""

import os

import numpy as np
import pandas as pd
import ta

RAW_PATH = os.path.join("data", "raw", "market_data.csv")
OUT_DIR = os.path.join("ensemble", "artifacts")


def build_features_5d(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Avoid pd.to_datetime hang (known issue on this system)
    df = df.sort_values("timestamps").reset_index(drop=True)

    # Returns and log volume change
    df["ret_1"] = df["close"].pct_change()
    df["ret_5"] = df["close"].pct_change(5)
    df["ret_10"] = df["close"].pct_change(10)
    df["log_vol_chg"] = np.log(df["volume"] + 1).diff()

    # Technical indicators (ta library)
    df["rsi_14"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    macd = ta.trend.MACD(df["close"])
    df["macd"] = macd.macd_diff()
    bb = ta.volatility.BollingerBands(df["close"], window=20)
    df["bb_pos"] = (df["close"] - bb.bollinger_mavg()) / bb.bollinger_wband()
    df["atr_14"] = ta.volatility.AverageTrueRange(
        df["high"], df["low"], df["close"], window=14).average_true_range() / df["close"]
    df["obv_slope"] = ta.volume.OnBalanceVolumeIndicator(
        df["close"], df["volume"]).on_balance_volume().diff(5)
    df["sma_ratio"] = df["close"] / ta.trend.SMAIndicator(df["close"], window=20).sma_indicator() - 1

    # Realized volatility
    df["rvol_5"] = df["ret_1"].rolling(5).std()
    df["rvol_20"] = df["ret_1"].rolling(20).std()

    feature_cols = ["ret_1", "ret_5", "ret_10", "log_vol_chg", "rsi_14", "macd",
                    "bb_pos", "atr_14", "obv_slope", "sma_ratio", "rvol_5", "rvol_20"]

    # Label: 5-day-ahead direction (matches production horizon)
    df["target_up"] = (df["close"].shift(-5) > df["close"]).astype(int)
    df["next_ret"] = df["close"].shift(-5) / df["close"] - 1

    # Also keep 1-day label for reference
    df["target_up_1d"] = (df["close"].shift(-1) > df["close"]).astype(int)

    df = df.dropna().reset_index(drop=True)
    return df, feature_cols


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.read_csv(RAW_PATH)
    df, feature_cols = build_features_5d(df)

    n = len(df)
    train_end = int(n * 0.70)
    val_end = int(n * (0.70 + 0.15))
    df["split"] = "train"
    df.loc[train_end:val_end - 1, "split"] = "val"
    df.loc[val_end:, "split"] = "test"

    out_path = os.path.join(OUT_DIR, "features_5d.csv")
    df.to_csv(out_path, index=False)

    print(f"Feature dataset (5-day target): {n} rows, {len(feature_cols)} features")
    print(f"Features: {feature_cols}")
    for split in ["train", "val", "test"]:
        sub = df[df["split"] == split]
        ts = sub["timestamps"]
        print(f"{split:>5}: {len(sub):>4} rows | "
              f"{str(ts.iloc[0])[:10]} -> {str(ts.iloc[-1])[:10]} | "
              f"P(up_5d) base rate: {sub['target_up'].mean():.3f} | "
              f"P(up_1d) base rate: {sub['target_up_1d'].mean():.3f}")
    print(f"Saved -> {out_path}")


if __name__ == "__main__":
    main()
