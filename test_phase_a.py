"""Phase A integration test — runs all new and existing endpoints."""

import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from service.app import app

client = TestClient(app)
passed = 0
failed = 0

def test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  PASS  {name}")
    except Exception as e:
        failed += 1
        print(f"  FAIL  {name}: {e}")


# ── Existing endpoints ──
def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_signal():
    r = client.post("/v1/signal", json={"ticker": "RELIANCE.NS"})
    assert r.status_code == 200
    assert r.json()["signal"] in ("BUY", "HOLD")

def test_portal():
    r = client.get("/app/")
    assert r.status_code == 200
    assert "Aarambh" in r.text

def test_root_redirect():
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307

def test_scanner():
    r = client.get("/scanner")
    assert r.status_code == 200
    assert r.json()["total"] > 0

def test_signal_stats():
    r = client.get("/signals/stats")
    assert r.status_code == 200
    assert "total_signals" in r.json()

def test_signal_history():
    r = client.get("/signals/history")
    assert r.status_code == 200


# ── Auth ──
TOKEN = None

def test_register():
    global TOKEN
    r = client.post("/auth/register", json={
        "email": "phaseatest@example.com",
        "username": "phasea_tester",
        "password": "secure123",
    })
    assert r.status_code == 200
    TOKEN = r.json()["access_token"]
    assert r.json()["user"]["tier"] == "free"

def test_login():
    r = client.post("/auth/login", json={
        "email": "phaseatest@example.com",
        "password": "secure123",
    })
    assert r.status_code == 200

def test_profile():
    headers = {"Authorization": f"Bearer {TOKEN}"}
    r = client.get("/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["username"] == "phasea_tester"


# ── Watchlist ──
WL_ID = None

def test_create_watchlist():
    global WL_ID
    headers = {"Authorization": f"Bearer {TOKEN}"}
    r = client.post("/watchlist", json={"name": "Long Term"}, headers=headers)
    assert r.status_code == 200
    WL_ID = r.json()["id"]

def test_add_to_watchlist():
    headers = {"Authorization": f"Bearer {TOKEN}"}
    r = client.post(f"/watchlist/{WL_ID}/add", json={"ticker": "RELIANCE.NS"}, headers=headers)
    assert r.status_code == 200

def test_list_watchlists():
    headers = {"Authorization": f"Bearer {TOKEN}"}
    r = client.get("/watchlist", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1


# ── Portfolio ──
def test_add_holding():
    headers = {"Authorization": f"Bearer {TOKEN}"}
    r = client.post("/portfolio/add", json={
        "ticker": "RELIANCE.NS", "quantity": 10,
        "purchase_price": 2500.0, "purchase_date": "2026-01-01T00:00:00",
    }, headers=headers)
    assert r.status_code == 200

def test_get_portfolio():
    headers = {"Authorization": f"Bearer {TOKEN}"}
    r = client.get("/portfolio", headers=headers)
    assert r.status_code == 200
    assert r.json()["total_value"] > 0


# ── Alerts ──
def test_create_alert():
    headers = {"Authorization": f"Bearer {TOKEN}"}
    r = client.post("/alerts", json={
        "ticker": "TCS.NS", "alert_type": "signal_change",
    }, headers=headers)
    assert r.status_code == 200

def test_list_alerts():
    headers = {"Authorization": f"Bearer {TOKEN}"}
    r = client.get("/alerts", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1


# ── Run all ──
if __name__ == "__main__":
    print("\n=== PHASE A INTEGRATION TESTS ===\n")

    print("Existing endpoints:")
    test("Health", test_health)
    test("Signal", test_signal)
    test("Portal", test_portal)
    test("Root redirect", test_root_redirect)
    test("Scanner", test_scanner)
    test("Signal stats", test_signal_stats)
    test("Signal history", test_signal_history)

    print("\nAuth:")
    test("Register", test_register)
    test("Login", test_login)
    test("Profile", test_profile)

    print("\nWatchlist:")
    test("Create watchlist", test_create_watchlist)
    test("Add ticker", test_add_to_watchlist)
    test("List watchlists", test_list_watchlists)

    print("\nPortfolio:")
    test("Add holding", test_add_holding)
    test("Get portfolio", test_get_portfolio)

    print("\nAlerts:")
    test("Create alert", test_create_alert)
    test("List alerts", test_list_alerts)

    print(f"\n{'='*40}")
    print(f"RESULTS: {passed} passed, {failed} failed")
    print(f"{'='*40}\n")

    if failed > 0:
        sys.exit(1)
