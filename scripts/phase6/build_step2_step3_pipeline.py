"""Multi-Taxonomy XBRL Parser & Standalone/Consolidated Resolver.

Phase 6 Gate 3: Steps 2 & 3.
Governing:
- docs/GATE_3_SOURCING_REPORT.md (Section 7)
- docs/GATE_3_XBRL_FEASIBILITY_REPORT.md

Standalone vs Consolidated Precedence Rule (Step 3):
For any ticker and reporting period (toDate), prefer Consolidated results where filed.
Fall back to Standalone ONLY when no Consolidated filing exists for that period.
If multiple filings exist with the same nature, pick the latest broadcast timestamp.
"""

import os
import sys
import json
import glob
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from features.universe import TICKERS

DEV_START = "2018-01-01"
DEV_CUTOFF = "2025-09-16"

META_DIR = os.path.join(BASE_DIR, "data", "fundamentals", "metadata")
XBRL_DIR = os.path.join(BASE_DIR, "data", "fundamentals", "xbrl")
PARSED_DIR = os.path.join(BASE_DIR, "data", "fundamentals", "parsed")
os.makedirs(XBRL_DIR, exist_ok=True)
os.makedirs(PARSED_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def parse_date(date_str):
    if not date_str or not isinstance(date_str, str):
        return None
    date_str = date_str.strip()
    for fmt in ('%d-%b-%Y %H:%M:%S', '%d-%b-%Y %H:%M', '%d-%b-%Y', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass
    return None

def resolve_ticker_quarters(symbol):
    """Apply Step 3 Rule: Prefer Consolidated over Standalone for each quarter in dev window."""
    meta_path = os.path.join(META_DIR, f"{symbol}_metadata.json")
    if not os.path.exists(meta_path):
        return []

    with open(meta_path, 'r', encoding='utf-8') as f:
        records = json.load(f)

    # Filter to machine-readable XBRL and dev window
    valid_rows = []
    for r in records:
        xbrl_url = r.get('xbrl') or ''
        if not xbrl_url.endswith('.xml'):
            continue

        b_dt = parse_date(r.get('broadCastDate')) or parse_date(r.get('filingDate'))
        t_dt = parse_date(r.get('toDate'))
        if not b_dt or not t_dt:
            continue

        b_str = b_dt.strftime('%Y-%m-%d %H:%M:%S')
        b_date_only = b_dt.strftime('%Y-%m-%d')
        t_str = t_dt.strftime('%Y-%m-%d')

        if not (DEV_START <= b_date_only <= DEV_CUTOFF):
            continue

        is_cons = (r.get('consolidated') or '').strip().lower() == 'consolidated'
        valid_rows.append({
            'symbol': symbol,
            'toDate': t_str,
            'broadCastDate': b_str,
            'filingDate': (parse_date(r.get('filingDate')) or b_dt).strftime('%Y-%m-%d %H:%M:%S'),
            'is_consolidated': is_cons,
            'nature': 'Consolidated' if is_cons else 'Standalone',
            'xbrl_url': xbrl_url,
            'seqNumber': r.get('seqNumber')
        })

    # Group by toDate
    by_quarter = {}
    for row in valid_rows:
        q = row['toDate']
        if q not in by_quarter:
            by_quarter[q] = []
        by_quarter[q].append(row)

    selected = []
    for q, rows in by_quarter.items():
        # Prefer Consolidated
        cons_rows = [r for r in rows if r['is_consolidated']]
        if cons_rows:
            # Sort by broadcast timestamp descending (latest revision)
            cons_rows.sort(key=lambda x: x['broadCastDate'], reverse=True)
            selected.append(cons_rows[0])
        else:
            # Fall back to Standalone
            rows.sort(key=lambda x: x['broadCastDate'], reverse=True)
            selected.append(rows[0])

    selected.sort(key=lambda x: x['toDate'])
    return selected

def download_xbrl_file(url, target_path):
    if os.path.exists(target_path) and os.path.getsize(target_path) > 100:
        return True
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200 and len(resp.content) > 100:
                with open(target_path, 'wb') as f:
                    f.write(resp.content)
                return True
            time.sleep(1)
        except Exception:
            time.sleep(1)
    return False

def parse_xbrl_xml(file_path):
    """Step 2 Multi-Taxonomy Parser: Ind-AS, Banking, NBFC."""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except Exception as e:
        return {'parse_error': str(e)}

    # Map contexts
    contexts = {}
    quarter_cids = set()

    for c in root.findall('{http://www.xbrl.org/2003/instance}context'):
        cid = c.attrib.get('id', '')
        start = c.find('{http://www.xbrl.org/2003/instance}period/{http://www.xbrl.org/2003/instance}startDate')
        end = c.find('{http://www.xbrl.org/2003/instance}period/{http://www.xbrl.org/2003/instance}endDate')

        start_txt = start.text.strip() if start is not None and start.text else None
        end_txt = end.text.strip() if end is not None and end.text else None
        dur_days = None

        if start_txt and end_txt:
            try:
                d1 = datetime.strptime(start_txt, '%Y-%m-%d')
                d2 = datetime.strptime(end_txt, '%Y-%m-%d')
                dur_days = (d2 - d1).days
            except:
                pass

        # Check if context has segment/explicitMember (dimensions)
        has_dimension = c.find('{http://www.xbrl.org/2003/instance}entity/{http://www.xbrl.org/2003/instance}segment') is not None

        contexts[cid] = {
            'start': start_txt,
            'end': end_txt,
            'duration_days': dur_days,
            'has_dimension': has_dimension
        }

        # Quarterly context candidates
        if cid == 'OneD':
            quarter_cids.add(cid)
        elif dur_days is not None and 75 <= dur_days <= 105 and not has_dimension:
            quarter_cids.add(cid)

    # If no base quarter found, allow OneD or any 75-105 day context
    if not quarter_cids:
        for cid, cinfo in contexts.items():
            dur = cinfo.get('duration_days')
            if dur is not None and 75 <= dur <= 105:
                quarter_cids.add(cid)
            elif cid in ['ThreeM', 'D_Quarterly', 'One', 'Q1', 'Q2', 'Q3', 'Q4']:
                quarter_cids.add(cid)

    eps_candidates = []
    pat_candidates = []
    taxonomy_type = "Ind-AS"

    for elem in root.iter():
        tag = elem.tag.split('}')[-1]
        tlower = tag.lower()
        cref = elem.attrib.get('contextRef', '')
        txt = elem.text.strip() if elem.text else None

        if not txt:
            continue

        try:
            val = float(txt.replace(',', ''))
        except ValueError:
            continue

        if 'bank' in elem.tag.lower():
            taxonomy_type = "Banking"
        elif 'nbfc' in elem.tag.lower():
            taxonomy_type = "NBFC"

        # Match EPS
        # 1. Ind-AS & NBFC: BasicEarningsLossPerShareFromContinuingOperations
        # 2. Bank: BasicEarningsPerShareAfterExtraordinaryItems / BasicEarningsPerShareBeforeExtraordinaryItems
        # 3. Fallback: any BasicEarnings
        if cref in quarter_cids or cref == 'OneD':
            if 'basicearnings' in tlower or 'basic_eps' in tlower:
                priority = 99
                if 'fromcontinuingoperations' in tlower:
                    priority = 1
                elif 'fromcontinuinganddiscontinuedoperations' in tlower:
                    priority = 2
                elif 'afterextraordinaryitems' in tlower:
                    priority = 3
                elif 'beforeextraordinaryitems' in tlower:
                    priority = 4
                elif 'basicearningsloss' in tlower or 'basicearningspershare' in tlower:
                    priority = 5
                eps_candidates.append((priority, val, tag, cref))

            # Match PAT
            if any(k in tlower for k in ['profitlossforperiod', 'profitlossfortheperiod', 'profitlossaftertax', 'netprofitlossforperiod']):
                priority = 99
                if 'profitlossforperiod' in tlower or 'profitlossfortheperiod' in tlower:
                    priority = 1
                elif 'aftertax' in tlower:
                    priority = 2
                pat_candidates.append((priority, val, tag, cref))

    eps_candidates.sort(key=lambda x: x[0])
    pat_candidates.sort(key=lambda x: x[0])

    chosen_eps = eps_candidates[0][1] if eps_candidates else None
    chosen_pat = pat_candidates[0][1] if pat_candidates else None
    eps_tag = eps_candidates[0][2] if eps_candidates else None
    pat_tag = pat_candidates[0][2] if pat_candidates else None

    return {
        'eps': chosen_eps,
        'pat': chosen_pat,
        'eps_tag': eps_tag,
        'pat_tag': pat_tag,
        'taxonomy': taxonomy_type
    }

def main():
    print("=" * 70)
    print("PHASE 6 GATE 3: STEP 2 (PARSER) & STEP 3 (CONSOLIDATED RESOLUTION)")
    print("=" * 70)

    # 1. Resolve quarters for all 138 tickers
    all_selected_filings = []
    per_ticker_counts = {}

    for ticker in TICKERS:
        sym = ticker.replace('.NS', '').strip()
        quarters = resolve_ticker_quarters(sym)
        per_ticker_counts[ticker] = len(quarters)
        for q in quarters:
            q['ticker'] = ticker
            all_selected_filings.append(q)

    print(f"Total resolved quarterly filings across universe: {len(all_selected_filings):,}")
    cons_count = sum(1 for f in all_selected_filings if f['is_consolidated'])
    sa_count = sum(1 for f in all_selected_filings if not f['is_consolidated'])
    print(f"Resolution breakdown: Consolidated = {cons_count} ({cons_count/len(all_selected_filings)*100:.1f}%), Standalone fallback = {sa_count} ({sa_count/len(all_selected_filings)*100:.1f}%)")

    # 2. Download any missing XBRL files using ThreadPool
    print(f"\nVerifying / downloading {len(all_selected_filings)} XBRL XML instances...")
    download_tasks = []
    for f in all_selected_filings:
        xml_fname = f['xbrl_url'].split('/')[-1]
        local_path = os.path.join(XBRL_DIR, xml_fname)
        f['local_path'] = local_path
        if not (os.path.exists(local_path) and os.path.getsize(local_path) > 100):
            download_tasks.append((f['xbrl_url'], local_path))

    print(f"Files to download: {len(download_tasks)} (Already cached: {len(all_selected_filings) - len(download_tasks)})")
    if download_tasks:
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(download_xbrl_file, url, path) for url, path in download_tasks]
            completed = 0
            for fut in as_completed(futures):
                completed += 1
                if completed % 250 == 0 or completed == len(download_tasks):
                    print(f"  Downloaded {completed}/{len(download_tasks)} files...")

    # 3. Parse all filings
    print("\nParsing all quarterly XBRL instances across taxonomies...")
    parsed_records = []
    missing_eps = 0
    missing_pat = 0

    for idx, f in enumerate(all_selected_filings, 1):
        parsed = parse_xbrl_xml(f['local_path'])
        eps = parsed.get('eps')
        pat = parsed.get('pat')
        
        if eps is None:
            missing_eps += 1
        if pat is None:
            missing_pat += 1

        parsed_records.append({
            'ticker': f['ticker'],
            'symbol': f['symbol'],
            'toDate': f['toDate'],
            'broadCastDate': f['broadCastDate'],
            'filingDate': f['filingDate'],
            'nature': f['nature'],
            'is_consolidated': f['is_consolidated'],
            'eps': eps,
            'pat': pat,
            'eps_tag': parsed.get('eps_tag'),
            'pat_tag': parsed.get('pat_tag'),
            'taxonomy': parsed.get('taxonomy'),
            'xbrl_url': f['xbrl_url']
        })

    df = pd.DataFrame(parsed_records)
    output_csv = os.path.join(BASE_DIR, "data", "fundamentals", "resolved_filings_parsed.csv")
    df.to_csv(output_csv, index=False)

    print(f"\nParsed results saved to: {output_csv}")
    print(f"Total parsed records: {len(df):,}")
    print(f"Records with valid EPS: {df['eps'].notna().sum():,} ({df['eps'].notna().mean()*100:.1f}%)")
    print(f"Records with valid PAT: {df['pat'].notna().sum():,} ({df['pat'].notna().mean()*100:.1f}%)")
    print(f"Taxonomy distribution:\n{df['taxonomy'].value_counts()}")

    # Summary by ticker
    summary_by_ticker = df.groupby('ticker').agg(
        total_quarters=('toDate', 'count'),
        valid_eps=('eps', 'count'),
        valid_pat=('pat', 'count')
    ).reset_index()

    summary_file = os.path.join(BASE_DIR, "data", "fundamentals", "step2_step3_summary.json")
    with open(summary_file, 'w', encoding='utf-8') as sf:
        json.dump({
            'total_resolved_quarters': len(df),
            'consolidated_count': cons_count,
            'standalone_fallback_count': sa_count,
            'valid_eps_count': int(df['eps'].notna().sum()),
            'valid_pat_count': int(df['pat'].notna().sum()),
            'usable_eps_rate': float(df['eps'].notna().mean()),
            'taxonomy_breakdown': df['taxonomy'].value_counts().to_dict(),
        }, sf, indent=2)

    print("\nStep 2 & Step 3 pipeline executed successfully!")

if __name__ == '__main__':
    main()
