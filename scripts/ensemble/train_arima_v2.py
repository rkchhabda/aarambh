"""ARIMA directional baseline: next-day horizon (tomorrow vs today) to match LSTM/XGB."""

import sys
sys.stdout.reconfigure(line_buffering=True)

import json
import os
import warnings

import numpy as np
import pandas as pd
from pmdarima import auto_arima
from sklearn.metrics import roc_auc_score

ART = os.path.join("ensemble", "artifacts")
warnings.filterwarnings("ignore")


def main():
    df = pd.read_csv(os.path.join(ART, "features.csv"))
    close = df["close"].values
    splits = df["split"].values

    train_end = np.where(splits == "train")[0][-1]
    eval_idx = np.where((splits == "val") | (splits == "test"))[0]
    # Need i+1 for next-day target, so exclude last index
    eval_idx = eval_idx[eval_idx < len(df) - 1]

    print("Fitting auto_arima on train close...", flush=True)
    model = auto_arima(close[:train_end + 1], seasonal=False,
                       error_action="ignore", suppress_warnings=True,
                       stepwise=True, max_p=4, max_q=4, d=None)
    print(f"Best order: {model.order}", flush=True)

    records = []
    for i in eval_idx:
        # Forecast next value (i+1) using info up to i
        fc = float(model.predict(n_periods=1)[0])
        direction_up = int(fc > close[i])  # compare forecast vs today's close
        actual_up = int(close[i + 1] > close[i])  # next day vs today
        records.append({
            "timestamps": df["timestamps"].iloc[i + 1],
            "p_up": None, "pred": direction_up, "actual": actual_up,
            "split": splits[i + 1], "fc_close": fc,
        })
        # Fold in the true observation (expanding without refit)
        model.update(np.array([close[i + 1]]), maxiter=0)

    res = pd.DataFrame(records)
    for split in ["val", "test"]:
        sub = res[res.split == split]
        acc = (sub["pred"] == sub["actual"]).mean()
        pred_up = sub["pred"].mean()
        actual_up = sub["actual"].mean()
        
        # Pseudo-prob from sign
        p_up = [0.5 + 0.5 * p for p in sub["pred"].tolist()]
        auc = roc_auc_score(sub["actual"], p_up)
        
        print(f"ARIMA {split}: accuracy={acc:.4f} AUC={auc:.4f} | pred_up_rate={pred_up:.4f} actual_up_rate={actual_up:.4f} | n={len(sub)}", flush=True)

    out = {}
    for split in ["val", "test"]:
        sub = res[res.split == split]
        out[split] = {
            "timestamps": sub["timestamps"].tolist(),
            "p_up": [0.5 + 0.5 * p for p in sub["pred"].tolist()],
            "pred": sub["pred"].tolist(),
            "actual": sub["actual"].tolist(),
        }
    with open(os.path.join(ART, "arima_preds_v2.json"), "w") as f:
        json.dump(out, f)
    print(f"Saved -> {os.path.join(ART, 'arima_preds_v2.json')}", flush=True)


if __name__ == "__main__":
    main()