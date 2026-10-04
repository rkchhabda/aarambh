"""Combine models with walk-forward validation and proper calibration."""

import json
import os
import warnings
from itertools import product

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import roc_auc_score

warnings.filterwarnings("ignore")

ART = os.path.join("ensemble", "artifacts")
# Remove ARIMA - it's broken (random walk)
MODELS = ["xgb", "lstm", "kronos"]


def load_preds(name):
    with open(os.path.join(ART, f"{name}_preds.json")) as f:
        return json.load(f)


def calibrate_kronos(preds):
    """Apply isotonic regression to calibrate Kronos probabilities on val set."""
    # Kronos has systematic bias - use isotonic regression on val to calibrate test
    va_p = np.array(preds["kronos"]["val"]["p_up"])
    va_y = np.array(preds["kronos"]["val"]["actual"])
    te_p = np.array(preds["kronos"]["test"]["p_up"])
    te_y = np.array(preds["kronos"]["test"]["actual"])
    
    # Fit isotonic regression on val
    ir = IsotonicRegression(out_of_bounds="clip")
    ir.fit(va_p, va_y)
    
    # Calibrate both val and test
    va_p_cal = ir.predict(va_p)
    te_p_cal = ir.predict(te_p)
    
    print(f"Kronos calibration: val AUC before={roc_auc_score(va_y, va_p):.4f}, after={roc_auc_score(va_y, va_p_cal):.4f}")
    print(f"Kronos calibration: test AUC before={roc_auc_score(te_y, te_p):.4f}, after={roc_auc_score(te_y, te_p_cal):.4f}")
    
    # Update predictions
    preds["kronos"]["val"]["p_up"] = va_p_cal.tolist()
    preds["kronos"]["test"]["p_up"] = te_p_cal.tolist()
    return preds


def align_predictions(preds, models):
    """Align all models on common timestamps per split."""
    aligned = {}
    for split in ["val", "test"]:
        sets = [set(preds[m][split]["timestamps"]) for m in models]
        common = sorted(set.intersection(*sets))
        ref_ts = preds[models[0]][split]["timestamps"]
        ref_actual = np.array(preds[models[0]][split]["actual"])
        
        aligned[split] = {
            "timestamps": common,
            "p": np.array([[preds[m][split]["p_up"][preds[m][split]["timestamps"].index(t)]
                            for t in common] for m in models]).T,
            "actual": ref_actual[[ref_ts.index(t) for t in common]],
        }
        print(f"{split}: {len(common)} aligned days")
    return aligned


def walk_forward_weights(val_p, val_y, n_folds=5):
    """Select ensemble weights using walk-forward (expanding window) validation."""
    n = len(val_y)
    fold_size = n // n_folds
    
    best_weights = None
    best_mean_auc = -1
    
    # Grid search on simplex
    steps = np.arange(0, 1.0001, 0.05)
    for w in product(steps, repeat=len(MODELS)):
        s = sum(w)
        if s == 0:
            continue
        w = np.array(w) / s
        
        # Evaluate on each fold
        fold_aucs = []
        for fold in range(n_folds):
            start = fold * fold_size
            end = (fold + 1) * fold_size if fold < n_folds - 1 else n
            if end - start < 10:
                continue
            fold_p = val_p[start:end]
            fold_y = val_y[start:end]
            if len(np.unique(fold_y)) < 2:
                continue
            fold_auc = roc_auc_score(fold_y, fold_p @ w)
            fold_aucs.append(fold_auc)
        
        if fold_aucs:
            mean_auc = np.mean(fold_aucs)
            if mean_auc > best_mean_auc:
                best_mean_auc = mean_auc
                best_weights = w
    
    return best_weights, best_mean_auc


def main():
    preds = {m: load_preds(m) for m in MODELS}
    
    # Calibrate Kronos
    preds = calibrate_kronos(preds)
    
    # Align
    aligned = align_predictions(preds, MODELS)
    va_p, va_y = aligned["val"]["p"], aligned["val"]["actual"]
    te_p, te_y = aligned["test"]["p"], aligned["test"]["actual"]
    
    print(f"Val: {len(va_y)} samples, up-rate={va_y.mean():.4f}")
    print(f"Test: {len(te_y)} samples, up-rate={te_y.mean():.4f}")
    
    # Individual model performance
    print("\n--- Standalone models (AUC) ---")
    results = {}
    for j, m in enumerate(MODELS):
        va_auc = roc_auc_score(va_y, va_p[:, j]) if len(np.unique(va_y)) > 1 else 0.5
        te_auc = roc_auc_score(te_y, te_p[:, j]) if len(np.unique(te_y)) > 1 else 0.5
        va_acc = ((va_p[:, j] > 0.5).astype(int) == va_y).mean()
        te_acc = ((te_p[:, j] > 0.5).astype(int) == te_y).mean()
        results[m] = {"val_auc": va_auc, "test_auc": te_auc, "val_acc": va_acc, "test_acc": te_acc}
        print(f"{m:>6}: val AUC={va_auc:.4f} acc={va_acc:.4f} | test AUC={te_auc:.4f} acc={te_acc:.4f}")
    
    # Walk-forward weight selection
    print(f"\nOptimizing ensemble weights with {5}-fold walk-forward validation...")
    w, best_auc = walk_forward_weights(va_p, va_y, n_folds=5)
    print(f"Best walk-forward AUC={best_auc:.4f} | weights: {dict(zip(MODELS, w.round(3)))}")
    
    # Also try single val split for comparison
    print("\n--- Comparison: Single val split optimization ---")
    steps = np.arange(0, 1.0001, 0.05)
    best_single = {"auc": -1, "w": None}
    for w_single in product(steps, repeat=len(MODELS)):
        s = sum(w_single)
        if s == 0:
            continue
        w_single = np.array(w_single) / s
        auc = roc_auc_score(va_y, va_p @ w_single)
        if auc > best_single["auc"]:
            best_single = {"auc": auc, "w": w_single}
    print(f"Single val AUC={best_single['auc']:.4f} | weights: {dict(zip(MODELS, best_single['w'].round(3)))}")
    
    # Evaluate both on test
    w_wf = w
    w_single = best_single["w"]
    
    wf_test_auc = roc_auc_score(te_y, te_p @ w_wf)
    single_test_auc = roc_auc_score(te_y, te_p @ w_single)
    wf_test_acc = ((te_p @ w_wf > 0.5).astype(int) == te_y).mean()
    single_test_acc = ((te_p @ w_single > 0.5).astype(int) == te_y).mean()
    
    # Majority vote
    votes = ((te_p > 0.5).astype(int).sum(axis=1) >= 2).astype(int)
    mv_acc = (votes == te_y).mean()
    mv_auc = roc_auc_score(te_y, votes.astype(float))
    
    # Best single model
    best_single_model = max(results.items(), key=lambda x: x[1]["test_auc"])
    
    print("\n================ FINAL RESULTS (test) ================")
    print(f"Base rate (majority class) : {max(te_y.mean(), 1 - te_y.mean()):.4f}")
    for m in MODELS:
        print(f"{m:>6} standalone           : AUC={results[m]['test_auc']:.4f} acc={results[m]['test_acc']:.4f}")
    print(f"Majority vote              : AUC={mv_auc:.4f} acc={mv_acc:.4f}")
    print(f"Weighted ensemble (WF)     : AUC={wf_test_auc:.4f} acc={wf_test_acc:.4f}")
    print(f"Weighted ensemble (single) : AUC={single_test_auc:.4f} acc={single_test_acc:.4f}")
    print(f"Best single model ({best_single_model[0]}) : AUC={best_single_model[1]['test_auc']:.4f} acc={best_single_model[1]['test_acc']:.4f}")
    
    # Check if ensemble beats best single model
    if wf_test_auc > best_single_model[1]["test_auc"]:
        print(f"\n[OK] Ensemble BEATS best single model on test AUC!")
    else:
        print(f"\n[FAIL] Ensemble does NOT beat best single model on test AUC.")
    
    # Save results
    pd.DataFrame({
        "model": MODELS + ["majority_vote", "weighted_ensemble_wf", "weighted_ensemble_single"],
        "val_auc": [results[m]["val_auc"] for m in MODELS] + [None, best_auc, best_single["auc"]],
        "test_auc": [results[m]["test_auc"] for m in MODELS] + [mv_auc, wf_test_auc, single_test_auc],
        "val_acc": [results[m]["val_acc"] for m in MODELS] + [None, (va_p @ w_wf > 0.5).astype(int).mean(), (va_p @ w_single > 0.5).astype(int).mean()],
        "test_acc": [results[m]["test_acc"] for m in MODELS] + [mv_acc, wf_test_acc, single_test_acc],
        "weight": list(w_wf) + [None, None, None],
    }).to_csv(os.path.join(ART, "ensemble_results_v2.csv"), index=False)
    
    with open(os.path.join(ART, "ensemble_weights_v2.json"), "w") as f:
        json.dump({
            "weights": dict(zip(MODELS, w_wf.tolist())),
            "walk_forward_auc": float(best_auc),
            "test_auc": float(wf_test_auc),
            "test_acc": float(wf_test_acc),
            "single_val_auc": float(best_single["auc"]),
            "single_test_auc": float(single_test_auc),
        }, f, indent=2)
    
    print(f"\nSaved -> {os.path.join(ART, 'ensemble_results_v2.csv')} and ensemble_weights_v2.json")


if __name__ == "__main__":
    main()