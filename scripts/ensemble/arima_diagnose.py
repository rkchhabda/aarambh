"""Diagnose ARIMA fitting and predictions."""

import json
import os
import warnings

import numpy as np
import pandas as pd
from pmdarima import auto_arima

ART = os.path.join("ensemble", "artifacts")
warnings.filterwarnings("ignore")


def main():
    df = pd.read_csv(os.path.join(ART, "features.csv"))
    # Convert timestamps without pd.to_datetime
    df['ts'] = pd.to_datetime(df['timestamps'], format='%Y-%m-%d')
    close = df["close"].values
    splits = df["split"].values

    train_end = np.where(splits == "train")[0][-1]
    eval_idx = np.where((splits == "val") | (splits == "test"))[0]

    print(f"Train data: {train_end+1} points")
    print(f"Train close range: {close[:train_end+1].min():.2f} - {close[:train_end+1].max():.2f}")
    print(f"Eval points: {len(eval_idx)}")

    print("Fitting auto_arima on train close...")
    model = auto_arima(close[:train_end + 1], seasonal=False,
                       error_action="raise", suppress_warnings=False,
                       stepwise=True, max_p=4, max_q=4, d=None, trace=True)
    print(f"Best order: {model.order}")
    print(f"Model: {model}")

    # Check forecasts
    print("\nFirst 10 forecasts:")
    for i in eval_idx[:10]:
        fc = float(model.predict(n_periods=1)[0])
        direction_up = int(fc > close[i - 1])
        actual_up = int(close[i] > close[i - 1])
        print(f"  {df['timestamps'].iloc[i]}: fc={fc:.4f}, last={close[i-1]:.4f}, pred_up={direction_up}, actual_up={actual_up}")
        model.update(np.array([close[i]]), maxiter=0)

    # Full evaluation
    records = []
    for i in eval_idx:
        fc = float(model.predict(n_periods=1)[0])
        direction_up = int(fc > close[i - 1])
        actual_up = int(close[i] > close[i - 1])
        records.append({
            "timestamps": df["timestamps"].iloc[i],
            "fc": fc,
            "last_close": close[i-1],
            "pred": direction_up,
            "actual": actual_up,
            "split": splits[i],
        })
        model.update(np.array([close[i]]), maxiter=0)

    res = pd.DataFrame(records)
    for split in ["val", "test"]:
        sub = res[res.split == split]
        acc = (sub["pred"] == sub["actual"]).mean()
        pred_up_rate = sub["pred"].mean()
        print(f"\nARIMA {split}: accuracy={acc:.4f} | pred_up_rate={pred_up_rate:.4f} | n={len(sub)}")
        print(f"  fc stats: mean={sub['fc'].mean():.4f}, std={sub['fc'].std():.4f}")


if __name__ == "__main__":
    main()