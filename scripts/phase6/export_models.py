"""Export trained per-ticker LSTM models + scalers for the production API."""

import json
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "phase5"))
from train_multi import LSTMClassifier, train_models_for_ticker  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "service", "models")
WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.makedirs(OUT, exist_ok=True)


def main():
    # Re-run training but capture the fitted scaler + weights by re-implementing
    # the minimal export path via the shared trainer.
    import pandas as pd
    from sklearn.preprocessing import StandardScaler
    from train_multi import build_features, make_sequences, FEATURES, SEQ_LEN

    manifest = {}
    for ticker in ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]:
        torch.manual_seed(42)
        np.random.seed(42)
        raw = pd.read_csv(os.path.join(WORKSPACE, "data", "multi", f"{ticker}.csv"))
        df = build_features(raw)
        scaler = StandardScaler().fit(df.loc[df.split == "train", FEATURES])
        X_all = scaler.transform(df[FEATURES]).astype(np.float32)
        y_all = df["target_up_1d"].values.astype(np.float32)
        tr_idx = np.where(df["split"] == "train")[0]
        va_idx = np.where(df["split"] == "val")[0]

        X_tr, y_tr = make_sequences(X_all, y_all, tr_idx)
        model = LSTMClassifier(len(FEATURES))
        opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
        loss_fn = nn_loss = torch.nn.BCEWithLogitsLoss()
        X_t, y_t = torch.from_numpy(X_tr), torch.from_numpy(y_tr)
        best_acc, best_state, patience = 0.0, None, 0
        for epoch in range(30):
            model.train()
            perm = torch.randperm(len(X_t))
            for i in range(0, len(perm), 64):
                idx = perm[i:i + 64]
                opt.zero_grad()
                loss_fn(model(X_t[idx]), y_t[idx]).backward()
                opt.step()
            model.eval()
            with torch.no_grad():
                X_va, _ = make_sequences(X_all, y_all, va_idx)
                pv = torch.sigmoid(model(torch.from_numpy(X_va))).numpy()
            acc = ((pv > 0.5).astype(int) == y_all[va_idx]).mean()
            if acc > best_acc:
                best_acc, patience = acc, 0
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
            else:
                patience += 1
            if patience >= 6:
                break

        tdir = os.path.join(OUT, ticker)
        os.makedirs(tdir, exist_ok=True)
        torch.save(best_state, os.path.join(tdir, "lstm.pt"))
        np.savez(os.path.join(tdir, "scaler.npz"),
                 mean=scaler.mean_, scale=scaler.scale_)
        manifest[ticker] = {"val_accuracy": round(float(best_acc), 4),
                            "features": FEATURES, "seq_len": SEQ_LEN,
                            "hidden": 64}
        print(f"{ticker:>5}: exported (val_acc={best_acc:.4f})")

    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest -> {os.path.join(OUT, 'manifest.json')}")


if __name__ == "__main__":
    import torch.nn as nn  # noqa: F401
    main()
