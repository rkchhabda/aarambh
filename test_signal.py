from fastapi.testclient import TestClient
from service.app import app

client = TestClient(app)
response = client.post('/v1/signal', json={'ticker': 'RELIANCE'}, headers={'X-API-Key': 'qs_Aa3jiN74kYmy8l2Z-fREAGqsgDT0a6gaWKIgp_1y'})
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")