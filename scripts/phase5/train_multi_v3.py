"""Phase5 multi-ticker pipeline v3: XGB + LSTM (fixed).

Changes from train_multi.py:
  (a) LSTM early-stopping on val AUC, not accuracy
  (b) pos_weight in BCEWithLogitsLoss for class imbalance
  (c) Logs p_up std/mean per epoch to detect output collapse
  (d) Gradient clipping (max_norm=1.0)
  (e) Increased patience (10 epochs) and max epochs (50)
  (f) Reports AUC alongside accuracy for all splits
  (g) Hyperparameter experiments for seq_len and hidden
"""

import json
import os

import numpy as np
import pandas as pd
import ta
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score, log_loss
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

FEATURES = ["ret_1", "ret_5", "ret_10", "log_vol_chg", "rsi_14", "macd",
            "bb_pos", "atr_14", "obv_slope", "sma_ratio", "rvol_5", "rvol_20"]
SEED = 42


def build_features(df):
    df = df.copy()
    df = df.sort_values("timestamps").reset_index(drop=True)
    df["ret_1"] = df["close"].pct_change()
    df["ret_5"] = df["close"].pct_change(5)
    df["ret_10"] = df["close"].pct_change(10)
    df["log_vol_chg"] = np.log(df["volume"] + 1).diff()
    df["rsi_14"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    df["macd"] = ta.trend.MACD(df["close"]).macd_diff()
    bb = ta.volatility.BollingerBands(df["close"], window=20)
    df["bb_pos"] = (df["close"] - bb.bollinger_mavg()) / bb.bollinger_wband()
    df["atr_14"] = ta.volatility.AverageTrueRange(
        df["high"], df["low"], df["close"], window=14).average_true_range() / df["close"]
    df["obv_slope"] = ta.volume.OnBalanceVolumeIndicator(
        df["close"], df["volume"]).on_balance_volume().diff(5)
    df["sma_ratio"] = df["close"] / ta.trend.SMAIndicator(df["close"], window=20).sma_indicator() - 1
    df["rvol_5"] = df["ret_1"].rolling(5).std()
    df["rvol_20"] = df["ret_1"].rolling(20).std()
    # 5-day-ahead label (native horizon for this phase) + 1-day for reference
    df["target_up_1d"] = (df["close"].shift(-1) > df["close"]).astype(int)
    df["fwd_ret_1d"] = df["close"].shift(-1) / df["close"] - 1
    df["sma_200"] = ta.trend.SMAIndicator(df["close"], window=200).sma_indicator()

    df = df.dropna().reset_index(drop=True)
    n = len(df)
    tr_end, va_end = int(n * 0.70), int(n * 0.85)
    df["split"] = "train"
    df.loc[tr_end:va_end - 1, "split"] = "val"
    df.loc[va_end:, "split"] = "test"
    return df


class LSTMClassifier(nn.Module):
    def __init__(self, n_features, hidden=64):
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden, num_layers=1, batch_first=True)
        self.head = nn.Sequential(nn.Linear(hidden, 16), nn.ReLU(), nn.Linear(16, 1))

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :]).squeeze(-1)


def make_sequences(X, y, idx, seq_len):
    keep = idx[idx >= seq_len]
    seqs = np.stack([X[i - seq_len:i + 1] for i in keep])
    return seqs.astype(np.float32), y[keep]


def train_models_for_ticker(ticker, data_dir="data/multi", seq_len=32, hidden=64):
    torch.manual_seed(SEED)
    np.random.seed(SEED)

    raw = pd.read_csv(os.path.join(data_dir, f"{ticker}.csv"))
    df = build_features(raw)
    scaler = StandardScaler().fit(df.loc[df.split == "train", FEATURES])
    X_all = scaler.transform(df[FEATURES]).astype(np.float32)
    y_all = df["target_up_1d"].values.astype(np.float32)
    pos = {s: np.where(df["split"] == s)[0] for s in ["train", "val", "test"]}

    # Class balance
    train_pos = y_all[pos["train"]].sum()
    train_neg = len(y_all[pos["train"]]) - train_pos
    pw = train_neg / max(train_pos, 1)
    print(f"  {ticker}: train pos={train_pos:.0f} neg={train_neg:.0f} pos_weight={pw:.3f}")

    # ---- XGBoost (unchanged) ----
    xgb = XGBClassifier(n_estimators=400, max_depth=3, learning_rate=0.05,
                        subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0,
                        min_child_weight=5, eval_metric="logloss",
                        random_state=SEED, tree_method="hist")
    tr = pos["train"]
    xgb.fit(X_all[tr], y_all[tr])

    # ---- LSTM (v3: AUC stopping + pos_weight + grad clip) ----
    X_tr, y_tr = make_sequences(X_all, y_all, pos["train"], seq_len)
    model = LSTMClassifier(len(FEATURES), hidden=hidden)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, mode='max', factor=0.5, patience=4)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(pw))
    X_t, y_t = torch.from_numpy(X_tr), torch.from_numpy(y_tr)

    best_auc, best_state, patience = 0.0, None, 0
    print(f"  {ticker}: LSTM training (seq_len={seq_len}, hidden={hidden})")

    for epoch in range(50):
        model.train()
        perm = torch.randperm(len(X_t))
        for i in range(0, len(perm), 64):
            idx = perm[i:i + 64]
            opt.zero_grad()
            loss = loss_fn(model(X_t[idx]), y_t[idx])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            opt.step()
        model.eval()
        with torch.no_grad():
            X_va, y_va = make_sequences(X_all, y_all, pos["val"], seq_len)
            logits = model(torch.from_numpy(X_va))
            pv = torch.sigmoid(logits).numpy()

            va_acc = ((pv > 0.5).astype(int) == y_va).mean()
            va_auc = roc_auc_score(y_va, pv) if len(np.unique(y_va)) > 1 else 0.5
            p_std = pv.std()
            p_mean = pv.mean()
            up_rate = (pv > 0.5).mean()

        scheduler.step(va_auc)

        if epoch % 10 == 0 or epoch < 3:
            print(f"    ep {epoch:2d}: val_auc={va_auc:.4f} acc={va_acc:.4f} "
                  f"p_mean={p_mean:.4f} p_std={p_std:.5f} up_rate={up_rate:.3f}")

        # Early stop on AUC (NOT accuracy)
        if va_auc > best_auc:
            best_auc, patience = va_auc, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            patience += 1
        if patience >= 10:
            print(f"    Early stop at epoch {epoch} (best AUC={best_auc:.4f})")
            break

    model.load_state_dict(best_state)
    model.eval()

    # ---- Collect val+test predictions ----
    out_frames = []
    with torch.no_grad():
        for split in ["val", "test"]:
            p_xgb = xgb.predict_proba(X_all[pos[split]])[:, 1]
            X_s, _ = make_sequences(X_all, y_all, pos[split], seq_len)
            logits = model(torch.from_numpy(X_s))
            p_lstm = torch.sigmoid(logits).numpy()

            print(f"  {ticker} {split}: LSTM p_mean={p_lstm.mean():.4f} p_std={p_lstm.std():.5f} "
                  f"up_rate={(p_lstm > 0.5).mean():.3f}")

            sub = pd.DataFrame({
                "timestamps": df["timestamps"].iloc[pos[split]].values,
                "split": split,
                "p_xgb": p_xgb,
                "p_lstm": p_lstm,
                "p_avg": (p_xgb + p_lstm) / 2,
                "actual_up": y_all[pos[split]].astype(int),
                "fwd_ret": df["fwd_ret_1d"].values[pos[split]],
                "close": df["close"].values[pos[split]],
                "sma_200": df["sma_200"].values[pos[split]],
                "above_sma200": (df["close"].values[pos[split]] > df["sma_200"].values[pos[split]]).astype(int),
            })
            out_frames.append(sub)

    preds = pd.concat(out_frames).reset_index(drop=True)
    acc = {}
    for split in ["val", "test"]:
        m = preds[preds.split == split]
        acc[f"xgb_{split}"] = float(((m.p_xgb > .5).astype(int) == m.actual_up).mean())
        acc[f"lstm_{split}"] = float(((m.p_lstm > .5).astype(int) == m.actual_up).mean())
        acc[f"avg_{split}"] = float(((m.p_avg > .5).astype(int) == m.actual_up).mean())
        # AUC
        acc[f"xgb_{split}_auc"] = float(roc_auc_score(m.actual_up, m.p_xgb) if m.actual_up.nunique() > 1 else 0.5)
        acc[f"lstm_{split}_auc"] = float(roc_auc_score(m.actual_up, m.p_lstm) if m.actual_up.nunique() > 1 else 0.5)
        acc[f"avg_{split}_auc"] = float(roc_auc_score(m.actual_up, m.p_avg) if m.actual_up.nunique() > 1 else 0.5)
        # p_std
        acc[f"lstm_{split}_p_std"] = float(m.p_lstm.std())
    return preds, acc


def run_experiments():
    """Run LSTM hyperparameter experiments across all tickers."""
    results = {}
    os.makedirs("phase5_artifacts", exist_ok=True)

    configs = [
        {"seq_len": 32, "hidden": 64, "name": "baseline"},
        {"seq_len": 16, "hidden": 64, "name": "seq16"},
        {"seq_len": 64, "hidden": 64, "name": "seq64"},
        {"seq_len": 32, "hidden": 32, "name": "hidden32"},
        {"seq_len": 32, "hidden": 128, "name": "hidden128"},
    ]

    all_results = {}
    for config in configs:
        print(f"\n{'=' * 60}")
        print(f"Config: {config['name']} (seq_len={config['seq_len']}, hidden={config['hidden']})")
        print(f"{'=' * 60}")

        config_results = {}
        for t in ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]:
            preds, acc = train_models_for_ticker(t, seq_len=config["seq_len"], hidden=config["hidden"])
            preds.to_csv(f"phase5_artifacts/preds_{t}_{config['name']}_v3.csv", index=False)
            config_results[t] = acc
            print(f"{t:>5}: LSTM val={acc['lstm_val']:.4f}({acc['lstm_val_auc']:.4f}) "
                  f"test={acc['lstm_test']:.4f}({acc['lstm_test_auc']:.4f}) "
                  f"p_std={acc['lstm_test_p_std']:.5f} | "
                  f"XGB val={acc['xgb_val']:.4f} test={acc['xgb_test']:.4f}")

        # Summary
        for metric in ["lstm_val", "lstm_test", "lstm_val_auc", "lstm_test_auc", "lstm_test_p_std"]:
            vals = [config_results[t][metric] for t in config_results]
            print(f"  Mean {metric}: {np.mean(vals):.4f}")
        all_results[config["name"]] = config_results

    with open("phase5_artifacts/ticker_accuracies_v3.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved -> phase5_artifacts/ticker_accuracies_v3.json")

    return all_results


if __name__ == "__main__":
    run_experiments()
