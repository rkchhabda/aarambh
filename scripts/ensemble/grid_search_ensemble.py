"""Grid search for ensemble weights."""

import sys
sys.stdout.reconfigure(line_buffering=True)

import json
import os

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ART = os.path.join("ensemble", "artifacts")


def load_aligned(model_names):
    preds = {}
    for m in model_names:
        with open(os.path.join(ART, f"{m}_preds.json")) as f:
            preds[m] = json.load(f)
    
    aligned = {}
    for split in ["val", "test"]:
        common = set(preds[model_names[0]][split]["timestamps"])
        for m in model_names[1:]:
            common &= set(preds[m][split]["timestamps"])
        common = sorted(common)
        
        P = np.array([[preds[m][split]["p_up"][preds[m][split]["timestamps"].index(t)]
                       for t in common] for m in model_names]).T
        y = np.array([preds[model_names[0]][split]["actual"][preds[model_names[0]][split]["timestamps"].index(t)]
                      for t in common])
        
        aligned[split] = {"P": P, "y": y, "timestamps": common}
    
    return aligned


def grid_search_weights(P, y, n_models, steps=21):
    """Grid search over simplex for best AUC weights."""
    best_auc = -1
    best_w = None
    
    # Generate weight combinations on simplex
    if n_models == 2:
        for i in range(steps + 1):
            w1 = i / steps
            w2 = 1 - w1
            w = np.array([w1, w2])
            p_ens = P @ w
            auc = roc_auc_score(y, p_ens)
            if auc > best_auc:
                best_auc = auc
                best_w = w
    elif n_models == 3:
        for i in range(steps + 1):
            for j in range(steps + 1 - i):
                w1 = i / steps
                w2 = j / steps
                w3 = 1 - w1 - w2
                if w3 < 0:
                    continue
                w = np.array([w1, w2, w3])
                p_ens = P @ w
                auc = roc_auc_score(y, p_ens)
                if auc > best_auc:
                    best_auc = auc
                    best_w = w
    else:
        raise ValueError("Only 2 or 3 models supported")
    
    return best_w, best_auc


def main():
    # Test different model combinations
    combinations = [
        (["xgb", "lstm"], "XGB+LSTM"),
        (["xgb", "lstm", "kronos"], "XGB+LSTM+Kronos"),
        (["xgb", "kronos"], "XGB+Kronos"),
        (["lstm", "kronos"], "LSTM+Kronos"),
    ]
    
    for model_names, label in combinations:
        print(f"\n{'='*60}")
        print(f"GRID SEARCH: {label}")
        print(f"{'='*60}")
        
        aligned = load_aligned(model_names)
        val_P = aligned["val"]["P"]
        val_y = aligned["val"]["y"]
        test_P = aligned["test"]["P"]
        test_y = aligned["test"]["y"]
        
        print(f"Val: n={len(val_y)}, up_rate={val_y.mean():.4f}")
        print(f"Test: n={len(test_y)}, up_rate={test_y.mean():.4f}")
        
        # Grid search on val
        best_w, best_val_auc = grid_search_weights(val_P, val_y, len(model_names), steps=20)
        print(f"\nBest val weights: {dict(zip(model_names, np.round(best_w, 4)))}")
        print(f"Best val AUC: {best_val_auc:.4f}")
        
        # Evaluate on test
        test_auc = roc_auc_score(test_y, test_P @ best_w)
        test_acc = ((test_P @ best_w > 0.5).astype(int) == test_y).mean()
        print(f"Test AUC: {test_auc:.4f}, Test Acc: {test_acc:.4f}")
        
        # Individual model test AUC
        for i, m in enumerate(model_names):
            m_auc = roc_auc_score(test_y, test_P[:, i])
            m_acc = ((test_P[:, i] > 0.5).astype(int) == test_y).mean()
            print(f"  {m}: AUC={m_auc:.4f}, Acc={m_acc:.4f}")
    
    # Also evaluate LSTM_only as baseline
    print(f"\n{'='*60}")
    print("BASELINE: LSTM_ONLY")
    print(f"{'='*60}")
    with open(os.path.join(ART, "lstm_preds.json")) as f:
        lstm = json.load(f)
    for split in ["val", "test"]:
        p = np.array(lstm[split]["p_up"])
        actual = np.array(lstm[split]["actual"])
        auc = roc_auc_score(actual, p)
        acc = ((p > 0.5).astype(int) == actual).mean()
        print(f"LSTM {split}: AUC={auc:.4f}, Acc={acc:.4f}")


if __name__ == "__main__":
    main()