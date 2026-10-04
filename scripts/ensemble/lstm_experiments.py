"""Comprehensive LSTM experiments to find working configuration."""

import sys
sys.stdout.reconfigure(line_buffering=True)

import json
import os

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

ART = os.path.join("ensemble", "artifacts")
EPOCHS = 30
LR = 1e-3
BATCH = 64
SEED = 42
PATIENCE = 8


class LSTMClassifier(nn.Module):
    def __init__(self, n_features, hidden):
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden, num_layers=1,
                            batch_first=True, dropout=0.0)
        self.head = nn.Sequential(nn.Linear(hidden, 16), nn.ReLU(), nn.Linear(16, 1))

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :]).squeeze(-1)


def make_sequences(feat_scaled, labels, idx_range, seq_len):
    X, y = [], []
    for i in idx_range:
        if i - seq_len < 0:
            continue
        X.append(feat_scaled[i - seq_len:i + 1])
        y.append(labels[i])
    return np.asarray(X, np.float32), np.asarray(y, np.float32)


def run_experiment(seq_len, hidden, early_stop_metric, label):
    print(f"\n{'='*60}")
    print(f"EXPERIMENT: {label} (seq_len={seq_len}, hidden={hidden}, metric={early_stop_metric})")
    print(f"{'='*60}")

    torch.manual_seed(SEED)
    np.random.seed(SEED)

    df = pd.read_csv(os.path.join(ART, "features.csv"))
    features = ["ret_1", "ret_5", "ret_10", "log_vol_chg", "rsi_14", "macd",
                "bb_pos", "atr_14", "obv_slope", "sma_ratio", "rvol_5", "rvol_20"]

    tr_mask = df.split == "train"
    scaler = StandardScaler().fit(df.loc[tr_mask, features])
    X_all = scaler.transform(df[features]).astype(np.float32)
    y_all = df["target_up"].values.astype(np.float32)
    pos = {s: np.where(df["split"] == s)[0] for s in ["train", "val", "test"]}

    X_tr, y_tr = make_sequences(X_all, y_all, pos["train"], seq_len)
    X_va, y_va = make_sequences(X_all, y_all, pos["val"], seq_len)

    train_pos = y_tr.sum()
    train_neg = len(y_tr) - train_pos
    pos_weight = torch.tensor([train_neg / train_pos]) if train_pos > 0 else torch.tensor([1.0])
    print(f"Train class balance: pos={train_pos:.0f}, neg={train_neg:.0f}, pos_weight={pos_weight.item():.4f}")

    model = LSTMClassifier(len(features), hidden)
    opt = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-4)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    X_tr_t = torch.from_numpy(X_tr)
    y_tr_t = torch.from_numpy(y_tr)
    X_va_t = torch.from_numpy(X_va)
    y_va_t = torch.from_numpy(y_va)

    best_val_metric = -1.0 if early_stop_metric == "auc" else float("inf")
    best_state, patience = None, 0

    print(f"{'epoch':>4}  {'loss':>8}  {'val_auc':>7}  {'val_acc':>7}  {'p_up_mean':>9}  {'p_up_std':>9}")

    for epoch in range(EPOCHS):
        model.train()
        perm = torch.randperm(len(X_tr_t))
        ep_loss = 0.0
        for i in range(0, len(perm), BATCH):
            idx = perm[i:i + BATCH]
            opt.zero_grad()
            logits = model(X_tr_t[idx])
            loss = loss_fn(logits, y_tr_t[idx])
            loss.backward()
            opt.step()
            ep_loss += loss.item() * len(idx)

        model.eval()
        with torch.no_grad():
            logits_va = model(X_va_t)
            proba_va = torch.sigmoid(logits_va).numpy()
            pred_va = (proba_va > 0.5).astype(int)
            val_acc = (pred_va == y_va).mean()
            val_auc = roc_auc_score(y_va, proba_va)
            val_logloss = -np.mean(y_va * np.log(proba_va + 1e-15) + (1 - y_va) * np.log(1 - proba_va + 1e-15))
            p_up_mean = proba_va.mean()
            p_up_std = proba_va.std()

        print(f"{epoch:>4}  {ep_loss/len(X_tr_t):.4f}  {val_auc:.4f}  {val_acc:.4f}  {p_up_mean:.4f}  {p_up_std:.4f}")

        if early_stop_metric == "auc":
            improved = val_auc > best_val_metric
            best_val_metric = max(best_val_metric, val_auc)
        elif early_stop_metric == "logloss":
            improved = val_logloss < best_val_metric
            best_val_metric = min(best_val_metric, val_logloss)
        else:
            improved = val_acc > best_val_metric
            best_val_metric = max(best_val_metric, val_acc)

        if improved:
            patience = 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            patience += 1

        if patience >= PATIENCE:
            print(f"early stop at epoch {epoch} (best val_{early_stop_metric}={best_val_metric:.4f})")
            break

    model.load_state_dict(best_state)
    model.eval()

    results = {}
    with torch.no_grad():
        for split in ["val", "test"]:
            X_s, _ = make_sequences(X_all, y_all, pos[split], seq_len)
            proba = torch.sigmoid(model(torch.from_numpy(X_s))).numpy()
            actual = y_all[pos[split]].astype(int)
            pred = (proba > 0.5).astype(int)
            acc = (pred == actual).mean()
            auc = roc_auc_score(actual, proba)
            results[split] = {"acc": acc, "auc": auc, "p_up_mean": proba.mean(), "p_up_std": proba.std(), "pred_up_rate": (proba > 0.5).mean()}
            print(f"LSTM {split}: accuracy={acc:.4f} AUC={auc:.4f} | mean P(up)={proba.mean():.4f} std={proba.std():.4f} pred_up_rate={(proba > 0.5).mean():.4f} n={len(proba)}")

    return results


def main():
    # Load data once to check class balance
    df = pd.read_csv(os.path.join(ART, "features.csv"))
    features = ["ret_1", "ret_5", "ret_10", "log_vol_chg", "rsi_14", "macd",
                "bb_pos", "atr_14", "obv_slope", "sma_ratio", "rvol_5", "rvol_20"]
    tr_mask = df.split == "train"
    print(f"Train samples: {tr_mask.sum()}, Val: {(df.split=='val').sum()}, Test: {(df.split=='test').sum()}")

    # Grid of experiments
    configs = [
        # (seq_len, hidden, metric, label)
        (32, 64, "auc", "baseline_auc"),
        (32, 64, "logloss", "baseline_logloss"),
        (32, 64, "acc", "baseline_acc"),
        (16, 64, "auc", "seq16_auc"),
        (16, 64, "logloss", "seq16_logloss"),
        (64, 64, "auc", "seq64_auc"),
        (64, 64, "logloss", "seq64_logloss"),
        (32, 32, "auc", "hidden32_auc"),
        (32, 32, "logloss", "hidden32_logloss"),
        (32, 128, "auc", "hidden128_auc"),
        (32, 128, "logloss", "hidden128_logloss"),
    ]

    all_results = {}
    for seq_len, hidden, metric, label in configs:
        try:
            results = run_experiment(seq_len, hidden, metric, label)
            all_results[label] = results
        except Exception as e:
            print(f"ERROR in {label}: {e}")
            all_results[label] = {"error": str(e)}

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"{'config':<20} {'val_auc':>7} {'test_auc':>7} {'val_std':>8} {'test_std':>8} {'val_pred_up':>10} {'test_pred_up':>10}")
    for label, res in all_results.items():
        if "error" in res:
            print(f"{label:<20} ERROR: {res['error']}")
        else:
            print(f"{label:<20} {res['val']['auc']:.4f}  {res['test']['auc']:.4f}  {res['val']['p_up_std']:.4f}  {res['test']['p_up_std']:.4f}  {res['val']['pred_up_rate']:.4f}  {res['test']['pred_up_rate']:.4f}")

    with open(os.path.join(ART, "lstm_experiments_v2.json"), "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved -> {os.path.join(ART, 'lstm_experiments_v2.json')}")


if __name__ == "__main__":
    main()