"""Combine XGB + LSTM + ARIMA + Kronos: optimize blend weights on val, evaluate on test."""

import json
import os
from itertools import product

import numpy as np
import pandas as pd

ART = os.path.join("ensemble", "artifacts")
MODELS = ["xgb", "lstm", "arima", "kronos"]


def load_preds(name):
    with open(os.path.join(ART, f"{name}_preds.json")) as f:
        return json.load(f)


def main():
    preds = {m: load_preds(m) for m in MODELS}

    # Align all models on common timestamps per split
    aligned = {}
    for split in ["val", "test"]:
        sets = [set(preds[m][split]["timestamps"]) for m in MODELS]
        common = sorted(set.intersection(*sets))
        xgb_actual = np.array(preds["xgb"][split]["actual"])
        xgb_ts = preds["xgb"][split]["timestamps"]
        aligned[split] = {
            "timestamps": common,
            "p": np.array([[preds[m][split]["p_up"][preds[m][split]["timestamps"].index(t)]
                            for t in common] for m in MODELS]).T,   # (N, 4)
            "actual": xgb_actual[[xgb_ts.index(t) for t in common]],
        }
        print(f"{split}: {len(common)} aligned days")

    va_p, va_y = aligned["val"]["p"], aligned["val"]["actual"]
    te_p, te_y = aligned["test"]["p"], aligned["test"]["actual"]

    # Individual model performance
    print("\n--- Standalone models ---")
    results = {}
    for j, m in enumerate(MODELS):
        va_acc = ((va_p[:, j] > 0.5).astype(int) == va_y).mean()
        te_acc = ((te_p[:, j] > 0.5).astype(int) == te_y).mean()
        results[m] = {"val": va_acc, "test": te_acc}
        print(f"{m:>6}: val={va_acc:.4f}  test={te_acc:.4f}")

    # Weight grid search on validation accuracy (simplex, step 0.05)
    print("\nOptimizing ensemble weights on validation set...")
    steps = np.arange(0, 1.0001, 0.05)
    best = {"acc": -1, "w": None}
    for w in product(steps, repeat=len(MODELS)):
        s = sum(w)
        if s == 0:
            continue
        w = np.array(w) / s
        acc = (((va_p @ w) > 0.5).astype(int) == va_y).mean()
        if acc > best["acc"]:
            best = {"acc": acc, "w": w}
    w = best["w"]
    print(f"Best val acc={best['acc']:.4f} | weights: "
          f"{dict(zip(MODELS, w.round(3)))}")

    # Evaluate on test
    ens_val = (va_p @ w > 0.5).astype(int)
    ens_test = (te_p @ w > 0.5).astype(int)
    ens_val_acc = (ens_val == va_y).mean()
    ens_test_acc = (ens_test == te_y).mean()

    # Majority-vote comparison
    votes = ((te_p > 0.5).astype(int).sum(axis=1) >= 2).astype(int)
    mv_acc = (votes == te_y).mean()

    base_rate = max(te_y.mean(), 1 - te_y.mean())

    print("\n================ FINAL RESULTS (test) ================")
    print(f"Base rate (majority class) : {base_rate:.4f}")
    for m in MODELS:
        print(f"{m:>6} standalone           : {results[m]['test']:.4f}")
    print(f"Majority vote              : {mv_acc:.4f}")
    print(f"Weighted ensemble          : {ens_test_acc:.4f}")
    print(f"(weighted ensemble val acc : {ens_val_acc:.4f})")

    pd.DataFrame({
        "model": MODELS + ["majority_vote", "weighted_ensemble"],
        "val_acc": [results[m]["val"] for m in MODELS] + [None, ens_val_acc],
        "test_acc": [results[m]["test"] for m in MODELS] + [mv_acc, ens_test_acc],
        "weight": list(w) + [None, None],
    }).to_csv(os.path.join(ART, "ensemble_results.csv"), index=False)

    with open(os.path.join(ART, "ensemble_weights.json"), "w") as f:
        json.dump({"weights": dict(zip(MODELS, w.tolist())),
                   "val_acc": float(ens_val_acc), "test_acc": float(ens_test_acc)}, f, indent=2)
    print(f"\nSaved -> {os.path.join(ART, 'ensemble_results.csv')} and ensemble_weights.json")


if __name__ == "__main__":
    main()
