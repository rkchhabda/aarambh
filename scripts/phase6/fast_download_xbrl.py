import os
import sys
import glob
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from scripts.phase6.build_step2_step3_pipeline import resolve_ticker_quarters, TICKERS, XBRL_DIR, HEADERS, download_xbrl_file

def main():
    tasks = []
    for ticker in TICKERS:
        sym = ticker.replace('.NS', '').strip()
        quarters = resolve_ticker_quarters(sym)
        for q in quarters:
            fname = q['xbrl_url'].split('/')[-1]
            p = os.path.join(XBRL_DIR, fname)
            if not (os.path.exists(p) and os.path.getsize(p) > 100):
                tasks.append((q['xbrl_url'], p))

    print(f"Fast downloader: {len(tasks)} files remaining. Launching with 24 workers...")
    if not tasks:
        print("All files already downloaded!")
        return

    with ThreadPoolExecutor(max_workers=24) as ex:
        futures = [ex.submit(download_xbrl_file, url, path) for url, path in tasks]
        done = 0
        for f in as_completed(futures):
            done += 1
            if done % 200 == 0 or done == len(tasks):
                print(f"  Fast downloader: {done}/{len(tasks)} done")

    print("Fast downloader finished.")

if __name__ == '__main__':
    main()
