"""Admin routes — user management, metrics, model monitoring."""

import os
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from service.database import get_db, ensure_db
from service.auth import require_admin
from service.models_db import User, Alert, Portfolio, Watchlist, SignalRecord, APIKey, Subscription

ensure_db()

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard")
def admin_dashboard(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
    pro_users = db.query(func.count(User.id)).filter(User.tier == "pro").scalar() or 0
    premium_users = db.query(func.count(User.id)).filter(User.tier == "premium").scalar() or 0
    free_users = db.query(func.count(User.id)).filter(User.tier == "free").scalar() or 0
    total_signals = db.query(func.count(SignalRecord.id)).scalar() or 0
    total_alerts = db.query(func.count(Alert.id)).filter(Alert.is_active == True).scalar() or 0
    total_watchlists = db.query(func.count(Watchlist.id)).scalar() or 0
    total_portfolios = db.query(func.count(Portfolio.id)).scalar() or 0

    return {
        "users": {"total": total_users, "active": active_users, "free": free_users, "pro": pro_users, "premium": premium_users},
        "signals": {"total": total_signals},
        "alerts": {"active": total_alerts},
        "watchlists": {"total": total_watchlists},
        "portfolios": {"total": total_portfolios},
    }


@router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    offset = (page - 1) * per_page
    total = db.query(func.count(User.id)).scalar() or 0
    users = db.query(User).order_by(User.created_at.desc()).offset(offset).limit(per_page).all()
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "username": u.username,
                "tier": u.tier,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ],
    }


@router.get("/model-status")
def model_status(user: User = Depends(require_admin)):
    models_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "service", "models",
    )
    models = {}
    for fname in ["xgboost.pkl", "randomforest.pkl", "logisticregression.pkl", "meta_model.pkl", "scaler.pkl"]:
        path = os.path.join(models_dir, fname)
        size = os.path.getsize(path) if os.path.exists(path) else 0
        models[fname] = {"exists": os.path.exists(path), "size_kb": round(size / 1024, 1)}

    cache_path = os.path.join(models_dir, "ticker_cache.json")
    cache_age_hours = None
    if os.path.exists(cache_path):
        mtime = os.path.getmtime(cache_path)
        import time
        cache_age_hours = round((time.time() - mtime) / 3600, 1)
        with open(cache_path) as f:
            cache_tickers = len(json.load(f))
    else:
        cache_tickers = 0

    return {
        "models": models,
        "cache": {"tickers": cache_tickers, "age_hours": cache_age_hours},
    }
