"""LSTM directional classifier (v3): fixes output collapse.

Changes from v1:
  (a) Early-stopping on val AUC (not accuracy) — accuracy is misleading with ~53% base rate
  (b) pos_weight in BCEWithLogitsLoss for class imbalance
  (c) Logs predicted-probability std per epoch to confirm model spreads outputs
  (d) Hyperparameter grid: seq_len ∈ {16,32,64}, hidden ∈ {32,64,128}
  (e) Learning rate schedule with ReduceLROnPlateau
  (f) Gradient clipping to prevent LSTM exploding gradients

Outputs: lstm_preds_v3.json (best config), lstm_v3_experiments.json (all configs)
"""

import sys
sys.stdout.reconfigure(line_buffering=True)

import json
import os
from itertools import product as iter_product

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score, log_loss
from sklearn.preprocessing import StandardScaler

ART = os.path.join("ensemble", "artifacts")
EPOCHS = 50
LR = 1e-3
BATCH = 64
SEED = 42
PATIENCE = 10


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
    """idx_range: absolute row indices. Sample at row i uses [i-seq_len, i]."""
    X, y = [], []
    for i in idx_range:
        if i - seq_len < 0:
            continue
        X.append(feat_scaled[i - seq_len:i + 1])
        y.append(labels[i])
    return np.asarray(X, np.float32), np.asarray(y, np.float32)


def train_single_config(X_all, y_all, pos, features, seq_len, hidden, verbose=True):
    """Train LSTM with a single config, return predictions + metrics."""
    torch.manual_seed(SEED)
    np.random.seed(SEED)

    X_tr, y_tr = make_sequences(X_all, y_all, pos["train"], seq_len)
    X_va, y_va = make_sequences(X_all, y_all, pos["val"], seq_len)

    if len(X_tr) == 0 or len(X_va) == 0:
        print(f"  SKIP: empty sequences (seq_len={seq_len} too large?)")
        return None

    # Class balance for pos_weight
    train_pos = y_tr.sum()
    train_neg = len(y_tr) - train_pos
    pw = train_neg / max(train_pos, 1)
    pos_weight = torch.tensor([pw])

    if verbose:
        print(f"  Train: {len(y_tr)} seqs, pos={train_pos:.0f}, neg={train_neg:.0f}, pos_weight={pw:.4f}")
        print(f"  Val: {len(y_va)} seqs")

    model = LSTMClassifier(len(features), hidden)
    opt = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, mode='max', factor=0.5, patience=4)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    X_tr_t = torch.from_numpy(X_tr)
    y_tr_t = torch.from_numpy(y_tr)
    X_va_t = torch.from_numpy(X_va)

    best_auc = -1.0
    best_state = None
    patience_counter = 0

    if verbose:
        print(f"  {'ep':>3}  {'loss':>7}  {'v_auc':>6}  {'v_acc':>6}  {'v_ll':>7}  {'p_mean':>6}  {'p_std':>7}  {'up_rt':>5}")

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
            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            opt.step()
            ep_loss += loss.item() * len(idx)

        model.eval()
        with torch.no_grad():
            logits_va = model(X_va_t)
            proba_va = torch.sigmoid(logits_va).numpy()
            pred_va = (proba_va > 0.5).astype(int)
            val_acc = (pred_va == y_va).mean()
            val_auc = roc_auc_score(y_va, proba_va) if len(np.unique(y_va)) > 1 else 0.5
            val_ll = log_loss(y_va, np.clip(proba_va, 1e-7, 1 - 1e-7))
            p_mean = proba_va.mean()
            p_std = proba_va.std()
            up_rate = (proba_va > 0.5).mean()

        scheduler.step(val_auc)

        if verbose and (epoch % 5 == 0 or epoch < 5 or epoch == EPOCHS - 1):
            print(f"  {epoch:3d}  {ep_loss/len(X_tr_t):.4f}  {val_auc:.4f}  {val_acc:.4f}  {val_ll:.5f}  {p_mean:.4f}  {p_std:.5f}  {up_rate:.3f}")

        if val_auc > best_auc:
            best_auc = val_auc
            patience_counter = 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            patience_counter += 1

        if patience_counter >= PATIENCE:
            if verbose:
                print(f"  Early stop at epoch {epoch} (best AUC={best_auc:.4f})")
            break

    if best_state is None:
        print("  WARNING: no best state saved, model may be garbage")
        return None

    model.load_state_dict(best_state)
    model.eval()

    # Collect predictions for val + test
    results = {}
    with torch.no_grad():
        for split in ["val", "test"]:
            X_s, y_s = make_sequences(X_all, y_all, pos[split], seq_len)
            if len(X_s) == 0:
                continue
            proba = torch.sigmoid(model(torch.from_numpy(X_s))).numpy()
            pred = (proba > 0.5).astype(int)
            actual = y_s.astype(int)
            acc = (pred == actual).mean()
            auc = roc_auc_score(actual, proba) if len(np.unique(actual)) > 1 else 0.5
            ll = log_loss(actual, np.clip(proba, 1e-7, 1 - 1e-7))

            results[split] = {
                "proba": proba,
                "pred": pred,
                "actual": actual,
                "acc": float(acc),
                "auc": float(auc),
                "logloss": float(ll),
                "p_mean": float(proba.mean()),
                "p_std": float(proba.std()),
                "pred_up_rate": float((proba > 0.5).mean()),
            }

            if verbose:
                print(f"  {split}: acc={acc:.4f} AUC={auc:.4f} logloss={ll:.4f} "
                      f"p_mean={proba.mean():.4f} p_std={proba.std():.5f} "
                      f"pred_up_rate={(proba > 0.5).mean():.3f}")

    return results


def main():
    print("=" * 60)
    print("LSTM v3: Fixing output collapse")
    print("=" * 60)

    df = pd.read_csv(os.path.join(ART, "features.csv"))
    features = ["ret_1", "ret_5", "ret_10", "log_vol_chg", "rsi_14", "macd",
                "bb_pos", "atr_14", "obv_slope", "sma_ratio", "rvol_5", "rvol_20"]

    tr_mask = df.split == "train"
    scaler = StandardScaler().fit(df.loc[tr_mask, features])
    X_all = scaler.transform(df[features]).astype(np.float32)
    y_all = df["target_up"].values.astype(np.float32)
    pos = {s: np.where(df["split"] == s)[0] for s in ["train", "val", "test"]}

    # Baseline stats
    for split in ["val", "test"]:
        up_rate = y_all[pos[split]].mean()
        majority_acc = max(up_rate, 1 - up_rate)
        print(f"{split}: n={len(pos[split])}, up_rate={up_rate:.4f}, majority_class_acc={majority_acc:.4f}")

    # ---- Hyperparameter grid ----
    configs = [
        {"seq_len": 32, "hidden": 64, "name": "default"},     # same as v1 but with AUC stopping
        {"seq_len": 16, "hidden": 64, "name": "seq16"},
        {"seq_len": 64, "hidden": 64, "name": "seq64"},
        {"seq_len": 32, "hidden": 32, "name": "hidden32"},
        {"seq_len": 32, "hidden": 128, "name": "hidden128"},
    ]

    all_experiments = {}
    best_config = None
    best_test_auc = -1.0

    for cfg in configs:
        print(f"\n{'='*50}")
        print(f"Config: {cfg['name']} (seq_len={cfg['seq_len']}, hidden={cfg['hidden']})")
        print(f"{'='*50}")

        results = train_single_config(X_all, y_all, pos, features,
                                       seq_len=cfg["seq_len"], hidden=cfg["hidden"])

        if results is None:
            continue

        all_experiments[cfg["name"]] = {
            "config": cfg,
            "val": {k: v for k, v in results.get("val", {}).items() if k not in ("proba", "pred", "actual")},
            "test": {k: v for k, v in results.get("test", {}).items() if k not in ("proba", "pred", "actual")},
        }

        # Track best by val AUC (not test — that would be leaking)
        val_auc = results.get("val", {}).get("auc", 0)
        test_auc = results.get("test", {}).get("auc", 0)
        if val_auc > best_test_auc:
            best_test_auc = val_auc
            best_config = cfg.copy()
            best_results = results

    # ---- Save best config predictions ----
    print(f"\n{'='*60}")
    print(f"BEST CONFIG (by val AUC): {best_config}")
    print(f"{'='*60}")

    if best_results:
        # Need to re-get timestamps
        timestamps = {}
        for split in ["val", "test"]:
            # Timestamps correspond to the indices that survived make_sequences
            split_idx = pos[split]
            keep_idx = split_idx[split_idx >= best_config["seq_len"]]
            timestamps[split] = [str(df["timestamps"].iloc[i])[:10] for i in keep_idx]

        out = {}
        for split in ["val", "test"]:
            if split not in best_results:
                continue
            r = best_results[split]
            out[split] = {
                "timestamps": timestamps[split][:len(r["proba"])],
                "p_up": r["proba"].round(6).tolist(),
                "pred": r["pred"].tolist(),
                "actual": r["actual"].tolist(),
            }

        with open(os.path.join(ART, "lstm_preds_v3.json"), "w") as f:
            json.dump(out, f)
        print(f"Saved -> {os.path.join(ART, 'lstm_preds_v3.json')}")

    # ---- Save experiment summary ----
    with open(os.path.join(ART, "lstm_v3_experiments.json"), "w") as f:
        json.dump(all_experiments, f, indent=2)
    print(f"Saved -> {os.path.join(ART, 'lstm_v3_experiments.json')}")

    # ---- Summary table ----
    print(f"\n{'='*80}")
    print(f"{'Config':<12} {'Val AUC':>8} {'Val Acc':>8} {'Test AUC':>9} {'Test Acc':>9} {'Test p_std':>10}")
    print(f"{'-'*80}")
    for name, exp in all_experiments.items():
        va = exp.get("val", {})
        te = exp.get("test", {})
        print(f"{name:<12} {va.get('auc',0):.4f}   {va.get('acc',0):.4f}   {te.get('auc',0):.4f}    {te.get('acc',0):.4f}    {te.get('p_std',0):.5f}")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
