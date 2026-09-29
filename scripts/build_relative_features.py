"""
Build cross-sectional and relative return features for GaurviDEEP.
Month 1 of research pre-registration deliverable.
Data / Feature building only — no modeling, no test-set access.

METHODOLOGICAL DISCLOSURES & REFINEMENTS:
1. Sector Grouping & Real Estate Sparsity Resolution:
   In the raw 11-sector classification, Real Estate contains only 3 tickers
   (DLF.NS, GODREJPROP.NS, OBEROIRLTY.NS; only 2 active prior to 2018).
   Instead of dropping these 3 tradable names (which would reduce universe coverage
   and cause train/serve skew), Real Estate is merged into "Industrials & Real Estate"
   (18 tickers total, >=16 active on every trading day). This ensures that every
   sector has at least 6 members across history, providing statistically reliable
   cross-sectional averages and robust intra-sector ranking distributions.

2. Point-In-Time Classification Limitation:
   SECTOR_MAP_MODELING reflects each company's sector classification as established
   in 2026 and applies this grouping uniformly backward across the 10-year dataset
   (2016-2026). While large-cap sector assignments are historically stable, this is
   disclosed as a known limitation: historical corporate spin-offs or sector
   re-classifications are not dynamically reconstructed point-in-time day-by-day.
   However, cross-sectional calculations (means, rankings) on any given trading day
   use ONLY returns available up to and including that specific day (zero lookahead).
"""

import os
import sys
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from features.universe import TICKERS, SECTOR_MAP_MODELING, SECTOR_GROUPS_MODELING

RAW_DATA_PATH = os.path.join(BASE_DIR, "data", "multi", "historical_10y_raw.csv")
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "multi", "relative_features_v1.csv")

def main():
    print(f"Loading raw data from: {RAW_DATA_PATH}")
    df = pd.read_csv(RAW_DATA_PATH)
    print(f"Loaded {len(df):,} rows across {df['ticker'].nunique()} tickers.")
    
    # Dates are in ISO YYYY-MM-DD format, lexicographical sort is chronological
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)
    
    # Map sectors from universe.py (using SECTOR_MAP_MODELING with Real Estate merged into Industrials & Real Estate)
    df["sector"] = df["ticker"].map(SECTOR_MAP_MODELING)
    
    # 1. Compute individual stock returns
    # 5-day return: (Close_t - Close_{t-5}) / Close_{t-5}
    # 20-day return: (Close_t - Close_{t-20}) / Close_{t-20}
    print("Computing trailing 5-day and 20-day returns per ticker...")
    df["ret_5d"] = df.groupby("ticker")["Close"].pct_change(5)
    df["ret_20d"] = df.groupby("ticker")["Close"].pct_change(20)
    
    # 2. Point-in-time cross-sectional averages
    # For any given trading day 't', compute:
    # - sector_avg_ret_5d: mean(ret_5d) of all active tickers in that sector on day 't'
    # - index_avg_ret_5d: mean(ret_5d) of all active universe tickers on day 't'
    # - sector_rank_pct: percentile rank of stock within its sector on day 't' by trailing 20-day relative strength
    print("Computing cross-sectional sector and index averages (Point-In-Time)...")
    
    # Sector average 5-day return on each date
    df["sector_avg_ret_5d"] = df.groupby(["date", "sector"])["ret_5d"].transform("mean")
    df["relative_ret_5d"] = df["ret_5d"] - df["sector_avg_ret_5d"]
    
    # Equal-weight Nifty 100 universe average 5-day return on each date
    df["index_avg_ret_5d"] = df.groupby("date")["ret_5d"].transform("mean")
    df["relative_ret_5d_vs_index"] = df["ret_5d"] - df["index_avg_ret_5d"]
    
    # Trailing 20-day sector relative return and percentile rank within sector
    df["sector_avg_ret_20d"] = df.groupby(["date", "sector"])["ret_20d"].transform("mean")
    df["relative_ret_20d"] = df["ret_20d"] - df["sector_avg_ret_20d"]
    
    # Percentile rank within sector on that date: values in [0, 1] or (0, 1]
    df["sector_rank_pct"] = df.groupby(["date", "sector"])["relative_ret_20d"].rank(pct=True)
    
    # Sort back to standard date, ticker order
    df = df.sort_values(["date", "ticker"]).reset_index(drop=True)
    
    # Select columns to save
    output_cols = [
        "date",
        "ticker",
        "sector",
        "Close",
        "ret_5d",
        "sector_avg_ret_5d",
        "relative_ret_5d",
        "index_avg_ret_5d",
        "relative_ret_5d_vs_index",
        "ret_20d",
        "sector_avg_ret_20d",
        "relative_ret_20d",
        "sector_rank_pct"
    ]
    out_df = df[output_cols]
    
    print(f"Saving engineered features to: {OUTPUT_PATH}")
    out_df.to_csv(OUTPUT_PATH, index=False)
    print(f"File saved successfully! Size: {os.path.getsize(OUTPUT_PATH):,} bytes.")
    
    # Report summary stats
    print("\n" + "=" * 60)
    print("SECTOR COVERAGE SUMMARY (MODELING GROUPINGS)")
    print("=" * 60)
    sector_summary = df.groupby("sector")["ticker"].nunique().reset_index()
    sector_summary.columns = ["Sector", "Ticker Count"]
    print(sector_summary.to_string(index=False))
    
    print("\n" + "=" * 60)
    print("DISTRIBUTION STATS FOR NEW FEATURES")
    print("=" * 60)
    feature_cols = ["relative_ret_5d", "relative_ret_5d_vs_index", "sector_rank_pct"]
    stats = out_df[feature_cols].describe().T[["count", "mean", "std", "min", "25%", "50%", "75%", "max"]]
    stats["range"] = stats["max"] - stats["min"]
    print(stats.to_string())

if __name__ == "__main__":
    main()
