"""XGBoost directional classifier: train on train split, output P(up) on val+test."""

import json
import os

import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score

ART = os.path.join("ensemble", "artifacts")


def main():
    df = pd.read_csv(os.path.join(ART, "features.csv"), parse_dates=["timestamps"])
    features = ["ret_1", "ret_5", "ret_10", "log_vol_chg", "rsi_14", "macd",
                "bb_pos", "atr_14", "obv_slope", "sma_ratio", "rvol_5", "rvol_20"]

    tr = df[df.split == "train"]
    va = df[df.split == "val"]
    te = df[df.split == "test"]

    model = XGBClassifier(
        n_estimators=400, max_depth=3, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        reg_lambda=1.0, min_child_weight=5,
        eval_metric="logloss", random_state=42, tree_method="hist",
    )
    model.fit(tr[features], tr["target_up"])

    out = {}
    for name, part in [("val", va), ("test", te)]:
        proba = model.predict_proba(part[features])[:, 1]
        pred = (proba > 0.5).astype(int)
        acc = accuracy_score(part["target_up"], pred)
        out[name] = {
            "timestamps": part["timestamps"].dt.strftime("%Y-%m-%d").tolist(),
            "p_up": proba.round(6).tolist(),
            "pred": pred.tolist(),
            "actual": part["target_up"].tolist(),
        }
        print(f"XGB {name}: accuracy={acc:.4f} | mean P(up)={proba.mean():.3f} | "
              f"n={len(proba)}")

    with open(os.path.join(ART, "xgb_preds.json"), "w") as f:
        json.dump(out, f)

    imp = sorted(zip(features, model.feature_importances_), key=lambda x: -x[1])[:5]
    print("Top-5 features:", [(k, round(v, 3)) for k, v in imp])
    print(f"Saved -> {os.path.join(ART, 'xgb_preds.json')}")


if __name__ == "__main__":
    main()
