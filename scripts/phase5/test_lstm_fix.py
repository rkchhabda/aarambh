"""Quick test of LSTM fix on single ticker."""

import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

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
SEQ_LEN = 32
SEED = 42


def build_features(df):
    print("  build_features: start", flush=True)
    df = df.copy()
    print("  build_features: copy done", flush=True)
    # Keep timestamps as strings to avoid pd.to_datetime hang
    # df["timestamps"] = pd.to_datetime(df["timestamps"])
    df = df.sort_values("timestamps").reset_index(drop=True)
    print("  build_features: sort done", flush=True)
    df["ret_1"] = df["close"].pct_change()
    df["ret_5"] = df["close"].pct_change(5)
    df["ret_10"] = df["close"].pct_change(10)
    df["log_vol_chg"] = np.log(df["volume"] + 1).diff()
    print("  build_features: basic features done", flush=True)
    df["rsi_14"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    print("  build_features: rsi done", flush=True)
    df["macd"] = ta.trend.MACD(df["close"]).macd_diff()
    print("  build_features: macd done", flush=True)
    bb = ta.volatility.BollingerBands(df["close"], window=20)
    df["bb_pos"] = (df["close"] - bb.bollinger_mavg()) / bb.bollinger_wband()
    print("  build_features: bb done", flush=True)
    df["atr_14"] = ta.volatility.AverageTrueRange(
        df["high"], df["low"], df["close"], window=14).average_true_range() / df["close"]
    print("  build_features: atr done", flush=True)
    df["obv_slope"] = ta.volume.OnBalanceVolumeIndicator(
        df["close"], df["volume"]).on_balance_volume().diff(5)
    print("  build_features: obv done", flush=True)
    df["sma_ratio"] = df["close"] / ta.trend.SMAIndicator(df["close"], window=20).sma_indicator() - 1
    print("  build_features: sma done", flush=True)
    df["rvol_5"] = df["ret_1"].rolling(5).std()
    df["rvol_20"] = df["ret_1"].rolling(20).std()
    print("  build_features: rvol done", flush=True)
    df["target_up_1d"] = (df["close"].shift(-1) > df["close"]).astype(int)
    df["fwd_ret_1d"] = df["close"].shift(-1) / df["close"] - 1
    df["sma_200"] = ta.trend.SMAIndicator(df["close"], window=200).sma_indicator()
    print("  build_features: sma200 done", flush=True)

    df = df.dropna().reset_index(drop=True)
    print("  build_features: dropna done", flush=True)
    n = len(df)
    tr_end, va_end = int(n * 0.70), int(n * 0.85)
    df["split"] = "train"
    df.loc[tr_end:va_end - 1, "split"] = "val"
    df.loc[va_end:, "split"] = "test"
    print("  build_features: split done", flush=True)
    return df


class LSTMClassifier(nn.Module):
    def __init__(self, n_features, hidden=64):
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden, num_layers=1, batch_first=True)
        self.head = nn.Sequential(nn.Linear(hidden, 16), nn.ReLU(), nn.Linear(16, 1))

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :]).squeeze(-1)


def make_sequences(X, y, idx):
    keep = idx[idx >= SEQ_LEN]
    seqs = np.stack([X[i - SEQ_LEN:i + 1] for i in keep])
    return seqs.astype(np.float32), y[keep]


def main():
    print("main() started", flush=True)
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    print("seeds set", flush=True)

    ticker = "AAPL"
    data_dir = "data/multi"
    print("reading csv...", flush=True)
    raw = pd.read_csv(os.path.join(data_dir, f"{ticker}.csv"))
    print(f"csv read: {raw.shape}", flush=True)
    df = build_features(raw)
    print(f"features built: {df.shape}", flush=True)
    scaler = StandardScaler().fit(df.loc[df.split == "train", FEATURES])
    print("scaler fit", flush=True)
    X_all = scaler.transform(df[FEATURES]).astype(np.float32)
    y_all = df["target_up_1d"].values.astype(np.float32)
    pos = {s: np.where(df["split"] == s)[0] for s in ["train", "val", "test"]}
    print("positions computed", flush=True)

    # Class balance
    train_pos = y_all[pos["train"]].sum()
    train_neg = len(y_all[pos["train"]]) - train_pos
    pos_weight = train_neg / max(train_pos, 1)
    print(f"{ticker}: train pos={train_pos:.0f} neg={train_neg:.0f} pos_weight={pos_weight:.3f}", flush=True)
    print(f"  val class balance: pos={y_all[pos['val']].sum():.0f}/{len(pos['val'])}", flush=True)
    print(f"  test class balance: pos={y_all[pos['test']].sum():.0f}/{len(pos['test'])}", flush=True)

    # XGBoost (baseline)
    xgb = XGBClassifier(n_estimators=400, max_depth=3, learning_rate=0.05,
                        subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0,
                        min_child_weight=5, eval_metric="logloss",
                        random_state=SEED, tree_method="hist")
    tr = pos["train"]
    xgb.fit(X_all[tr], y_all[tr])

    # LSTM FIXED
    X_tr, y_tr = make_sequences(X_all, y_all, pos["train"])
    model = LSTMClassifier(len(FEATURES), hidden=64)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(pos_weight))
    X_t, y_t = torch.from_numpy(X_tr), torch.from_numpy(y_tr)
    
    best_auc, best_state, patience = 0.0, None, 0
    print(f"\nTraining LSTM (seq_len={SEQ_LEN}, hidden=64, pos_weight={pos_weight:.3f})", flush=True)
    print(f"  Train sequences: {len(X_tr)}, Val indices: {len(pos['val'])}, Test indices: {len(pos['test'])}", flush=True)
    print(f"  X_t shape: {X_t.shape}, y_t shape: {y_t.shape}", flush=True)
    for epoch in range(20):  # Reduced epochs for quick test
        model.train()
        perm = torch.randperm(len(X_t))
        print(f"  Epoch {epoch}: starting training loop...", flush=True)
        for i in range(0, len(perm), 128):  # Larger batch size
            idx = perm[i:i + 128]
            opt.zero_grad()
            loss = loss_fn(model(X_t[idx]), y_t[idx])
            loss.backward()
            opt.step()
        print(f"  Epoch {epoch}: training loop done, evaluating...", flush=True)
        model.eval()
        with torch.no_grad():
            X_va, y_va = make_sequences(X_all, y_all, pos["val"])
            logits = model(torch.from_numpy(X_va))
            pv = torch.sigmoid(logits).numpy()
            
            va_acc = ((pv > 0.5).astype(int) == y_va).mean()
            va_auc = roc_auc_score(y_va, pv) if len(np.unique(y_va)) > 1 else 0.5
            va_ll = log_loss(y_va, np.clip(pv, 1e-7, 1-1e-7))
            prob_std = pv.std()
            prob_mean = pv.mean()
            pred_up_rate = (pv > 0.5).mean()
            
            print(f"  epoch {epoch:2d}: acc={va_acc:.4f} auc={va_auc:.4f} ll={va_ll:.4f} "
                  f"mean={prob_mean:.4f} std={prob_std:.4f} up_rate={pred_up_rate:.4f}", flush=True)
            
            if va_auc > best_auc:
                best_auc, patience = va_auc, 0
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
            else:
                patience += 1
            if patience >= 5:
                print(f"  Early stop at epoch {epoch}, best AUC={best_auc:.4f}", flush=True)
                break
    
    model.load_state_dict(best_state)
    model.eval()
    
    # Evaluate on val and test
    with torch.no_grad():
        for split in ["val", "test"]:
            p_xgb = xgb.predict_proba(X_all[pos[split]])[:, 1]
            X_s, _ = make_sequences(X_all, y_all, pos[split])
            logits = model(torch.from_numpy(X_s))
            p_lstm = torch.sigmoid(logits).numpy()
            
            print(f"\n  {split}: LSTM prob_mean={p_lstm.mean():.4f} prob_std={p_lstm.std():.4f} up_rate={(p_lstm>0.5).mean():.4f}")
            print(f"  {split}: XGB  prob_mean={p_xgb.mean():.4f} prob_std={p_xgb.std():.4f} up_rate={(p_xgb>0.5).mean():.4f}")
            
            # AUC
            lstm_auc = roc_auc_score(y_all[pos[split]], p_lstm) if len(np.unique(y_all[pos[split]])) > 1 else 0.5
            xgb_auc = roc_auc_score(y_all[pos[split]], p_xgb) if len(np.unique(y_all[pos[split]])) > 1 else 0.5
            print(f"  {split}: LSTM AUC={lstm_auc:.4f} XGB AUC={xgb_auc:.4f}")
            
            # Accuracy
            lstm_acc = ((p_lstm > 0.5).astype(int) == y_all[pos[split]]).mean()
            xgb_acc = ((p_xgb > 0.5).astype(int) == y_all[pos[split]]).mean()
            print(f"  {split}: LSTM ACC={lstm_acc:.4f} XGB ACC={xgb_acc:.4f}")
    
    return model, xgb, scaler, df, pos, X_all, y_all


if __name__ == "__main__":
    main()