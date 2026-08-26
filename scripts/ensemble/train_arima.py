"""ARIMA directional baseline: auto_arima on train close, rolling 1-step forecasts."""

import json
import os
import warnings

import numpy as np
import pandas as pd
from pmdarima import auto_arima

ART = os.path.join("ensemble", "artifacts")
warnings.filterwarnings("ignore")


def main():
    df = pd.read_csv(os.path.join(ART, "features.csv"), parse_dates=["timestamps"])
    close = df["close"].values
    splits = df["split"].values

    train_end = np.where(splits == "train")[0][-1]
    eval_idx = np.where((splits == "val") | (splits == "test"))[0]

    print("Fitting auto_arima on train close...")
    model = auto_arima(close[:train_end + 1], seasonal=False,
                       error_action="ignore", suppress_warnings=True,
                       stepwise=True, max_p=4, max_q=4, d=None)
    print(f"Best order: {model.order}")

    records = []
    for i in eval_idx:
        # forecast next value using info up to i-1
        fc = float(model.predict(n_periods=1)[0])
        direction_up = int(fc > close[i - 1])
        actual_up = int(close[i] > close[i - 1])
        records.append({
            "timestamps": df["timestamps"].iloc[i].strftime("%Y-%m-%d"),
            "p_up": None, "pred": direction_up, "actual": actual_up,
            "split": splits[i], "fc_close": fc,
        })
        # fold in the true observation (expanding without refit)
        model.update(np.array([close[i]]), maxiter=0)

    res = pd.DataFrame(records)
    for split in ["val", "test"]:
        sub = res[res.split == split]
        acc = (sub["pred"] == sub["actual"]).mean()
        mae = np.abs(sub["fc_close"].values - close[df.index[res.index[res.split == split]]]).mean()
        print(f"ARIMA {split}: accuracy={acc:.4f} | close MAE={mae:.2f} | n={len(sub)}")

    out = {}
    for split in ["val", "test"]:
        sub = res[res.split == split]
        out[split] = {
            "timestamps": sub["timestamps"].tolist(),
            "p_up": [0.5 + 0.5 * p for p in sub["pred"].tolist()],  # pseudo-prob from sign
            "pred": sub["pred"].tolist(),
            "actual": sub["actual"].tolist(),
        }
    with open(os.path.join(ART, "arima_preds.json"), "w") as f:
        json.dump(out, f)
    print(f"Saved -> {os.path.join(ART, 'arima_preds.json')}")


if __name__ == "__main__":
    main()
