"""Ensemble v3: Walk-forward weight selection with proper validation.

Fixes from v1 (combine.py):
  1. Removes ARIMA — confirmed broken (constant 0.5 / random walk)
  2. Uses v3 LSTM predictions (AUC-stopped, not collapsed)
  3. Uses v3 Kronos predictions (isotonic-calibrated)
  4. Walk-forward validation: 3+ expanding-window folds
  5. Optimizes mean OOF AUC across folds (not accuracy on 1 split)
  6. Compares against lstm_only baseline — ensemble must beat it

Outputs: ensemble_weights_v3.json, ensemble_results_v3.csv
"""

import sys
sys.stdout.reconfigure(line_buffering=True)

import json
import os
from itertools import product as iter_product

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.metrics import roc_auc_score, log_loss

ART = os.path.join("ensemble", "artifacts")
N_FOLDS = 4  # Expanding window folds within val set


def load_preds(name):
    path = os.path.join(ART, f"{name}_preds.json")
    if not os.path.exists(path):
        # Try v3 variants
        path = os.path.join(ART, f"{name}_preds_v3.json")
    with open(path) as f:
        return json.load(f)


def align_predictions(preds, model_names):
    """Align all models on common timestamps per split."""
    aligned = {}
    for split in ["val", "test"]:
        common = set(preds[model_names[0]][split]["timestamps"])
        for m in model_names[1:]:
            common &= set(preds[m][split]["timestamps"])
        common = sorted(common)

        if not common:
            raise ValueError(f"No common timestamps for {split}")

        P = np.array([[preds[m][split]["p_up"][preds[m][split]["timestamps"].index(t)]
                        for t in common] for m in model_names]).T
        y = np.array([preds[model_names[0]][split]["actual"][
            preds[model_names[0]][split]["timestamps"].index(t)] for t in common])

        aligned[split] = {"P": P, "y": y, "timestamps": common}
        print(f"  {split}: {len(common)} aligned days, up_rate={y.mean():.4f}")

    return aligned


def walkforward_weights(P, y, n_models, n_folds=N_FOLDS):
    """Walk-forward (expanding window) weight selection on val set.

    Folds:
      Fold 0: train=[0, fold_size), val=[fold_size, 2*fold_size)
      Fold 1: train=[0, 2*fold_size), val=[2*fold_size, 3*fold_size)
      ...etc
    """
    n = len(y)
    fold_size = n // (n_folds + 1)  # +1 because first fold is train-only

    if fold_size < 20:
        print(f"  WARNING: fold_size={fold_size} is very small, results may be noisy")

    fold_weights = []
    fold_aucs = []

    for fold in range(n_folds):
        train_end = (fold + 1) * fold_size
        val_start = train_end
        val_end = min(train_end + fold_size, n) if fold < n_folds - 1 else n

        if val_start >= val_end or val_end - val_start < 10:
            continue

        train_P = P[:train_end]
        train_y = y[:train_end]
        val_P = P[val_start:val_end]
        val_y = y[val_start:val_end]

        if len(np.unique(train_y)) < 2 or len(np.unique(val_y)) < 2:
            continue

        # Optimize weights on training window using scipy
        def neg_auc(w):
            w = np.abs(w)  # ensure non-negative
            w = w / w.sum() if w.sum() > 0 else np.ones(n_models) / n_models
            return -roc_auc_score(train_y, train_P @ w)

        x0 = np.ones(n_models) / n_models
        bounds = [(0, 1)] * n_models
        constraints = {'type': 'eq', 'fun': lambda w: np.abs(w).sum() - 1}

        result = minimize(neg_auc, x0, bounds=bounds, constraints=constraints, method='SLSQP')
        w = np.abs(result.x) / np.abs(result.x).sum() if result.success else x0

        # Evaluate on validation window (OOF)
        val_auc = roc_auc_score(val_y, val_P @ w)
        val_acc = ((val_P @ w > 0.5).astype(int) == val_y).mean()

        fold_weights.append(w)
        fold_aucs.append(val_auc)

        print(f"  Fold {fold+1}: train={len(train_y)}, val={len(val_y)} | "
              f"OOF AUC={val_auc:.4f} acc={val_acc:.4f} | "
              f"weights={dict(zip(['xgb','lstm','kronos'], np.round(w, 3)))}")

    # Average weights across folds (more stable than picking best fold)
    mean_weights = np.mean(fold_weights, axis=0)
    mean_weights = mean_weights / mean_weights.sum()
    mean_auc = np.mean(fold_aucs)

    return mean_weights, fold_weights, fold_aucs, mean_auc


def main():
    print("=" * 60)
    print("ENSEMBLE v3: Walk-forward weight selection")
    print("=" * 60)

    # ---- Load predictions ----
    # Use v3 versions of LSTM and Kronos, original XGB
    model_files = {
        "xgb": "xgb_preds.json",
        "lstm": "lstm_preds_v3.json",
        "kronos": "kronos_preds_v3.json",
    }
    model_names = ["xgb", "lstm", "kronos"]

    preds = {}
    for m in model_names:
        path = os.path.join(ART, model_files[m])
        if not os.path.exists(path):
            # Fallback to original
            fallback = os.path.join(ART, f"{m}_preds.json")
            print(f"  WARNING: {path} not found, falling back to {fallback}")
            path = fallback
        with open(path) as f:
            preds[m] = json.load(f)
        print(f"  Loaded {m} from {os.path.basename(path)}")

    # ---- Align ----
    print("\nAligning predictions...")
    aligned = align_predictions(preds, model_names)
    va_P, va_y = aligned["val"]["P"], aligned["val"]["y"]
    te_P, te_y = aligned["test"]["P"], aligned["test"]["y"]

    # ---- Individual model performance ----
    print(f"\n{'='*60}")
    print("INDIVIDUAL MODEL PERFORMANCE")
    print(f"{'='*60}")
    print(f"{'Model':<10} {'Val AUC':>8} {'Val Acc':>8} {'Test AUC':>9} {'Test Acc':>9} {'Test p_std':>10}")
    results = {}
    for j, m in enumerate(model_names):
        va_auc = roc_auc_score(va_y, va_P[:, j]) if len(np.unique(va_y)) > 1 else 0.5
        te_auc = roc_auc_score(te_y, te_P[:, j]) if len(np.unique(te_y)) > 1 else 0.5
        va_acc = ((va_P[:, j] > 0.5).astype(int) == va_y).mean()
        te_acc = ((te_P[:, j] > 0.5).astype(int) == te_y).mean()
        te_std = te_P[:, j].std()
        results[m] = {"val_auc": va_auc, "test_auc": te_auc, "val_acc": va_acc, "test_acc": te_acc}
        print(f"{m:<10} {va_auc:.4f}   {va_acc:.4f}   {te_auc:.4f}    {te_acc:.4f}    {te_std:.5f}")

    # ---- Walk-forward weight optimization ----
    print(f"\n{'='*60}")
    print(f"WALK-FORWARD ENSEMBLE ({N_FOLDS} folds)")
    print(f"{'='*60}")

    wf_weights, fold_weights, fold_aucs, mean_oof_auc = walkforward_weights(
        va_P, va_y, len(model_names), N_FOLDS)

    print(f"\nMean OOF AUC: {mean_oof_auc:.4f}")
    print(f"Final weights: {dict(zip(model_names, np.round(wf_weights, 4)))}")

    # ---- Evaluate on test ----
    wf_p_test = te_P @ wf_weights
    wf_test_auc = roc_auc_score(te_y, wf_p_test) if len(np.unique(te_y)) > 1 else 0.5
    wf_test_acc = ((wf_p_test > 0.5).astype(int) == te_y).mean()
    wf_test_std = wf_p_test.std()

    wf_p_val = va_P @ wf_weights
    wf_val_auc = roc_auc_score(va_y, wf_p_val) if len(np.unique(va_y)) > 1 else 0.5
    wf_val_acc = ((wf_p_val > 0.5).astype(int) == va_y).mean()

    # ---- Comparison baselines ----
    print(f"\n{'='*60}")
    print("FINAL COMPARISON (test set)")
    print(f"{'='*60}")

    base_rate = max(te_y.mean(), 1 - te_y.mean())

    baselines = {
        "majority_class": {"auc": 0.5, "acc": base_rate, "weights": "N/A"},
    }
    for j, m in enumerate(model_names):
        w = np.zeros(len(model_names))
        w[j] = 1.0
        p = te_P @ w
        baselines[f"{m}_only"] = {
            "auc": roc_auc_score(te_y, p) if len(np.unique(te_y)) > 1 else 0.5,
            "acc": ((p > 0.5).astype(int) == te_y).mean(),
            "weights": dict(zip(model_names, w.tolist())),
        }
    baselines["equal_blend"] = {
        "auc": roc_auc_score(te_y, te_P @ np.ones(len(model_names)) / len(model_names)),
        "acc": ((te_P @ np.ones(len(model_names)) / len(model_names) > 0.5).astype(int) == te_y).mean(),
        "weights": {m: round(1/len(model_names), 3) for m in model_names},
    }
    baselines["walkforward_v3"] = {
        "auc": wf_test_auc,
        "acc": wf_test_acc,
        "weights": dict(zip(model_names, wf_weights.round(4).tolist())),
    }

    print(f"{'Method':<20} {'Test AUC':>9} {'Test Acc':>9}")
    print(f"{'-'*40}")
    for name, bl in baselines.items():
        print(f"{name:<20} {bl['auc']:.4f}    {bl['acc']:.4f}")

    # Check: does ensemble beat lstm_only?
    lstm_test_auc = baselines["lstm_only"]["auc"]
    lstm_test_acc = baselines["lstm_only"]["acc"]
    
    print(f"\n--- Ensemble vs LSTM-only ---")
    print(f"  LSTM-only test AUC: {lstm_test_auc:.4f}, acc: {lstm_test_acc:.4f}")
    print(f"  Ensemble test AUC:  {wf_test_auc:.4f}, acc: {wf_test_acc:.4f}")
    if wf_test_auc > lstm_test_auc:
        print(f"  [OK] Ensemble BEATS lstm_only by {wf_test_auc - lstm_test_auc:+.4f} AUC")
    else:
        print(f"  [FAIL] Ensemble does NOT beat lstm_only (delta={wf_test_auc - lstm_test_auc:+.4f} AUC)")
        print(f"  -> Recommend using LSTM-only for predictions until base models improve")

    # ---- Save results ----
    output = {
        "models": model_names,
        "model_sources": model_files,
        "weights": dict(zip(model_names, wf_weights.tolist())),
        "walkforward": {
            "n_folds": N_FOLDS,
            "mean_oof_auc": float(mean_oof_auc),
            "fold_aucs": fold_aucs,
            "fold_weights": [w.tolist() for w in fold_weights],
        },
        "val": {"auc": float(wf_val_auc), "acc": float(wf_val_acc)},
        "test": {"auc": float(wf_test_auc), "acc": float(wf_test_acc), "p_std": float(wf_test_std)},
        "individual_test": {m: results[m] for m in model_names},
        "baselines_test": baselines,
        "ensemble_beats_lstm_only": bool(wf_test_auc > lstm_test_auc),
    }

    with open(os.path.join(ART, "ensemble_weights_v3.json"), "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nSaved -> {os.path.join(ART, 'ensemble_weights_v3.json')}")

    # CSV summary
    rows = []
    for name, bl in baselines.items():
        rows.append({"method": name, "test_auc": bl["auc"], "test_acc": bl["acc"],
                      "weights": str(bl.get("weights", ""))})
    pd.DataFrame(rows).to_csv(os.path.join(ART, "ensemble_results_v3.csv"), index=False)
    print(f"Saved -> {os.path.join(ART, 'ensemble_results_v3.csv')}")


if __name__ == "__main__":
    main()
