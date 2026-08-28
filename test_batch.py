from fastapi.testclient import TestClient
from service.app import app, TICKERS

client = TestClient(app)

# Test a few major tickers
test_tickers = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", 
                "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS"]

print("Testing major Nifty 100 tickers...")
for t in test_tickers:
    r = client.post('/v1/signal', json={'ticker': t})
    if r.status_code == 200:
        d = r.json()
        print(f"  OK {t}: {d['signal']} (conf={d['confidence']:.2f}, regime={d['regime']}, price=Rs.{d['price']:.2f})")
    else:
        print(f"  FAIL {t}: {r.status_code} - {r.json().get('detail', 'Error')}")

# Test a few more that might have issues
more_tickers = ["ADANIENT.NS", "ADANIPORTS.NS", "ZOMATO.NS"]
print("\nTesting additional tickers...")
for t in more_tickers:
    if t in TICKERS:
        r = client.post('/v1/signal', json={'ticker': t})
        if r.status_code == 200:
            d = r.json()
            print(f"  OK {t}: {d['signal']} (conf={d['confidence']:.2f})")
        else:
            print(f"  FAIL {t}: {r.status_code} - {r.json().get('detail', 'Error')}")