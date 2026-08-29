import warnings; warnings.filterwarnings('ignore')
import os, json, joblib, numpy as np, pandas as pd
from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

BASE = os.path.dirname(os.path.abspath(__file__))
MULTI_DIR = os.path.join(BASE, "data", "multi")
MODELS_DIR = os.path.join(BASE, "service", "models")

FEATURES = ["bb_pos", "macd", "obv_slope", "sma_ratio", "cci", "ret_10", "williams_r", "rsi_14", "atr_14", "roc_10"]
HORIZON = "5d"

with open(os.path.join(MODELS_DIR, "best_params.json")) as f:
    cfg = json.load(f)

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

print("Retraining on train+val with 10 features...")

dx = XGBClassifier(**bp_xgb, random_state=42, eval_metric="logloss", n_jobs=-1, verbosity=0)
dx.fit(X_tv, y_tv)
print(f"  XGB: {dx.n_features_in_} features")

dr = RandomForestClassifier(**bp_rf, random_state=42, n_jobs=-1)
dr.fit(X_tv, y_tv)
print(f"  RF:  {dr.n_features_in_} features")

dl = LogisticRegression(**lr_p)
dl.fit(X_tv, y_tv)
print(f"  LR:  {dl.n_features_in_} features")

ds = np.column_stack([dx.predict_proba(X_v)[:,1], dr.predict_proba(X_v)[:,1], dl.predict_proba(X_v)[:,1]])
dm = LogisticRegression(C=1.0, random_state=42, max_iter=5000)
dm.fit(ds, y_v)
print(f"  Meta: trained")

joblib.dump(dx, os.path.join(MODELS_DIR, "xgboost.pkl"))
joblib.dump(dr, os.path.join(MODELS_DIR, "randomforest.pkl"))
joblib.dump(dl, os.path.join(MODELS_DIR, "logisticregression.pkl"))
joblib.dump(dm, os.path.join(MODELS_DIR, "meta_model.pkl"))
joblib.dump(["XGBoost", "RandomForest", "LogisticRegression"], os.path.join(MODELS_DIR, "ensemble_models.pkl"))
print("Saved models.")
