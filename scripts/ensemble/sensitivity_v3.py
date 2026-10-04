"""Sensitivity analysis v3: pre-specified ensemble blends on fixed v3 models."""

import json
import os

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ART = os.path.join("ensemble", "artifacts")
MODELS = ["xgb", "lstm", "kronos"]
MODEL_FILES = {
    "xgb": "xgb_preds.json",
    "lstm": "lstm_preds_v3.json",
    "kronos": "kronos_preds_v3.json",
}


def load_aligned():
    preds = {}
    for m in MODELS:
        with open(os.path.join(ART, MODEL_FILES[m])) as f:
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
    "equal_3":        {"xgb": 1/3, "lstm": 1/3, "kronos": 1/3},
    "ml_only":        {"xgb": 0.5, "lstm": 0.5, "kronos": 0.0},
    "lstm_kronos":    {"xgb": 0.0, "lstm": 0.5, "kronos": 0.5},
    "lstm_heavy":     {"xgb": 0.2, "lstm": 0.6, "kronos": 0.2},
    "lstm_only":      {"xgb": 0.0, "lstm": 1.0, "kronos": 0.0},
    "xgb_only":       {"xgb": 1.0, "lstm": 0.0, "kronos": 0.0},
    "kronos_only":    {"xgb": 0.0, "lstm": 0.0, "kronos": 1.0},
}


def main():
    av = load_aligned()
    va_p, va_y = av["val"]
    te_p, te_y = av["test"]

    rows = []
    print(f"{'Blend':<15} {'Val AUC':>8} {'Val Acc':>8} {'Test AUC':>9} {'Test Acc':>9}")
    print("-" * 55)
    for name, wmap in BLENDS.items():
        w = np.array([wmap[m] for m in MODELS])
        va_pred = va_p @ w
        te_pred = te_p @ w
        va_auc = roc_auc_score(va_y, va_pred)
        te_auc = roc_auc_score(te_y, te_pred)
        va_acc = ((va_pred > 0.5).astype(int) == va_y).mean()
        te_acc = ((te_pred > 0.5).astype(int) == te_y).mean()
        rows.append({
            "blend": name,
            "weights": w.round(3).tolist(),
            "val_auc": round(va_auc, 4),
            "val_acc": round(va_acc, 4),
            "test_auc": round(te_auc, 4),
            "test_acc": round(te_acc, 4),
        })
        print(f"{name:<15} {va_auc:.4f}   {va_acc:.4f}   {te_auc:.4f}    {te_acc:.4f}")

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(ART, "blend_sensitivity_v3.csv"), index=False)
    print(f"\nSaved -> {os.path.join(ART, 'blend_sensitivity_v3.csv')}")


if __name__ == "__main__":
    main()
