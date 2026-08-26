"""API key & tier management for the Quant Signal API.

Keys are stored SHA-256 hashed in keys.json. Tiers control rate/delay/access.
"""

import hashlib
import json
import os
import secrets
import time

KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys.json")

TIERS = {
    "free":       {"delay_hours": 24, "tickers": 1,  "realtime": False, "webhook": False},
    "pro":        {"delay_hours": 0,  "tickers": 5,  "realtime": True,  "webhook": True},
    "enterprise": {"delay_hours": 0,  "tickers": -1, "realtime": True,  "webhook": True},
}


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _load() -> dict:
    if not os.path.exists(KEYS_FILE):
        return {}
    with open(KEYS_FILE) as f:
        return json.load(f)


def _save(db: dict) -> None:
    with open(KEYS_FILE, "w") as f:
        json.dump(db, f, indent=2)


def create_api_key(tier: str, owner: str) -> str:
    """Generate a new API key. Returns the plaintext key ONCE; store only hash."""
    if tier not in TIERS:
        raise ValueError(f"Unknown tier: {tier}")
    raw = f"qs_{secrets.token_urlsafe(30)}"
    db = _load()
    db[_hash(raw)] = {"tier": tier, "owner": owner,
                      "created": int(time.time()), "calls_today": 0}
    _save(db)
    return raw


def validate_api_key(raw_key: str):
    """Return key record if valid, else None."""
    if not raw_key:
        return None
    return _load().get(_hash(raw_key))


def get_tier(raw_key: str) -> str:
    rec = validate_api_key(raw_key)
    return rec["tier"] if rec else "anonymous"


if __name__ == "__main__":
    # Seed one demo key per tier
    for tier, owner in [("pro", "demo@internal"), ("enterprise", "demo@internal")]:
        k = create_api_key(tier, owner)
        print(f"[{tier:>10}] key for {owner}: {k}")
