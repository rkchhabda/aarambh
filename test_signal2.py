from fastapi.testclient import TestClient
from service.app import app

client = TestClient(app)

# Test health
r = client.get('/health')
print(f"Health: {r.status_code} - {r.json()}")

# Test signal endpoint (should fail with 401 without API key)
r = client.post('/v1/signal', json={'ticker': 'AAPL'})
print(f"Signal (no key): {r.status_code} - {r.json()}")

# Test with valid API key
r = client.post('/v1/signal', json={'ticker': 'AAPL'}, headers={'X-API-Key': 'qs_Aa3jiN74kYmy8l2Z-fREAGqsgDT0a6gaWKIgp_1y'})
print(f"Signal (with key): {r.status_code} - {r.json()}")

# Test unsupported ticker
r = client.post('/v1/signal', json={'ticker': 'RELIANCE'}, headers={'X-API-Key': 'qs_Aa3jiN74kYmy8l2Z-fREAGqsgDT0a6gaWKIgp_1y'})
print(f"Signal (unsupported): {r.status_code} - {r.json()}")