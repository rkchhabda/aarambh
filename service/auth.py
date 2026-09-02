"""Authentication — JWT tokens, password hashing, login/register.

All secrets come from environment variables. No hardcoded keys.
"""

import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from service.database import get_db, ensure_db
from service.models_db import User, UserSession

# Ensure DB tables exist on import
ensure_db()

# ─── Config ──────────────────────────────────────────────────────────────────
JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_urlsafe(48))
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.environ.get("JWT_EXPIRE_HOURS", "72"))

security = HTTPBearer(auto_error=False)


# ─── Password ────────────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ─── JWT ─────────────────────────────────────────────────────────────────────
def create_token(user_id: str, email: str, tier: str = "free") -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "tier": tier,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ─── FastAPI Dependencies ───────────────────────────────────────────────────
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Extract user from Bearer token. Returns None for unauthenticated requests."""
    if credentials is None:
        return None
    payload = decode_token(credentials.credentials)
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_auth(user: User = Depends(get_current_user)) -> User:
    """Require authenticated user — raises 401 if not logged in."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_pro(user: User = Depends(require_auth)) -> User:
    """Require Pro or higher tier."""
    if user.tier not in ("pro", "premium", "admin"):
        raise HTTPException(status_code=403, detail="Pro subscription required")
    return user


def require_admin(user: User = Depends(require_auth)) -> User:
    """Require admin role."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ─── Registration / Login ───────────────────────────────────────────────────
def register_user(db: Session, email: str, username: str, password: str, referral_code: str = None) -> User:
    """Create a new user. Raises ValueError on duplicates."""
    if db.query(User).filter(User.email == email).first():
        raise ValueError("Email already registered")
    if db.query(User).filter(User.username == username).first():
        raise ValueError("Username already taken")

    referred_by = None
    if referral_code:
        referrer = db.query(User).filter(User.referral_code == referral_code).first()
        if referrer:
            referred_by = referrer.id

    user = User(
        email=email,
        username=username,
        password_hash=hash_password(password),
        referral_code=secrets.token_urlsafe(8),
        referred_by=referred_by,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login_user(db: Session, email: str, password: str) -> dict:
    """Validate credentials and return JWT + user info."""
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    token = create_token(user.id, user.email, user.tier)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "tier": user.tier,
            "is_admin": user.is_admin,
        },
    }
