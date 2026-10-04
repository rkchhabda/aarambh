"""Step 5 & Step 6: SUE Feature Construction and Data Quality Audit.

Governing: Phase 6 Gate 3 Steps 5 & 6.
Formula:
    YoY_delta_EPS_t = EPS_adj_t - EPS_adj_{t-4}
    SUE_t = YoY_delta_EPS_t / rolling_std(YoY_delta_EPS, window=8, min_periods=3)

Timestamp Assignment:
    Assign to actual broadcast timestamp (broadCastDate) so data is strictly point-in-time.
    Effective trading date advances to next session if announced post-market (>= 15:30).
"""

import os
import sys
import json
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from features.universe import TICKERS

INPUT_CSV = os.path.join(BASE_DIR, "data", "fundamentals", "resolved_filings_split_adjusted.csv")
OUTPUT_SUE_CSV = os.path.join(BASE_DIR, "data", "fundamentals", "sue_features_quarterly.csv")
DEV_CUTOFF = "2025-09-16"

def build_sue():
    print(f"Loading input filings from: {INPUT_CSV}")
    if not os.path.exists(INPUT_CSV):
        print(f"Error: {INPUT_CSV} not found.")
        return None

    df = pd.read_csv(INPUT_CSV)
    # Sort chronologically by ticker and ISO broadCastDate string
    df = df.sort_values(["ticker", "broadCastDate"]).reset_index(drop=True)

    sue_records = []

    for ticker, group in df.groupby("ticker"):
        g = group.copy().sort_values("broadCastDate").reset_index(drop=True)
        if len(g) < 5:
            continue

        g["eps_adj_lag4"] = g["eps_adj"].shift(4)
        g["eps_yoy_delta"] = g["eps_adj"] - g["eps_adj_lag4"]
        g["rolling_std_delta"] = g["eps_yoy_delta"].rolling(window=8, min_periods=3).std()

        valid_mask = g["rolling_std_delta"] >= 1e-4
        g["sue"] = np.where(valid_mask, g["eps_yoy_delta"] / g["rolling_std_delta"], np.nan)

        effective_dates = []
        for b_str in g["broadCastDate"]:
            b_str = str(b_str).strip()
            date_part = b_str[:10]
            time_part = b_str[11:19] if len(b_str) >= 19 else "00:00:00"
            if time_part >= "15:30:00":
                d = datetime.strptime(date_part, "%Y-%m-%d") + timedelta(days=1)
                eff = d.strftime("%Y-%m-%d")
            else:
                eff = date_part
            effective_dates.append(eff)
        g["effective_date"] = effective_dates
        sue_records.append(g)

    if not sue_records:
        print("No SUE records generated.")
        return None

    full_sue = pd.concat(sue_records, ignore_index=True)
    full_sue.to_csv(OUTPUT_SUE_CSV, index=False)
    print(f"Quarterly SUE features saved to: {OUTPUT_SUE_CSV}")

    valid_sue = full_sue[full_sue["sue"].notna()].copy()

    print("\n" + "=" * 70)
    print("PHASE 6 GATE 3: STEP 6 DATA QUALITY REPORT (SUE FEATURE)")
    print("=" * 70)
    universe_tickers_count = len(TICKERS)
    tickers_with_sue = valid_sue["ticker"].nunique()
    print(f"Total Tickers in Universe: {universe_tickers_count}")
    print(f"Tickers with Usable SUE Series: {tickers_with_sue} / {universe_tickers_count} ({tickers_with_sue / universe_tickers_count * 100:.1f}%)")
    print(f"Total Usable Quarterly SUE Observations: {len(valid_sue):,}")

    per_ticker_sue = valid_sue.groupby("ticker")["sue"].count()
    print("\n--- SUE OBSERVATIONS PER TICKER DISTRIBUTION ---")
    print(per_ticker_sue.describe())

    print("\n--- SUE DISTRIBUTION STATISTICS (ACROSS ALL OBSERVATIONS) ---")
    print(valid_sue["sue"].describe(percentiles=[0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]))

    print(f"\nSUE Skewness: {valid_sue['sue'].skew():.3f}")
    print(f"SUE Kurtosis: {valid_sue['sue'].kurtosis():.3f}")

    summary_path = os.path.join(BASE_DIR, "data", "fundamentals", "gate3_sue_data_quality_summary.json")
    with open(summary_path, "w", encoding="utf-8") as sf:
        json.dump({
            "total_universe_tickers": universe_tickers_count,
            "tickers_with_sue": int(tickers_with_sue),
            "total_sue_observations": int(len(valid_sue)),
            "sue_quarters_per_ticker": {
                "mean": float(per_ticker_sue.mean()),
                "median": float(per_ticker_sue.median()),
                "min": int(per_ticker_sue.min()),
                "max": int(per_ticker_sue.max())
            },
            "sue_distribution": {
                "mean": float(valid_sue["sue"].mean()),
                "std": float(valid_sue["sue"].std()),
                "min": float(valid_sue["sue"].min()),
                "p01": float(valid_sue["sue"].quantile(0.01)),
                "p05": float(valid_sue["sue"].quantile(0.05)),
                "p25": float(valid_sue["sue"].quantile(0.25)),
                "p50": float(valid_sue["sue"].quantile(0.50)),
                "p75": float(valid_sue["sue"].quantile(0.75)),
                "p95": float(valid_sue["sue"].quantile(0.95)),
                "p99": float(valid_sue["sue"].quantile(0.99)),
                "max": float(valid_sue["sue"].max()),
                "skewness": float(valid_sue["sue"].skew()),
                "kurtosis": float(valid_sue["sue"].kurtosis())
            }
        }, sf, indent=2)

    print(f"\nData quality summary saved to: {summary_path}")
    return full_sue

if __name__ == "__main__":
    build_sue()
