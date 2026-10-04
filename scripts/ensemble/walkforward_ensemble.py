"""Walk-forward ensemble weight selection with expanding windows."""

import sys
sys.stdout.reconfigure(line_buffering=True)

import json
import os

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.metrics import roc_auc_score

ART = os.path.join("ensemble", "artifacts")
N_FOLDS = 4  # Number of expanding window folds


def load_aligned_predictions(model_names):
    """Load predictions and align by timestamp."""
    preds = {}
    for m in model_names:
        with open(os.path.join(ART, f"{m}_preds.json")) as f:
            preds[m] = json.load(f)
    
    # Get common timestamps for each split
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
        y = np.array([preds[model_names[0]][split]["actual"][preds[model_names[0]][split]["timestamps"].index(t)]
                      for t in common])
        
        aligned[split] = {"P": P, "y": y, "timestamps": common}
    
    return aligned


def optimize_weights_auc(P, y, n_models):
    """Find weights that maximize AUC on given data."""
    def neg_auc(w):
        w = np.array(w)
        w = w / w.sum() if w.sum() > 0 else np.ones(n_models) / n_models
        p_ens = P @ w
        return -roc_auc_score(y, p_ens)
    
    # Initial guess: equal weights
    x0 = np.ones(n_models) / n_models
    bounds = [(0, 1) for _ in range(n_models)]
    constraints = {'type': 'eq', 'fun': lambda w: w.sum() - 1}
    
    result = minimize(neg_auc, x0, bounds=bounds, constraints=constraints, method='SLSQP')
    if result.success:
        return result.x / result.x.sum()
    else:
        return x0


def walkforward_ensemble(model_names, n_folds=N_FOLDS):
    """Run walk-forward validation on val set to select weights."""
    aligned = load_aligned_predictions(model_names)
    val_P = aligned["val"]["P"]
    val_y = aligned["val"]["y"]
    val_ts = aligned["val"]["timestamps"]
    n_models = len(model_names)
    
    n_val = len(val_y)
    fold_size = n_val // n_folds
    
    print(f"Walk-forward on val set: {n_val} samples, {n_folds} folds, fold_size={fold_size}")
    print(f"Val up rate: {val_y.mean():.4f}")
    
    fold_weights = []
    fold_aucs = []
    
    for fold in range(n_folds):
        # Expanding window: train on folds 0..fold, validate on fold+1
        if fold == n_folds - 1:
            # Last fold: use all but last fold_size for training, last fold_size for validation
            train_end = n_val - fold_size
        else:
            train_end = (fold + 1) * fold_size
        
        val_start = train_end
        val_end = min(train_end + fold_size, n_val)
        
        if val_start >= val_end:
            continue
        
        train_P = val_P[:train_end]
        train_y = val_y[:train_end]
        val_P_fold = val_P[val_start:val_end]
        val_y_fold = val_y[val_start:val_end]
        
        print(f"\nFold {fold+1}: train={len(train_y)}, val={len(val_y_fold)}")
        print(f"  Train period: {val_ts[0]} to {val_ts[train_end-1]}")
        print(f"  Val period:   {val_ts[val_start]} to {val_ts[val_end-1]}")
        print(f"  Train up rate: {train_y.mean():.4f}, Val up rate: {val_y_fold.mean():.4f}")
        
        # Optimize weights on training window
        w = optimize_weights_auc(train_P, train_y, n_models)
        
        # Evaluate on validation window
        val_auc = roc_auc_score(val_y_fold, val_P_fold @ w)
        val_acc = ((val_P_fold @ w > 0.5).astype(int) == val_y_fold).mean()
        
        fold_weights.append(w)
        fold_aucs.append(val_auc)
        
        print(f"  Weights: {dict(zip(model_names, np.round(w, 4)))}")
        print(f"  Val AUC: {val_auc:.4f}, Val Acc: {val_acc:.4f}")
        
        # Individual model performance on this val fold
        for i, m in enumerate(model_names):
            m_auc = roc_auc_score(val_y_fold, val_P_fold[:, i])
            m_acc = ((val_P_fold[:, i] > 0.5).astype(int) == val_y_fold).mean()
            print(f"    {m}: AUC={m_auc:.4f}, Acc={m_acc:.4f}")
    
    # Average weights across folds
    mean_weights = np.mean(fold_weights, axis=0)
    mean_weights = mean_weights / mean_weights.sum()
    mean_auc = np.mean(fold_aucs)
    
    print(f"\n{'='*50}")
    print(f"Walk-forward results:")
    print(f"  Mean OOF AUC: {mean_auc:.4f}")
    print(f"  Mean weights: {dict(zip(model_names, np.round(mean_weights, 4)))}")
    
    return mean_weights, fold_weights, fold_aucs


def evaluate_on_test(model_names, weights):
    """Evaluate ensemble with given weights on test set."""
    aligned = load_aligned_predictions(model_names)
    test_P = aligned["test"]["P"]
    test_y = aligned["test"]["y"]
    
    p_ens = test_P @ weights
    test_auc = roc_auc_score(test_y, p_ens)
    test_acc = ((p_ens > 0.5).astype(int) == test_y).mean()
    p_up_mean = p_ens.mean()
    p_up_std = p_ens.std()
    pred_up_rate = (p_ens > 0.5).mean()
    
    print(f"\nTest evaluation:")
    print(f"  Weights: {dict(zip(model_names, np.round(weights, 4)))}")
    print(f"  Test AUC: {test_auc:.4f}, Test Acc: {test_acc:.4f}")
    print(f"  p_up_mean: {p_up_mean:.4f}, p_up_std: {p_up_std:.4f}, pred_up_rate: {pred_up_rate:.4f}")
    print(f"  Actual up rate: {test_y.mean():.4f}")
    
    # Individual model performance
    for i, m in enumerate(model_names):
        m_auc = roc_auc_score(test_y, test_P[:, i])
        m_acc = ((test_P[:, i] > 0.5).astype(int) == test_y).mean()
        print(f"  {m}: AUC={m_auc:.4f}, Acc={m_acc:.4f}")
    
    return test_auc, test_acc


def main():
    # Model candidates (exclude ARIMA - it's useless)
    model_names = ["xgb", "lstm", "kronos"]
    
    print("="*60)
    print("WALK-FORWARD ENSEMBLE WEIGHT SELECTION")
    print("="*60)
    
    # Run walk-forward on val
    mean_weights, fold_weights, fold_aucs = walkforward_ensemble(model_names)
    
    # Evaluate on test
    test_auc, test_acc = evaluate_on_test(model_names, mean_weights)
    
    # Compare with baseline blends
    print(f"\n{'='*60}")
    print("COMPARISON WITH BASELINE BLENDS")
    print(f"{'='*60}")
    
    aligned = load_aligned_predictions(model_names)
    test_P = aligned["test"]["P"]
    test_y = aligned["test"]["y"]
    
    baselines = {
        "equal": np.ones(3) / 3,
        "xgb_only": np.array([1.0, 0.0, 0.0]),
        "lstm_only": np.array([0.0, 1.0, 0.0]),
        "kronos_only": np.array([0.0, 0.0, 1.0]),
        "xgb_lstm": np.array([0.5, 0.5, 0.0]),
        "walkforward": mean_weights,
    }
    
    print(f"{'Blend':<15} {'Test AUC':>8} {'Test Acc':>8} {'Weights'}")
    for name, w in baselines.items():
        p_ens = test_P @ w
        auc = roc_auc_score(test_y, p_ens)
        acc = ((p_ens > 0.5).astype(int) == test_y).mean()
        print(f"{name:<15} {auc:.4f}  {acc:.4f}  {dict(zip(model_names, np.round(w, 4)))}")
    
    # Save results
    results = {
        "model_names": model_names,
        "walkforward_weights": mean_weights.tolist(),
        "fold_weights": [w.tolist() for w in fold_weights],
        "fold_aucs": fold_aucs,
        "test_auc": test_auc,
        "test_acc": test_acc,
    }
    
    with open(os.path.join(ART, "ensemble_walkforward.json"), "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved -> {os.path.join(ART, 'ensemble_walkforward.json')}")


if __name__ == "__main__":
    main()