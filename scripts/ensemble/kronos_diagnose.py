"""Diagnose Kronos directional bias - check raw outputs, feature order, label inversion."""

import json
import os
import sys

import numpy as np
import pandas as pd

# Add Kronos path
_HERE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.dirname(os.path.dirname(_HERE))
REPO = os.path.join(WORKSPACE, "workflow-shiyu-coder-kronos-csv-finetuning")
sys.path.insert(0, REPO)

from src.model import Kronos, KronosTokenizer, KronosPredictor

TOK_PATH = os.path.join(REPO, "finetuned", "aapl_cpu_phase2", "tokenizer", "best_model")
PRED_PATH = os.path.join(REPO, "finetuned", "aapl_cpu_phase2", "basemodel", "best_model")
ART = os.path.abspath(os.path.join(WORKSPACE, "ensemble", "artifacts"))
CONTEXT = 192


def main():
    print("Loading Kronos model...", flush=True)
    tokenizer = KronosTokenizer.from_pretrained(TOK_PATH)
    model = Kronos.from_pretrained(PRED_PATH)
    predictor = KronosPredictor(model, tokenizer, device="cpu",
                                max_context=CONTEXT, clip=5.0)

    df = pd.read_csv(os.path.join(ART, "features.csv"))
    # Manual datetime conversion to avoid pd.to_datetime hanging issue
    import numpy as np
    ts_array = np.array([pd.Timestamp(x) for x in df["timestamps"]], dtype="datetime64[ns]")
    df["timestamps"] = pd.Series(ts_array, index=df.index)
    cols = ["open", "high", "low", "close", "volume", "amount"]

    eval_idx = np.where((df["split"] == "val") | (df["split"] == "test"))[0]
    print(f"Rolling Kronos over {len(eval_idx)} days "
          f"({df['timestamps'].iloc[eval_idx[0]].date()} -> {df['timestamps'].iloc[eval_idx[-1]].date()})", flush=True)

    records = []
    for k, i in enumerate(eval_idx[:20]):  # First 20 for detailed inspection
        hist = df.iloc[max(0, i - CONTEXT):i]
        x_ts = hist["timestamps"]
        y_ts = pd.Series([df["timestamps"].iloc[i]])

        pred = predictor.predict(df=hist[cols].reset_index(drop=True),
                                 x_timestamp=x_ts.reset_index(drop=True),
                                 y_timestamp=y_ts,
                                 pred_len=1, T=1.0, top_p=0.9,
                                 sample_count=1, verbose=False)
        
        pred_close = float(pred["close"].iloc[0])
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
        
        print(f"\nDay {k} ({y_ts.iloc[0].date()}):", flush=True)
        print(f"  last_close={last_close:.4f}, pred_close={pred_close:.4f}, actual_close={raw_actual_close:.4f}", flush=True)
        print(f"  pred_ret={pred_ret:.6f}, actual_ret={(raw_actual_close/last_close-1):.6f}", flush=True)
        print(f"  pred_up={pred_up}, actual_up={actual_up}", flush=True)
        print(f"  p_up(T=0.01)={p_up_001:.4f}, p_up(T=0.1)={p_up_01:.4f}, p_up(T=1)={p_up_1:.4f}, p_up(T=10)={p_up_10:.4f}", flush=True)
        
        # Check feature values
        last_row = hist.iloc[-1]
        print(f"  Features: open={last_row['open']:.4f} high={last_row['high']:.4f} low={last_row['low']:.4f} close={last_row['close']:.4f} vol={last_row['volume']:.0f}", flush=True)

        records.append({"timestamps": y_ts.iloc[0].strftime("%Y-%m-%d"),
                        "p_up": p_up_001, "pred": pred_up, "actual": actual_up,
                        "split": df["split"].iloc[i], "pred_ret": pred_ret,
                        "actual_ret": raw_actual_close/last_close-1})

    # Full evaluation
    print("\n\n=== FULL EVALUATION ===", flush=True)
    all_records = []
    for k, i in enumerate(eval_idx):
        hist = df.iloc[max(0, i - CONTEXT):i]
        x_ts = hist["timestamps"]
        y_ts = pd.Series([df["timestamps"].iloc[i]])

        pred = predictor.predict(df=hist[cols].reset_index(drop=True),
                                 x_timestamp=x_ts.reset_index(drop=True),
                                 y_timestamp=y_ts,
                                 pred_len=1, T=1.0, top_p=0.9,
                                 sample_count=1, verbose=False)
        
        pred_close = float(pred["close"].iloc[0])
        last_close = float(hist["close"].iloc[-1])
        pred_ret = pred_close / last_close - 1
        pred_up = int(pred_close > last_close)
        actual_up = int(float(df["close"].iloc[i]) > last_close)
        
        # Try different temperatures
        for T in [0.01, 0.1, 1.0, 10.0]:
            p_up = float(1 / (1 + np.exp(-pred_ret / T)))
            if k == 0:
                all_records.append({"T": T, "records": []})
            all_records[-1]["records"].append({
                "timestamps": y_ts.iloc[0].strftime("%Y-%m-%d"),
                "p_up": p_up, "pred": pred_up, "actual": actual_up,
                "split": df["split"].iloc[i], "pred_ret": pred_ret
            })

    for T_data in all_records:
        T = T_data["T"]
        recs = T_data["records"]
        for split in ["val", "test"]:
            sub = [r for r in recs if r["split"] == split]
            if not sub:
                continue
            acc = np.mean([r["pred"] == r["actual"] for r in sub])
            p_up_vals = [r["p_up"] for r in sub]
            pred_up_rate = np.mean([r["pred"] for r in sub])
            print(f"KRONOS T={T} {split}: accuracy={acc:.4f} | pred_up_rate={pred_up_rate:.4f} | "
                  f"p_up_mean={np.mean(p_up_vals):.4f} p_up_std={np.std(p_up_vals):.4f} | n={len(sub)}", flush=True)


if __name__ == "__main__":
    main()