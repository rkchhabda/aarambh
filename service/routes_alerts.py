"""Alert routes — create, list, delete signal/price/score alerts."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from service.database import get_db, ensure_db
from service.auth import require_auth
from service.models_db import User, Alert

ensure_db()

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertCreate(BaseModel):
    ticker: str
    alert_type: str  # signal_change | confidence_above | price_cross_sma | score_above
    threshold: float | None = None
    target_signal: str | None = None


@router.get("")
def list_alerts(user: User = Depends(require_auth), db: Session = Depends(get_db)):
    alerts = db.query(Alert).filter(Alert.user_id == user.id, Alert.is_active == True).all()
    return [
        {
            "id": a.id,
            "ticker": a.ticker,
            "alert_type": a.alert_type,
            "condition": a.condition_json,
            "is_active": a.is_active,
            "last_triggered": a.last_triggered_at.isoformat() if a.last_triggered_at else None,
            "created_at": a.created_at.isoformat(),
        }
        for a in alerts
    ]


@router.post("")
def create_alert(req: AlertCreate, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    count = db.query(Alert).filter(Alert.user_id == user.id, Alert.is_active == True).count()
    if count >= 10:
        raise HTTPException(status_code=403, detail="Maximum 10 alerts on free tier. Upgrade for more.")

    valid_types = ["signal_change", "confidence_above", "price_cross_sma", "score_above"]
    if req.alert_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid alert_type. Must be one of: {valid_types}")

    condition = {}
    if req.threshold is not None:
        condition["threshold"] = req.threshold
    if req.target_signal:
        condition["target_signal"] = req.target_signal

    alert = Alert(
        user_id=user.id,
        ticker=req.ticker.upper(),
        alert_type=req.alert_type,
        condition_json=condition,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return {"ok": True, "id": alert.id}


@router.delete("/{alert_id}")
def delete_alert(alert_id: str, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.user_id == user.id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_active = False
    db.commit()
    return {"ok": True}
