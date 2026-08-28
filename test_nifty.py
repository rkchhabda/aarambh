from fastapi.testclient import TestClient
from service.app import app

client = TestClient(app)

# Test health
r = client.get('/health')
print(f"Health: {r.status_code} - {r.json()}")

# Test signal endpoint with Nifty 100 ticker (no API key needed)
r = client.post('/v1/signal', json={'ticker': 'RELIANCE.NS'})
print(f"Signal RELIANCE.NS: {r.status_code} - {r.json()}")

# Test another
r = client.post('/v1/signal', json={'ticker': 'TCS.NS'})
print(f"Signal TCS.NS: {r.status_code} - {r.json()}")

# Test unsupported
r = client.post('/v1/signal', json={'ticker': 'AAPL'})
print(f"Signal AAPL (unsupported): {r.status_code} - {r.json()}")