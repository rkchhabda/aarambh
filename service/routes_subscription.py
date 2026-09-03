"""Subscription routes — plan management, tier upgrade, billing status."""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from service.database import get_db, ensure_db
from service.auth import require_auth
from service.models_db import User, Subscription

ensure_db()

router = APIRouter(prefix="/subscription", tags=["subscription"])

PLANS = {
    "free": {"name": "Free", "price": 0, "features": ["Basic signals", "5 watchlists", "20 holdings", "10 alerts"]},
    "pro": {"name": "Pro", "price": 999, "features": ["Full signals", "Unlimited watchlists", "50 holdings", "50 alerts", "Backtesting", "Portfolio analytics", "Priority support"]},
    "premium": {"name": "Premium", "price": 2999, "features": ["Everything in Pro", "API access", "White-label reports", "Custom models", "Dedicated support", "Early access"]},
}


class UpgradeRequest(BaseModel):
    plan: str  # pro | premium


@router.get("/plans")
def list_plans():
    return PLANS


@router.get("/status")
def get_subscription_status(user: User = Depends(require_auth), db: Session = Depends(get_db)):
    sub = db.query(Subscription).filter(
        Subscription.user_id == user.id, Subscription.status.in_(["active", "trial"])
    ).order_by(Subscription.created_at.desc()).first()

    if sub and sub.expires_at:
        exp = sub.expires_at.replace(tzinfo=timezone.utc) if sub.expires_at.tzinfo is None else sub.expires_at
        if exp < datetime.now(timezone.utc):
            sub.status = "expired"
            db.commit()

    return {
        "tier": user.tier,
        "plan": sub.plan if sub else "free",
        "status": sub.status if sub else "active",
        "expires_at": sub.expires_at.isoformat() if sub and sub.expires_at else None,
        "features": PLANS.get(user.tier, PLANS["free"])["features"],
    }


@router.post("/upgrade")
def upgrade_plan(req: UpgradeRequest, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    if req.plan not in PLANS or req.plan == "free":
        raise HTTPException(status_code=400, detail="Invalid plan. Choose 'pro' or 'premium'.")

    existing = db.query(Subscription).filter(
        Subscription.user_id == user.id, Subscription.status.in_(["active", "trial"])
    ).first()

    if existing and existing.plan == req.plan:
        raise HTTPException(status_code=400, detail=f"Already on {req.plan} plan.")

    # Deactivate old subscription
    if existing:
        existing.status = "cancelled"
        db.commit()

    plan_info = PLANS[req.plan]
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=30)

    sub = Subscription(
        user_id=user.id,
        plan=req.plan,
        status="active",
        provider="manual",
        amount=plan_info["price"],
        currency="INR",
        starts_at=now,
        expires_at=expires,
    )
    db.add(sub)

    user.tier = req.plan
    db.commit()

    return {
        "ok": True,
        "plan": req.plan,
        "status": "active",
        "expires_at": expires.isoformat(),
        "message": f"Upgraded to {req.plan} plan (manual activation). In production, this would integrate with Razorpay.",
    }


@router.post("/cancel")
def cancel_subscription(user: User = Depends(require_auth), db: Session = Depends(get_db)):
    sub = db.query(Subscription).filter(
        Subscription.user_id == user.id, Subscription.status.in_(["active", "trial"])
    ).first()

    if not sub:
        raise HTTPException(status_code=404, detail="No active subscription to cancel.")

    sub.status = "cancelled"
    user.tier = "free"
    db.commit()

    return {"ok": True, "message": "Subscription cancelled. Downgraded to free tier."}


@router.post("/admin/set-tier")
def admin_set_tier(email: str = "", plan: str = "free", user: User = Depends(require_auth), db: Session = Depends(get_db)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only.")

    target = db.query(User).filter(User.email == email).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"User {email} not found.")

    if plan not in PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan.")

    target.tier = plan

    if plan != "free":
        existing = db.query(Subscription).filter(
            Subscription.user_id == target.id, Subscription.status.in_(["active", "trial"])
        ).first()
        if existing:
            existing.status = "cancelled"

        sub = Subscription(
            user_id=target.id, plan=plan, status="active", provider="manual",
            amount=PLANS[plan]["price"], currency="INR",
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        )
        db.add(sub)

    db.commit()
    return {"ok": True, "message": f"Set {email} to {plan} tier."}
