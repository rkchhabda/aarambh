"""Diagnose Kronos directional bias - check raw outputs, feature order, label inversion."""

import sys
sys.stdout.reconfigure(line_buffering=True)

import json
import os

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, "workflow-shiyu-coder-kronos-csv-finetuning")
from src.model import Kronos, KronosTokenizer, KronosPredictor

TOK_PATH = os.path.join("workflow-shiyu-coder-kronos-csv-finetuning", "finetuned", "aapl_cpu_phase2", "tokenizer", "best_model")
PRED_PATH = os.path.join("workflow-shiyu-coder-kronos-csv-finetuning", "finetuned", "aapl_cpu_phase2", "basemodel", "best_model")
ART = os.path.join("ensemble", "artifacts")
CONTEXT = 192


def compute_time_features(ts_str):
    """Compute minute, hour, weekday, day, month from timestamp string YYYY-MM-DD"""
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

    eval_idx = np.where((df["split"] == "val") | (df["split"] == "test"))[0]
    print(f"Rolling Kronos over {len(eval_idx)} days "
          f"({df['timestamps'].iloc[eval_idx[0]]} -> {df['timestamps'].iloc[eval_idx[-1]]})", flush=True)

    records = []
    for k, i in enumerate(eval_idx[:20]):  # First 20 for detailed inspection
        hist = df.iloc[max(0, i - CONTEXT):i]
        x_ts = hist["timestamps"].values
        y_ts_str = df["timestamps"].iloc[i]

        # Prepare data
        x = hist[cols].values.astype(np.float32)
        x_mean, x_std = np.mean(x, axis=0), np.std(x, axis=0)
        x_norm = (x - x_mean) / (x_std + 1e-5)
        x_norm = np.clip(x_norm, -5.0, 5.0)

        # Compute time features manually
        x_stamp = np.array([compute_time_features(ts) for ts in x_ts], dtype=np.float32)
        y_stamp = compute_time_features(y_ts_str).reshape(1, -1)

        # Add batch dimension
        x_norm = x_norm[np.newaxis, :]
        x_stamp = x_stamp[np.newaxis, :]
        y_stamp = y_stamp[np.newaxis, :]

        preds = predictor.generate(x_norm, x_stamp, y_stamp, pred_len=1, T=1.0, top_k=0, top_p=0.9,
                                   sample_count=1, verbose=False)
        preds = preds.squeeze(0)  # shape: (pred_len, 6)
        preds = preds * (x_std + 1e-5) + x_mean

        pred_close = float(preds[0, 3])  # close is index 3 (open=0, high=1, low=2, close=3)
        last_close = float(hist["close"].iloc[-1])
        pred_ret = pred_close / last_close - 1
        pred_up = int(pred_close > last_close)
        actual_up = int(float(df["close"].iloc[i]) > last_close)

        # Raw outputs for diagnosis
        raw_pred_ret = pred_ret
        raw_pred_close = pred_close
        raw_last_close = last_close
        raw_actual_close = float(df["close"].iloc[i])

        # Different temperature scalings
        p_up_001 = float(1 / (1 + np.exp(-pred_ret / 0.01)))
        p_up_01 = float(1 / (1 + np.exp(-pred_ret / 0.1)))
        p_up_1 = float(1 / (1 + np.exp(-pred_ret / 1.0)))
        p_up_10 = float(1 / (1 + np.exp(-pred_ret / 10.0)))

        print(f"\nDay {k} ({y_ts_str}):", flush=True)
        print(f"  last_close={last_close:.4f}, pred_close={pred_close:.4f}, actual_close={raw_actual_close:.4f}", flush=True)
        print(f"  pred_ret={pred_ret:.6f}, actual_ret={(raw_actual_close/last_close-1):.6f}", flush=True)
        print(f"  pred_up={pred_up}, actual_up={actual_up}", flush=True)
        print(f"  p_up(T=0.01)={p_up_001:.4f}, p_up(T=0.1)={p_up_01:.4f}, p_up(T=1)={p_up_1:.4f}, p_up(T=10)={p_up_10:.4f}", flush=True)

        # Check feature values
        last_row = hist.iloc[-1]
        print(f"  Features: open={last_row['open']:.4f} high={last_row['high']:.4f} low={last_row['low']:.4f} close={last_row['close']:.4f} vol={last_row['volume']:.0f}", flush=True)

        records.append({"timestamps": y_ts_str,
                        "p_up": p_up_001, "pred": pred_up, "actual": actual_up,
                        "split": df["split"].iloc[i], "pred_ret": pred_ret,
                        "actual_ret": raw_actual_close/last_close-1})

    # Full evaluation with different temperatures
    print("\n\n=== FULL EVALUATION ===", flush=True)
    all_records = {0.01: [], 0.1: [], 1.0: [], 10.0: []}

    for k, i in enumerate(eval_idx):
        hist = df.iloc[max(0, i - CONTEXT):i]
        x_ts = hist["timestamps"].values
        y_ts_str = df["timestamps"].iloc[i]

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
        preds = preds.squeeze(0)  # shape: (pred_len, 6)
        preds = preds * (x_std + 1e-5) + x_mean

        pred_close = float(preds[0, 3])  # close is index 3
        last_close = float(hist["close"].iloc[-1])
        pred_ret = pred_close / last_close - 1
        pred_up = int(pred_close > last_close)
        actual_up = int(float(df["close"].iloc[i]) > last_close)

        for T in [0.01, 0.1, 1.0, 10.0]:
            p_up = float(1 / (1 + np.exp(-pred_ret / T)))
            all_records[T].append({
                "timestamps": y_ts_str,
                "p_up": p_up, "pred": pred_up, "actual": actual_up,
                "split": df["split"].iloc[i], "pred_ret": pred_ret
            })

        if (k + 1) % 50 == 0 or k == len(eval_idx) - 1:
            sub_acc = np.mean([r["pred"] == r["actual"] for r in all_records[0.01][-50:]])
            print(f"[{k + 1}/{len(eval_idx)}] running acc (T=0.01, last 50)={sub_acc:.4f}", flush=True)

    for T in [0.01, 0.1, 1.0, 10.0]:
        recs = all_records[T]
        for split in ["val", "test"]:
            sub = [r for r in recs if r["split"] == split]
            if not sub:
                continue
            acc = np.mean([r["pred"] == r["actual"] for r in sub])
            p_up_vals = [r["p_up"] for r in sub]
            pred_up_rate = np.mean([r["pred"] for r in sub])
            print(f"KRONOS T={T} {split}: accuracy={acc:.4f} | pred_up_rate={pred_up_rate:.4f} | "
                  f"p_up_mean={np.mean(p_up_vals):.4f} p_up_std={np.std(p_up_vals):.4f} | n={len(sub)}", flush=True)

    # Save detailed records for T=0.01 (original)
    out = {}
    for split in ["val", "test"]:
        sub = [r for r in all_records[0.01] if r["split"] == split]
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