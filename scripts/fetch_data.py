import os
import sys

import yfinance as yf
import pandas as pd

TICKER = "AAPL"
PERIOD = "6y"
RAW_DIR = os.path.join("data", "raw")
OUT_PATH = os.path.join(RAW_DIR, "market_data.csv")


def main():
    os.makedirs(RAW_DIR, exist_ok=True)

    print(f"Fetching {PERIOD} of daily data for {TICKER} via yfinance...")
    df = yf.download(TICKER, period=PERIOD, interval="1d",
                     auto_adjust=False, progress=False)
    if df is None or df.empty:
        sys.exit(f"ERROR: no data returned for {TICKER}")

    # yfinance may return MultiIndex columns when passing a list/tuple; flatten
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()

    out = pd.DataFrame({
        "timestamps": pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d"),
        "open": df["Open"].astype(float),
        "high": df["High"].astype(float),
        "low": df["Low"].astype(float),
        "close": df["Close"].astype(float),
        "volume": df["Volume"].astype(float),
    })
    # amount = approximate traded value in USD (close * volume)
    out["amount"] = out["close"] * out["volume"]

    before = len(out)
    out = out.dropna().reset_index(drop=True)

    out.to_csv(OUT_PATH, index=False)

    print(f"\nSaved -> {os.path.abspath(OUT_PATH)}")
    print(f"Rows dropped for missing values: {before - len(out)}")
    print(f"Row count: {len(out)}")
    print(f"Date range: {out['timestamps'].iloc[0]} to {out['timestamps'].iloc[-1]}")

    years = (pd.Timestamp(out['timestamps'].iloc[-1]) -
             pd.Timestamp(out['timestamps'].iloc[0])).days / 365.25
    print(f"Span: {years:.2f} years (requirement: >= 5)")

    print("\nMissing values per column:")
    print(out.isna().sum().to_string())

    print("\nSummary statistics:")
    print(out.drop(columns=["timestamps"]).describe().to_string())

    print("\nHead:")
    print(out.head(3).to_string(index=False))
    print("\nTail:")
    print(out.tail(3).to_string(index=False))


if __name__ == "__main__":
    main()
