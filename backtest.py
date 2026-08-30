"""Trading backtest for the ensemble signal (5d horizon).

Validates economic value, not just accuracy:
  - Reconstructs each ticker's REALIZED 5-day forward return from price history.
  - Generates BUY signals using the exact deployed logic:
        signal = (ensemble_prob > 0.5) AND (Close > SMA200)
  - Applies a realistic round-trip cost and compares the long-only strategy
    against (a) always-invested and (b) doing-nothing.

Run:  python backtest.py
"""
import warnings; warnings.filterwarnings('ignore')
import os, json, joblib, numpy as np, pandas as pd
from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

BASE = os.path.dirname(os.path.abspath(__file__))
MULTI_DIR = os.path.join(BASE, "data", "multi")
MODELS_DIR = os.path.join(BASE, "service", "models")
COST = 0.002  # ~0.1% per side round-trip (brokerage + slippage)

with open(os.path.join(MODELS_DIR, "best_params.json")) as f:
    cfg = json.load(f)
FEATURES = cfg["features"]
HORIZON = cfg["horizon"]

xgb = joblib.load(os.path.join(MODELS_DIR, "xgboost.pkl"))
rf = joblib.load(os.path.join(MODELS_DIR, "randomforest.pkl"))
lr = joblib.load(os.path.join(MODELS_DIR, "logisticregression.pkl"))
meta = joblib.load(os.path.join(MODELS_DIR, "meta_model.pkl"))
bases = [xgb, rf, lr]

# Selected probability threshold (from training; default 0.5 if missing).
manifest = os.path.join(MODELS_DIR, "features.json")
THR = json.load(open(manifest)).get("threshold", 0.5) if os.path.exists(manifest) else 0.5

# ---- Reconstruct realized forward returns from full history ----
def load(name):
    df = pd.read_csv(os.path.join(MULTI_DIR, f"{name}_multi_v2_{HORIZON}.csv"))
    df["split"] = name
    return df

full = pd.concat([load("train"), load("val"), load("test")], ignore_index=True)
full["date"] = pd.to_datetime(full["date"])
full = full.sort_values(["ticker", "date"]).reset_index(drop=True)
# 5-day forward return per ticker (the trade we'd actually make at time t)
full["fwd_ret"] = full.groupby("ticker")["Close"].transform(lambda s: s.shift(-5) / s - 1)
full["sma200"] = full.groupby("ticker")["Close"].transform(lambda s: s.rolling(200).mean())
test = full[full["split"] == "test"].copy().reset_index(drop=True)
test = test.dropna(subset=["fwd_ret", "sma200"]).reset_index(drop=True)

# ---- Generate signals ----
X = test[FEATURES].fillna(0).values
probas = np.column_stack([m.predict_proba(X)[:, 1] for m in bases])
final_prob = meta.predict_proba(probas)[:, 1]
test["prob"] = final_prob
test["signal"] = (final_prob > THR) & (test["Close"] > test["sma200"])
test["ret"] = np.where(test["signal"], test["fwd_ret"] - COST, 0.0)

# ---- Reporting ----
# NOTE: signals are generated every trading day and 5d trades OVERLAP, so they
# cannot be compounded sequentially. We report mean return PER SIGNAL (each
# trade is an independent 5d holding) which is the correct, honest summary.
n = len(test)
n_buy = int(test["signal"].sum())
hit = test.loc[test["signal"], "fwd_ret"] > 0
hit_rate = hit.mean() if n_buy else 0.0
strat_mean = test["ret"].mean()           # long-only, cost-adjusted, 0 when HOLD
always_mean = (test["fwd_ret"] - COST).mean()  # always invested, cost-adjusted
win = test.loc[test["signal"], "fwd_ret"].mean()   # raw mean return on BUY days
lose = test.loc[~test["signal"], "fwd_ret"].mean()  # raw mean return on HOLD days

print(f"Horizon: {HORIZON} | Test rows: {n} | Cost/round-trip: {COST:.3f}")
print(f"BUY signals: {n_buy} ({n_buy/n:.1%} coverage)")
print(f"  Signal hit-rate (fwd_ret>0 on BUY): {hit_rate:.3f}")
print(f"  Mean return on BUY days  (raw): {win:+.4f}")
print(f"  Mean return on HOLD days (raw): {lose:+.4f}")
print(f"  Strategy mean/trade return (cost-adj, HOLD=0): {strat_mean:+.4f}")
print(f"  Always-invested mean/trade return (cost-adj):  {always_mean:+.4f}")
print(f"  => Strategy edge vs always-invested: {(strat_mean-always_mean):+.4f}")

# Threshold sweep on the test set (SMA200-gated) to see if ANY subset is profitable.
print(f"\nThreshold sweep (test, SMA200-gated, cost={COST:.3f}):")
for t in [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85]:
    sig = (final_prob > t) & (test["Close"] > test["sma200"])
    cov = sig.mean()
    if sig.sum() == 0:
        print(f"  t={t:.2f}  coverage={cov:.1%}  meanBUY=n/a")
        continue
    r = (test.loc[sig, "fwd_ret"] - COST).mean()
    print(f"  t={t:.2f}  coverage={cov:.1%}  mean BUY return={r:+.4f}")

print(f"  Per-ticker BUY counts: {test.groupby('ticker')['signal'].sum().to_dict()}")
