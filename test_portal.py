from fastapi.testclient import TestClient
from service.app import app

c = TestClient(app)
h = c.get("/app/").text

items = [
    'id="navbar"',
    'id="page-dashboard"',
    'id="page-scanner"',
    'id="page-signals"',
    'id="page-watchlist"',
    'id="page-methodology"',
    'id="page-pricing"',
    'id="auth-modal"',
    'not guaranteed',
    'quant-score',
    'hamburger',
    '/v1/signal/detailed',
    'loginForm',
    'Aarambh',
    'Disclaimer',
]

for item in items:
    status = "OK" if item in h else "MISS"
    print(f"  {status}  {item[:40]}")

print(f"\n  Portal size: {len(h)} bytes ({len(h)//1024} KB)")
