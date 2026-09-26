"""
Isolated 10-Year Historical Data Backfill for Nifty 100 Equities.
Fetches daily OHLCV from 2016 to 2026 via Yahoo Chart API.
Saves strictly to an isolated CSV: data/multi/historical_10y_raw.csv
Does NOT touch existing production files, models, or caches.
"""

import os
import sys
import json
import time
import datetime
import urllib.request
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from features.universe import TICKERS
OUT_FILE = os.path.join(BASE_DIR, "data", "multi", "historical_10y_raw.csv")

def fetch_ticker_data(ticker):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=10y&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            res = data.get("chart", {}).get("result")
            if not res:
                return None
            result = res[0]
            timestamps = result.get("timestamp", [])
            indicators = result.get("indicators", {}).get("quote", [{}])[0]
            closes = indicators.get("close", [])
            adj_closes = result.get("indicators", {}).get("adjclose", [{}])[0].get("adjclose", closes)
            
            records = []
            for ts, c, ac in zip(timestamps, closes, adj_closes):
                if c is None or ac is None:
                    continue
                dt_str = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                records.append({
                    "date": dt_str,
                    "ticker": ticker,
                    "Close": float(ac)  # use split/div adjusted close for correct returns & drawdowns
                })
            return records
    except Exception as e:
        print(f"  Error fetching {ticker}: {e}")
        return None

def main():
    print("=" * 70)
    print("ISOLATED 10-YEAR HISTORICAL DATA BACKFILL")
    print(f"Target Universe: {len(TICKERS)} tickers | Output: {OUT_FILE}")
    print("=" * 70)

    all_records = []
    success_count = 0
    failed = []

    t0_all = time.time()
    for i, sym in enumerate(TICKERS):
        print(f"[{i+1}/{len(TICKERS)}] Fetching {sym}...", end=" ", flush=True)
        recs = fetch_ticker_data(sym)
        if recs and len(recs) > 200:
            all_records.extend(recs)
            success_count += 1
            print(f"OK ({len(recs)} bars, {recs[0]['date']} to {recs[-1]['date']})")
        else:
            failed.append(sym)
            print(f"FAILED / SHORT ({len(recs) if recs else 0} bars)")
        time.sleep(0.08)  # respectful pacing

    df = pd.DataFrame(all_records)
    df = df.sort_values(["ticker", "date"]).drop_duplicates(subset=["ticker", "date"]).reset_index(drop=True)
    df.to_csv(OUT_FILE, index=False)

    dt_total = time.time() - t0_all
    print("=" * 70)
    print(f"BACKFILL COMPLETE in {dt_total:.1f}s")
    print(f"Successful tickers: {success_count}/{len(TICKERS)}")
    if failed:
        print(f"Failed/short tickers ({len(failed)}): {failed}")
    print(f"Total rows: {len(df)}")
    print(f"Earliest date: {df['date'].min()}, Latest date: {df['date'].max()}")
    print(f"Saved to: {OUT_FILE}")
    print("=" * 70)

if __name__ == "__main__":
    main()
