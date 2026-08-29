"""
Enhanced Ensemble Tuning v2
- Tests 1d/3d/5d horizons with quick XGB scan
- Tunes full ensemble on best horizon
- Feature selection via importance
- Walk-forward validation
- Saves deployment models
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

ALL_FEATURES = [
    "ret_1", "ret_5", "ret_10", "log_vol_chg", "rsi_14", "macd",
    "bb_pos", "atr_14", "obv_slope", "sma_ratio", "rvol_5", "rvol_20",
    "stoch_k", "stoch_d", "cci", "williams_r", "roc_10",
    "adx", "aroon_up", "aroon_down", "sma_5_20_cross",
    "mfi", "volume_sma_ratio",
    "price_vs_high20", "price_vs_low20",
    "ret_20", "rvol_10",
]

t0 = time.time()

# ============================================================
# PHASE 1: Quick horizon scan with XGB (20 trials each)
# ============================================================
print("=" * 60)
print("PHASE 1: Horizon Scan (XGB only, 20 trials each)")
print("=" * 60)

horizon_results = {}

for horizon in ["1d", "3d", "5d"]:
    print(f"\n--- {horizon} target ---")
    train = pd.read_csv(os.path.join(MULTI_DIR, f"train_multi_v2_{horizon}.csv"))
    val = pd.read_csv(os.path.join(MULTI_DIR, f"val_multi_v2_{horizon}.csv"))

    X_tr = train[ALL_FEATURES].fillna(0).values
    y_tr = train["target"].values
    X_v = val[ALL_FEATURES].fillna(0).values
    y_v = val["target"].values

    def obj(trial):
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

    s = optuna.create_study(direction="minimize", sampler=TPESampler(seed=42))
    s.optimize(obj, n_trials=20, show_progress_bar=True)
    horizon_results[horizon] = {"best_val": -s.best_value, "params": s.best_params}
    print(f"  Best val acc: {-s.best_value:.4f}")

# Pick best horizon
best_horizon = max(horizon_results, key=lambda h: horizon_results[h]["best_val"])
print(f"\nBest horizon: {best_horizon} ({horizon_results[best_horizon]['best_val']:.4f})")
base_xgb_params = horizon_results[best_horizon]["params"]

# ============================================================
# PHASE 2: Feature selection on best horizon
# ============================================================
print("\n" + "=" * 60)
print("PHASE 2: Feature Selection")
print("=" * 60)

train = pd.read_csv(os.path.join(MULTI_DIR, f"train_multi_v2_{best_horizon}.csv"))
val = pd.read_csv(os.path.join(MULTI_DIR, f"val_multi_v2_{best_horizon}.csv"))
test = pd.read_csv(os.path.join(MULTI_DIR, f"test_multi_v2_{best_horizon}.csv"))

X_tr = train[ALL_FEATURES].fillna(0).values
y_tr = train["target"].values
X_v = val[ALL_FEATURES].fillna(0).values
y_v = val["target"].values
X_te = test[ALL_FEATURES].fillna(0).values
y_te = test["target"].values

# Feature importance via XGB
xgb_imp = XGBClassifier(**base_xgb_params, random_state=42, eval_metric="logloss", verbosity=0, n_jobs=-1)
xgb_imp.fit(X_tr, y_tr)
imp = pd.Series(xgb_imp.feature_importances_, index=ALL_FEATURES).sort_values(ascending=False)

# Try top-K features
best_feat_count, best_feat_acc = len(ALL_FEATURES), 0
for k in [10, 12, 15, 18, 20, 22, 25, 27]:
    top_feats = list(imp.head(k).index)
    Xtr_k = train[top_feats].fillna(0).values
    Xv_k = val[top_feats].fillna(0).values
    m = XGBClassifier(**base_xgb_params, random_state=42, eval_metric="logloss", verbosity=0, n_jobs=-1)
    m.fit(Xtr_k, y_tr)
    acc = accuracy_score(y_v, (m.predict_proba(Xv_k)[:,1] > 0.5).astype(int))
    print(f"  Top {k:2d} features: val acc = {acc:.4f}")
    if acc >= best_feat_acc:
        best_feat_acc, best_feat_count = acc, k

selected_features = list(imp.head(best_feat_count).index)
print(f"\nSelected {best_feat_count} features: {selected_features}")

X_tr = train[selected_features].fillna(0).values
X_v = val[selected_features].fillna(0).values
X_te = test[selected_features].fillna(0).values
X_tv = np.vstack([X_tr, X_v])
y_tv = np.concatenate([y_tr, y_v])

# ============================================================
# PHASE 3: Full ensemble tuning with selected features
# ============================================================
print("\n" + "=" * 60)
print(f"PHASE 3: Ensemble Tuning ({best_horizon} target, {best_feat_count} features)")
print("=" * 60)

# XGB: 40 more trials with feature subset
print("\n[1/3] Tuning XGBoost (40 trials)...")
def xgb_obj(trial):
    p = {"max_depth": trial.suggest_int("max_depth", 3, 7),
         "n_estimators": trial.suggest_int("n_estimators", 100, 500, step=50),
         "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
         "subsample": trial.suggest_float("subsample", 0.5, 1.0),
         "colsample_bytree": trial.suggest_float("colsample_bytree", 0.4, 1.0),
         "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
         "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
         "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
         "random_state": 42, "eval_metric": "logloss", "n_jobs": -1, "verbosity": 0}
    m = XGBClassifier(**p)
    m.fit(X_tr, y_tr, eval_set=[(X_v, y_v)], verbose=False)
    return -accuracy_score(y_v, (m.predict_proba(X_v)[:,1] > 0.5).astype(int))

s_xgb = optuna.create_study(direction="minimize", sampler=TPESampler(seed=42))
s_xgb.optimize(xgb_obj, n_trials=40, show_progress_bar=True)
bp_xgb = s_xgb.best_params
print(f"  Best XGB val acc: {-s_xgb.best_value:.4f}")

# RF: 15 trials
print("\n[2/3] Tuning RandomForest (15 trials)...")
def rf_obj(trial):
    p = {"n_estimators": trial.suggest_int("n_estimators", 200, 500, step=100),
         "max_depth": trial.suggest_int("max_depth", 5, 15),
         "min_samples_leaf": trial.suggest_int("min_samples_leaf", 10, 50),
         "random_state": 42, "n_jobs": -1}
    m = RandomForestClassifier(**p)
    m.fit(X_tr, y_tr)
    return -accuracy_score(y_v, (m.predict_proba(X_v)[:,1] > 0.5).astype(int))

s_rf = optuna.create_study(direction="minimize", sampler=TPESampler(seed=42))
s_rf.optimize(rf_obj, n_trials=15, show_progress_bar=True)
bp_rf = s_rf.best_params
print(f"  Best RF val acc: {-s_rf.best_value:.4f}")

# LR: 15 trials
print("\n[3/3] Tuning LogisticRegression (15 trials)...")
def lr_obj(trial):
    C = trial.suggest_float("C", 1e-3, 100.0, log=True)
    penalty = trial.suggest_categorical("penalty", ["l1", "l2"])
    m = LogisticRegression(C=C, penalty=penalty, solver="saga", max_iter=5000, random_state=42, n_jobs=-1)
    m.fit(X_tr, y_tr)
    return -accuracy_score(y_v, (m.predict_proba(X_v)[:,1] > 0.5).astype(int))

s_lr = optuna.create_study(direction="minimize", sampler=TPESampler(seed=42))
s_lr.optimize(lr_obj, n_trials=15, show_progress_bar=True)
bp_lr = s_lr.best_params
print(f"  Best LR val acc: {-s_lr.best_value:.4f}")

print(f"\nTuning time: {time.time()-t0:.0f}s")

# ============================================================
# PHASE 4: Train, stack, evaluate
# ============================================================
print("\n" + "=" * 60)
print("PHASE 4: Evaluation")
print("=" * 60)

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
               ("LR10", LogisticRegression(C=10.0, random_state=42, max_iter=5000)),
               ("LR001", LogisticRegression(C=0.001, random_state=42, max_iter=5000))]:
    mt.fit(sv, y_v)
    a = accuracy_score(y_v, (mt.predict_proba(sv)[:,1] > 0.5).astype(int))
    print(f"  Meta {nm}: {a:.4f}")
    if a > best_meta_acc:
        best_meta_acc, best_meta, best_meta_name = a, mt, nm

# Test set
print("\n--- Test Set ---")
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
# PHASE 5: Walk-forward (20 windows)
# ============================================================
print("\n--- Walk-Forward (20 windows) ---")
all_d = pd.concat([train, val, test], ignore_index=True).sort_values("date").reset_index(drop=True)
Xa = all_d[selected_features].fillna(0).values
ya = all_d["target"].values
n = len(all_d)
wf = []
for i in range(max(500, n - 20*60 - 60), n - 60, 60):
    tX, tY = Xa[i-500:i], ya[i-500:i]
    eX, eY = Xa[i:i+60], ya[i:i+60]
    if len(np.unique(tY)) < 2 or len(np.unique(eY)) < 2:
        continue
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
    print(f"  Min/Max: {np.min(wf):.4f} / {np.max(wf):.4f}")

# ============================================================
# PHASE 6: Save deployment models
# ============================================================
print("\n" + "=" * 60)
print("PHASE 6: Saving Deployment Models")
print("=" * 60)

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
joblib.dump(["XGBoost", "RandomForest", "LogisticRegression"], os.path.join(MODELS_DIR, "ensemble_models.pkl"))

# Save config for inference
config = {
    "horizon": best_horizon,
    "features": selected_features,
    "XGBoost": bp_xgb,
    "RandomForest": bp_rf,
    "LogisticRegression": bp_lr,
    "meta": best_meta_name,
}
with open(os.path.join(MODELS_DIR, "best_params.json"), "w") as f:
    json.dump(config, f, indent=2)

print("\n" + "=" * 60)
print(f"HORIZON:   {best_horizon}")
print(f"FEATURES:  {best_feat_count}")
print(f"ENSEMBLE TEST ACC: {ea:.4f}")
if wf:
    print(f"WALK-FORWARD MEAN: {np.mean(wf):.4f}")
print(f"TOTAL TIME: {time.time()-t0:.0f}s")
print("=" * 60)
