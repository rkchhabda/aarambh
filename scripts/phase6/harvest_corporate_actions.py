"""Harvest NSE corporate actions history for all 138 tickers.

Target: Bonus issues, Stock splits, and Rights issues.
Governing: Phase 6 Gate 3 Step 4.
"""

import os
import sys
import time
import json
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from features.universe import TICKERS

OUTPUT_DIR = os.path.join(BASE_DIR, "data", "fundamentals")
CA_DIR = os.path.join(OUTPUT_DIR, "corporate_actions")
os.makedirs(CA_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://www.nseindia.com/companies-listing/corporate-filings-actions'
}

def clean_symbol(ticker_ns: str) -> str:
    return ticker_ns.replace(".NS", "").strip()

def harvest_ca_ticker(session: requests.Session, symbol: str, retries: int = 3):
    url = "https://www.nseindia.com/api/corporates-corporateActions"
    params = {
        'index': 'equities',
        'symbol': symbol
    }
    for attempt in range(retries):
        try:
            resp = session.get(url, params=params, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 404:
                return []
            time.sleep(2)
        except Exception:
            time.sleep(2)
    return None

def main():
    session = requests.Session()
    try:
        session.get("https://www.nseindia.com/companies-listing/corporate-filings-actions", headers=HEADERS, timeout=10)
    except Exception:
        pass

    summary = {
        'total': len(TICKERS),
        'success': 0,
        'failed': []
    }

    print(f"Starting corporate actions harvest for {len(TICKERS)} tickers...")

    for idx, ticker in enumerate(TICKERS, 1):
        sym = clean_symbol(ticker)
        ca_file = os.path.join(CA_DIR, f"{sym}_ca.json")
        
        if os.path.exists(ca_file) and os.path.getsize(ca_file) > 10:
            print(f"[{idx}/{len(TICKERS)}] {sym} cached")
            summary['success'] += 1
            continue

        data = harvest_ca_ticker(session, sym)
        time.sleep(1.0) # Throttled
        
        if data is None:
            print(f"[{idx}/{len(TICKERS)}] {sym} FAILED")
            summary['failed'].append(sym)
            continue

        with open(ca_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"[{idx}/{len(TICKERS)}] {sym} retrieved ({len(data)} actions)")
        summary['success'] += 1

    print(f"\nCorporate actions harvest complete. Success: {summary['success']}/{len(TICKERS)}")

if __name__ == '__main__':
    main()
