"""
Fast RF tuning + ensemble evaluation. XGB already done, skip it.
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

FEATURES = ["ret_1", "ret_5", "ret_10", "log_vol_chg", "rsi_14", "macd",
            "bb_pos", "atr_14", "obv_slope", "sma_ratio", "rvol_5", "rvol_20"]

train_df = pd.read_csv(os.path.join(MULTI_DIR, "train_multi.csv"))
val_df = pd.read_csv(os.path.join(MULTI_DIR, "val_multi.csv"))
test_df = pd.read_csv(os.path.join(MULTI_DIR, "test_multi.csv"))

X_train = train_df[FEATURES].fillna(0).values
y_train = train_df["target"].values
X_val = val_df[FEATURES].fillna(0).values
y_val = val_df["target"].values
X_test = test_df[FEATURES].fillna(0).values
y_test = test_df["target"].values
X_trainval = np.vstack([X_train, X_val])
y_trainval = np.concatenate([y_train, y_val])

# Load best XGB params from first run
with open(os.path.join(MODELS_DIR, "best_params.json")) as f:
    saved = json.load(f)
best_xgb_params = saved["XGBoost"]
best_lr_params = saved["LogisticRegression"]
print(f"Loaded XGB params, LR params from previous run")

# ============================================================
# TUNE RF (30 trials only, smaller search)
# ============================================================
print("\nOPTUNA: RandomForest (30 trials)")
def rf_objective(trial):
    p = {
        "n_estimators": trial.suggest_int("n_estimators", 150, 500, step=50),
        "max_depth": trial.suggest_int("max_depth", 5, 20),
        "min_samples_leaf": trial.suggest_int("min_samples_leaf", 5, 50),
        "max_features": trial.suggest_categorical("max_features", ["sqrt", 0.5]),
        "random_state": 42, "n_jobs": -1,
    }
    m = RandomForestClassifier(**p)
    m.fit(X_train, y_train)
    return -accuracy_score(y_val, m.predict(X_val))

study_rf = optuna.create_study(direction="minimize", sampler=TPESampler(seed=42))
study_rf.optimize(rf_objective, n_trials=30, show_progress_bar=True)
best_rf_params = study_rf.best_params
print(f"Best RF val acc: {-study_rf.best_value:.4f}")

# ============================================================
# TRAIN ALL BASE MODELS
# ============================================================
print("\nTraining all models...")
xgb_m = XGBClassifier(**best_xgb_params, random_state=42, eval_metric="logloss", n_jobs=-1, verbosity=0)
xgb_m.fit(X_train, y_train)

rf_m = RandomForestClassifier(**best_rf_params, random_state=42, n_jobs=-1)
rf_m.fit(X_train, y_train)

lr_params = {**best_lr_params, "max_iter": 5000, "random_state": 42, "n_jobs": -1}
if lr_params.get("penalty") == "l1":
    lr_params["solver"] = "saga"
lr_m = LogisticRegression(**lr_params)
lr_m.fit(X_train, y_train)

# Stacking probas on val
stack_val = np.column_stack([
    xgb_m.predict_proba(X_val)[:, 1],
    rf_m.predict_proba(X_val)[:, 1],
    lr_m.predict_proba(X_val)[:, 1],
])

# Meta candidates
best_meta, best_meta_acc, best_meta_name = None, 0, ""
for name, meta in [
    ("LR_C1", LogisticRegression(C=1.0, random_state=42, max_iter=5000)),
    ("LR_C01", LogisticRegression(C=0.01, random_state=42, max_iter=5000)),
    ("LR_C10", LogisticRegression(C=10.0, random_state=42, max_iter=5000)),
    ("LR_l1", LogisticRegression(C=1.0, penalty="l1", solver="saga", random_state=42, max_iter=5000)),
]:
    meta.fit(stack_val, y_val)
    acc = accuracy_score(y_val, (meta.predict_proba(stack_val)[:, 1] > 0.5).astype(int))
    print(f"  Meta {name}: val acc={acc:.4f}")
    if acc > best_meta_acc:
        best_meta_acc, best_meta, best_meta_name = acc, meta, name

print(f"Best meta: {best_meta_name} ({best_meta_acc:.4f})")

# ============================================================
# TEST SET EVALUATION
# ============================================================
print("\n" + "="*60)
print("TEST SET RESULTS")
print("="*60)

xgb_acc = accuracy_score(y_test, (xgb_m.predict_proba(X_test)[:, 1] > 0.5).astype(int))
rf_acc = accuracy_score(y_test, (rf_m.predict_proba(X_test)[:, 1] > 0.5).astype(int))
lr_acc = accuracy_score(y_test, (lr_m.predict_proba(X_test)[:, 1] > 0.5).astype(int))

stack_test = np.column_stack([
    xgb_m.predict_proba(X_test)[:, 1],
    rf_m.predict_proba(X_test)[:, 1],
    lr_m.predict_proba(X_test)[:, 1],
])
ens_prob = best_meta.predict_proba(stack_test)[:, 1]
ens_acc = accuracy_score(y_test, (ens_prob > 0.5).astype(int))
brier = brier_score_loss(y_test, ens_prob)

print(f"  XGBoost:            {xgb_acc:.4f}")
print(f"  RandomForest:       {rf_acc:.4f}")
print(f"  LogisticRegression: {lr_acc:.4f}")
print(f"  ENSEMBLE:           {ens_acc:.4f}")
print(f"  Brier score:        {brier:.6f}")

# ============================================================
# WALK-FORWARD (abbreviated: 30 windows)
# ============================================================
print("\nWalk-Forward (30 recent windows)...")
all_data = pd.concat([train_df, val_df, test_df], ignore_index=True).sort_values("date").reset_index(drop=True)
X_all = all_data[FEATURES].fillna(0).values
y_all = all_data["target"].values
n = len(all_data)
wf_accs = []
start = max(500, n - 30*60 - 60)

for i in range(start, n - 60, 60):
    trX, trY = X_all[i-500:i], y_all[i-500:i]
    teX, teY = X_all[i:i+60], y_all[i:i+60]
    if len(np.unique(trY)) < 2 or len(np.unique(teY)) < 2:
        continue
    wx = XGBClassifier(**best_xgb_params, random_state=42, eval_metric="logloss", n_jobs=-1, verbosity=0)
    wx.fit(trX, trY, verbose=False)
    wr = RandomForestClassifier(**best_rf_params, random_state=42, n_jobs=-1)
    wr.fit(trX, trY)
    wl = LogisticRegression(**lr_params)
    wl.fit(trX, trY)
    stk = np.column_stack([wx.predict_proba(teX)[:,1], wr.predict_proba(teX)[:,1], wl.predict_proba(teX)[:,1]])
    stk_tr = np.column_stack([wx.predict_proba(trX[-500:])[:,1], wr.predict_proba(trX[-500:])[:,1], wl.predict_proba(trX[-500:])[:,1]])
    wm = LogisticRegression(C=1.0, random_state=42, max_iter=5000)
    wm.fit(stk_tr, trY[-500:])
    wf_accs.append(accuracy_score(teY, wm.predict(stk)))

if wf_accs:
    print(f"  Windows: {len(wf_accs)}")
    print(f"  Mean:    {np.mean(wf_accs):.4f}")
    print(f"  Median:  {np.median(wf_accs):.4f}")
    print(f"  Min/Max: {np.min(wf_accs):.4f} / {np.max(wf_accs):.4f}")

# ============================================================
# SAVE DEPLOYMENT MODELS
# ============================================================
print("\nSaving deployment models...")
dep_xgb = XGBClassifier(**best_xgb_params, random_state=42, eval_metric="logloss", n_jobs=-1, verbosity=0)
dep_xgb.fit(X_trainval, y_trainval)
dep_rf = RandomForestClassifier(**best_rf_params, random_state=42, n_jobs=-1)
dep_rf.fit(X_trainval, y_trainval)
dep_lr = LogisticRegression(**lr_params)
dep_lr.fit(X_trainval, y_trainval)
dep_stack = np.column_stack([dep_xgb.predict_proba(X_val)[:,1], dep_rf.predict_proba(X_val)[:,1], dep_lr.predict_proba(X_val)[:,1]])
dep_meta = LogisticRegression(C=1.0, random_state=42, max_iter=5000)
dep_meta.fit(dep_stack, y_val)

joblib.dump(dep_xgb, os.path.join(MODELS_DIR, "xgboost.pkl"))
joblib.dump(dep_rf, os.path.join(MODELS_DIR, "randomforest.pkl"))
joblib.dump(dep_lr, os.path.join(MODELS_DIR, "logisticregression.pkl"))
joblib.dump(dep_meta, os.path.join(MODELS_DIR, "meta_model.pkl"))
joblib.dump(["XGBoost", "RandomForest", "LogisticRegression"], os.path.join(MODELS_DIR, "ensemble_models.pkl"))
with open(os.path.join(MODELS_DIR, "best_params.json"), "w") as f:
    json.dump({"XGBoost": best_xgb_params, "RandomForest": best_rf_params, "LogisticRegression": best_lr_params, "meta": best_meta_name}, f, indent=2)
print("Done!")
