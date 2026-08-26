"""Sensitivity analysis: pre-specified ensemble blends vs. fine-tuned weight grid."""

import json
import os

import numpy as np
import pandas as pd

ART = os.path.join("ensemble", "artifacts")
MODELS = ["xgb", "lstm", "arima", "kronos"]


def load_aligned():
    preds = {}
    for m in MODELS:
        with open(os.path.join(ART, f"{m}_preds.json")) as f:
            preds[m] = json.load(f)
    aligned = {}
    for split in ["val", "test"]:
        common = sorted(set.intersection(*[set(preds[m][split]["timestamps"]) for m in MODELS]))
        P = np.array([[preds[m][split]["p_up"][preds[m][split]["timestamps"].index(t)]
                       for t in common] for m in MODELS]).T
        y = np.array([preds["xgb"][split]["actual"][preds["xgb"][split]["timestamps"].index(t)]
                      for t in common])
        aligned[split] = (P, y)
    return aligned


BLENDS = {
    "equal_4":        {"xgb": 0.25, "lstm": 0.25, "arima": 0.25, "kronos": 0.25},
    "no_arima":       {"xgb": 1/3, "lstm": 1/3, "arima": 0.0, "kronos": 1/3},
    "ml_only":        {"xgb": 0.5, "lstm": 0.5, "arima": 0.0, "kronos": 0.0},
    "lstm_kronos":    {"xgb": 0.0, "lstm": 0.5, "arima": 0.0, "kronos": 0.5},
    "lstm_heavy":     {"xgb": 0.15, "lstm": 0.55, "arima": 0.05, "kronos": 0.25},
    "lstm_only":      {"xgb": 0.0, "lstm": 1.0, "arima": 0.0, "kronos": 0.0},
}


def main():
    av = load_aligned()
    va_p, va_y = av["val"]
    te_p, te_y = av["test"]

    rows = []
    for name, wmap in BLENDS.items():
        w = np.array([wmap[m] for m in MODELS])
        va_acc = ((va_p @ w > 0.5).astype(int) == va_y).mean()
        te_acc = ((te_p @ w > 0.5).astype(int) == te_y).mean()
        rows.append({"blend": name, "weights": w.round(3).tolist(),
                     "val_acc": round(va_acc, 4), "test_acc": round(te_acc, 4)})
        print(f"{name:<12} w={w.round(3)}  val={va_acc:.4f}  test={te_acc:.4f}")

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(ART, "blend_sensitivity.csv"), index=False)
    print(f"\nSaved -> {os.path.join(ART, 'blend_sensitivity.csv')}")


if __name__ == "__main__":
    main()
