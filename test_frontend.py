from fastapi.testclient import TestClient
from service.app import app

client = TestClient(app)

# Test root redirect
r = client.get('/', follow_redirects=False)
print(f"GET / -> {r.status_code}, Location: {r.headers.get('location')}")

# Test static file mount
r = client.get('/app/')
print(f"GET /app/ -> {r.status_code}")

# Test API still works (use AAPL for US tickers)
r = client.post('/v1/signal', json={'ticker': 'AAPL'}, headers={'X-API-Key': 'qs_Aa3jiN74kYmy8l2Z-fREAGqsgDT0a6gaWKIgp_1y'})
print(f"POST /v1/signal -> {r.status_code}, {r.json()}")