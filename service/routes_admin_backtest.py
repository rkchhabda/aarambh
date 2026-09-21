import os
import json
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/backtest-data")
def backtest_data():
    """Return aggregated backtest net series for dashboard.
    If the backtest JSON is not present, compute on the fly using phase5 scripts.
    """
    # Path to precomputed final report (optional)
    workdir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    report_path = os.path.join(workdir, "scripts", "phase5", "final_report.json")
    if os.path.exists(report_path):
        try:
            with open(report_path) as f:
                report = json.load(f)
                # This report may contain aggregated metrics but not the time series.
                # For simplicity we always recompute the net series below.
        except Exception:
            pass
    # Compute on the fly
    try:
        from scripts.phase5.backtest_final import load_all, strategy_positions, bt
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest scripts not available: {e}")
    data, _ = load_all()
    nets = []
    for t, df in data.items():
        pos = strategy_positions(df, "regime_long")
        nets.append(bt(pos, df["fwd_ret"].values, 5.0))
    # Use pandas to compute mean series
    import pandas as pd
    port_net = pd.DataFrame(nets).T.mean(axis=1).values
    return {"net_series": port_net.tolist()}

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
