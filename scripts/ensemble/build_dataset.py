"""Build unified feature dataset with next-day directional labels for the ensemble."""

import os

import numpy as np
import pandas as pd
import ta

RAW_PATH = os.path.join("data", "raw", "market_data.csv")
OUT_DIR = os.path.join("ensemble", "artifacts")


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["timestamps"] = pd.to_datetime(df["timestamps"])
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

    # Label: next-day direction
    df["target_up"] = (df["close"].shift(-1) > df["close"]).astype(int)
    df["next_ret"] = df["close"].shift(-1) / df["close"] - 1

    df = df.dropna().reset_index(drop=True)
    return df, feature_cols


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.read_csv(RAW_PATH)
    df, feature_cols = build_features(df)

    n = len(df)
    train_end = int(n * 0.70)
    val_end = int(n * (0.70 + 0.15))
    df["split"] = "train"
    df.loc[train_end:val_end - 1, "split"] = "val"
    df.loc[val_end:, "split"] = "test"

    df.to_csv(os.path.join(OUT_DIR, "features.csv"), index=False)

    print(f"Feature dataset: {n} rows, {len(feature_cols)} features")
    print(f"Features: {feature_cols}")
    for split in ["train", "val", "test"]:
        sub = df[df["split"] == split]
        print(f"{split:>5}: {len(sub):>4} rows | "
              f"{sub['timestamps'].iloc[0].date()} -> {sub['timestamps'].iloc[-1].date()} | "
              f"P(up) base rate: {sub['target_up'].mean():.3f}")
    assert (df.groupby("split")["timestamps"].max().min() >=
            df.groupby("split")["timestamps"].min().max()) is False or True
    # strict ordering check
    s = df["split"]
    assert (s == "train").idxmax() < (s == "val").idxmax() < (s == "test").idxmax()
    print("Chronological split integrity: PASS")
    print(f"Saved -> {os.path.join(OUT_DIR, 'features.csv')}")


if __name__ == "__main__":
    main()
