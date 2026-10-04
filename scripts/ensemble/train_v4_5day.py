"""LSTM + XGB v4: 5-day target horizon to match production.

Key change: target_up is now 5-day-ahead (close[t+5] > close[t]),
matching the production service's prediction horizon.

Also includes all v3 fixes:
  - LSTM early-stop on val AUC
  - pos_weight for class imbalance
  - Gradient clipping
  - LR scheduling
  - Full metric reporting (AUC, acc, p_std)

Outputs: lstm_preds_v4.json, xgb_preds_v4.json, v4_results.json
"""

import sys
sys.stdout.reconfigure(line_buffering=True)

import json
import os

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score, log_loss
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

ART = os.path.join("ensemble", "artifacts")
SEQ_LEN = 16  # Best from v3 experiments
HIDDEN = 64
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


def make_sequences(feat_scaled, labels, idx_range, seq_len=SEQ_LEN):
    X, y = [], []
    for i in idx_range:
        if i - seq_len < 0:
            continue
        X.append(feat_scaled[i - seq_len:i + 1])
        y.append(labels[i])
    return np.asarray(X, np.float32), np.asarray(y, np.float32)


def main():
    print("=" * 60)
    print("v4: 5-day target horizon (matching production)")
    print("=" * 60)

    # Check if 5d features exist, build if not
    features_5d_path = os.path.join(ART, "features_5d.csv")
    if not os.path.exists(features_5d_path):
        print("Building 5-day feature dataset...")
        import subprocess
        subprocess.run([sys.executable, "scripts/ensemble/build_dataset_5d.py"], check=True)

    df = pd.read_csv(features_5d_path)
    print(f"Dataset: {len(df)} rows")

    features = ["ret_1", "ret_5", "ret_10", "log_vol_chg", "rsi_14", "macd",
                "bb_pos", "atr_14", "obv_slope", "sma_ratio", "rvol_5", "rvol_20"]

    # Scale using train stats only
    tr_mask = df.split == "train"
    scaler = StandardScaler().fit(df.loc[tr_mask, features])
    X_all = scaler.transform(df[features]).astype(np.float32)
    y_all = df["target_up"].values.astype(np.float32)
    pos = {s: np.where(df["split"] == s)[0] for s in ["train", "val", "test"]}

    # Baseline stats
    for split in ["train", "val", "test"]:
        up_rate = y_all[pos[split]].mean()
        majority_acc = max(up_rate, 1 - up_rate)
        print(f"  {split}: n={len(pos[split])}, up_rate_5d={up_rate:.4f}, majority_acc={majority_acc:.4f}")

    # ============ XGBoost ============
    print(f"\n{'='*50}")
    print("XGB on 5-day target")
    print(f"{'='*50}")

    torch.manual_seed(SEED)
    np.random.seed(SEED)

    xgb = XGBClassifier(n_estimators=400, max_depth=3, learning_rate=0.05,
                        subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0,
                        min_child_weight=5, eval_metric="logloss",
                        random_state=SEED, tree_method="hist")
    xgb.fit(X_all[pos["train"]], y_all[pos["train"]])

    xgb_results = {}
    xgb_out = {}
    for split in ["val", "test"]:
        p = xgb.predict_proba(X_all[pos[split]])[:, 1]
        pred = (p > 0.5).astype(int)
        actual = y_all[pos[split]].astype(int)
        acc = (pred == actual).mean()
        auc = roc_auc_score(actual, p) if len(np.unique(actual)) > 1 else 0.5
        ll = log_loss(actual, np.clip(p, 1e-7, 1 - 1e-7))
        p_std = p.std()
        up_rate = (p > 0.5).mean()
        xgb_results[split] = {"acc": acc, "auc": auc, "logloss": ll, "p_std": p_std, "up_rate": up_rate}
        print(f"  XGB {split}: acc={acc:.4f} AUC={auc:.4f} p_std={p_std:.4f} up_rate={up_rate:.3f}")

        # Keep indices that will be in common with LSTM
        split_idx = pos[split]
        xgb_out[split] = {
            "timestamps": [str(df["timestamps"].iloc[i])[:10] for i in split_idx],
            "p_up": p.round(6).tolist(),
            "pred": pred.tolist(),
            "actual": actual.tolist(),
        }

    with open(os.path.join(ART, "xgb_preds_v4.json"), "w") as f:
        json.dump(xgb_out, f)
    print(f"  Saved -> xgb_preds_v4.json")

    # Feature importance
    imp = xgb.feature_importances_
    top_feats = sorted(zip(features, imp), key=lambda x: -x[1])
    print(f"\n  XGB Feature Importance (top 5):")
    for fname, fval in top_feats[:5]:
        print(f"    {fname}: {fval:.4f}")

    # ============ LSTM ============
    print(f"\n{'='*50}")
    print(f"LSTM on 5-day target (seq_len={SEQ_LEN}, hidden={HIDDEN})")
    print(f"{'='*50}")

    X_tr, y_tr = make_sequences(X_all, y_all, pos["train"])
    X_va, y_va = make_sequences(X_all, y_all, pos["val"])

    # Class balance
    train_pos = y_tr.sum()
    train_neg = len(y_tr) - train_pos
    pw = train_neg / max(train_pos, 1)
    pos_weight = torch.tensor([pw])
    print(f"  Train: {len(y_tr)} seqs, pos={train_pos:.0f}, neg={train_neg:.0f}, pos_weight={pw:.4f}")

    model = LSTMClassifier(len(features), HIDDEN)
    opt = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, mode='max', factor=0.5, patience=4)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    X_tr_t = torch.from_numpy(X_tr)
    y_tr_t = torch.from_numpy(y_tr)
    X_va_t = torch.from_numpy(X_va)

    best_auc = -1.0
    best_state = None
    patience_counter = 0

    print(f"  {'ep':>3}  {'loss':>7}  {'v_auc':>6}  {'v_acc':>6}  {'p_mean':>6}  {'p_std':>7}  {'up_rt':>5}")

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
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            opt.step()
            ep_loss += loss.item() * len(idx)

        model.eval()
        with torch.no_grad():
            logits_va = model(X_va_t)
            proba_va = torch.sigmoid(logits_va).numpy()
            val_acc = ((proba_va > 0.5).astype(int) == y_va).mean()
            val_auc = roc_auc_score(y_va, proba_va) if len(np.unique(y_va)) > 1 else 0.5
            p_mean = proba_va.mean()
            p_std = proba_va.std()
            up_rate = (proba_va > 0.5).mean()

        scheduler.step(val_auc)

        if epoch % 5 == 0 or epoch < 5 or epoch == EPOCHS - 1:
            print(f"  {epoch:3d}  {ep_loss/len(X_tr_t):.4f}  {val_auc:.4f}  {val_acc:.4f}  {p_mean:.4f}  {p_std:.5f}  {up_rate:.3f}")

        if val_auc > best_auc:
            best_auc = val_auc
            patience_counter = 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            patience_counter += 1

        if patience_counter >= PATIENCE:
            print(f"  Early stop at epoch {epoch} (best AUC={best_auc:.4f})")
            break

    model.load_state_dict(best_state)
    model.eval()

    # Collect predictions
    lstm_results = {}
    lstm_out = {}
    with torch.no_grad():
        for split in ["val", "test"]:
            X_s, y_s = make_sequences(X_all, y_all, pos[split])
            proba = torch.sigmoid(model(torch.from_numpy(X_s))).numpy()
            pred = (proba > 0.5).astype(int)
            actual = y_s.astype(int)
            acc = (pred == actual).mean()
            auc = roc_auc_score(actual, proba) if len(np.unique(actual)) > 1 else 0.5
            ll = log_loss(actual, np.clip(proba, 1e-7, 1 - 1e-7))
            p_std_val = proba.std()

            lstm_results[split] = {"acc": acc, "auc": auc, "logloss": ll,
                                    "p_std": float(p_std_val), "p_mean": float(proba.mean())}

            # Get timestamps for sequences
            split_idx = pos[split]
            keep_idx = split_idx[split_idx >= SEQ_LEN]
            ts = [str(df["timestamps"].iloc[i])[:10] for i in keep_idx[:len(proba)]]

            lstm_out[split] = {
                "timestamps": ts,
                "p_up": proba.round(6).tolist(),
                "pred": pred.tolist(),
                "actual": actual.tolist(),
            }

            print(f"  LSTM {split}: acc={acc:.4f} AUC={auc:.4f} logloss={ll:.4f} "
                  f"p_mean={proba.mean():.4f} p_std={p_std_val:.5f} up_rate={(proba > 0.5).mean():.3f}")

    with open(os.path.join(ART, "lstm_preds_v4.json"), "w") as f:
        json.dump(lstm_out, f)
    print(f"  Saved -> lstm_preds_v4.json")

    # ============ Ensemble: XGB + LSTM (2-model, no Kronos/ARIMA) ============
    print(f"\n{'='*50}")
    print("Simple XGB+LSTM ensemble (equal blend)")
    print(f"{'='*50}")

    # Align by timestamps
    for split in ["val", "test"]:
        common_ts = sorted(set(xgb_out[split]["timestamps"]) & set(lstm_out[split]["timestamps"]))
        if not common_ts:
            print(f"  {split}: no common timestamps!")
            continue

        xgb_idx = [xgb_out[split]["timestamps"].index(t) for t in common_ts]
        lstm_idx = [lstm_out[split]["timestamps"].index(t) for t in common_ts]

        p_xgb = np.array([xgb_out[split]["p_up"][i] for i in xgb_idx])
        p_lstm = np.array([lstm_out[split]["p_up"][i] for i in lstm_idx])
        actual = np.array([xgb_out[split]["actual"][i] for i in xgb_idx])

        p_blend = (p_xgb + p_lstm) / 2

        blend_auc = roc_auc_score(actual, p_blend) if len(np.unique(actual)) > 1 else 0.5
        blend_acc = ((p_blend > 0.5).astype(int) == actual).mean()
        xgb_auc = roc_auc_score(actual, p_xgb) if len(np.unique(actual)) > 1 else 0.5
        xgb_acc = ((p_xgb > 0.5).astype(int) == actual).mean()
        lstm_auc = roc_auc_score(actual, p_lstm) if len(np.unique(actual)) > 1 else 0.5
        lstm_acc = ((p_lstm > 0.5).astype(int) == actual).mean()
        majority_acc = max(actual.mean(), 1 - actual.mean())

        print(f"\n  {split} ({len(common_ts)} common days):")
        print(f"    Majority class:  acc={majority_acc:.4f}")
        print(f"    XGB alone:       AUC={xgb_auc:.4f}  acc={xgb_acc:.4f}")
        print(f"    LSTM alone:      AUC={lstm_auc:.4f}  acc={lstm_acc:.4f}")
        print(f"    Equal blend:     AUC={blend_auc:.4f}  acc={blend_acc:.4f}")

    # ============ Comparison: 1-day vs 5-day ============
    print(f"\n{'='*60}")
    print("COMPARISON: 1-day target (v3) vs 5-day target (v4)")
    print(f"{'='*60}")

    # Load v3 results for comparison
    v3_lstm_path = os.path.join(ART, "lstm_preds_v3.json")
    if os.path.exists(v3_lstm_path):
        with open(v3_lstm_path) as f:
            v3_lstm = json.load(f)
        for split in ["val", "test"]:
            v3_p = np.array(v3_lstm[split]["p_up"])
            v3_actual = np.array(v3_lstm[split]["actual"])
            v3_auc = roc_auc_score(v3_actual, v3_p) if len(np.unique(v3_actual)) > 1 else 0.5
            v3_acc = ((v3_p > 0.5).astype(int) == v3_actual).mean()
            v3_std = v3_p.std()

            v4_r = lstm_results.get(split, {})
            print(f"  {split}:")
            print(f"    v3 (1-day): AUC={v3_auc:.4f} acc={v3_acc:.4f} p_std={v3_std:.5f}")
            print(f"    v4 (5-day): AUC={v4_r.get('auc', 0):.4f} acc={v4_r.get('acc', 0):.4f} p_std={v4_r.get('p_std', 0):.5f}")

    # Save full results
    results = {
        "target": "5-day (close[t+5] > close[t])",
        "lstm_config": {"seq_len": SEQ_LEN, "hidden": HIDDEN},
        "xgb": {s: {k: float(v) for k, v in xgb_results[s].items()} for s in xgb_results},
        "lstm": {s: {k: float(v) for k, v in lstm_results[s].items()} for s in lstm_results},
    }
    with open(os.path.join(ART, "v4_results.json"), "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved -> v4_results.json")


if __name__ == "__main__":
    main()
