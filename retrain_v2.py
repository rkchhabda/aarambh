import warnings; warnings.filterwarnings('ignore')
import os, json, joblib, numpy as np, pandas as pd
from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, roc_auc_score

BASE = os.path.dirname(os.path.abspath(__file__))
MULTI_DIR = os.path.join(BASE, "data", "multi")
MODELS_DIR = os.path.join(BASE, "service", "models")

with open(os.path.join(MODELS_DIR, "best_params.json")) as f:
    cfg = json.load(f)

# Single source of truth: features/horizon come from the tuning config.
FEATURES = cfg["features"]
HORIZON = cfg["horizon"]

train = pd.read_csv(os.path.join(MULTI_DIR, f"train_multi_v2_{HORIZON}.csv"))
val = pd.read_csv(os.path.join(MULTI_DIR, f"val_multi_v2_{HORIZON}.csv"))

X_tr = train[FEATURES].fillna(0).values; y_tr = train["target"].values
X_v = val[FEATURES].fillna(0).values; y_v = val["target"].values
X_tv = np.vstack([X_tr, X_v]); y_tv = np.concatenate([y_tr, y_v])

bp_xgb = cfg["XGBoost"]
bp_rf = cfg["RandomForest"]
bp_lr = cfg["LogisticRegression"]
lr_p = {**bp_lr, "max_iter": 5000, "random_state": 42, "n_jobs": -1}
if lr_p.get("penalty") == "l1":
    lr_p["solver"] = "saga"

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
COST = 0.002  # round-trip cost used for threshold selection


def fwd_ret(df):
    """5-day forward return per ticker (aligned back to df's row order)."""
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d.sort_values(["ticker", "date"])
    d["fr"] = d.groupby("ticker")["Close"].transform(lambda s: s.shift(-5) / s - 1)
    return d["fr"].reindex(df.index).values


# Return-weighted training: weight each sample by |5d forward return| so the
# model focuses on trades that actually move P&L. (Backtest showed the
# equal-weight directional signal has no magnitude edge.)
fr_tv = fwd_ret(pd.concat([train, val], ignore_index=True))
w_tv = np.abs(fr_tv)
w_tv = np.nan_to_num(w_tv, nan=np.nanmedian(w_tv))
w_tv = w_tv / np.median(w_tv)
fr_tr = fwd_ret(train)
w_tr = np.abs(fr_tr)
w_tr = np.nan_to_num(w_tr, nan=np.nanmedian(w_tr))
w_tr = w_tr / np.median(w_tr)

# Feature scaling: required so the L1-penalised LogisticRegression base model
# treats all features fairly (XGB/RF are scale-invariant, so this only helps LR).
scaler = StandardScaler().fit(X_tv)
Xs_tv = scaler.transform(X_tv)
Xs_tr = scaler.transform(X_tr)
Xs_v = scaler.transform(X_v)

print(f"Retraining ensemble (return-weighted) on train+val with {len(FEATURES)} features...")


def xgb_f():
    return XGBClassifier(**bp_xgb, random_state=42, eval_metric="logloss", n_jobs=-1, verbosity=0)


def rf_f():
    return RandomForestClassifier(**bp_rf, random_state=42, n_jobs=-1)


def lr_f():
    return LogisticRegression(**lr_p)


dx, dr, dl = xgb_f(), rf_f(), lr_f()
dx.fit(Xs_tv, y_tv, sample_weight=w_tv)
dr.fit(Xs_tv, y_tv, sample_weight=w_tv)
dl.fit(Xs_tv, y_tv, sample_weight=w_tv)
print(f"  Base models trained on {len(X_tv)} rows (return-weighted, scaled)")

# Honest meta training: 5-fold OUT-OF-FOLD base predictions on the TRAIN set,
# so the meta never sees predictions from a base model trained on those rows.
def oof_proba(factory, X, y, sw):
    proba = np.zeros(len(y))
    for tr, te in cv.split(X, y):
        sc = StandardScaler().fit(X[tr])
        m = factory()
        m.fit(sc.transform(X[tr]), y[tr], sample_weight=sw[tr])
        proba[te] = m.predict_proba(sc.transform(X[te]))[:, 1]
    return proba


print("  Generating OOF predictions for meta...")
p_xgb = oof_proba(xgb_f, X_tr, y_tr, w_tr)
p_rf = oof_proba(rf_f, X_tr, y_tr, w_tr)
p_lr = oof_proba(lr_f, X_tr, y_tr, w_tr)
stack_oof = np.column_stack([p_xgb, p_rf, p_lr])

ax = accuracy_score(y_tr, (p_xgb > 0.5).astype(int))
ar = accuracy_score(y_tr, (p_rf > 0.5).astype(int))
al = accuracy_score(y_tr, (p_lr > 0.5).astype(int))
print(f"  OOF base acc -> XGB:{ax:.4f} RF:{ar:.4f} LR:{al:.4f}")

dm = LogisticRegression(C=1.0, random_state=42, max_iter=5000)
dm.fit(stack_oof, y_tr, sample_weight=w_tr)
print(f"  Meta trained on OOF (train acc={accuracy_score(y_tr, dm.predict(stack_oof)):.4f}, "
      f"AUC={roc_auc_score(y_tr, dm.predict_proba(stack_oof)[:,1]):.4f})")

# Threshold selection on OUT-OF-FOLD train predictions (the base models never
# trained on these exact rows), NOT on validation (which is in-sample for the
# base models and therefore overconfident). This makes the chosen threshold
# transfer to the truly out-of-sample test period.
oof_meta_prob = dm.predict_proba(stack_oof)[:, 1]
best_t, best_ret, best_cov = 0.5, -1e9, 0
for t in np.arange(0.50, 0.861, 0.01):
    sig = oof_meta_prob > t
    if sig.sum() < 50:
        continue
    ret = np.nanmean(fr_tr[sig] - COST)
    if ret > best_ret:
        best_t, best_ret, best_cov = round(t, 2), ret, int(sig.sum())
print(f"  Best OOF threshold={best_t:.2f} -> mean BUY return={best_ret:+.4f} (coverage={best_cov})")

joblib.dump(dx, os.path.join(MODELS_DIR, "xgboost.pkl"))
joblib.dump(dr, os.path.join(MODELS_DIR, "randomforest.pkl"))
joblib.dump(dl, os.path.join(MODELS_DIR, "logisticregression.pkl"))
joblib.dump(dm, os.path.join(MODELS_DIR, "meta_model.pkl"))
joblib.dump(["XGBoost", "RandomForest", "LogisticRegression"], os.path.join(MODELS_DIR, "ensemble_models.pkl"))
joblib.dump(scaler, os.path.join(MODELS_DIR, "scaler.pkl"))

# Feature-schema manifest: lets the live service assert it serves the same
# features the model was trained on (catches train/serve skew at startup).
with open(os.path.join(MODELS_DIR, "features.json"), "w") as f:
    json.dump({
        "features": FEATURES,
        "horizon": HORIZON,
        "feature_version": 1,
        "threshold": best_t,
    }, f, indent=2)
print("Saved models + features.json manifest.")
