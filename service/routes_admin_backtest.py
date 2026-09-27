"""Admin backtest endpoint — serves verified 4-year Nifty 100 regime filter net series."""

import os
import json
import numpy as np
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/admin", tags=["admin"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NET_SERIES_PATH = os.path.join(BASE_DIR, "scripts", "verification", "full_cycle_net_series.npy")
REPORT_PATH = os.path.join(BASE_DIR, "scripts", "verification", "drawdown_stress_test_results.json")

@router.get("/backtest-data")
def backtest_data():
    """Return verified multi-year Nifty 100 200-SMA regime filter net return series."""
    if os.path.exists(NET_SERIES_PATH):
        try:
            arr = np.load(NET_SERIES_PATH)
            return {
                "net_series": arr.tolist(),
                "universe": "Nifty 100 Indian Equities",
                "days": len(arr),
                "strategy": "Systematic 200-day SMA Regime Filter",
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load verified net series: {e}")
            
    # Fallback to report if json exists
    if os.path.exists(REPORT_PATH):
        try:
            with open(REPORT_PATH) as f:
                report = json.load(f)
            return {"report": report}
        except Exception:
            pass

    raise HTTPException(status_code=404, detail="Verified backtest artifacts not found.")

@router.get("/signal-count")
def signal_count():
    """Return the total number of recorded signals (for debugging)."""
    from service.database import SessionLocal
    from service.models_db import SignalRecord
    db = SessionLocal()
    try:
        count = db.query(SignalRecord).count()
    finally:
        db.close()
    return {"signal_count": count}
