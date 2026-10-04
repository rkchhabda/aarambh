"""Audit harvested NSE metadata across the 138-ticker universe.

Scope: Narrowed Development Window (2018-01-01 to 2025-09-16).
Deliverable: Step 1 Coverage Report (total filings retrieved, per-ticker coverage gaps,
and tickers with insufficient data [<10 quarters] to flag for exclusion).
"""

import os
import sys
import json
import glob
from datetime import datetime
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from features.universe import TICKERS

META_DIR = os.path.join(BASE_DIR, "data", "fundamentals", "metadata")
DEV_CUTOFF = "2025-09-16"
DEV_START = "2018-01-01"

def parse_date(date_str):
    if not date_str or not isinstance(date_str, str):
        return None
    date_str = date_str.strip()
    # Try various formats: '31-Dec-2024', '16-Jan-2025 20:20:21', '2024-12-31'
    for fmt in ('%d-%b-%Y %H:%M:%S', '%d-%b-%Y %H:%M', '%d-%b-%Y', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass
    return None

def analyze():
    results = []
    
    for ticker in TICKERS:
        sym = ticker.replace(".NS", "").strip()
        meta_file = os.path.join(META_DIR, f"{sym}_metadata.json")
        if not os.path.exists(meta_file):
            results.append({
                'ticker': ticker,
                'symbol': sym,
                'status': 'MISSING_FILE',
                'total_filings': 0,
                'xbrl_filings': 0,
                'distinct_quarters': 0,
                'quarters_in_dev_window': 0,
                'earliest_dev_quarter': None,
                'latest_dev_quarter': None,
                'earliest_dev_broadcast': None,
                'latest_dev_broadcast': None,
                'insufficient_data': True
            })
            continue

        with open(meta_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        total_filings = len(data)
        xbrl_filings = [r for r in data if (r.get('xbrl') or '').endswith('.xml')]
        
        # Filter for development window: 2018-01-01 <= broadCastDate <= 2025-09-16
        # Also check toDate >= 2018-01-01
        dev_xbrl = []
        quarter_periods = set()
        
        for r in xbrl_filings:
            b_dt = parse_date(r.get('broadCastDate')) or parse_date(r.get('filingDate'))
            t_dt = parse_date(r.get('toDate'))
            
            if b_dt is None and t_dt is not None:
                b_dt = t_dt
                
            if b_dt is None:
                continue
                
            b_str = b_dt.strftime('%Y-%m-%d')
            t_str = t_dt.strftime('%Y-%m-%d') if t_dt else None
            
            # Dev window constraint: must have been broadcast on or before 2025-09-16
            # and from 2018-01-01 onward
            if "2018-01-01" <= b_str <= DEV_CUTOFF:
                dev_xbrl.append({
                    'broadCastDate': b_str,
                    'toDate': t_str,
                    'consolidated': r.get('consolidated'),
                    'xbrl': r.get('xbrl')
                })
                if t_str:
                    quarter_periods.add(t_str)

        quarters_count = len(quarter_periods)
        dev_xbrl.sort(key=lambda x: x['broadCastDate'])
        
        earliest_q = min(quarter_periods) if quarter_periods else None
        latest_q = max(quarter_periods) if quarter_periods else None
        earliest_bc = dev_xbrl[0]['broadCastDate'] if dev_xbrl else None
        latest_bc = dev_xbrl[-1]['broadCastDate'] if dev_xbrl else None

        results.append({
            'ticker': ticker,
            'symbol': sym,
            'status': 'OK' if quarters_count >= 10 else 'INSUFFICIENT_DATA',
            'total_filings': total_filings,
            'xbrl_filings': len(xbrl_filings),
            'dev_xbrl_filings': len(dev_xbrl),
            'quarters_in_dev_window': quarters_count,
            'earliest_dev_quarter': earliest_q,
            'latest_dev_quarter': latest_q,
            'earliest_dev_broadcast': earliest_bc,
            'latest_dev_broadcast': latest_bc,
            'insufficient_data': quarters_count < 10
        })

    df = pd.DataFrame(results)
    
    # Save detailed audit CSV
    audit_csv = os.path.join(BASE_DIR, "data", "fundamentals", "step1_coverage_audit.csv")
    df.to_csv(audit_csv, index=False)
    
    print("=" * 70)
    print("PHASE 6 GATE 3 — STEP 1 COVERAGE AUDIT SUMMARY")
    print("=" * 70)
    print(f"Total Tickers Analyzed: {len(df)}")
    print(f"Total Raw Filings Across Universe: {df['total_filings'].sum():,}")
    print(f"Total Machine-Readable XBRL Filings: {df['xbrl_filings'].sum():,}")
    print(f"Total Dev-Window XBRL Filings (2018 to 2025-09-16): {df['dev_xbrl_filings'].sum():,}")
    
    sufficient = df[~df['insufficient_data']]
    insufficient = df[df['insufficient_data']]
    
    print(f"\nTickers with Usable Data (>=10 quarters): {len(sufficient)} / {len(df)} ({len(sufficient)/len(df)*100:.1f}%)")
    print(f"Tickers with Insufficient Data (<10 quarters): {len(insufficient)} / {len(df)}")
    
    print("\n--- TICKERS WITH INSUFFICIENT DATA (<10 QUARTERS) ---")
    for _, row in insufficient.iterrows():
        print(f"  {row['ticker']:15} | Quarters: {row['quarters_in_dev_window']:2} | Total Filings: {row['total_filings']:3} | XBRL: {row['xbrl_filings']:3} | Status: {row['status']}")

    print("\n--- QUARTER COVERAGE DISTRIBUTION (USABLE TICKERS) ---")
    print(sufficient['quarters_in_dev_window'].describe())
    
    # Save summary report JSON
    summary_path = os.path.join(BASE_DIR, "data", "fundamentals", "step1_summary.json")
    summary = {
        'total_tickers': len(df),
        'total_raw_filings': int(df['total_filings'].sum()),
        'total_xbrl_filings': int(df['xbrl_filings'].sum()),
        'total_dev_xbrl_filings': int(df['dev_xbrl_filings'].sum()),
        'usable_tickers_count': len(sufficient),
        'insufficient_tickers_count': len(insufficient),
        'insufficient_tickers': insufficient[['ticker', 'quarters_in_dev_window', 'total_filings', 'xbrl_filings']].to_dict(orient='records'),
        'coverage_stats': {
            'mean_quarters': float(sufficient['quarters_in_dev_window'].mean()),
            'median_quarters': float(sufficient['quarters_in_dev_window'].median()),
            'min_quarters': int(sufficient['quarters_in_dev_window'].min()),
            'max_quarters': int(sufficient['quarters_in_dev_window'].max())
        }
    }
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

if __name__ == '__main__':
    analyze()
