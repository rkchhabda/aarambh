import sys
sys.path.insert(0, r"C:\Users\r_chh\OneDrive - optgbrc\Apps\GaurviDEEP\service")
from app import fetch_history, compute_features, TICKERS, FEATURES
import pandas as pd

df = fetch_history('AAPL')
print(f"Fetched {len(df)} rows for AAPL")
df = compute_features(df)
print(f"Features computed: {df.shape}")
last = df.iloc[-1]
print(f"Close: {last['close']}, SMA200: {last['sma_200']}")
print(f"Last row features: {df[FEATURES].iloc[-1].values}")