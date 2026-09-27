"""SQLAlchemy ORM models — User, Session, Signal, Watchlist, Alert, Subscription, RegimeForwardLog."""

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


# ─── Live Forward-Test Regime Log ────────────────────────────────────────────
# LOCKED as of 2026-09-27. DO NOT ROTATE OR MODIFY based on forward performance.
#
# One row per ticker per NSE trading day. Stores:
#   - The regime state (RISK-ON / RISK-OFF) as determined by the 200-day SMA
#     at the close of trade_date.
#   - The next trading day's close and 1-day return, filled the following run
#     using only already-closed point-in-time data — no lookahead possible.
#   - A was_protected boolean grading whether the regime state delivered
#     protection (RISK-OFF + down day) or participation (RISK-ON + up day).
#
# SEPARATE from signal_ledger (ML ensemble events). Different grain (per
# calendar-day vs per signal event) and different semantics (pure 200-SMA
# regime filter vs directional ML signal).
#
# tracker_start records the hardcoded public start date of this live run —
# the date that makes this evidence rather than a claim.
# ─────────────────────────────────────────────────────────────────────────────
class RegimeForwardLog(Base):
    __tablename__ = "regime_forward_log"

    id            = Column(Integer, primary_key=True, autoincrement=True)

    # ── Identity (one row per ticker per trading day) ──
    trade_date    = Column(String(10), nullable=False)    # YYYY-MM-DD (NSE close date)
    ticker        = Column(String(20), nullable=False)

    # ── Regime state as-of this close ──
    close_price   = Column(Float, nullable=False)         # EOD close used for SMA calc
    sma_200       = Column(Float, nullable=False)         # Rolling 200-day SMA
    regime_state  = Column(String(10), nullable=False)    # 'RISK-ON' or 'RISK-OFF'

    # ── Next-day outcome (filled the following trading day's run) ──
    next_close    = Column(Float, nullable=True)          # Following day's close
    ret_1d        = Column(Float, nullable=True)          # (next_close/close_price) - 1

    # ── Grading (filled alongside ret_1d, no lookahead) ──
    # TRUE  if RISK-OFF + ret_1d <= 0  (protection delivered — filter was flat on a down day)
    # TRUE  if RISK-ON  + ret_1d >  0  (participation delivered — filter invested on up day)
    # FALSE if RISK-OFF + ret_1d >  0  (opportunity cost — filter was flat on an up day)
    # FALSE if RISK-ON  + ret_1d <= 0  (drawdown exposure — filter invested on a down day)
    was_protected = Column(Boolean, nullable=True)

    # ── Metadata ──
    data_source   = Column(String(20), nullable=False, default="NSE_DIRECT")
    tracker_start = Column(String(10), nullable=False)    # hardcoded public start date
    created_at    = Column(DateTime, default=_now)

    __table_args__ = (
        # Idempotent upsert safety: one row per ticker per day
        UniqueConstraint("trade_date", "ticker", name="uq_rfl_date_ticker"),
        Index("ix_rfl_ticker_date", "ticker", "trade_date"),
        Index("ix_rfl_date", "trade_date"),
    )

