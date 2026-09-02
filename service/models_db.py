"""SQLAlchemy ORM models — User, Session, Signal, Watchlist, Alert, Subscription."""

import uuid
import time
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text,
    ForeignKey, JSON, Index, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from service.database import Base


def _uuid():
    return uuid.uuid4().hex


def _now():
    return datetime.now(timezone.utc)


# ─── User ────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id = Column(String(32), primary_key=True, default=_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(128), default="")
    tier = Column(String(16), default="free")  # free | pro | premium
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    referral_code = Column(String(16), unique=True, default=_uuid)
    referred_by = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    watchlists = relationship("Watchlist", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")
    portfolios = relationship("Portfolio", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")


# ─── Session ─────────────────────────────────────────────────────────────────
class UserSession(Base):
    __tablename__ = "sessions"

    id = Column(String(32), primary_key=True, default=_uuid)
    user_id = Column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=_now)

    user = relationship("User", back_populates="sessions")


# ─── Signal Ledger ───────────────────────────────────────────────────────────
class SignalRecord(Base):
    __tablename__ = "signal_ledger"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False, index=True)
    signal = Column(String(10), nullable=False)  # BUY | HOLD | SELL | NEUTRAL
    confidence = Column(Float, nullable=False)
    regime = Column(String(10), nullable=False)  # BULL | BEAR
    price = Column(Float, nullable=False)
    sma_200 = Column(Float, nullable=False)
    model_version = Column(String(32), default="v2")
    threshold = Column(Float, nullable=False)
    features_snapshot = Column(JSON, nullable=True)
    # Performance tracking (populated later)
    ret_1d = Column(Float, nullable=True)
    ret_5d = Column(Float, nullable=True)
    ret_20d = Column(Float, nullable=True)
    max_favorable = Column(Float, nullable=True)
    max_adverse = Column(Float, nullable=True)
    created_at = Column(DateTime, default=_now, index=True)

    __table_args__ = (
        Index("ix_signal_ticker_date", "ticker", "created_at"),
    )


# ─── Watchlist ───────────────────────────────────────────────────────────────
class Watchlist(Base):
    __tablename__ = "watchlists"

    id = Column(String(32), primary_key=True, default=_uuid)
    user_id = Column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(64), nullable=False, default="My Watchlist")
    created_at = Column(DateTime, default=_now)

    user = relationship("User", back_populates="watchlists")
    items = relationship("WatchlistItem", back_populates="watchlist", cascade="all, delete-orphan")


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id = Column(String(32), primary_key=True, default=_uuid)
    watchlist_id = Column(String(32), ForeignKey("watchlists.id"), nullable=False, index=True)
    ticker = Column(String(20), nullable=False)
    added_at = Column(DateTime, default=_now)

    watchlist = relationship("Watchlist", back_populates="items")

    __table_args__ = (
        UniqueConstraint("watchlist_id", "ticker", name="uq_watchlist_ticker"),
    )


# ─── Alert ───────────────────────────────────────────────────────────────────
class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String(32), primary_key=True, default=_uuid)
    user_id = Column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    ticker = Column(String(20), nullable=False, index=True)
    alert_type = Column(String(32), nullable=False)
    # signal_change | confidence_above | price_cross_sma | score_above
    condition_json = Column(JSON, nullable=False, default=dict)
    is_active = Column(Boolean, default=True)
    last_triggered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)

    user = relationship("User", back_populates="alerts")


# ─── Portfolio ───────────────────────────────────────────────────────────────
class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(String(32), primary_key=True, default=_uuid)
    user_id = Column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    ticker = Column(String(20), nullable=False)
    quantity = Column(Integer, nullable=False)
    purchase_price = Column(Float, nullable=False)
    purchase_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=_now)

    user = relationship("User", back_populates="portfolios")

    __table_args__ = (
        Index("ix_portfolio_user_ticker", "user_id", "ticker"),
    )


# ─── Subscription / Payment ─────────────────────────────────────────────────
class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String(32), primary_key=True, default=_uuid)
    user_id = Column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    plan = Column(String(16), nullable=False)  # free | pro | premium
    status = Column(String(16), default="active")  # active | trial | expired | cancelled
    provider = Column(String(16), default="razorpay")  # razorpay | manual
    provider_subscription_id = Column(String(128), nullable=True)
    amount = Column(Float, nullable=True)
    currency = Column(String(8), default="INR")
    starts_at = Column(DateTime, default=_now)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)

    user = relationship("User", back_populates="subscriptions")


# ─── API Key (migrated from keys.json) ──────────────────────────────────────
class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(32), primary_key=True, default=_uuid)
    user_id = Column(String(32), ForeignKey("users.id"), nullable=True, index=True)
    key_hash = Column(String(64), unique=True, nullable=False, index=True)
    tier = Column(String(16), default="free")
    owner = Column(String(128), default="unknown")
    is_active = Column(Boolean, default=True)
    calls_today = Column(Integer, default=0)
    created_at = Column(DateTime, default=_now)
