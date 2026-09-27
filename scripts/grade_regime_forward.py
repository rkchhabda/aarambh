"""
grade_regime_forward.py — Daily live forward-test grading for the 200-SMA regime filter.

Run AFTER rebuild_cache_v2.py in the GitHub Actions pipeline (18:30 IST, M-F).

Two jobs per run:

  JOB 1 — Fill outcomes for yesterday's rows:
    For every row where trade_date = yesterday AND ret_1d IS NULL, pull
    today's close from ticker_cache.json (freshly rebuilt) and compute:
      ret_1d = (today_close / yesterday_close) - 1
      was_protected grading (see logic below)

  JOB 2 — Log today's regime state:
    For every ticker in the 138-universe, INSERT OR IGNORE one row for today
    with today's close, 200-SMA, and regime_state. ret_1d stays NULL until
    tomorrow's run.

NO LOOKAHEAD: Runs after 15:30 IST NSE close. Today's price in the cache is
a fully settled EOD price. Yesterday's outcomes are filled with today's
already-closed price — all data used existed before being referenced.

PANEL: The 10 display tickers are tracked alongside all 138 universe tickers.
The portfolio equity curve is computed from the full 138, not just the panel.

TRACKER START DATE: 2026-09-29 (first Monday after planning 2026-09-27).
HARDCODED. MUST NEVER CHANGE.
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, date, timedelta

# ── Repo root importable ──────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# ─── LIVE FORWARD-TEST VISIBILITY PANEL ──────────────────────────────────────
# LOCKED as of 2026-09-27. DO NOT ROTATE OR MODIFY based on forward performance.
#
# These 10 tickers are the public visibility subset of the 138-ticker tracked
# universe. Selected on 2026-09-27 by objective criteria (one per sector,
# market-cap spread, all in features/universe.py) BEFORE observing any forward
# outcomes. Rotating underperformers out or adding outperformers would introduce
# survivorship bias and retroactively invalidate the public track record.
#
# To propose a change: open a dated commit with explicit written rationale,
# reviewed separately from any performance observed during tracking.
# ─────────────────────────────────────────────────────────────────────────────
FORWARD_TEST_PANEL = [
    "RELIANCE.NS",   # Energy / Conglomerate  — largest NSE constituent
    "HDFCBANK.NS",   # Private Banking        — Nifty 50 anchor
    "TCS.NS",        # IT Services            — defensive export earner
    "SUNPHARMA.NS",  # Pharmaceuticals        — defensive domestic
    "TATASTEEL.NS",  # Metals & Mining        — cyclical stress amplifier
    "BAJFINANCE.NS", # NBFC                   — high-beta credit cycle
    "NTPC.NS",       # Utilities              — regulated PSU power
    "MARUTI.NS",     # Automobiles            — domestic consumer cyclical
    "HINDUNILVR.NS", # Consumer Staples       — most defensive in universe
    "APOLLOHOSP.NS", # Healthcare Services    — growth/defensive hybrid
]

# ── Constants ─────────────────────────────────────────────────────────────────
TRACKER_START  = "2026-09-29"   # Hardcoded public start — DO NOT CHANGE
MIN_SAMPLE_N   = 60             # Trading days before headline metrics show
CACHE_PATH     = os.path.join(BASE_DIR, "service", "models", "ticker_cache.json")
DB_PATH        = os.path.join(BASE_DIR, "service", "aarambh.db")
SUMMARY_PATH   = os.path.join(BASE_DIR, "service", "models", "regime_forward_summary.json")
CSV_PATH       = os.path.join(BASE_DIR, "service", "models", "regime_forward_log.csv")

# ── Universe ──────────────────────────────────────────────────────────────────
from features.universe import TICKERS as UNIVERSE_TICKERS


# ── DB helpers ────────────────────────────────────────────────────────────────

def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table(conn):
    """Create table and indexes idempotently (safe first run)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS regime_forward_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date    TEXT    NOT NULL,
            ticker        TEXT    NOT NULL,
            close_price   REAL    NOT NULL,
            sma_200       REAL    NOT NULL,
            regime_state  TEXT    NOT NULL,
            next_close    REAL,
            ret_1d        REAL,
            was_protected INTEGER,
            data_source   TEXT    NOT NULL DEFAULT 'NSE_DIRECT',
            tracker_start TEXT    NOT NULL,
            created_at    TEXT    NOT NULL,
            UNIQUE (trade_date, ticker)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS ix_rfl_ticker_date ON regime_forward_log (ticker, trade_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_rfl_date        ON regime_forward_log (trade_date)")
    conn.commit()


# ── Date helpers ──────────────────────────────────────────────────────────────

def _is_weekday(d: date) -> bool:
    return d.weekday() < 5


def _prev_weekday(d: date) -> date:
    prev = d - timedelta(days=1)
    while not _is_weekday(prev):
        prev -= timedelta(days=1)
    return prev


# ── Job 1: fill yesterday's outcomes ─────────────────────────────────────────

def job1_fill_yesterday_outcomes(conn, cache: dict, today_str: str) -> int:
    """
    For rows with trade_date = yesterday and ret_1d IS NULL:
    fill next_close, ret_1d, was_protected using today's settled close.

    Grading logic (2x2 matrix):
      RISK-OFF + ret_1d <= 0  → was_protected=True  (protection delivered)
      RISK-ON  + ret_1d >  0  → was_protected=True  (participation delivered)
      RISK-OFF + ret_1d >  0  → was_protected=False (opportunity cost)
      RISK-ON  + ret_1d <= 0  → was_protected=False (drawdown exposure)
    """
    yesterday_str = _prev_weekday(date.fromisoformat(today_str)).isoformat()

    rows = conn.execute(
        "SELECT id, ticker, regime_state, close_price FROM regime_forward_log "
        "WHERE trade_date = ? AND ret_1d IS NULL",
        (yesterday_str,)
    ).fetchall()

    if not rows:
        print(f"[JOB1] No unfilled rows for {yesterday_str}.")
        return 0

    filled = 0
    for row in rows:
        ticker = row["ticker"]
        entry  = cache.get(ticker)
        if not entry:
            continue

        today_close     = entry.get("close")
        yesterday_close = row["close_price"]
        if not today_close or not yesterday_close or yesterday_close <= 0:
            continue

        ret_1d       = (float(today_close) / float(yesterday_close)) - 1.0
        regime_state = row["regime_state"]

        if regime_state == "RISK-OFF":
            was_protected = 1 if ret_1d <= 0 else 0
        else:  # RISK-ON
            was_protected = 1 if ret_1d > 0 else 0

        conn.execute(
            "UPDATE regime_forward_log SET next_close=?, ret_1d=?, was_protected=? WHERE id=?",
            (round(float(today_close), 4), round(ret_1d, 6), was_protected, row["id"])
        )
        filled += 1

    conn.commit()
    print(f"[JOB1] Filled {filled}/{len(rows)} rows for {yesterday_str}.")
    return filled


# ── Job 2: log today's regime state ──────────────────────────────────────────

def job2_log_today(conn, cache: dict, today_str: str) -> int:
    """
    INSERT OR IGNORE one row per universe ticker for today.
    Idempotent — safe to re-run after a partial failure.
    """
    now_str  = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    inserted = 0
    skipped  = 0

    for ticker in UNIVERSE_TICKERS:
        entry = cache.get(ticker)
        if not entry:
            skipped += 1
            continue

        close_price = entry.get("close")
        sma_200     = entry.get("sma_200")
        above_sma   = entry.get("above_sma")

        if None in (close_price, sma_200, above_sma) or float(sma_200) <= 0:
            skipped += 1
            continue

        regime_state = "RISK-ON" if above_sma else "RISK-OFF"

        try:
            conn.execute(
                "INSERT OR IGNORE INTO regime_forward_log "
                "(trade_date,ticker,close_price,sma_200,regime_state,data_source,tracker_start,created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (today_str, ticker,
                 round(float(close_price), 4), round(float(sma_200), 4),
                 regime_state, "NSE_DIRECT", TRACKER_START, now_str)
            )
            inserted += 1
        except Exception as e:
            print(f"[WARN] Insert failed for {ticker}/{today_str}: {e}")
            skipped += 1

    conn.commit()
    print(f"[JOB2] Today ({today_str}): {inserted} inserted, {skipped} skipped.")
    return inserted


# ── Portfolio summary ─────────────────────────────────────────────────────────

def compute_portfolio_summary(conn) -> dict:
    """
    Build portfolio-level equity curves from graded rows. Mirrors exactly the
    backtest logic: equal-weight 138-ticker universe; position = 1.0 when RISK-ON,
    0.0 when RISK-OFF. No transaction costs applied (grading is cost-free).
    """
    rows = conn.execute(
        "SELECT trade_date, ticker, regime_state, ret_1d "
        "FROM regime_forward_log WHERE ret_1d IS NOT NULL "
        "ORDER BY trade_date ASC"
    ).fetchall()

    if not rows:
        return {"sample_n": 0, "tracker_start": TRACKER_START, "min_sample_n": MIN_SAMPLE_N}

    import collections
    by_date = collections.OrderedDict()
    for r in rows:
        by_date.setdefault(r["trade_date"], []).append(
            (r["ticker"], r["regime_state"], r["ret_1d"])
        )

    dates      = list(by_date.keys())
    sample_n   = len(dates)
    filter_eq  = 1.0
    bh_eq      = 1.0
    filter_curve = [1.0]
    bh_curve     = [1.0]

    for d in dates:
        day  = by_date[d]
        n    = len(day)
        if not n:
            continue
        bh_ret     = sum(r for _, _, r in day) / n
        riskon_rets = [r for _, s, r in day if s == "RISK-ON"]
        # pos=1 for RISK-ON, pos=0 for RISK-OFF, divide by full N (equal-weight)
        filter_ret = sum(riskon_rets) / n if riskon_rets else 0.0
        filter_eq *= (1.0 + filter_ret)
        bh_eq     *= (1.0 + bh_ret)
        filter_curve.append(round(filter_eq, 6))
        bh_curve.append(round(bh_eq, 6))

    def _max_dd(curve):
        peak = max_dd = 0.0
        peak = curve[0]
        for v in curve:
            if v > peak:
                peak = v
            dd = (v - peak) / peak
            if dd < max_dd:
                max_dd = dd
        return round(max_dd * 100, 2)

    # 2x2 grading matrix
    matrix_rows = conn.execute(
        "SELECT regime_state, was_protected, COUNT(*) as cnt "
        "FROM regime_forward_log WHERE was_protected IS NOT NULL "
        "GROUP BY regime_state, was_protected"
    ).fetchall()
    matrix = {"RISK-ON": {"protected": 0, "not": 0}, "RISK-OFF": {"protected": 0, "not": 0}}
    for r in matrix_rows:
        key = "protected" if r["was_protected"] else "not"
        if r["regime_state"] in matrix:
            matrix[r["regime_state"]][key] += int(r["cnt"])

    # Panel-level state for display (latest date only)
    panel_state = {}
    if dates:
        latest = dates[-1]
        panel_rows = conn.execute(
            "SELECT ticker, regime_state, close_price, sma_200 "
            "FROM regime_forward_log WHERE trade_date = ? AND ticker IN ({})".format(
                ",".join("?" * len(FORWARD_TEST_PANEL))
            ),
            [latest] + FORWARD_TEST_PANEL
        ).fetchall()
        for r in panel_rows:
            panel_state[r["ticker"]] = {
                "regime_state": r["regime_state"],
                "close_price": r["close_price"],
                "sma_200": r["sma_200"],
            }

    return {
        "tracker_start":           TRACKER_START,
        "sample_n":                sample_n,
        "min_sample_n":            MIN_SAMPLE_N,
        "last_date":               dates[-1],
        "universe_size":           len(UNIVERSE_TICKERS),
        "panel_tickers":           FORWARD_TEST_PANEL,
        "panel_state":             panel_state,
        "filter_total_return_pct": round((filter_eq - 1.0) * 100, 2),
        "bh_total_return_pct":     round((bh_eq - 1.0) * 100, 2),
        "filter_max_dd_pct":       _max_dd(filter_curve),
        "bh_max_dd_pct":           _max_dd(bh_curve),
        "filter_equity_curve":     filter_curve[-252:],  # up to 1 year of points
        "bh_equity_curve":         bh_curve[-252:],
        "dates":                   dates[-252:],
        "grading_matrix":          matrix,
    }


def write_summary_json(summary: dict):
    with open(SUMMARY_PATH, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[OK] Wrote summary → {SUMMARY_PATH}")


def export_csv(conn):
    """Export full graded log as downloadable CSV."""
    rows = conn.execute(
        "SELECT trade_date,ticker,close_price,sma_200,regime_state,"
        "next_close,ret_1d,was_protected,data_source,tracker_start "
        "FROM regime_forward_log ORDER BY trade_date ASC, ticker ASC"
    ).fetchall()
    with open(CSV_PATH, "w") as f:
        f.write("trade_date,ticker,close_price,sma_200,regime_state,"
                "next_close,ret_1d,was_protected,data_source,tracker_start\n")
        for r in rows:
            wp = ("" if r["was_protected"] is None else ("1" if r["was_protected"] else "0"))
            f.write(",".join([
                str(r["trade_date"] or ""), str(r["ticker"] or ""),
                str(r["close_price"] or ""), str(r["sma_200"] or ""),
                str(r["regime_state"] or ""), str(r["next_close"] or ""),
                str(r["ret_1d"] or ""), wp,
                str(r["data_source"] or ""), str(r["tracker_start"] or ""),
            ]) + "\n")
    print(f"[OK] Exported {len(rows)} rows → {CSV_PATH}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    today     = date.today()
    today_str = today.isoformat()

    if not _is_weekday(today):
        print(f"[SKIP] {today_str} is not a weekday.")
        return
    if today_str < TRACKER_START:
        print(f"[SKIP] Before tracker start ({TRACKER_START}).")
        return

    print(f"\n{'='*70}")
    print(f"REGIME FORWARD-TEST GRADER — {today_str}")
    print(f"Tracker start: {TRACKER_START}  |  Universe: {len(UNIVERSE_TICKERS)} tickers")
    print(f"{'='*70}\n")

    cache = {}
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            cache = json.load(f)
    else:
        print(f"[ERROR] Cache not found: {CACHE_PATH}")
        sys.exit(1)

    conn = _connect()
    try:
        _ensure_table(conn)
        job1_fill_yesterday_outcomes(conn, cache, today_str)
        job2_log_today(conn, cache, today_str)
        summary = compute_portfolio_summary(conn)
        write_summary_json(summary)
        export_csv(conn)

        n = summary.get("sample_n", 0)
        print(f"\n[SUMMARY] N={n} trading days graded.")
        if n < MIN_SAMPLE_N:
            print(f"[INFO] Below threshold ({MIN_SAMPLE_N}). "
                  f"{MIN_SAMPLE_N - n} more days needed before headline metrics show.")
        else:
            print(f"[RESULT] Filter MaxDD: {summary['filter_max_dd_pct']}%  "
                  f"B&H MaxDD: {summary['bh_max_dd_pct']}%")
    finally:
        conn.close()

    print(f"\n{'='*70}  Done.\n")


if __name__ == "__main__":
    main()
