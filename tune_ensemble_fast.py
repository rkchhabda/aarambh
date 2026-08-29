"""
TASK 2: Optuna Hyperparameter Tuning — Fast Version
Uses smaller search space and fewer trials to complete in reasonable time.
"""
import os
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import optuna
from optuna.samplers import TPESampler
from sklearn.linear_model import LogisticRegression, RidgeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, log_loss, brier_score_loss
from xgboost import XGBClassifier
import joblib
import json
import time

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

X_train = train_df[FEATURES].fillna(0).values
y_train = train_df["target"].values
X_val = val_df[FEATURES].fillna(0).values
y_val = val_df["target"].values
X_test = test_df[FEATURES].fillna(0).values
y_test = test_df["target"].values

X_trainval = np.vstack([X_train, X_val])
y_trainval = np.concatenate([y_train, y_val])

print(f"Train: {X_train.shape[0]} | Val: {X_val.shape[0]} | Test: {X_test.shape[0]}")

# ============================================================
# TUNE XGBOOST (main driver — usually the strongest)
# ============================================================
print("\n" + "="*60)
print("OPTUNA: XGBoost (100 trials)")
print("="*60)

def xgb_objective(trial):
    p = {
        "max_depth": trial.suggest_int("max_depth", 3, 8),
        "n_estimators": trial.suggest_int("n_estimators", 100, 500, step=50),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-4, 5.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-4, 5.0, log=True),
        "random_state": 42, "eval_metric": "logloss", "n_jobs": -1, "verbosity": 0,
    }
    m = XGBClassifier(**p)
    m.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    return log_loss(y_val, m.predict_proba(X_val)[:, 1])

study_xgb = optuna.create_study(direction="minimize", sampler=TPESampler(seed=42))
study_xgb.optimize(xgb_objective, n_trials=100, show_progress_bar=True)
best_xgb_params = study_xgb.best_params
print(f"Best XGB log_loss: {study_xgb.best_value:.6f}")

# ============================================================
# TUNE RANDOM FOREST (smaller search, 60 trials)
# ============================================================
print("\n" + "="*60)
print("OPTUNA: RandomForest (60 trials)")
print("="*60)

def rf_objective(trial):
    p = {
        "n_estimators": trial.suggest_int("n_estimators", 100, 400, step=50),
        "max_depth": trial.suggest_int("max_depth", 4, 15),
        "min_samples_leaf": trial.suggest_int("min_samples_leaf", 5, 30),
        "max_features": trial.suggest_categorical("max_features", ["sqrt", 0.5, 0.7]),
        "random_state": 42, "n_jobs": -1,
    }
    m = RandomForestClassifier(**p)
    m.fit(X_train, y_train)
    return log_loss(y_val, m.predict_proba(X_val)[:, 1])

study_rf = optuna.create_study(direction="minimize", sampler=TPESampler(seed=42))
study_rf.optimize(rf_objective, n_trials=60, show_progress_bar=True)
best_rf_params = study_rf.best_params
print(f"Best RF log_loss: {study_rf.best_value:.6f}")

# ============================================================
# TUNE LOGISTIC REGRESSION (fast, 40 trials)
# ============================================================
print("\n" + "="*60)
print("OPTUNA: LogisticRegression (40 trials)")
print("="*60)

def lr_objective(trial):
    C = trial.suggest_float("C", 1e-3, 100.0, log=True)
    penalty = trial.suggest_categorical("penalty", ["l1", "l2"])
    m = LogisticRegression(C=C, penalty=penalty, solver="saga",
                           max_iter=5000, random_state=42, n_jobs=-1)
    m.fit(X_train, y_train)
    return log_loss(y_val, m.predict_proba(X_val)[:, 1])

study_lr = optuna.create_study(direction="minimize", sampler=TPESampler(seed=42))
study_lr.optimize(lr_objective, n_trials=40, show_progress_bar=True)
best_lr_params = study_lr.best_params
print(f"Best LR log_loss: {study_lr.best_value:.6f}")

# ============================================================
# TRAIN FINAL MODELS
# ============================================================
print("\n" + "="*60)
print("TRAINING FINAL MODELS")
print("="*60)

# XGBoost on train-only (for stacking probas)
final_xgb = XGBClassifier(**best_xgb_params, random_state=42, eval_metric="logloss", n_jobs=-1, verbosity=0)
final_xgb.fit(X_train, y_train)

final_rf = RandomForestClassifier(**best_rf_params, random_state=42, n_jobs=-1)
final_rf.fit(X_train, y_train)

lr_train_params = {**best_lr_params, "max_iter": 5000, "random_state": 42, "n_jobs": -1}
if lr_train_params.get("penalty") == "l1":
    lr_train_params["solver"] = "saga"
final_lr = LogisticRegression(**lr_train_params)
final_lr.fit(X_train, y_train)

# Validation probas for stacking
stack_val = np.column_stack([
    final_xgb.predict_proba(X_val)[:, 1],
    final_rf.predict_proba(X_val)[:, 1],
    final_lr.predict_proba(X_val)[:, 1],
])

# Meta-model candidates
best_meta = None
best_meta_acc = 0
best_meta_name = ""
for name, meta in [
    ("LR_C1", LogisticRegression(C=1.0, random_state=42, max_iter=5000)),
    ("LR_C01", LogisticRegression(C=0.01, random_state=42, max_iter=5000)),
    ("LR_C10", LogisticRegression(C=10.0, random_state=42, max_iter=5000)),
]:
    meta.fit(stack_val, y_val)
    acc = accuracy_score(y_val, (meta.predict_proba(stack_val)[:, 1] > 0.5).astype(int))
    print(f"  Meta {name}: val acc={acc:.4f}")
    if acc > best_meta_acc:
        best_meta_acc = acc
        best_meta = meta
        best_meta_name = name

print(f"\nBest meta: {best_meta_name} (val acc: {best_meta_acc:.4f})")

# ============================================================
# EVALUATE ON TEST SET
# ============================================================
print("\n" + "="*60)
print("TEST SET EVALUATION")
print("="*60)

xgb_acc = accuracy_score(y_test, (final_xgb.predict_proba(X_test)[:, 1] > 0.5).astype(int))
rf_acc = accuracy_score(y_test, (final_rf.predict_proba(X_test)[:, 1] > 0.5).astype(int))
lr_acc = accuracy_score(y_test, (final_lr.predict_proba(X_test)[:, 1] > 0.5).astype(int))

stack_test = np.column_stack([
    final_xgb.predict_proba(X_test)[:, 1],
    final_rf.predict_proba(X_test)[:, 1],
    final_lr.predict_proba(X_test)[:, 1],
])
ens_pred = (best_meta.predict_proba(stack_test)[:, 1] > 0.5).astype(int)
ens_acc = accuracy_score(y_test, ens_pred)
brier = brier_score_loss(y_test, best_meta.predict_proba(stack_test)[:, 1])

print(f"  XGBoost:             {xgb_acc:.4f}")
print(f"  RandomForest:        {rf_acc:.4f}")
print(f"  LogisticRegression:  {lr_acc:.4f}")
print(f"  ENSEMBLE:            {ens_acc:.4f}")
print(f"  Brier score:         {brier:.6f}")

# ============================================================
# WALK-FORWARD VALIDATION
# ============================================================
print("\n" + "="*60)
print("WALK-FORWARD VALIDATION")
print("="*60)

all_data = pd.concat([train_df, val_df, test_df], ignore_index=True).sort_values("date").reset_index(drop=True)
X_all = all_data[FEATURES].fillna(0).values
y_all = all_data["target"].values

train_window = 500
test_window = 60
step = 60
wf_accs = []

for i in range(train_window, len(all_data) - test_window, step):
    trX = X_all[i-train_window:i]
    tryY = y_all[i-train_window:i]
    teX = X_all[i:i+test_window]
    teY = y_all[i:i+test_window]

    if len(np.unique(tryY)) < 2 or len(np.unique(teY)) < 2:
        continue

    wx = XGBClassifier(**best_xgb_params, random_state=42, eval_metric="logloss", n_jobs=-1, verbosity=0)
    wx.fit(trX, tryY, verbose=False)
    wr = RandomForestClassifier(**best_rf_params, random_state=42, n_jobs=-1)
    wr.fit(trX, tryY)
    wl = LogisticRegression(**lr_train_params)
    wl.fit(trX, tryY)

    stk = np.column_stack([
        wx.predict_proba(teX)[:, 1],
        wr.predict_proba(teX)[:, 1],
        wl.predict_proba(teX)[:, 1],
    ])
    # Train meta on last 500 of train window
    stk_tr = np.column_stack([
        wx.predict_proba(trX[-500:])[:, 1],
        wr.predict_proba(trX[-500:])[:, 1],
        wl.predict_proba(trX[-500:])[:, 1],
    ])
    wm = LogisticRegression(C=1.0, random_state=42, max_iter=5000)
    wm.fit(stk_tr, tryY[-500:])

    wf_accs.append(accuracy_score(teY, wm.predict(stk)))

if wf_accs:
    print(f"  Windows: {len(wf_accs)}")
    print(f"  Mean:    {np.mean(wf_accs):.4f}")
    print(f"  Median:  {np.median(wf_accs):.4f}")
    print(f"  Std:     {np.std(wf_accs):.4f}")
    print(f"  Min/Max: {np.min(wf_accs):.4f} / {np.max(wf_accs):.4f}")
    print(f"  >50%:    {sum(1 for a in wf_accs if a > 0.50)}/{len(wf_accs)}")
    print(f"  >55%:    {sum(1 for a in wf_accs if a > 0.55)}/{len(wf_accs)}")

# ============================================================
# SAVE MODELS (retrain on train+val for deployment)
# ============================================================
print("\n" + "="*60)
print("SAVING DEPLOYMENT MODELS")
print("="*60)

dep_xgb = XGBClassifier(**best_xgb_params, random_state=42, eval_metric="logloss", n_jobs=-1, verbosity=0)
dep_xgb.fit(X_trainval, y_trainval)

dep_rf = RandomForestClassifier(**best_rf_params, random_state=42, n_jobs=-1)
dep_rf.fit(X_trainval, y_trainval)

dep_lr = LogisticRegression(**lr_train_params)
dep_lr.fit(X_trainval, y_trainval)

dep_stack = np.column_stack([
    dep_xgb.predict_proba(X_val)[:, 1],
    dep_rf.predict_proba(X_val)[:, 1],
    dep_lr.predict_proba(X_val)[:, 1],
])
dep_meta = LogisticRegression(C=1.0, random_state=42, max_iter=5000)
dep_meta.fit(dep_stack, y_val)

joblib.dump(dep_xgb, os.path.join(MODELS_DIR, "xgboost.pkl"))
joblib.dump(dep_rf, os.path.join(MODELS_DIR, "randomforest.pkl"))
joblib.dump(dep_lr, os.path.join(MODELS_DIR, "logisticregression.pkl"))
joblib.dump(dep_meta, os.path.join(MODELS_DIR, "meta_model.pkl"))
joblib.dump(["XGBoost", "RandomForest", "LogisticRegression"],
            os.path.join(MODELS_DIR, "ensemble_models.pkl"))

with open(os.path.join(MODELS_DIR, "best_params.json"), "w") as f:
    json.dump({"XGBoost": best_xgb_params, "RandomForest": best_rf_params,
               "LogisticRegression": best_lr_params, "meta": best_meta_name}, f, indent=2)

print("Models saved!")
print(f"\nEnsemble Test Acc: {ens_acc:.4f}")
if wf_accs:
    print(f"Walk-Forward Mean: {np.mean(wf_accs):.4f}")
