"""Corporate Action Adjustment Engine for GaurviDEEP Phase 6 Gate 3.

Governing: Phase 6 Gate 3 Step 4.
Functionality:
- Ingests verified NSE corporate action histories (bonuses, splits).
- Computes exact cumulative split/bonus adjustment factors per filing based on broadCastDate.
- Retroactively scales nominal quarterly EPS to a split-adjusted basis.
- Validates adjustment resolution for known benchmark cases (e.g. RELIANCE, TATASTEEL, EICHERMOT).
"""

import os
import sys
import json
import glob
import re
from datetime import datetime
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

CA_DIR = os.path.join(BASE_DIR, "data", "fundamentals", "corporate_actions")
PARSED_CSV = os.path.join(BASE_DIR, "data", "fundamentals", "resolved_filings_parsed.csv")
OUTPUT_ADJUSTED_CSV = os.path.join(BASE_DIR, "data", "fundamentals", "resolved_filings_split_adjusted.csv")

def parse_date(date_str):
    if not date_str:
        return None
    for fmt in ('%d-%b-%Y %H:%M:%S', '%d-%b-%Y %H:%M', '%d-%b-%Y', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
        except ValueError:
            pass
    return None

def load_all_corporate_actions():
    """Extract all bonus and stock split actions across the 138-ticker universe."""
    files = glob.glob(os.path.join(CA_DIR, "*_ca.json"))
    actions_by_symbol = {}

    for f in files:
        sym = os.path.basename(f).replace("_ca.json", "").strip()
        with open(f, 'r', encoding='utf-8') as jf:
            records = json.load(jf)

        actions_by_symbol[sym] = []
        for r in records:
            subj = r.get('subject') or ''
            ex_str = r.get('exDate') or ''
            ex_dt = parse_date(ex_str)
            if not ex_dt:
                continue

            multiplier = 1.0
            action_type = None

            # 1. Bonus: "Bonus N:D"
            bonus_match = re.search(r'bonus\s+(\d+)\s*:\s*(\d+)', subj, re.IGNORECASE)
            if bonus_match:
                n = float(bonus_match.group(1))
                d = float(bonus_match.group(2))
                multiplier *= (n + d) / d
                action_type = "BONUS"

            # 2. Split: "From Rs ... To Rs ..."
            split_match = re.search(r'(?:split|sub-division).*?from\s+(?:rs\.?|re\.?)\s*(\d+(?:\.\d+)?).*?to\s+(?:rs\.?|re\.?)\s*(\d+(?:\.\d+)?)', subj, re.IGNORECASE)
            if split_match:
                from_fv = float(split_match.group(1))
                to_fv = float(split_match.group(2))
                if to_fv > 0:
                    multiplier *= (from_fv / to_fv)
                    action_type = "SPLIT" if not action_type else f"{action_type}+SPLIT"

            if multiplier > 1.0:
                actions_by_symbol[sym].append({
                    'ex_date': ex_dt.strftime('%Y-%m-%d'),
                    'ex_dt': ex_dt,
                    'multiplier': multiplier,
                    'action_type': action_type,
                    'subject': subj
                })

        # Sort chronologically
        actions_by_symbol[sym].sort(key=lambda x: x['ex_dt'])

    return actions_by_symbol

def adjust_filings(df, actions_by_symbol):
    """Adjust nominal EPS to modern split-adjusted basis using actual filing timestamps."""
    adjusted_rows = []

    for _, row in df.iterrows():
        sym = row['symbol']
        b_dt = parse_date(row['broadCastDate']) or parse_date(row['filingDate']) or parse_date(row['toDate'])
        
        ca_list = actions_by_symbol.get(sym, [])
        
        # Multiply all corporate actions occurring AFTER this filing date
        # (meaning the shares were subsequently multiplied, so historical nominal EPS must be divided by this factor)
        cum_factor = 1.0
        applied_actions = []

        for ca in ca_list:
            if ca['ex_dt'] > b_dt:
                cum_factor *= ca['multiplier']
                applied_actions.append(f"{ca['action_type']} {ca['multiplier']}x ({ca['ex_date']})")

        nominal_eps = row['eps']
        adj_eps = (nominal_eps / cum_factor) if pd.notna(nominal_eps) and cum_factor > 0 else nominal_eps

        row_dict = row.to_dict()
        row_dict['cum_ca_factor'] = cum_factor
        row_dict['eps_nominal'] = nominal_eps
        row_dict['eps_adj'] = adj_eps
        row_dict['ca_applied'] = "; ".join(applied_actions) if applied_actions else "None"
        adjusted_rows.append(row_dict)

    adj_df = pd.DataFrame(adjusted_rows)
    return adj_df

def validate_benchmark_tickers(adj_df):
    """Report validation on key benchmark tickers: RELIANCE, TATASTEEL, EICHERMOT."""
    benchmarks = ['RELIANCE', 'TATASTEEL', 'EICHERMOT']
    print("\n" + "=" * 70)
    print("STEP 4 CORPORATE ACTION ENGINE VALIDATION BENCHMARKS")
    print("=" * 70)

    for sym in benchmarks:
        sub = adj_df[adj_df['symbol'] == sym].sort_values('toDate').copy()
        if sub.empty:
            continue
        print(f"\nBenchmark Ticker: {sym}")
        print(f"{'toDate':12} | {'broadCastDate':20} | {'Nominal EPS':12} | {'CA Factor':10} | {'Adj EPS':10} | {'CA Applied'}")
        print("-" * 80)
        # Show sample quarters across the corporate action event
        for _, r in sub.tail(8).iterrows():
            print(f"{r['toDate']:12} | {str(r['broadCastDate'])[:19]:20} | {str(round(r['eps_nominal'], 2) if pd.notna(r['eps_nominal']) else 'N/A'):12} | {r['cum_ca_factor']:9.2f}x | {str(round(r['eps_adj'], 2) if pd.notna(r['eps_adj']) else 'N/A'):9} | {r['ca_applied']}")

def compute_sue_and_audit(adj_df):
    """Step 5 & Step 6: SUE Feature Construction and Data Quality Audit."""
    print("\n" + "=" * 70)
    print("STEP 5: SUE FEATURE CONSTRUCTION (POINT-IN-TIME)")
    print("=" * 70)

    adj_df['broadCastDate_dt'] = pd.to_datetime(adj_df['broadCastDate'])
    adj_df = adj_df.sort_values(['ticker', 'broadCastDate_dt']).reset_index(drop=True)

    sue_records = []
    for ticker, group in adj_df.groupby('ticker'):
        g = group.copy().sort_values('broadCastDate_dt').reset_index(drop=True)
        if len(g) < 5:
            continue

        g['eps_adj_lag4'] = g['eps_adj'].shift(4)
        g['eps_yoy_delta'] = g['eps_adj'] - g['eps_adj_lag4']
        g['rolling_std_delta'] = g['eps_yoy_delta'].rolling(window=8, min_periods=3).std()

        # Vectorized SUE calculation with threshold guard
        valid_mask = g['rolling_std_delta'] >= 1e-4
        g['sue'] = np.where(valid_mask, g['eps_yoy_delta'] / g['rolling_std_delta'], np.nan)

        effective_dates = []
        for dt in g['broadCastDate_dt']:
            if dt.hour >= 16 or (dt.hour == 15 and dt.minute >= 30):
                eff = (dt + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
            else:
                eff = dt.strftime('%Y-%m-%d')
            effective_dates.append(eff)
        g['effective_date'] = effective_dates
        sue_records.append(g)

    if not sue_records:
        print("No SUE records generated.")
        return

    full_sue = pd.concat(sue_records, ignore_index=True)
    output_sue_path = os.path.join(BASE_DIR, "data", "fundamentals", "sue_features_quarterly.csv")
    full_sue.to_csv(output_sue_path, index=False)
    print(f"Quarterly SUE features saved to: {output_sue_path}")

    # Step 6 Data Quality Report
    valid_sue = full_sue[full_sue['sue'].notna()].copy()

    print("\n" + "=" * 70)
    print("PHASE 6 GATE 3: STEP 6 DATA QUALITY REPORT (SUE FEATURE)")
    print("=" * 70)
    
    universe_tickers_count = adj_df['ticker'].nunique()
    tickers_with_sue = valid_sue['ticker'].nunique()
    print(f"Total Tickers in Universe: {universe_tickers_count}")
    print(f"Tickers with Usable SUE Series: {tickers_with_sue} / {universe_tickers_count} ({tickers_with_sue / universe_tickers_count * 100:.1f}%)")
    print(f"Total Usable Quarterly SUE Observations: {len(valid_sue):,}")

    per_ticker_sue = valid_sue.groupby('ticker')['sue'].count()
    print("\n--- SUE OBSERVATIONS PER TICKER DISTRIBUTION ---")
    print(per_ticker_sue.describe())

    print("\n--- SUE DISTRIBUTION STATISTICS (ACROSS ALL OBSERVATIONS) ---")
    print(valid_sue['sue'].describe(percentiles=[0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]))

    print(f"\nSUE Skewness: {valid_sue['sue'].skew():.3f}")
    print(f"SUE Kurtosis: {valid_sue['sue'].kurtosis():.3f}")

    # Summary JSON
    summary_path = os.path.join(BASE_DIR, "data", "fundamentals", "gate3_sue_data_quality_summary.json")
    with open(summary_path, 'w', encoding='utf-8') as sf:
        json.dump({
            'total_universe_tickers': universe_tickers_count,
            'tickers_with_sue': int(tickers_with_sue),
            'total_sue_observations': int(len(valid_sue)),
            'sue_quarters_per_ticker': {
                'mean': float(per_ticker_sue.mean()),
                'median': float(per_ticker_sue.median()),
                'min': int(per_ticker_sue.min()),
                'max': int(per_ticker_sue.max())
            },
            'sue_distribution': {
                'mean': float(valid_sue['sue'].mean()),
                'std': float(valid_sue['sue'].std()),
                'min': float(valid_sue['sue'].min()),
                'p01': float(valid_sue['sue'].quantile(0.01)),
                'p05': float(valid_sue['sue'].quantile(0.05)),
                'p25': float(valid_sue['sue'].quantile(0.25)),
                'p50': float(valid_sue['sue'].quantile(0.50)),
                'p75': float(valid_sue['sue'].quantile(0.75)),
                'p95': float(valid_sue['sue'].quantile(0.95)),
                'p99': float(valid_sue['sue'].quantile(0.99)),
                'max': float(valid_sue['sue'].max()),
                'skewness': float(valid_sue['sue'].skew()),
                'kurtosis': float(valid_sue['sue'].kurtosis())
            }
        }, sf, indent=2)

    print(f"\nData quality summary saved to: {summary_path}")

def main():
    print("Loading corporate actions and parsed filings...")
    if not os.path.exists(PARSED_CSV):
        print(f"Error: {PARSED_CSV} does not exist yet. Run Step 2 & 3 pipeline first.")
        return

    df = pd.read_csv(PARSED_CSV)
    actions_by_symbol = load_all_corporate_actions()

    adj_df = adjust_filings(df, actions_by_symbol)
    adj_df.to_csv(OUTPUT_ADJUSTED_CSV, index=False)
    print(f"Adjusted filings saved to: {OUTPUT_ADJUSTED_CSV}")

    validate_benchmark_tickers(adj_df)
    compute_sue_and_audit(adj_df)

if __name__ == '__main__':
    main()

