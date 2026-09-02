"""Watchlist routes — CRUD for user watchlists."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from service.database import get_db, ensure_db
from service.auth import require_auth
from service.models_db import User, Watchlist, WatchlistItem
from service.models_db import _uuid

ensure_db()

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistCreate(BaseModel):
    name: str = "My Watchlist"


class TickerAdd(BaseModel):
    ticker: str


@router.get("")
def list_watchlists(user: User = Depends(require_auth), db: Session = Depends(get_db)):
    lists = db.query(Watchlist).filter(Watchlist.user_id == user.id).all()
    return [
        {
            "id": w.id,
            "name": w.name,
            "items": [
                {"id": i.id, "ticker": i.ticker, "added_at": i.added_at.isoformat()}
                for i in w.items
            ],
            "item_count": len(w.items),
            "created_at": w.created_at.isoformat(),
        }
        for w in lists
    ]


@router.post("")
def create_watchlist(req: WatchlistCreate, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    count = db.query(Watchlist).filter(Watchlist.user_id == user.id).count()
    if count >= 5:
        raise HTTPException(status_code=403, detail="Maximum 5 watchlists. Upgrade for unlimited.")
    wl = Watchlist(user_id=user.id, name=req.name)
    db.add(wl)
    db.commit()
    db.refresh(wl)
    return {"id": wl.id, "name": wl.name, "items": [], "item_count": 0}


@router.delete("/{watchlist_id}")
def delete_watchlist(watchlist_id: str, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id, Watchlist.user_id == user.id).first()
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    db.delete(wl)
    db.commit()
    return {"ok": True}


@router.post("/{watchlist_id}/add")
def add_ticker(watchlist_id: str, req: TickerAdd, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id, Watchlist.user_id == user.id).first()
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    item_count = db.query(WatchlistItem).filter(WatchlistItem.watchlist_id == watchlist_id).count()
    if item_count >= 20:
        raise HTTPException(status_code=403, detail="Maximum 20 tickers per watchlist on free tier. Upgrade for more.")
    exists = db.query(WatchlistItem).filter(
        WatchlistItem.watchlist_id == watchlist_id, WatchlistItem.ticker == req.ticker
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="Ticker already in watchlist")
    item = WatchlistItem(watchlist_id=watchlist_id, ticker=req.ticker.upper())
    db.add(item)
    db.commit()
    return {"ok": True, "ticker": req.ticker.upper()}


@router.delete("/{watchlist_id}/remove/{ticker}")
def remove_ticker(watchlist_id: str, ticker: str, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id, Watchlist.user_id == user.id).first()
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    item = db.query(WatchlistItem).filter(
        WatchlistItem.watchlist_id == watchlist_id, WatchlistItem.ticker == ticker
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Ticker not in watchlist")
    db.delete(item)
    db.commit()
    return {"ok": True}
