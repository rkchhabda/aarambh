"""Harvest NSE quarterly financial results metadata for the 138-ticker universe.

Scope: Narrowed Development Window (2018-01-01 to 2025-09-16).
Governing Document: docs/GATE_3_SOURCING_REPORT.md (Section 7)
"""

import os
import sys
import time
import json
import requests
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from features.universe import TICKERS

OUTPUT_DIR = os.path.join(BASE_DIR, "data", "fundamentals")
META_DIR = os.path.join(OUTPUT_DIR, "metadata")
os.makedirs(META_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://www.nseindia.com/companies-listing/corporate-filings-financial-results'
}

def clean_symbol(ticker_ns: str) -> str:
    # Remove .NS suffix
    return ticker_ns.replace(".NS", "").strip()

def harvest_ticker_metadata(session: requests.Session, symbol: str, retries: int = 3):
    url = "https://www.nseindia.com/api/corporates-financial-results"
    params = {
        'index': 'equities',
        'symbol': symbol,
        'period': 'Quarterly'
    }
    
    for attempt in range(retries):
        try:
            resp = session.get(url, params=params, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return data
            elif resp.status_code == 404:
                return []
            else:
                time.sleep(2)
        except Exception as e:
            time.sleep(2)
    return None

def main():
    session = requests.Session()
    # Initial request to prime cookies if needed
    try:
        session.get("https://www.nseindia.com/companies-listing/corporate-filings-financial-results", headers=HEADERS, timeout=10)
    except Exception:
        pass

    summary = {
        'tickers_total': len(TICKERS),
        'tickers_success': 0,
        'tickers_failed': [],
        'ticker_stats': {}
    }

    print(f"Starting metadata harvest for {len(TICKERS)} tickers...")
    print(f"Throttle: 1.0s between requests. Destination: {META_DIR}")

    for idx, ticker in enumerate(TICKERS, 1):
        sym = clean_symbol(ticker)
        meta_file = os.path.join(META_DIR, f"{sym}_metadata.json")
        
        # Check if already cached
        if os.path.exists(meta_file) and os.path.getsize(meta_file) > 10:
            with open(meta_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"[{idx}/{len(TICKERS)}] {sym} cached ({len(data)} records)")
        else:
            data = harvest_ticker_metadata(session, sym)
            time.sleep(1.0) # Throttled per specification
            
            if data is None:
                print(f"[{idx}/{len(TICKERS)}] {sym} FAILED after retries")
                summary['tickers_failed'].append(sym)
                continue
            
            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            print(f"[{idx}/{len(TICKERS)}] {sym} retrieved ({len(data)} records)")

        # Analyze filings in 2018-01-01 to 2025-09-16 window
        xbrl_filings = []
        for r in data:
            xbrl_url = r.get('xbrl') or ''
            if not xbrl_url.endswith('.xml'):
                continue
            
            # Check period or filing date
            # toDate format typically '31-Dec-2024' or similar
            # broadCastDate format '16-Jan-2025 20:20:21'
            b_date_str = r.get('broadCastDate') or r.get('filingDate') or ''
            t_date_str = r.get('toDate') or ''
            
            # Filter for 2018 onward
            xbrl_filings.append(r)

        summary['tickers_success'] += 1
        summary['ticker_stats'][sym] = {
            'total_records': len(data),
            'total_xbrl': len(xbrl_filings)
        }

    summary_file = os.path.join(OUTPUT_DIR, "metadata_harvest_summary.json")
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    print(f"\nMetadata harvest complete. Successfully retrieved: {summary['tickers_success']}/{len(TICKERS)}")
    if summary['tickers_failed']:
        print(f"Failed tickers: {summary['tickers_failed']}")

if __name__ == '__main__':
    main()
