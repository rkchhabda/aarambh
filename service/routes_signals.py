"""Signal history routes — record every signal, query past signals."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from service.database import get_db, ensure_db
from service.auth import require_auth
from service.models_db import SignalRecord

ensure_db()

router = APIRouter(prefix="/signals", tags=["signals"])


class SignalLogRequest(BaseModel):
    ticker: str
    signal: str
    confidence: float
    regime: str
    price: float
    sma_200: float
    model_version: str = "v2"
    threshold: float = 0.85
    features: dict | None = None


@router.post("/log")
def log_signal(req: SignalLogRequest, db: Session = Depends(get_db)):
    """Record a signal to the ledger. Called internally after each /v1/signal response."""
    rec = SignalRecord(
        ticker=req.ticker,
        signal=req.signal,
        confidence=req.confidence,
        regime=req.regime,
        price=req.price,
        sma_200=req.sma_200,
        model_version=req.model_version,
        threshold=req.threshold,
        features_snapshot=req.features,
    )
    db.add(rec)
    db.commit()
    return {"ok": True, "id": rec.id}


@router.get("/history")
def signal_history(
    ticker: str | None = Query(None),
    signal: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Query signal history. Public endpoint (no auth required)."""
    q = db.query(SignalRecord).order_by(SignalRecord.created_at.desc())
    if ticker:
        q = q.filter(SignalRecord.ticker == ticker.upper())
    if signal:
        q = q.filter(SignalRecord.signal == signal.upper())
    records = q.limit(limit).all()

    return {
        "total": len(records),
        "signals": [
            {
                "id": r.id,
                "ticker": r.ticker,
                "signal": r.signal,
                "confidence": r.confidence,
                "regime": r.regime,
                "price": r.price,
                "sma_200": r.sma_200,
                "model_version": r.model_version,
                "ret_1d": r.ret_1d,
                "ret_5d": r.ret_5d,
                "ret_20d": r.ret_20d,
                "timestamp": r.created_at.isoformat(),
            }
            for r in records
        ],
    }


@router.get("/stats")
def signal_stats(db: Session = Depends(get_db)):
    """Aggregate signal performance stats. Public endpoint."""
    from sqlalchemy import func

    total = db.query(func.count(SignalRecord.id)).scalar() or 0
    buy_count = db.query(func.count(SignalRecord.id)).filter(SignalRecord.signal == "BUY").scalar() or 0
    hold_count = db.query(func.count(SignalRecord.id)).filter(SignalRecord.signal == "HOLD").scalar() or 0

    avg_conf = db.query(func.avg(SignalRecord.confidence)).scalar() or 0

    # Performance (where return data is available)
    ret_count = db.query(func.count(SignalRecord.id)).filter(SignalRecord.ret_5d.isnot(None)).scalar() or 0
    avg_ret = db.query(func.avg(SignalRecord.ret_5d)).filter(SignalRecord.ret_5d.isnot(None)).scalar() or 0

    return {
        "total_signals": total,
        "buy_signals": buy_count,
        "hold_signals": hold_count,
        "avg_confidence": round(float(avg_conf), 4),
        "signals_with_return": ret_count,
        "avg_5d_return": round(float(avg_ret), 6),
    }
