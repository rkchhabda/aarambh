"""Kronos v3: Diagnose directional bias and fix probability calibration.

Diagnosis findings:
  - Kronos predicts "up" only 15% of the time vs 53% actual up-rate
  - The p_up formula uses T=0.01 which is too aggressive
  - Kronos's raw point predictions are systematically pessimistic
  
Fix strategy:
  1. Print 10-sample raw outputs to confirm direction of bias
  2. Test multiple temperature scalings for p_up conversion
  3. Apply isotonic regression calibration (val → test)
  4. Re-generate predictions with calibrated probabilities
  
Outputs: kronos_preds_v3.json, kronos_v3_diagnosis.json
"""

import sys
sys.stdout.reconfigure(line_buffering=True)

import json
import os
import pickle

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import roc_auc_score, log_loss

ART = os.path.join("ensemble", "artifacts")


def diagnose_existing_predictions():
    """Analyze existing kronos_preds.json to understand the bias."""
    print("=" * 60)
    print("KRONOS DIAGNOSIS: Analyzing existing predictions")
    print("=" * 60)

    with open(os.path.join(ART, "kronos_preds.json")) as f:
        preds = json.load(f)

    diagnosis = {}
    for split in ["val", "test"]:
        p_up = np.array(preds[split]["p_up"])
        pred = np.array(preds[split]["pred"])
        actual = np.array(preds[split]["actual"])

        # Basic stats
        n = len(actual)
        actual_up_rate = actual.mean()
        pred_up_rate = pred.mean()
        p_up_mean = p_up.mean()
        p_up_std = p_up.std()
        p_up_median = np.median(p_up)

        # Accuracy
        acc = (pred == actual).mean()

        # AUC — uses the raw p_up (however miscalibrated)
        auc = roc_auc_score(actual, p_up) if len(np.unique(actual)) > 1 else 0.5

        # Distribution of p_up
        pct_below_01 = (p_up < 0.1).mean()
        pct_below_05 = (p_up < 0.5).mean()
        pct_above_09 = (p_up > 0.9).mean()

        diagnosis[split] = {
            "n": int(n),
            "actual_up_rate": float(actual_up_rate),
            "pred_up_rate": float(pred_up_rate),
            "p_up_mean": float(p_up_mean),
            "p_up_std": float(p_up_std),
            "p_up_median": float(p_up_median),
            "accuracy": float(acc),
            "auc": float(auc),
            "pct_p_up_below_0.1": float(pct_below_01),
            "pct_p_up_below_0.5": float(pct_below_05),
            "pct_p_up_above_0.9": float(pct_above_09),
        }

        print(f"\n{split.upper()} SET (n={n}):")
        print(f"  Actual up-rate:  {actual_up_rate:.4f}")
        print(f"  Pred up-rate:    {pred_up_rate:.4f}  (bias: {pred_up_rate - actual_up_rate:+.4f})")
        print(f"  p_up mean:       {p_up_mean:.4f}")
        print(f"  p_up std:        {p_up_std:.4f}")
        print(f"  p_up median:     {p_up_median:.4f}")
        print(f"  Accuracy:        {acc:.4f}")
        print(f"  AUC:             {auc:.4f}")
        print(f"  % p_up < 0.1:    {pct_below_01:.2%}")
        print(f"  % p_up < 0.5:    {pct_below_05:.2%}  (pred=down)")
        print(f"  % p_up > 0.9:    {pct_below_01:.2%}")

        # Show 10 sample predictions
        print(f"\n  Sample predictions (first 10):")
        for i in range(min(10, n)):
            marker = "OK" if pred[i] == actual[i] else "WRONG"
            print(f"    {preds[split]['timestamps'][i]}  p_up={p_up[i]:.6f}  "
                  f"pred={pred[i]}  actual={actual[i]}  {marker}")

    return diagnosis


def calibrate_kronos_isotonic():
    """Apply isotonic regression to fix Kronos calibration.
    
    Even if the raw probabilities are poorly calibrated, isotonic regression
    can recover discriminative ability if the RANKING of predictions has signal.
    """
    print("\n" + "=" * 60)
    print("KRONOS CALIBRATION: Isotonic regression")
    print("=" * 60)

    with open(os.path.join(ART, "kronos_preds.json")) as f:
        preds = json.load(f)

    va_p = np.array(preds["val"]["p_up"])
    va_y = np.array(preds["val"]["actual"])
    te_p = np.array(preds["test"]["p_up"])
    te_y = np.array(preds["test"]["actual"])

    # Pre-calibration metrics
    va_auc_pre = roc_auc_score(va_y, va_p) if len(np.unique(va_y)) > 1 else 0.5
    te_auc_pre = roc_auc_score(te_y, te_p) if len(np.unique(te_y)) > 1 else 0.5

    print(f"Pre-calibration:")
    print(f"  Val AUC:  {va_auc_pre:.4f}")
    print(f"  Test AUC: {te_auc_pre:.4f}")

    # ---- Isotonic regression fitted on val ----
    ir = IsotonicRegression(out_of_bounds="clip", y_min=0.01, y_max=0.99)
    ir.fit(va_p, va_y)

    va_p_cal = ir.predict(va_p)
    te_p_cal = ir.predict(te_p)

    # Post-calibration metrics
    va_auc_post = roc_auc_score(va_y, va_p_cal) if len(np.unique(va_y)) > 1 else 0.5
    te_auc_post = roc_auc_score(te_y, te_p_cal) if len(np.unique(te_y)) > 1 else 0.5

    va_acc_cal = ((va_p_cal > 0.5).astype(int) == va_y).mean()
    te_acc_cal = ((te_p_cal > 0.5).astype(int) == te_y).mean()

    print(f"\nPost-calibration (isotonic on val):")
    print(f"  Val AUC:  {va_auc_post:.4f}  (was {va_auc_pre:.4f}, delta={va_auc_post - va_auc_pre:+.4f})")
    print(f"  Test AUC: {te_auc_post:.4f}  (was {te_auc_pre:.4f}, delta={te_auc_post - te_auc_pre:+.4f})")
    print(f"  Val Acc:  {va_acc_cal:.4f}")
    print(f"  Test Acc: {te_acc_cal:.4f}")
    print(f"  Val p_up mean:  {va_p_cal.mean():.4f}  std={va_p_cal.std():.4f}")
    print(f"  Test p_up mean: {te_p_cal.mean():.4f}  std={te_p_cal.std():.4f}")
    print(f"  Val pred_up_rate:  {(va_p_cal > 0.5).mean():.4f}")
    print(f"  Test pred_up_rate: {(te_p_cal > 0.5).mean():.4f}")

    # ---- Also try: simple label flip (if the model is informatively wrong) ----
    print("\n--- Alternative: Flip predictions (1 - p_up) ---")
    va_p_flip = 1 - va_p
    te_p_flip = 1 - te_p
    va_auc_flip = roc_auc_score(va_y, va_p_flip) if len(np.unique(va_y)) > 1 else 0.5
    te_auc_flip = roc_auc_score(te_y, te_p_flip) if len(np.unique(te_y)) > 1 else 0.5
    va_acc_flip = ((va_p_flip > 0.5).astype(int) == va_y).mean()
    te_acc_flip = ((te_p_flip > 0.5).astype(int) == te_y).mean()
    print(f"  Val AUC: {va_auc_flip:.4f}  Acc: {va_acc_flip:.4f}")
    print(f"  Test AUC: {te_auc_flip:.4f}  Acc: {te_acc_flip:.4f}")

    # ---- Also try: using raw pred_ret as the score instead of sigmoid transform ----
    # This tests whether the RANKING in raw returns has more signal than the sigmoid-squashed version
    # We can reconstruct pred_ret from p_up using the inverse sigmoid: ret = -T * ln(1/p_up - 1)
    # But the extreme values (near 0 or 1) make this noisy. Better to just use p_up directly.

    # ---- Build output: use isotonic-calibrated predictions ----
    out = {}
    for split, p_cal, y in [("val", va_p_cal, va_y), ("test", te_p_cal, te_y)]:
        out[split] = {
            "timestamps": preds[split]["timestamps"],
            "p_up": p_cal.round(6).tolist(),
            "pred": (p_cal > 0.5).astype(int).tolist(),
            "actual": y.tolist(),
        }

    with open(os.path.join(ART, "kronos_preds_v3.json"), "w") as f:
        json.dump(out, f)
    print(f"\nSaved -> {os.path.join(ART, 'kronos_preds_v3.json')}")

    # Save isotonic model
    with open(os.path.join(ART, "kronos_isotonic_v3.pkl"), "wb") as f:
        pickle.dump(ir, f)

    return {
        "pre_calibration": {"val_auc": va_auc_pre, "test_auc": te_auc_pre},
        "isotonic": {
            "val_auc": float(va_auc_post), "test_auc": float(te_auc_post),
            "val_acc": float(va_acc_cal), "test_acc": float(te_acc_cal),
            "val_p_std": float(va_p_cal.std()), "test_p_std": float(te_p_cal.std()),
        },
        "flipped": {
            "val_auc": float(va_auc_flip), "test_auc": float(te_auc_flip),
            "val_acc": float(va_acc_flip), "test_acc": float(te_acc_flip),
        },
    }


def main():
    # Step 1: Diagnose
    diagnosis = diagnose_existing_predictions()

    # Step 2: Calibrate
    calibration = calibrate_kronos_isotonic()

    # Step 3: Save full diagnosis
    full_report = {
        "diagnosis": diagnosis,
        "calibration": calibration,
    }
    with open(os.path.join(ART, "kronos_v3_diagnosis.json"), "w") as f:
        json.dump(full_report, f, indent=2, default=str)
    print(f"\nSaved diagnosis -> {os.path.join(ART, 'kronos_v3_diagnosis.json')}")


if __name__ == "__main__":
    main()
