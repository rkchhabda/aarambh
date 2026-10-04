"""Apply isotonic regression to calibrate Kronos predictions."""

import sys
sys.stdout.reconfigure(line_buffering=True)

import json
import os

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import roc_auc_score

ART = os.path.join("ensemble", "artifacts")


def load_preds(model_name):
    with open(os.path.join(ART, f"{model_name}_preds.json")) as f:
        return json.load(f)


def main():
    # Load original Kronos predictions
    kronos = load_preds("kronos")
    lstm = load_preds("lstm")
    xgb = load_preds("xgb")
    arima = load_preds("arima")

    # Align timestamps
    for split in ["val", "test"]:
        common = sorted(set(kronos[split]["timestamps"]) &
                       set(lstm[split]["timestamps"]) &
                       set(xgb[split]["timestamps"]) &
                       set(arima[split]["timestamps"]))
        kronos[split]["common_idx"] = [kronos[split]["timestamps"].index(t) for t in common]
        lstm[split]["common_idx"] = [lstm[split]["timestamps"].index(t) for t in common]
        xgb[split]["common_idx"] = [xgb[split]["timestamps"].index(t) for t in common]
        arima[split]["common_idx"] = [arima[split]["timestamps"].index(t) for t in common]

    # Fit isotonic regression on val set
    val_p_kronos = np.array([kronos["val"]["p_up"][i] for i in kronos["val"]["common_idx"]])
    val_y = np.array([kronos["val"]["actual"][i] for i in kronos["val"]["common_idx"]])

    iso_reg = IsotonicRegression(out_of_bounds="clip")
    iso_reg.fit(val_p_kronos, val_y)

    print("Isotonic regression fitted on val set")
    print(f"  Val: n={len(val_p_kronos)}, p_up range=[{val_p_kronos.min():.4f}, {val_p_kronos.max():.4f}]")

    # Apply to val and test
    for split in ["val", "test"]:
        idx = kronos[split]["common_idx"]
        p_raw = np.array([kronos[split]["p_up"][i] for i in idx])
        p_cal = iso_reg.predict(p_raw)
        actual = np.array([kronos[split]["actual"][i] for i in idx])

        pred_raw = (p_raw > 0.5).astype(int)
        pred_cal = (p_cal > 0.5).astype(int)

        acc_raw = (pred_raw == actual).mean()
        acc_cal = (pred_cal == actual).mean()
        auc_raw = roc_auc_score(actual, p_raw)
        auc_cal = roc_auc_score(actual, p_cal)

        print(f"\n{split.upper()} set:")
        print(f"  Raw:  acc={acc_raw:.4f}, auc={auc_raw:.4f}, p_up_mean={p_raw.mean():.4f}, p_up_std={p_raw.std():.4f}, pred_up_rate={(p_raw>0.5).mean():.4f}")
        print(f"  Cal:  acc={acc_cal:.4f}, auc={auc_cal:.4f}, p_up_mean={p_cal.mean():.4f}, p_up_std={p_cal.std():.4f}, pred_up_rate={(p_cal>0.5).mean():.4f}")

        # Update Kronos predictions with calibrated probabilities
        for j, i in enumerate(idx):
            kronos[split]["p_up"][i] = float(p_cal[j])
            kronos[split]["pred"][i] = int(pred_cal[j])

    # Save calibrated Kronos predictions
    with open(os.path.join(ART, "kronos_preds_calibrated.json"), "w") as f:
        json.dump(kronos, f)
    print(f"\nSaved calibrated Kronos -> {os.path.join(ART, 'kronos_preds_calibrated.json')}")

    # Also save the isotonic regression model
    import joblib
    joblib.dump(iso_reg, os.path.join(ART, "kronos_isotonic.pkl"))
    print(f"Saved isotonic regression model -> {os.path.join(ART, 'kronos_isotonic.pkl')}")


if __name__ == "__main__":
    main()