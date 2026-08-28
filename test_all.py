from fastapi.testclient import TestClient
from service.app import app, TICKERS

client = TestClient(app)

print(f"Total tickers in list: {len(TICKERS)}")
print("Testing all tickers for validity...")

failed = []
success = []

for t in TICKERS:
    r = client.post('/v1/signal', json={'ticker': t})
    if r.status_code == 200:
        success.append(t)
    else:
        failed.append((t, r.json().get('detail', 'Error')))
    if len(success) + len(failed) % 20 == 0:
        print(f"  Progress: {len(success)} ok, {len(failed)} failed")

print(f"\n=== Results ===")
print(f"Success: {len(success)}")
print(f"Failed: {len(failed)}")
for t, err in failed:
    print(f"  FAIL {t}: {err}")

# Print working tickers list
print(f"\n=== Working tickers ({len(success)}) ===")
print(str(success).replace("'", '"'))