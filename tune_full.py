"""
Complete Optuna tuning pipeline - fast version.
Tunes all 3 models with appropriate trial counts.
"""
import os, warnings, json, time
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, optuna, joblib
from optuna.samplers import TPESampler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, brier_score_loss
from xgboost import XGBClassifier
optuna.logging.set_verbosity(optuna.logging.WARNING)

BASE = os.path.dirname(os.path.abspath(__file__))
MULTI_DIR = os.path.join(BASE, "data", "multi")
MODELS_DIR = os.path.join(BASE, "service", "models")
os.makedirs(MODELS_DIR, exist_ok=True)

FEATURES = ["ret_1", "ret_5", "ret_10", "log_vol_chg", "rsi_14", "macd",
            "bb_pos", "atr_14", "obv_slope", "sma_ratio", "rvol_5", "rvol_20"]

print("Loading data...")
train_df = pd.read_csv(os.path.join(MULTI_DIR, "train_multi.csv"))
val_df = pd.read_csv(os.path.join(MULTI_DIR, "val_multi.csv"))
test_df = pd.read_csv(os.path.join(MULTI_DIR, "test_multi.csv"))

X_tr = train_df[FEATURES].fillna(0).values
y_tr = train_df["target"].values
X_v = val_df[FEATURES].fillna(0).values
y_v = val_df["target"].values
X_te = test_df[FEATURES].fillna(0).values
y_te = test_df["target"].values
X_tv = np.vstack([X_tr, X_v])
y_tv = np.concatenate([y_tr, y_v])
print(f"Train={len(X_tr)} Val={len(X_v)} Test={len(X_te)}")

t0 = time.time()

# === XGBoost: 60 trials ===
print("\n[1/3] Tuning XGBoost (60 trials)...")
def xgb_obj(trial):
    p = {"max_depth": trial.suggest_int("max_depth", 3, 7),
         "n_estimators": trial.suggest_int("n_estimators", 100, 400, step=50),
         "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
         "subsample": trial.suggest_float("subsample", 0.6, 1.0),
         "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
         "min_child_weight": trial.suggest_int("min_child_weight", 1, 8),
         "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 5.0, log=True),
         "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 5.0, log=True),
         "random_state": 42, "eval_metric": "logloss", "n_jobs": -1, "verbosity": 0}
    m = XGBClassifier(**p)
    m.fit(X_tr, y_tr, eval_set=[(X_v, y_v)], verbose=False)
    return -accuracy_score(y_v, (m.predict_proba(X_v)[:,1] > 0.5).astype(int))

s_xgb = optuna.create_study(direction="minimize", sampler=TPESampler(seed=42))
s_xgb.optimize(xgb_obj, n_trials=60, show_progress_bar=True)
bp_xgb = s_xgb.best_params
print(f"  Best XGB val acc: {-s_xgb.best_value:.4f} ({time.time()-t0:.0f}s)")

# === RandomForest: 20 trials (fast) ===
print(f"\n[2/3] Tuning RandomForest (20 trials)...")
t1 = time.time()
def rf_obj(trial):
    p = {"n_estimators": trial.suggest_int("n_estimators", 200, 500, step=100),
         "max_depth": trial.suggest_int("max_depth", 5, 15),
         "min_samples_leaf": trial.suggest_int("min_samples_leaf", 10, 50),
         "random_state": 42, "n_jobs": -1}
    m = RandomForestClassifier(**p)
    m.fit(X_tr, y_tr)
    return -accuracy_score(y_v, (m.predict_proba(X_v)[:,1] > 0.5).astype(int))

s_rf = optuna.create_study(direction="minimize", sampler=TPESampler(seed=42))
s_rf.optimize(rf_obj, n_trials=20, show_progress_bar=True)
bp_rf = s_rf.best_params
print(f"  Best RF val acc: {-s_rf.best_value:.4f} ({time.time()-t1:.0f}s)")

# === LR: 20 trials ===
print(f"\n[3/3] Tuning LogisticRegression (20 trials)...")
t2 = time.time()
def lr_obj(trial):
    C = trial.suggest_float("C", 1e-3, 100.0, log=True)
    penalty = trial.suggest_categorical("penalty", ["l1", "l2"])
    m = LogisticRegression(C=C, penalty=penalty, solver="saga", max_iter=5000, random_state=42, n_jobs=-1)
    m.fit(X_tr, y_tr)
    return -accuracy_score(y_v, (m.predict_proba(X_v)[:,1] > 0.5).astype(int))

s_lr = optuna.create_study(direction="minimize", sampler=TPESampler(seed=42))
s_lr.optimize(lr_obj, n_trials=20, show_progress_bar=True)
bp_lr = s_lr.best_params
print(f"  Best LR val acc: {-s_lr.best_value:.4f} ({time.time()-t2:.0f}s)")

print(f"\nTotal tuning time: {time.time()-t0:.0f}s")

# ============================================================
# TRAIN & STACK
# ============================================================
print("\n" + "="*60)
print("TRAINING & STACKING")
print("="*60)

xgb_m = XGBClassifier(**bp_xgb, random_state=42, eval_metric="logloss", n_jobs=-1, verbosity=0)
xgb_m.fit(X_tr, y_tr)

rf_m = RandomForestClassifier(**bp_rf, random_state=42, n_jobs=-1)
rf_m.fit(X_tr, y_tr)

lr_p = {**bp_lr, "max_iter": 5000, "random_state": 42, "n_jobs": -1}
if lr_p.get("penalty") == "l1":
    lr_p["solver"] = "saga"
lr_m = LogisticRegression(**lr_p)
lr_m.fit(X_tr, y_tr)

sv = np.column_stack([xgb_m.predict_proba(X_v)[:,1], rf_m.predict_proba(X_v)[:,1], lr_m.predict_proba(X_v)[:,1]])

best_meta, best_meta_acc, best_meta_name = None, 0, ""
for nm, mt in [("LR1", LogisticRegression(C=1.0, random_state=42, max_iter=5000)),
               ("LR01", LogisticRegression(C=0.01, random_state=42, max_iter=5000)),
               ("LR10", LogisticRegression(C=10.0, random_state=42, max_iter=5000))]:
    mt.fit(sv, y_v)
    a = accuracy_score(y_v, (mt.predict_proba(sv)[:,1] > 0.5).astype(int))
    print(f"  Meta {nm}: {a:.4f}")
    if a > best_meta_acc:
        best_meta_acc, best_meta, best_meta_name = a, mt, nm

# ============================================================
# TEST SET
# ============================================================
print("\n" + "="*60)
print("TEST SET EVALUATION")
print("="*60)

xa = accuracy_score(y_te, (xgb_m.predict_proba(X_te)[:,1] > 0.5).astype(int))
ra = accuracy_score(y_te, (rf_m.predict_proba(X_te)[:,1] > 0.5).astype(int))
la = accuracy_score(y_te, (lr_m.predict_proba(X_te)[:,1] > 0.5).astype(int))

st = np.column_stack([xgb_m.predict_proba(X_te)[:,1], rf_m.predict_proba(X_te)[:,1], lr_m.predict_proba(X_te)[:,1]])
ep = best_meta.predict_proba(st)[:,1]
ea = accuracy_score(y_te, (ep > 0.5).astype(int))
br = brier_score_loss(y_te, ep)

print(f"  XGBoost:            {xa:.4f}")
print(f"  RandomForest:       {ra:.4f}")
print(f"  LogisticRegression: {la:.4f}")
print(f"  ENSEMBLE:           {ea:.4f}")
print(f"  Brier:              {br:.6f}")

# ============================================================
# WALK-FORWARD (last 20 windows)
# ============================================================
print("\nWalk-Forward (20 recent windows)...")
all_d = pd.concat([train_df, val_df, test_df], ignore_index=True).sort_values("date").reset_index(drop=True)
Xa = all_d[FEATURES].fillna(0).values
ya = all_d["target"].values
n = len(all_d)
wf = []
for i in range(max(500, n-20*60-60), n-60, 60):
    tX, tY = Xa[i-500:i], ya[i-500:i]
    eX, eY = Xa[i:i+60], ya[i:i+60]
    if len(np.unique(tY))<2 or len(np.unique(eY))<2: continue
    wx = XGBClassifier(**bp_xgb, random_state=42, eval_metric="logloss", n_jobs=-1, verbosity=0)
    wx.fit(tX, tY, verbose=False)
    wr = RandomForestClassifier(**bp_rf, random_state=42, n_jobs=-1)
    wr.fit(tX, tY)
    wl = LogisticRegression(**lr_p)
    wl.fit(tX, tY)
    s_ = np.column_stack([wx.predict_proba(eX)[:,1], wr.predict_proba(eX)[:,1], wl.predict_proba(eX)[:,1]])
    s_t = np.column_stack([wx.predict_proba(tX[-500:])[:,1], wr.predict_proba(tX[-500:])[:,1], wl.predict_proba(tX[-500:])[:,1]])
    wm = LogisticRegression(C=1.0, random_state=42, max_iter=5000)
    wm.fit(s_t, tY[-500:])
    wf.append(accuracy_score(eY, wm.predict(s_)))

if wf:
    print(f"  Windows: {len(wf)}")
    print(f"  Mean:    {np.mean(wf):.4f}")
    print(f"  Median:  {np.median(wf):.4f}")

# ============================================================
# SAVE
# ============================================================
print("\nSaving models...")
dx = XGBClassifier(**bp_xgb, random_state=42, eval_metric="logloss", n_jobs=-1, verbosity=0)
dx.fit(X_tv, y_tv)
dr = RandomForestClassifier(**bp_rf, random_state=42, n_jobs=-1)
dr.fit(X_tv, y_tv)
dl = LogisticRegression(**lr_p)
dl.fit(X_tv, y_tv)
ds = np.column_stack([dx.predict_proba(X_v)[:,1], dr.predict_proba(X_v)[:,1], dl.predict_proba(X_v)[:,1]])
dm = LogisticRegression(C=1.0, random_state=42, max_iter=5000)
dm.fit(ds, y_v)

joblib.dump(dx, os.path.join(MODELS_DIR, "xgboost.pkl"))
joblib.dump(dr, os.path.join(MODELS_DIR, "randomforest.pkl"))
joblib.dump(dl, os.path.join(MODELS_DIR, "logisticregression.pkl"))
joblib.dump(dm, os.path.join(MODELS_DIR, "meta_model.pkl"))
joblib.dump(["XGBoost","RandomForest","LogisticRegression"], os.path.join(MODELS_DIR, "ensemble_models.pkl"))
with open(os.path.join(MODELS_DIR, "best_params.json"), "w") as f:
    json.dump({"XGBoost": bp_xgb, "RandomForest": bp_rf, "LogisticRegression": bp_lr, "meta": best_meta_name}, f, indent=2)

print("\n" + "="*60)
print(f"ENSEMBLE TEST ACC: {ea:.4f}")
if wf:
    print(f"WALK-FORWARD MEAN: {np.mean(wf):.4f}")
print(f"TOTAL TIME: {time.time()-t0:.0f}s")
print("="*60)
