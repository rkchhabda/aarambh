"""Rolling 1-day-ahead Kronos forecasts (NEXT DAY horizon) across val+test."""

import sys
sys.stdout.reconfigure(line_buffering=True)

import json
import os

import numpy as np
import pandas as pd

sys.path.insert(0, "workflow-shiyu-coder-kronos-csv-finetuning")
from src.model import Kronos, KronosTokenizer, KronosPredictor

TOK_PATH = os.path.join("workflow-shiyu-coder-kronos-csv-finetuning", "finetuned", "aapl_cpu_phase2", "tokenizer", "best_model")
PRED_PATH = os.path.join("workflow-shiyu-coder-kronos-csv-finetuning", "finetuned", "aapl_cpu_phase2", "basemodel", "best_model")
ART = os.path.join("ensemble", "artifacts")
CONTEXT = 192


def compute_time_features(ts_str):
    year = int(ts_str[:4])
    month = int(ts_str[5:7])
    day = int(ts_str[8:10])
    import datetime
    dt = datetime.date(year, month, day)
    weekday = dt.weekday()
    return np.array([0, 0, weekday, day, month], dtype=np.float32)


def main():
    print("Loading Kronos model...", flush=True)
    tokenizer = KronosTokenizer.from_pretrained(TOK_PATH)
    model = Kronos.from_pretrained(PRED_PATH)
    predictor = KronosPredictor(model, tokenizer, device="cpu",
                                max_context=CONTEXT, clip=5.0)

    df = pd.read_csv(os.path.join(ART, "features.csv"))
    cols = ["open", "high", "low", "close", "volume", "amount"]

    # Use the SAME target as LSTM/XGB: target_up = tomorrow > today (shift(-1))
    # For prediction at row i, we predict df['close'].iloc[i+1] vs df['close'].iloc[i]
    # So we need hist up to i, and target is i+1
    eval_idx = np.where((df["split"] == "val") | (df["split"] == "test"))[0]
    # Remove last index since we need i+1 for target
    eval_idx = eval_idx[eval_idx < len(df) - 1]
    print(f"Rolling Kronos over {len(eval_idx)} days "
          f"({df['timestamps'].iloc[eval_idx[0]]} -> {df['timestamps'].iloc[eval_idx[-1]]})", flush=True)

    records = []
    for k, i in enumerate(eval_idx):
        # History up to i (inclusive) for predicting i+1
        hist = df.iloc[max(0, i - CONTEXT + 1):i + 1]
        x_ts = hist["timestamps"].values
        y_ts_str = df["timestamps"].iloc[i + 1]  # NEXT day timestamp

        # Prepare data
        x = hist[cols].values.astype(np.float32)
        x_mean, x_std = np.mean(x, axis=0), np.std(x, axis=0)
        x_norm = (x - x_mean) / (x_std + 1e-5)
        x_norm = np.clip(x_norm, -5.0, 5.0)

        x_stamp = np.array([compute_time_features(ts) for ts in x_ts], dtype=np.float32)
        y_stamp = compute_time_features(y_ts_str).reshape(1, -1)

        x_norm = x_norm[np.newaxis, :]
        x_stamp = x_stamp[np.newaxis, :]
        y_stamp = y_stamp[np.newaxis, :]

        preds = predictor.generate(x_norm, x_stamp, y_stamp, pred_len=1, T=1.0, top_k=0, top_p=0.9,
                                   sample_count=1, verbose=False)
        preds = preds.squeeze(0)  # (1, 6)
        preds = preds * (x_std + 1e-5) + x_mean

        pred_close = float(preds[0, 3])  # close is index 3
        last_close = float(hist["close"].iloc[-1])  # close at day i
        pred_ret = pred_close / last_close - 1
        pred_up = int(pred_close > last_close)
        
        # Actual: next day close vs today close (SAME as LSTM/XGB target_up)
        actual_up = int(float(df["close"].iloc[i + 1]) > last_close)

        # Temperature scaling for probability
        p_up = float(1 / (1 + np.exp(-pred_ret / 0.01)))

        records.append({"timestamps": df["timestamps"].iloc[i],  # as-of date (consistent with LSTM/XGB)
                        "p_up": p_up, "pred": pred_up, "actual": actual_up,
                        "split": df["split"].iloc[i], "pred_ret": pred_ret,
                        "actual_ret": float(df["close"].iloc[i + 1]) / last_close - 1})

        if (k + 1) % 50 == 0 or k == len(eval_idx) - 1:
            sub_acc = np.mean([r["pred"] == r["actual"] for r in records])
            print(f"[{k + 1}/{len(eval_idx)}] running acc={sub_acc:.4f}", flush=True)

    # Evaluate
    out = {}
    for split in ["val", "test"]:
        sub = [r for r in records if r["split"] == split]
        if not sub:
            continue
        acc = np.mean([r["pred"] == r["actual"] for r in sub])
        p_up_vals = [r["p_up"] for r in sub]
        pred_up_rate = np.mean([r["pred"] for r in sub])
        actual_up_rate = np.mean([r["actual"] for r in sub])
        
        # AUC
        from sklearn.metrics import roc_auc_score
        auc = roc_auc_score([r["actual"] for r in sub], p_up_vals)
        
        print(f"KRONOS {split}: accuracy={acc:.4f} AUC={auc:.4f} | pred_up_rate={pred_up_rate:.4f} actual_up_rate={actual_up_rate:.4f} | "
              f"p_up_mean={np.mean(p_up_vals):.4f} p_up_std={np.std(p_up_vals):.4f} | n={len(sub)}", flush=True)
        
        out[split] = {
            "timestamps": [r["timestamps"] for r in sub],
            "p_up": [r["p_up"] for r in sub],
            "pred": [r["pred"] for r in sub],
            "actual": [r["actual"] for r in sub],
        }

    with open(os.path.join(ART, "kronos_preds_v2.json"), "w") as f:
        json.dump(out, f)
    print(f"\nSaved -> {os.path.join(ART, 'kronos_preds_v2.json')}", flush=True)


if __name__ == "__main__":
    main()