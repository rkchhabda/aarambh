import requests
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime

s = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://www.nseindia.com/companies-listing/corporate-filings-financial-results'
}

def parse_xbrl_text(xml_text):
    try:
        root = ET.fromstring(xml_text)
    except Exception as e:
        return {'parse_error': str(e)}
        
    contexts = {}
    for c in root.findall('{http://www.xbrl.org/2003/instance}context'):
        cid = c.attrib.get('id')
        start = c.find('{http://www.xbrl.org/2003/instance}period/{http://www.xbrl.org/2003/instance}startDate')
        end = c.find('{http://www.xbrl.org/2003/instance}period/{http://www.xbrl.org/2003/instance}endDate')
        instant = c.find('{http://www.xbrl.org/2003/instance}period/{http://www.xbrl.org/2003/instance}instant')
        
        start_txt = start.text if start is not None else None
        end_txt = end.text if end is not None else None
        duration_days = None
        if start_txt and end_txt:
            try:
                d1 = datetime.strptime(start_txt.strip(), '%Y-%m-%d')
                d2 = datetime.strptime(end_txt.strip(), '%Y-%m-%d')
                duration_days = (d2 - d1).days
            except:
                pass
                
        contexts[cid] = {
            'start': start_txt,
            'end': end_txt,
            'duration_days': duration_days
        }

    extracted = {
        'board_meeting_date': None,
        'report_nature': None,
        'quarter_eps': None,
        'quarter_pat': None,
        'quarter_start': None,
        'quarter_end': None,
    }

    for elem in root.iter():
        tag = elem.tag.split('}')[-1]
        tlower = tag.lower()
        txt = elem.text.strip() if elem.text else None
        
        if 'dateofboardmeetingwhenfinancialresultswereapproved' in tlower and not extracted['board_meeting_date']:
            extracted['board_meeting_date'] = txt
        elif 'natureofreportstandaloneconsolidated' in tlower and not extracted['report_nature']:
            extracted['report_nature'] = txt
        elif 'dateofstartofreportingperiod' in tlower and not extracted['quarter_start']:
            extracted['quarter_start'] = txt
        elif 'dateofendofreportingperiod' in tlower and not extracted['quarter_end']:
            extracted['quarter_end'] = txt

    # Extract EPS and PAT matching the quarterly duration (~80-95 days) or OneD
    for elem in root.iter():
        tag = elem.tag.split('}')[-1]
        tlower = tag.lower()
        cref = elem.attrib.get('contextRef')
        txt = elem.text.strip() if elem.text else None
        
        cinfo = contexts.get(cref, {})
        dur = cinfo.get('duration_days')
        is_quarter = False
        if dur is not None and 75 <= dur <= 100:
            is_quarter = True
        elif cref in ['OneD', 'ThreeM', 'D_Quarterly', 'One']:
            is_quarter = True
            
        if is_quarter and txt is not None:
            if 'basicearningsloss' in tlower and extracted['quarter_eps'] is None:
                extracted['quarter_eps'] = txt
            if 'profitlossforperiod' in tlower and extracted['quarter_pat'] is None:
                extracted['quarter_pat'] = txt

    return extracted

def run_5_ticker_feasibility():
    tickers = ['RELIANCE', 'TCS', 'HDFCBANK', 'TORNTPOWER', 'GRANULES']
    results = {}
    
    for sym in tickers:
        print(f"\n==========================================")
        print(f"Fetching metadata for {sym}...")
        url_results = f'https://www.nseindia.com/api/corporates-financial-results?index=equities&symbol={sym}&period=Quarterly'
        try:
            r = s.get(url_results, headers=headers, timeout=12)
            if r.status_code != 200:
                print(f"Error {r.status_code} for {sym}")
                results[sym] = {'error': f"Status {r.status_code}"}
                continue
            data = r.json()
            
            xbrl_rows = [d for d in data if (d.get('xbrl') or '').endswith('.xml')]
            html_rows = [d for d in data if (d.get('resultDetailedDataLink') or '').endswith('.html')]
            
            print(f"{sym}: Total rows={len(data)}, XBRL rows={len(xbrl_rows)}, HTML rows={len(html_rows)}")
            
            # Select 3 sample filings across history: recent (2024), mid (2021), earliest (2018)
            samples = []
            if len(xbrl_rows) > 0:
                indices_to_test = [0, len(xbrl_rows) // 2, len(xbrl_rows) - 1]
                indices_to_test = list(dict.fromkeys(indices_to_test))
                
                for idx in indices_to_test:
                    row = xbrl_rows[idx]
                    x_url = row.get('xbrl')
                    print(f"  Downloading XBRL {idx}: {row.get('toDate')} (filed: {row.get('filingDate')})...")
                    time.sleep(0.5)
                    try:
                        rx = s.get(x_url, headers=headers, timeout=12)
                        parsed = parse_xbrl_text(rx.text)
                    except Exception as ex:
                        parsed = {'error': str(ex)}
                        
                    samples.append({
                        'toDate': row.get('toDate'),
                        'filingDate': row.get('filingDate'),
                        'broadCastDate': row.get('broadCastDate'),
                        'consolidated': row.get('consolidated'),
                        'xbrl_url': x_url,
                        'parsed': parsed
                    })
                    
            # Check pre-2018 HTML rows
            sample_pre2018_html = None
            pre2018_candidates = [d for d in data if not (d.get('xbrl') or '').endswith('.xml') and (d.get('resultDetailedDataLink') or '').endswith('.html')]
            if pre2018_candidates:
                c = pre2018_candidates[0]
                sample_pre2018_html = {
                    'toDate': c.get('toDate'),
                    'filingDate': c.get('filingDate'),
                    'broadCastDate': c.get('broadCastDate'),
                    'html_url': c.get('resultDetailedDataLink')
                }
                
            results[sym] = {
                'total_filings_count': len(data),
                'xbrl_filings_count': len(xbrl_rows),
                'html_filings_count': len(html_rows),
                'earliest_xbrl_toDate': xbrl_rows[-1].get('toDate') if xbrl_rows else None,
                'earliest_xbrl_filingDate': xbrl_rows[-1].get('filingDate') if xbrl_rows else None,
                'latest_xbrl_toDate': xbrl_rows[0].get('toDate') if xbrl_rows else None,
                'latest_xbrl_filingDate': xbrl_rows[0].get('filingDate') if xbrl_rows else None,
                'sample_pre2018_html': sample_pre2018_html,
                'samples': samples
            }
        except Exception as e:
            print(f"Exception for {sym}: {e}")
            results[sym] = {'error': str(e)}
            
    with open('scratch/feasibility_5tickers.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("\nSaved all 5-ticker results to scratch/feasibility_5tickers.json")

if __name__ == '__main__':
    run_5_ticker_feasibility()
