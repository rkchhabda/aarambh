"""Shared multi-ticker pipeline: features, chronological split, XGB + LSTM models."""

import json
import os

import numpy as np
import pandas as pd
import ta
import torch
import torch.nn as nn
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

FEATURES = ["ret_1", "ret_5", "ret_10", "log_vol_chg", "rsi_14", "macd",
            "bb_pos", "atr_14", "obv_slope", "sma_ratio", "rvol_5", "rvol_20"]
SEQ_LEN = 32
SEED = 42


def build_features(df):
    df = df.copy()
    df["timestamps"] = pd.to_datetime(df["timestamps"])
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


def make_sequences(X, y, idx):
    keep = idx[idx >= SEQ_LEN]
    seqs = np.stack([X[i - SEQ_LEN:i + 1] for i in keep])
    return seqs.astype(np.float32), y[keep]


def train_models_for_ticker(ticker, data_dir="data/multi"):
    torch.manual_seed(SEED)
    np.random.seed(SEED)

    raw = pd.read_csv(os.path.join(data_dir, f"{ticker}.csv"))
    df = build_features(raw)
    scaler = StandardScaler().fit(df.loc[df.split == "train", FEATURES])
    X_all = scaler.transform(df[FEATURES]).astype(np.float32)
    y_all = df["target_up_1d"].values.astype(np.float32)
    pos = {s: np.where(df["split"] == s)[0] for s in ["train", "val", "test"]}

    # ---- XGBoost ----
    xgb = XGBClassifier(n_estimators=400, max_depth=3, learning_rate=0.05,
                        subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0,
                        min_child_weight=5, eval_metric="logloss",
                        random_state=SEED, tree_method="hist")
    tr = pos["train"]
    xgb.fit(X_all[tr], y_all[tr])

    # ---- LSTM ----
    X_tr, y_tr = make_sequences(X_all, y_all, pos["train"])
    model = LSTMClassifier(len(FEATURES))
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    loss_fn = nn.BCEWithLogitsLoss()
    X_t, y_t = torch.from_numpy(X_tr), torch.from_numpy(y_tr)
    best_acc, best_state, patience = 0.0, None, 0
    for epoch in range(30):
        model.train()
        perm = torch.randperm(len(X_t))
        for i in range(0, len(perm), 64):
            idx = perm[i:i + 64]
            opt.zero_grad()
            loss = loss_fn(model(X_t[idx]), y_t[idx])
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            X_va, _ = make_sequences(X_all, y_all, pos["val"])
            pv = torch.sigmoid(model(torch.from_numpy(X_va))).numpy()
        acc = ((pv > 0.5).astype(int) == y_all[pos["val"]]).mean()
        if acc > best_acc:
            best_acc, patience = acc, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            patience += 1
        if patience >= 6:
            break
    model.load_state_dict(best_state)
    model.eval()

    # ---- Collect val+test predictions ----
    out_frames = []
    with torch.no_grad():
        for split in ["val", "test"]:
            p_xgb = xgb.predict_proba(X_all[pos[split]])[:, 1]
            X_s, _ = make_sequences(X_all, y_all, pos[split])
            p_lstm = torch.sigmoid(model(torch.from_numpy(X_s))).numpy()
            sub = pd.DataFrame({
                "timestamps": df["timestamps"].iloc[pos[split]].dt.strftime("%Y-%m-%d").values,
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
    return preds, acc


if __name__ == "__main__":
    results = {}
    os.makedirs("phase5_artifacts", exist_ok=True)
    for t in ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]:
        preds, acc = train_models_for_ticker(t)
        preds.to_csv(f"phase5_artifacts/preds_{t}.csv", index=False)
        results[t] = acc
        print(f"{t:>5}: LSTM val={acc['lstm_val']:.4f} test={acc['lstm_test']:.4f} | "
              f"XGB val={acc['xgb_val']:.4f} test={acc['xgb_test']:.4f} | "
              f"AVG val={acc['avg_val']:.4f} test={acc['avg_test']:.4f}")

    lstm_val = np.mean([results[t]["lstm_val"] for t in results])
    lstm_test = np.mean([results[t]["lstm_test"] for t in results])
    avg_val = np.mean([results[t]["avg_val"] for t in results])
    avg_test = np.mean([results[t]["avg_test"] for t in results])
    print(f"\nMean across {len(results)} tickers:")
    print(f"  LSTM val accuracy: {lstm_val:.4f} | test: {lstm_test:.4f}")
    print(f"  AVG-blend val accuracy: {avg_val:.4f} | test: {avg_test:.4f}")
    with open("phase5_artifacts/ticker_accuracies.json", "w") as f:
        json.dump(results, f, indent=2)
