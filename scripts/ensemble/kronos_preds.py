"""Rolling 1-day-ahead Kronos forecasts across val+test using Phase-2 checkpoints."""

import json
import os

import numpy as np
import pandas as pd
from src.model import Kronos, KronosTokenizer, KronosPredictor

_HERE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.dirname(os.path.dirname(_HERE))  # GaurviDEEP/
REPO = os.path.join(WORKSPACE, "workflow-shiyu-coder-kronos-csv-finetuning")
TOK_PATH = os.path.join(REPO, "finetuned", "aapl_cpu_phase2", "tokenizer", "best_model")
PRED_PATH = os.path.join(REPO, "finetuned", "aapl_cpu_phase2", "basemodel", "best_model")
ART = os.path.abspath(os.path.join(WORKSPACE, "ensemble", "artifacts"))
CONTEXT = 192


def main():
    tokenizer = KronosTokenizer.from_pretrained(TOK_PATH)
    model = Kronos.from_pretrained(PRED_PATH)
    predictor = KronosPredictor(model, tokenizer, device="cpu",
                                max_context=CONTEXT, clip=5.0)

    df = pd.read_csv(os.path.join(ART, "features.csv"), parse_dates=["timestamps"])
    cols = ["open", "high", "low", "close", "volume", "amount"]

    eval_idx = np.where((df["split"] == "val") | (df["split"] == "test"))[0]
    print(f"Rolling Kronos over {len(eval_idx)} days "
          f"({df['timestamps'].iloc[eval_idx[0]].date()} -> {df['timestamps'].iloc[eval_idx[-1]].date()})")

    records = []
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

        records.append({"timestamps": y_ts.iloc[0].strftime("%Y-%m-%d"),
                        "p_up": float(1 / (1 + np.exp(-pred_ret / 0.01))),
                        "pred": pred_up, "actual": actual_up,
                        "split": df["split"].iloc[i]})

        if (k + 1) % 25 == 0 or k == len(eval_idx) - 1:
            sub_acc = np.mean([r["pred"] == r["actual"] for r in records])
            print(f"[{k + 1}/{len(eval_idx)}] running acc={sub_acc:.4f}")
            with open(os.path.join(ART, "kronos_preds.json"), "w") as f:
                json.dump({s: {"timestamps": [r["timestamps"] for r in records if r["split"] == s],
                               "p_up": [r["p_up"] for r in records if r["split"] == s],
                               "pred": [r["pred"] for r in records if r["split"] == s],
                               "actual": [r["actual"] for r in records if r["split"] == s]}
                           for s in ["val", "test"]}, f)

    for split in ["val", "test"]:
        sub = [r for r in records if r["split"] == split]
        acc = np.mean([r["pred"] == r["actual"] for r in sub])
        print(f"KRONOS {split}: accuracy={acc:.4f} | n={len(sub)}")
    print("Done.")


if __name__ == "__main__":
    main()
