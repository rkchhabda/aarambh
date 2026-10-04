"""LSTM directional classifier (PyTorch): sequences of scaled features -> P(up).
Fixed version addressing output collapse:
- Early stopping on val AUC (not accuracy)
- pos_weight in BCEWithLogitsLoss for class imbalance
- Logs predicted-probability std per epoch
- Supports configurable SEQ_LEN and HIDDEN for capacity experiments
"""

import sys
sys.stdout.reconfigure(line_buffering=True)
print("SCRIPT STARTED", flush=True)

import json
import os

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

print("IMPORTS DONE", flush=True)

ART = os.path.join("ensemble", "artifacts")
SEQ_LEN = 32
HIDDEN = 64
EPOCHS = 30
LR = 1e-3
BATCH = 64
SEED = 42
EARLY_STOP_METRIC = "auc"  # "auc" or "logloss" or "acc"
PATIENCE = 8


class LSTMClassifier(nn.Module):
    def __init__(self, n_features, hidden):
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden, num_layers=1,
                            batch_first=True, dropout=0.0)
        self.head = nn.Sequential(nn.Linear(hidden, 16), nn.ReLU(), nn.Linear(16, 1))

    def forward(self, x):                       # x: (B, T, F)
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :]).squeeze(-1)


def make_sequences(feat_scaled, labels, idx_range):
    """idx_range: absolute row indices of rows that belong to this split.
    A sample at row i uses rows [i-SEQ_LEN, i] and label of row i."""
    X, y = [], []
    for i in idx_range:
        if i - SEQ_LEN < 0:
            continue
        X.append(feat_scaled[i - SEQ_LEN:i + 1])
        y.append(labels[i])
    return np.asarray(X, np.float32), np.asarray(y, np.float32)


def main():
    print("MAIN STARTED", flush=True)
    torch.manual_seed(SEED)
    rng = np.random.default_rng(SEED)

    print("READING CSV...", flush=True)
    df = pd.read_csv(os.path.join(ART, "features.csv"))
    print(f"CSV READ: {df.shape}", flush=True)
    # Keep timestamps as strings for output, no datetime conversion needed
    print("TIMESTAMPS KEPT AS STRINGS", flush=True)
    features = ["ret_1", "ret_5", "ret_10", "log_vol_chg", "rsi_14", "macd",
                "bb_pos", "atr_14", "obv_slope", "sma_ratio", "rvol_5", "rvol_20"]

    # Scale using train statistics only (no leakage)
    tr_mask = df.split == "train"
    scaler = StandardScaler().fit(df.loc[tr_mask, features])
    X_all = scaler.transform(df[features]).astype(np.float32)
    y_all = df["target_up"].values.astype(np.float32)
    pos = {s: np.where(df["split"] == s)[0] for s in ["train", "val", "test"]}

    X_tr, y_tr = make_sequences(X_all, y_all, pos["train"])
    X_va, y_va = make_sequences(X_all, y_all, pos["val"])

    # Class balance for pos_weight
    train_pos = y_tr.sum()
    train_neg = len(y_tr) - train_pos
    pos_weight = torch.tensor([train_neg / train_pos]) if train_pos > 0 else torch.tensor([1.0])
    print(f"Train class balance: pos={train_pos:.0f}, neg={train_neg:.0f}, pos_weight={pos_weight.item():.4f}")

    model = LSTMClassifier(len(features), HIDDEN)
    opt = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-4)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    X_tr_t = torch.from_numpy(X_tr)
    y_tr_t = torch.from_numpy(y_tr)
    X_va_t = torch.from_numpy(X_va)
    y_va_t = torch.from_numpy(y_va)

    best_val_metric = -1.0 if EARLY_STOP_METRIC == "auc" else float("inf")
    best_state, patience = None, 0

    print(f"Early stopping metric: {EARLY_STOP_METRIC}")
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

        if EARLY_STOP_METRIC == "auc":
            improved = val_auc > best_val_metric
            best_val_metric = max(best_val_metric, val_auc)
        elif EARLY_STOP_METRIC == "logloss":
            improved = val_logloss < best_val_metric
            best_val_metric = min(best_val_metric, val_logloss)
        else:  # accuracy
            improved = val_acc > best_val_metric
            best_val_metric = max(best_val_metric, val_acc)

        if improved:
            patience = 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            patience += 1

        if patience >= PATIENCE:
            print(f"early stop at epoch {epoch} (best val_{EARLY_STOP_METRIC}={best_val_metric:.4f})")
            break

    model.load_state_dict(best_state)
    model.eval()

    out = {}
    with torch.no_grad():
        for split in ["val", "test"]:
            X_s, _ = make_sequences(X_all, y_all, pos[split])
            proba = torch.sigmoid(model(torch.from_numpy(X_s))).numpy()
            ts = df["timestamps"].iloc[pos[split]]
            actual = y_all[pos[split]].astype(int)
            pred = (proba > 0.5).astype(int)
            acc = (pred == actual).mean()
            auc = roc_auc_score(actual, proba)
            out[split] = {
                "timestamps": [str(ts.iloc[i])[:10] for i in range(len(ts))],
                "p_up": proba.round(6).tolist(),
                "pred": pred.tolist(),
                "actual": actual.tolist(),
            }
            print(f"LSTM {split}: accuracy={acc:.4f} AUC={auc:.4f} | "
                  f"mean P(up)={proba.mean():.4f} std={proba.std():.4f} "
                  f"pred_up_rate={(proba > 0.5).mean():.4f} n={len(proba)}")

    with open(os.path.join(ART, "lstm_preds_v2.json"), "w") as f:
        json.dump(out, f)
    print(f"Saved -> {os.path.join(ART, 'lstm_preds_v2.json')}")


if __name__ == "__main__":
    main()