"""Portfolio routes — add holdings, view P&L, portfolio health score."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from service.database import get_db, ensure_db
from service.auth import require_auth
from service.models_db import User, Portfolio

ensure_db()

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class HoldingCreate(BaseModel):
    ticker: str
    quantity: int
    purchase_price: float
    purchase_date: str  # ISO format


class HoldingUpdate(BaseModel):
    quantity: int | None = None
    purchase_price: float | None = None


def _get_current_price(ticker: str) -> float | None:
    """Fetch current price from the ticker cache (same source as API)."""
    import json, os
    cache_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "service", "models", "ticker_cache.json",
    )
    if not os.path.exists(cache_path):
        return None
    with open(cache_path) as f:
        cache = json.load(f)
    entry = cache.get(ticker)
    return entry.get("close") if entry else None


def _get_quant_score(ticker: str) -> dict:
    """Compute a basic quant score from cached features."""
    import json, os
    cache_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "service", "models", "ticker_cache.json",
    )
    if not os.path.exists(cache_path):
        return {"score": 50, "label": "Neutral"}
    with open(cache_path) as f:
        cache = json.load(f)
    entry = cache.get(ticker)
    if not entry:
        return {"score": 50, "label": "Neutral"}

    features = entry.get("features", {})
    above_sma = entry.get("above_sma", False)

    score = 50
    if above_sma:
        score += 15
    rsi = features.get("rsi_14", 50)
    if 40 <= rsi <= 60:
        score += 5
    elif rsi > 60:
        score += 10
    elif rsi < 30:
        score -= 5
    macd = features.get("macd", 0)
    if macd > 0:
        score += 10
    else:
        score -= 5
    ret10 = features.get("ret_10", 0)
    if ret10 > 0.03:
        score += 10
    elif ret10 > 0:
        score += 5
    elif ret10 < -0.03:
        score -= 10
    elif ret10 < 0:
        score -= 5

    score = max(0, min(100, score))
    if score >= 70:
        label = "Strong"
    elif score >= 55:
        label = "Healthy"
    elif score >= 40:
        label = "Neutral"
    else:
        label = "Risk Elevated"

    return {"score": score, "label": label}


@router.get("")
def get_portfolio(user: User = Depends(require_auth), db: Session = Depends(get_db)):
    holdings = db.query(Portfolio).filter(Portfolio.user_id == user.id).all()
    items = []
    total_value = 0
    total_cost = 0

    for h in holdings:
        current_price = _get_current_price(h.ticker)
        qty_data = _get_quant_score(h.ticker)
        if current_price is None:
            current_price = h.purchase_price
        current_value = current_price * h.quantity
        cost = h.purchase_price * h.quantity
        pnl = current_value - cost
        pnl_pct = (pnl / cost * 100) if cost > 0 else 0
        total_value += current_value
        total_cost += cost
        items.append({
            "id": h.id,
            "ticker": h.ticker,
            "quantity": h.quantity,
            "purchase_price": h.purchase_price,
            "purchase_date": h.purchase_date.isoformat(),
            "current_price": round(current_price, 2),
            "current_value": round(current_value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "quant_score": qty_data,
        })

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

    avg_score = 50
    if items:
        avg_score = sum(it["quant_score"]["score"] for it in items) // len(items)

    if avg_score >= 70:
        health = "Strong"
    elif avg_score >= 55:
        health = "Healthy"
    elif avg_score >= 40:
        health = "Neutral"
    else:
        health = "Risk Elevated"

    return {
        "holdings": items,
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "portfolio_score": avg_score,
        "portfolio_health": health,
    }


@router.post("/add")
def add_holding(req: HoldingCreate, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    from datetime import datetime
    count = db.query(Portfolio).filter(Portfolio.user_id == user.id).count()
    if count >= 20:
        raise HTTPException(status_code=403, detail="Maximum 20 holdings on free tier. Upgrade for more.")
    h = Portfolio(
        user_id=user.id,
        ticker=req.ticker.upper(),
        quantity=req.quantity,
        purchase_price=req.purchase_price,
        purchase_date=datetime.fromisoformat(req.purchase_date),
    )
    db.add(h)
    db.commit()
    db.refresh(h)
    return {"ok": True, "id": h.id}


@router.delete("/{holding_id}")
def remove_holding(holding_id: str, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    h = db.query(Portfolio).filter(Portfolio.id == holding_id, Portfolio.user_id == user.id).first()
    if not h:
        raise HTTPException(status_code=404, detail="Holding not found")
    db.delete(h)
    db.commit()
    return {"ok": True}
