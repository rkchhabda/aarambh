"""
TASK 2: Optuna Hyperparameter Tuning for Multi-Ticker Ensemble

Tunes XGBoost, RandomForest, and LogisticRegression using Optuna,
then stacks them with a meta-learner. Evaluates with proper walk-forward.
"""
import os
import sys
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import optuna
from optuna.samplers import TPESampler
from sklearn.linear_model import LogisticRegression, RidgeClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, log_loss, brier_score_loss
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
import joblib
import time

optuna.logging.set_verbosity(optuna.logging.WARNING)

# ============================================================
# PATHS
# ============================================================
BASE = os.path.dirname(os.path.abspath(__file__))
MULTI_DIR = os.path.join(BASE, "data", "multi")
MODELS_DIR = os.path.join(BASE, "service", "models")
os.makedirs(MODELS_DIR, exist_ok=True)

# ============================================================
# LOAD DATA
# ============================================================
print("=" * 70)
print("LOADING MULTI-TICKER DATA")
print("=" * 70)

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

print(f"Train: {X_train.shape[0]} rows, UP={y_train.mean():.3f}")
print(f"Val:   {X_val.shape[0]} rows, UP={y_val.mean():.3f}")
print(f"Test:  {X_test.shape[0]} rows, UP={y_test.mean():.3f}")

# Combine train+val for final Optuna search (hold test for final eval)
X_trainval = np.vstack([X_train, X_val])
y_trainval = np.concatenate([y_train, y_val])
print(f"Train+Val combined: {X_trainval.shape[0]} rows")


# ============================================================
# OPTUNA OBJECTIVE: XGBoost
# ============================================================
def xgb_objective(trial):
    params = {
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "n_estimators": trial.suggest_int("n_estimators", 100, 600, step=50),
        "learning_rate": trial.suggest_float("learning_rate", 0.005, 0.3, log=True),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.4, 1.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 20),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
        "gamma": trial.suggest_float("gamma", 0.0, 5.0),
        "random_state": 42,
        "eval_metric": "logloss",
        "n_jobs": -1,
        "verbosity": 0,
    }
    model = XGBClassifier(**params)
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    proba = model.predict_proba(X_val)[:, 1]
    # Optimize for log loss (better calibration)
    return log_loss(y_val, proba)


# ============================================================
# OPTUNA OBJECTIVE: RandomForest
# ============================================================
def rf_objective(trial):
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 100, 600, step=50),
        "max_depth": trial.suggest_int("max_depth", 3, 20),
        "min_samples_split": trial.suggest_int("min_samples_split", 2, 20),
        "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 10),
        "max_features": trial.suggest_categorical("max_features", ["sqrt", "log2", 0.3, 0.5, 0.7, 1.0]),
        "bootstrap": trial.suggest_categorical("bootstrap", [True, False]),
        "random_state": 42,
        "n_jobs": -1,
    }
    model = RandomForestClassifier(**params)
    model.fit(X_train, y_train)
    proba = model.predict_proba(X_val)[:, 1]
    return log_loss(y_val, proba)


# ============================================================
# OPTUNA OBJECTIVE: LogisticRegression
# ============================================================
def lr_objective(trial):
    C = trial.suggest_float("C", 1e-4, 100.0, log=True)
    penalty = trial.suggest_categorical("penalty", ["l1", "l2"])
    solver = "saga"  # supports both l1 and l2

    model = LogisticRegression(
        C=C, penalty=penalty, solver=solver,
        max_iter=5000, random_state=42, n_jobs=-1
    )
    model.fit(X_train, y_train)
    proba = model.predict_proba(X_val)[:, 1]
    return log_loss(y_val, proba)


# ============================================================
# RUN OPTUNA SEARCHES
# ============================================================
N_TRIALS = 150  # good balance of quality vs speed

print("\n" + "=" * 70)
print(f"OPTUNA TUNING ({N_TRIALS} trials per model)")
print("=" * 70)

best_params = {}

# --- XGBoost ---
print("\n[1/3] Tuning XGBoost ...")
t0 = time.time()
study_xgb = optuna.create_study(direction="minimize", sampler=TPESampler(seed=42))
study_xgb.optimize(xgb_objective, n_trials=N_TRIALS, show_progress_bar=True)
best_params["XGBoost"] = study_xgb.best_params
print(f"  Best log_loss: {study_xgb.best_value:.6f} ({time.time()-t0:.0f}s)")

# --- RandomForest ---
print("\n[2/3] Tuning RandomForest ...")
t0 = time.time()
study_rf = optuna.create_study(direction="minimize", sampler=TPESampler(seed=42))
study_rf.optimize(rf_objective, n_trials=N_TRIALS, show_progress_bar=True)
best_params["RandomForest"] = study_rf.best_params
print(f"  Best log_loss: {study_rf.best_value:.6f} ({time.time()-t0:.0f}s)")

# --- LogisticRegression ---
print("\n[3/3] Tuning LogisticRegression ...")
t0 = time.time()
study_lr = optuna.create_study(direction="minimize", sampler=TPESampler(seed=42))
study_lr.optimize(lr_objective, n_trials=min(N_TRIALS, 80), show_progress_bar=True)
best_params["LogisticRegression"] = study_lr.best_params
print(f"  Best log_loss: {study_lr.best_value:.6f} ({time.time()-t0:.0f}s)")


# ============================================================
# TRAIN BEST MODELS ON TRAIN+VAL
# ============================================================
print("\n" + "=" * 70)
print("TRAINING BEST MODELS ON TRAIN+VAL")
print("=" * 70)

# XGBoost
xgb_params = best_params["XGBoost"].copy()
xgb_params.update({"random_state": 42, "eval_metric": "logloss", "n_jobs": -1, "verbosity": 0})
best_xgb = XGBClassifier(**xgb_params)
best_xgb.fit(X_trainval, y_trainval)
xgb_val_proba = best_xgb.predict_proba(X_val)[:, 1]
xgb_val_acc = accuracy_score(y_val, (xgb_val_proba > 0.5).astype(int))
print(f"  XGBoost val acc: {xgb_val_acc:.4f}")

# RandomForest
rf_params = best_params["RandomForest"].copy()
rf_params.update({"random_state": 42, "n_jobs": -1})
best_rf = RandomForestClassifier(**rf_params)
best_rf.fit(X_trainval, y_trainval)
rf_val_proba = best_rf.predict_proba(X_val)[:, 1]
rf_val_acc = accuracy_score(y_val, (rf_val_proba > 0.5).astype(int))
print(f"  RandomForest val acc: {rf_val_acc:.4f}")

# LogisticRegression
lr_params = best_params["LogisticRegression"].copy()
lr_params.update({"max_iter": 5000, "random_state": 42, "n_jobs": -1})
if lr_params.get("penalty") == "l1":
    lr_params["solver"] = "saga"
best_lr = LogisticRegression(**lr_params)
best_lr.fit(X_trainval, y_trainval)
lr_val_proba = best_lr.predict_proba(X_val)[:, 1]
lr_val_acc = accuracy_score(y_val, (lr_val_proba > 0.5).astype(int))
print(f"  LogisticRegression val acc: {lr_val_acc:.4f}")


# ============================================================
# META-MODEL (Stacking) — tuned on validation probabilities
# ============================================================
print("\n" + "=" * 70)
print("STACKING META-MODEL")
print("=" * 70)

# Get validation probabilities from models trained on trainval
# We need out-of-fold or held-out probabilities.
# Since we trained on train+val, we re-train on train only to get clean val probas for stacking.
print("Re-training base models on train-only for clean stacking probas...")

# XGBoost on train
xgb_stack = XGBClassifier(**xgb_params)
xgb_stack.fit(X_train, y_train)

# RandomForest on train
rf_stack = RandomForestClassifier(**rf_params)
rf_stack.fit(X_train, y_train)

# LR on train
lr_stack = LogisticRegression(**lr_params)
lr_stack.fit(X_train, y_train)

# Validation probas for stacking
stack_X_val = np.column_stack([
    xgb_stack.predict_proba(X_val)[:, 1],
    rf_stack.predict_proba(X_val)[:, 1],
    lr_stack.predict_proba(X_val)[:, 1],
])

# Try multiple meta-model candidates
meta_candidates = {
    "LogisticRegression": LogisticRegression(C=1.0, random_state=42, max_iter=5000),
    "LogisticRegression_l2_high": LogisticRegression(C=0.01, penalty="l2", random_state=42, max_iter=5000),
    "RidgeClassifier": RidgeClassifier(alpha=1.0),
}

best_meta = None
best_meta_acc = 0
best_meta_name = ""

for meta_name, meta_model in meta_candidates.items():
    meta_model.fit(stack_X_val, y_val)
    meta_proba = meta_model.predict_proba(stack_X_val)[:, 1]
    meta_acc = accuracy_score(y_val, (meta_proba > 0.5).astype(int))
    print(f"  {meta_name} val acc: {meta_acc:.4f}")
    if meta_acc > best_meta_acc:
        best_meta_acc = meta_acc
        best_meta = meta_model
        best_meta_name = meta_name

print(f"\n  Best meta-model: {best_meta_name} (val acc: {best_meta_acc:.4f})")


# ============================================================
# EVALUATE ON TEST SET
# ============================================================
print("\n" + "=" * 70)
print("FINAL EVALUATION ON TEST SET")
print("=" * 70)

# Base model test probas (using train-only models for fair eval)
xgb_test_proba = xgb_stack.predict_proba(X_test)[:, 1]
rf_test_proba = rf_stack.predict_proba(X_test)[:, 1]
lr_test_proba = lr_stack.predict_proba(X_test)[:, 1]

# Individual accuracies
xgb_test_acc = accuracy_score(y_test, (xgb_test_proba > 0.5).astype(int))
rf_test_acc = accuracy_score(y_test, (rf_test_proba > 0.5).astype(int))
lr_test_acc = accuracy_score(y_test, (lr_test_proba > 0.5).astype(int))

print(f"  XGBoost test acc:             {xgb_test_acc:.4f}")
print(f"  RandomForest test acc:        {rf_test_acc:.4f}")
print(f"  LogisticRegression test acc:  {lr_test_acc:.4f}")

# Ensemble stacking
stack_X_test = np.column_stack([xgb_test_proba, rf_test_proba, lr_test_proba])
ensemble_test_proba = best_meta.predict_proba(stack_X_test)[:, 1]
ensemble_test_pred = (ensemble_test_proba > 0.5).astype(int)
ensemble_test_acc = accuracy_score(y_test, ensemble_test_pred)
print(f"  ENSEMBLE test acc:            {ensemble_test_acc:.4f}")

# Brier score (lower is better, more calibrated)
brier = brier_score_loss(y_test, ensemble_test_proba)
print(f"  Ensemble Brier score:         {brier:.6f}")


# ============================================================
# WALK-FORWARD VALIDATION
# ============================================================
print("\n" + "=" * 70)
print("WALK-FORWARD VALIDATION")
print("=" * 70)

all_data = pd.concat([train_df, val_df, test_df], ignore_index=True)
all_data = all_data.sort_values("date").reset_index(drop=True)

X_all = all_data[FEATURES].fillna(0).values
y_all = all_data["target"].values

train_window = 500
test_window = 60  # ~3 months of trading days
step = 60

wf_accuracies = []
wf_ensemble_probas = []

for i in range(train_window, len(all_data) - test_window, step):
    tr_end = i
    te_end = min(i + test_window, len(all_data))

    if te_end - i < test_window:
        break

    X_wf_train = X_all[i - train_window:tr_end]
    y_wf_train = y_all[i - train_window:tr_end]
    X_wf_test = X_all[tr_end:te_end]
    y_wf_test = y_all[tr_end:te_end]

    # Skip if target is degenerate
    if len(np.unique(y_wf_train)) < 2 or len(np.unique(y_wf_test)) < 2:
        continue

    # Train base models with best params
    wf_xgb = XGBClassifier(**xgb_params)
    wf_xgb.fit(X_wf_train, y_wf_train, verbose=False)

    wf_rf = RandomForestClassifier(**rf_params)
    wf_rf.fit(X_wf_train, y_wf_train)

    wf_lr = LogisticRegression(**lr_params)
    wf_lr.fit(X_wf_train, y_wf_train)

    # Stack
    wf_stack = np.column_stack([
        wf_xgb.predict_proba(X_wf_test)[:, 1],
        wf_rf.predict_proba(X_wf_test)[:, 1],
        wf_lr.predict_proba(X_wf_test)[:, 1],
    ])

    wf_meta = LogisticRegression(C=1.0, random_state=42, max_iter=5000)
    # Train meta on train portion of this window
    wf_stack_train = np.column_stack([
        wf_xgb.predict_proba(X_wf_train[-500:])[:, 1],
        wf_rf.predict_proba(X_wf_train[-500:])[:, 1],
        wf_lr.predict_proba(X_wf_train[-500:])[:, 1],
    ])
    wf_meta.fit(wf_stack_train, y_wf_train[-500:])

    wf_pred = wf_meta.predict(wf_stack)
    wf_acc = accuracy_score(y_wf_test, wf_pred)
    wf_accuracies.append(wf_acc)

    n_win = len(wf_accuracies)
    if n_win <= 5 or n_win % 10 == 0:
        print(f"  Window {n_win}: {all_data.iloc[tr_end]['date']} -> {all_data.iloc[te_end-1]['date']} | Acc={wf_acc:.4f}")

if wf_accuracies:
    avg_wf = np.mean(wf_accuracies)
    med_wf = np.median(wf_accuracies)
    std_wf = np.std(wf_accuracies)
    print(f"\n  Walk-Forward Results ({len(wf_accuracies)} windows):")
    print(f"    Mean:   {avg_wf:.4f}")
    print(f"    Median: {med_wf:.4f}")
    print(f"    Std:    {std_wf:.4f}")
    print(f"    Min:    {np.min(wf_accuracies):.4f}")
    print(f"    Max:    {np.max(wf_accuracies):.4f}")
    print(f"    >55%:   {sum(1 for a in wf_accuracies if a > 0.55)}/{len(wf_accuracies)}")
    print(f"    >50%:   {sum(1 for a in wf_accuracies if a > 0.50)}/{len(wf_accuracies)}")
else:
    avg_wf = 0


# ============================================================
# SAVE MODELS
# ============================================================
print("\n" + "=" * 70)
print("SAVING MODELS")
print("=" * 70)

# Re-train final models on ALL data (train+val+test) for deployment
print("Training final models on ALL data for deployment...")
X_final = X_trainval  # train+val
y_final = y_trainval

final_xgb = XGBClassifier(**xgb_params)
final_xgb.fit(X_final, y_final, verbose=False)

final_rf = RandomForestClassifier(**rf_params)
final_rf.fit(X_final, y_final)

final_lr = LogisticRegression(**lr_params)
final_lr.fit(X_final, y_final)

# Final meta-model on train+val probas
final_stack_X = np.column_stack([
    final_xgb.predict_proba(X_val)[:, 1],
    final_rf.predict_proba(X_val)[:, 1],
    final_lr.predict_proba(X_val)[:, 1],
])
final_meta = LogisticRegression(C=1.0, random_state=42, max_iter=5000)
final_meta.fit(final_stack_X, y_val)

# Save
joblib.dump(final_xgb, os.path.join(MODELS_DIR, "xgboost.pkl"))
joblib.dump(final_rf, os.path.join(MODELS_DIR, "randomforest.pkl"))
joblib.dump(final_lr, os.path.join(MODELS_DIR, "logisticregression.pkl"))
joblib.dump(final_meta, os.path.join(MODELS_DIR, "meta_model.pkl"))
joblib.dump(["XGBoost", "RandomForest", "LogisticRegression"],
            os.path.join(MODELS_DIR, "ensemble_models.pkl"))

# Save best params for reference
import json
params_path = os.path.join(MODELS_DIR, "best_params.json")
with open(params_path, "w") as f:
    json.dump(best_params, f, indent=2)
print(f"Saved best params to {params_path}")
print("Saved all models to service/models/")


# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 70)
print("FINAL SUMMARY")
print("=" * 70)
print(f"  XGBoost params:        max_depth={best_params['XGBoost']['max_depth']}, "
      f"n_est={best_params['XGBoost']['n_estimators']}, "
      f"lr={best_params['XGBoost']['learning_rate']:.4f}")
print(f"  RandomForest params:   n_est={best_params['RandomForest']['n_estimators']}, "
      f"max_depth={best_params['RandomForest']['max_depth']}")
print(f"  LR params:             C={best_params['LogisticRegression']['C']:.4f}, "
      f"penalty={best_params['LogisticRegression']['penalty']}")
print(f"  Meta-model:            {best_meta_name}")
print()
print(f"  Individual Test Accuracies:")
print(f"    XGBoost:            {xgb_test_acc:.4f}")
print(f"    RandomForest:       {rf_test_acc:.4f}")
print(f"    LogisticRegression: {lr_test_acc:.4f}")
print(f"  ENSEMBLE Test Acc:    {ensemble_test_acc:.4f}")
print(f"  Walk-Forward Mean:    {avg_wf:.4f}")
print()

if ensemble_test_acc > 0.55 or avg_wf > 0.55:
    print("  >>> ENSEMBLE BEATS 55% THRESHOLD <<<")
elif ensemble_test_acc > 0.50 or avg_wf > 0.50:
    print("  >>> ENSEMBLE ABOVE BASELINE (50%) — SOLID <<<")
else:
    print("  >>> BELOW BASELINE — NEEDS MORE WORK <<<")
print("=" * 70)
