"""LSTM directional classifier (PyTorch): sequences of scaled features -> P(up)."""

import json
import os

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.preprocessing import StandardScaler

ART = os.path.join("ensemble", "artifacts")
SEQ_LEN = 32
HIDDEN = 64
EPOCHS = 30
LR = 1e-3
BATCH = 64
SEED = 42


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
    torch.manual_seed(SEED)
    rng = np.random.default_rng(SEED)

    df = pd.read_csv(os.path.join(ART, "features.csv"), parse_dates=["timestamps"])
    features = ["ret_1", "ret_5", "ret_10", "log_vol_chg", "rsi_14", "macd",
                "bb_pos", "atr_14", "obv_slope", "sma_ratio", "rvol_5", "rvol_20"]

    # Scale using train statistics only (no leakage)
    tr_mask = df.split == "train"
    scaler = StandardScaler().fit(df.loc[tr_mask, features])
    X_all = scaler.transform(df[features]).astype(np.float32)
    y_all = df["target_up"].values.astype(np.float32)
    pos = {s: np.where(df["split"] == s)[0] for s in ["train", "val", "test"]}

    X_tr, y_tr = make_sequences(X_all, y_all, pos["train"])
    model = LSTMClassifier(len(features), HIDDEN)
    opt = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-4)
    loss_fn = nn.BCEWithLogitsLoss()

    X_tr_t = torch.from_numpy(X_tr)
    y_tr_t = torch.from_numpy(y_tr)

    best_val_acc, best_state, patience = 0.0, None, 0
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
            def eval_split(split):
                X_s, _ = make_sequences(X_all, y_all, pos[split])
                p = torch.sigmoid(model(torch.from_numpy(X_s))).numpy()
                return p

            pv = eval_split("val")
            acc_v = ((pv > 0.5).astype(int) == y_all[pos['val']]).mean()
        if acc_v > best_val_acc:
            best_val_acc, patience = acc_v, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            patience += 1
        if epoch % 5 == 0 or epoch == EPOCHS - 1:
            print(f"epoch {epoch:>2}: loss={ep_loss/len(X_tr_t):.4f} val_acc={acc_v:.4f}")
        if patience >= 6:
            print(f"early stop at epoch {epoch} (best val_acc={best_val_acc:.4f})")
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
            out[split] = {
                "timestamps": ts.dt.strftime("%Y-%m-%d").tolist(),
                "p_up": proba.round(6).tolist(),
                "pred": pred.tolist(),
                "actual": actual.tolist(),
            }
            print(f"LSTM {split}: accuracy={acc:.4f} | mean P(up)={proba.mean():.3f} | n={len(proba)}")

    with open(os.path.join(ART, "lstm_preds.json"), "w") as f:
        json.dump(out, f)
    print(f"Saved -> {os.path.join(ART, 'lstm_preds.json')}")


if __name__ == "__main__":
    main()
