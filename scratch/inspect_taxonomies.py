"""Download 1 filing each from Ind-AS, Banking, and NBFC to inspect taxonomy tags."""

import json
import requests
import xml.etree.ElementTree as ET

s = requests.Session()
h = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

def check_ticker(sym):
    with open(f'data/fundamentals/metadata/{sym}_metadata.json') as f:
        meta = json.load(f)
    xbrl_rows = [r for r in meta if (r.get('xbrl') or '').endswith('.xml')]
    if not xbrl_rows:
        return
    row = xbrl_rows[0]
    url = row['xbrl']
    print(f"\n--- {sym} ({row.get('consolidated')}) ---")
    print("URL:", url)
    rx = s.get(url, headers=h, timeout=15)
    root = ET.fromstring(rx.text)
    
    eps_tags = []
    pat_tags = []
    for elem in root.iter():
        tag = elem.tag.split('}')[-1]
        tlow = tag.lower()
        if 'earnings' in tlow or 'eps' in tlow:
            eps_tags.append((tag, elem.attrib.get('contextRef'), elem.text))
        if 'profit' in tlow or 'pat' in tlow:
            pat_tags.append((tag, elem.attrib.get('contextRef'), elem.text))
            
    print(f"EPS tags found ({len(eps_tags)}):")
    for t in eps_tags[:5]:
        print(" ", t)
    print(f"PAT tags found ({len(pat_tags)}):")
    for t in pat_tags[:5]:
        print(" ", t)

if __name__ == '__main__':
    for s_name in ['TCS', 'HDFCBANK', 'BAJFINANCE']:
        check_ticker(s_name)
