import os, sys
import pandas as pd
import numpy as np
from scipy import stats

DATA_FILE = 'data/multi/historical_10y_raw.csv'
print(f"Loading dataset from {DATA_FILE}...")
df_raw = pd.read_csv(DATA_FILE)
n_raw = len(df_raw)
n_tickers = df_raw["ticker"].nunique()
print(f"Raw rows: {n_raw:,}, Unique tickers: {n_tickers}")

records = []
for ticker, group in df_raw.groupby('ticker', sort=False):
    group = group.sort_values('date').reset_index(drop=True)
    c = group['Close']
    sma_200 = c.rolling(200).mean()
    # 5-trading-day forward return: (Close[t+5] - Close[t]) / Close[t] * 100%
    fwd_ret_5d = (c.shift(-5) / c - 1.0) * 100.0
    sma_dist_pct = ((c - sma_200) / sma_200) * 100.0
    
    sub = pd.DataFrame({
        'ticker': group['ticker'],
        'date': group['date'],
        'Close': c,
        'sma_200': sma_200,
        'sma_dist_pct': sma_dist_pct,
        'fwd_ret_5d': fwd_ret_5d
    }).dropna()
    records.append(sub)

df = pd.concat(records, ignore_index=True)
total_n = len(df)
print(f"Total valid post-warmup instances with forward 5-day return: {total_n:,}")
print(f"Date range: {df['date'].min()} to {df['date'].max()}\n")

base_ret = df['fwd_ret_5d']
base_mean = float(base_ret.mean())
base_median = float(base_ret.median())
base_std = float(base_ret.std())
base_se = float(base_std / np.sqrt(total_n))
base_win = float((base_ret > 0).mean() * 100.0)

print("=" * 75)
print("1. UNCONDITIONAL BASELINE (ALL DAYS REGARDLESS OF SMA DISTANCE)")
print("=" * 75)
print(f"Sample Size (N)       : {total_n:,}")
print(f"Mean 5-Day Return     : {base_mean:+.4f}%")
print(f"Median 5-Day Return   : {base_median:+.4f}%")
print(f"Standard Deviation    : {base_std:.4f}%")
print(f"Standard Error (SE)   : {base_se:.4f}%")
print(f"Min / Max Range       : [{base_ret.min():.2f}%, {base_ret.max():.2f}%]")
print(f"IQR (25th to 75th %)  : [{base_ret.quantile(0.25):.2f}%, {base_ret.quantile(0.75):.2f}%]")
print(f"10th to 90th %        : [{base_ret.quantile(0.10):.2f}%, {base_ret.quantile(0.90):.2f}%]")
print(f"Positive Return %     : {base_win:.2f}% (fraction of 5-day periods > 0%)\n")

bands = [
    ("15% to 40% (Top 10 Scanner typical band)", (df['sma_dist_pct'] >= 15.0) & (df['sma_dist_pct'] <= 40.0)),
    ("0% to 15% (Modest Risk-On / Near-SMA)", (df['sma_dist_pct'] >= 0.0) & (df['sma_dist_pct'] < 15.0)),
    ("> 40% (Extreme Momentum / Extended)", df['sma_dist_pct'] > 40.0),
    ("< 0% (All Risk-Off combined)", df['sma_dist_pct'] < 0.0),
    ("-15% to 0% (Moderate Risk-Off)", (df['sma_dist_pct'] >= -15.0) & (df['sma_dist_pct'] < 0.0)),
    ("< -15% (Deep Distress / Severe Risk-Off)", df['sma_dist_pct'] < -15.0),
]

print("=" * 75)
print("2. CONDITIONAL ANALYSIS ACROSS SMA DISTANCE BANDS")
print("=" * 75)

for label, cond in bands:
    sub = df.loc[cond, 'fwd_ret_5d']
    n = len(sub)
    if n == 0:
        continue
    m = float(sub.mean())
    med = float(sub.median())
    s = float(sub.std())
    se = float(s / np.sqrt(n))
    win = float((sub > 0).mean() * 100.0)
    diff_mean = m - base_mean
    diff_med = med - base_median
    
    # Welch's t-test comparing band vs all other instances
    other = df.loc[~cond, 'fwd_ret_5d']
    t_stat, p_val = stats.ttest_ind(sub, other, equal_var=False)
    
    # Standard errors separation from baseline mean
    se_from_base = diff_mean / se if se > 0 else 0.0

    print(f"\n--- BAND: {label} ---")
    print(f"Sample Size (N)       : {n:,} ({n/total_n*100:.2f}% of total data)")
    print(f"Mean 5-Day Return     : {m:+.4f}%")
    print(f"Difference from Base  : {diff_mean:+.4f}%")
    print(f"Median 5-Day Return   : {med:+.4f}%")
    print(f"Difference from Median: {diff_med:+.4f}%")
    print(f"Standard Deviation    : {s:.4f}%")
    print(f"Standard Error (SE)   : {se:.4f}%")
    print(f"Distance in SE units  : {se_from_base:+.2f} SE")
    print(f"Positive Return %     : {win:.2f}% (Baseline: {base_win:.2f}%)")
    print(f"Min / Max Range       : [{sub.min():.2f}%, {sub.max():.2f}%]")
    print(f"IQR (25th to 75th %)  : [{sub.quantile(0.25):.2f}%, {sub.quantile(0.75):.2f}%]")
    print(f"10th to 90th %        : [{sub.quantile(0.10):.2f}%, {sub.quantile(0.90):.2f}%]")
    print(f"Welch t-test vs Rest  : t = {t_stat:+.3f}, p-value = {p_val:.4e}")
