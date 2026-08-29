import warnings; warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, joblib, json
from sklearn.metrics import accuracy_score, brier_score_loss

MULTI_DIR = 'data/multi'
MODELS_DIR = 'service/models'

with open(f'{MODELS_DIR}/best_params.json') as f:
    cfg = json.load(f)

FEATURES = cfg['features']
horizon = cfg['horizon']
print(f'Horizon: {horizon}')
print(f'Features ({len(FEATURES)}): {FEATURES}')

train = pd.read_csv(f'{MULTI_DIR}/train_multi_v2_{horizon}.csv')
val = pd.read_csv(f'{MULTI_DIR}/val_multi_v2_{horizon}.csv')
test = pd.read_csv(f'{MULTI_DIR}/test_multi_v2_{horizon}.csv')

X_tr = train[FEATURES].fillna(0).values; y_tr = train['target'].values
X_v = val[FEATURES].fillna(0).values; y_v = val['target'].values
X_te = test[FEATURES].fillna(0).values; y_te = test['target'].values

xgb_m = joblib.load(f'{MODELS_DIR}/xgboost.pkl')
rf_m = joblib.load(f'{MODELS_DIR}/randomforest.pkl')
lr_m = joblib.load(f'{MODELS_DIR}/logisticregression.pkl')
meta_m = joblib.load(f'{MODELS_DIR}/meta_model.pkl')

print(f'\nTrain: {len(X_tr)}, Val: {len(X_v)}, Test: {len(X_te)}')

xa = accuracy_score(y_te, (xgb_m.predict_proba(X_te)[:,1] > 0.5).astype(int))
ra = accuracy_score(y_te, (rf_m.predict_proba(X_te)[:,1] > 0.5).astype(int))
la = accuracy_score(y_te, (lr_m.predict_proba(X_te)[:,1] > 0.5).astype(int))
st = np.column_stack([xgb_m.predict_proba(X_te)[:,1], rf_m.predict_proba(X_te)[:,1], lr_m.predict_proba(X_te)[:,1]])
ep = meta_m.predict_proba(st)[:,1]
ea = accuracy_score(y_te, (ep > 0.5).astype(int))
br = brier_score_loss(y_te, ep)

print(f'\nTEST SET:')
print(f'  XGBoost:            {xa:.4f}')
print(f'  RandomForest:       {ra:.4f}')
print(f'  LogisticRegression: {la:.4f}')
print(f'  ENSEMBLE:           {ea:.4f}')
print(f'  Brier:              {br:.6f}')

print('\n--- Walk-Forward (20 windows) ---')
all_d = pd.concat([train, val, test], ignore_index=True).sort_values('date').reset_index(drop=True)
Xa = all_d[FEATURES].fillna(0).values
ya = all_d['target'].values
n = len(all_d)
wf = []
for i in range(max(500, n - 20*60 - 60), n - 60, 60):
    tX, tY = Xa[i-500:i], ya[i-500:i]
    eX, eY = Xa[i:i+60], ya[i:i+60]
    if len(np.unique(tY)) < 2 or len(np.unique(eY)) < 2:
        continue
    from xgboost import XGBClassifier
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    bp_xgb = cfg['XGBoost']
    bp_rf = cfg['RandomForest']
    bp_lr = cfg['LogisticRegression']
    lr_p = {**bp_lr, 'max_iter': 5000, 'random_state': 42, 'n_jobs': -1}
    if lr_p.get('penalty') == 'l1':
        lr_p['solver'] = 'saga'
    wx = XGBClassifier(**bp_xgb, random_state=42, eval_metric='logloss', n_jobs=-1, verbosity=0)
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
    print(f'  Windows: {len(wf)}')
    print(f'  Mean:    {np.mean(wf):.4f}')
    print(f'  Median:  {np.median(wf):.4f}')
    print(f'  Min/Max: {np.min(wf):.4f} / {np.max(wf):.4f}')
