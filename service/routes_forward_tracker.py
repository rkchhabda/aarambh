"""
routes_forward_tracker.py — Live 200-SMA Regime Forward-Test Tracker API.

Serves pre-computed summary data (written nightly by scripts/grade_regime_forward.py)
and the full daily log as a downloadable CSV.

Endpoints:
  GET /forward-tracker/summary   — JSON summary: equity curves, MaxDD, grading matrix
  GET /forward-tracker/download  — CSV download of the full daily log
"""

import json
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter(prefix="/forward-tracker", tags=["forward-tracker"])

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUMMARY_PATH = os.path.join(BASE_DIR, "service", "models", "regime_forward_summary.json")
CSV_PATH     = os.path.join(BASE_DIR, "service", "models", "regime_forward_log.csv")

# Tracker constants (mirrored from grading script — single truth in the script,
# reflected here only for the "not yet started" response body)
TRACKER_START = "2026-09-29"
MIN_SAMPLE_N  = 60


@router.get("/summary")
def get_forward_tracker_summary():
    """
    Return the live regime forward-test tracker summary.

    If the grader has not yet run (pre-start or first run not yet executed),
    returns a structured "too early" response rather than an error so the
    dashboard can display the informational message correctly.
    """
    if not os.path.exists(SUMMARY_PATH):
        return JSONResponse({
            "tracker_start": TRACKER_START,
            "sample_n": 0,
            "min_sample_n": MIN_SAMPLE_N,
            "status": "pending",
            "message": (
                f"Live tracking started {TRACKER_START}. "
                "First data will appear after the first trading day's pipeline run."
            ),
        })

    try:
        with open(SUMMARY_PATH) as f:
            summary = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read tracker summary: {e}")

    n = summary.get("sample_n", 0)
    if n == 0:
        summary["status"] = "pending"
        summary["message"] = (
            f"Live tracking started {TRACKER_START}. "
            "Awaiting first graded trading day."
        )
    elif n < MIN_SAMPLE_N:
        remaining = MIN_SAMPLE_N - n
        summary["status"] = "early"
        summary["message"] = (
            f"Live tracking started {TRACKER_START} — "
            f"N={n} days collected, {remaining} more needed before "
            f"reliable headline metrics can be shown."
        )
    else:
        summary["status"] = "active"

    return JSONResponse(summary)


@router.get("/download")
def download_forward_log():
    """
    Return the full regime forward-test daily log as a downloadable CSV.
    This is the complete, un-processed audit trail.
    """
    if not os.path.exists(CSV_PATH):
        raise HTTPException(
            status_code=404,
            detail=(
                "Forward-test log CSV not yet available. "
                f"Tracking begins {TRACKER_START}."
            )
        )
    return FileResponse(
        CSV_PATH,
        media_type="text/csv",
        filename="aarambh_regime_forward_log.csv",
        headers={"Content-Disposition": "attachment; filename=aarambh_regime_forward_log.csv"},
    )
