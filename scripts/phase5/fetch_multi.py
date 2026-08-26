"""Fetch 10 years of daily OHLCV data for 5 liquid US tickers."""

import os

import pandas as pd
import yfinance as yf

TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
OUT_DIR = os.path.join("data", "multi")
YEARS = "10y"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for t in TICKERS:
        df = yf.download(t, period=YEARS, interval="1d", auto_adjust=False, progress=False)
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
        out["amount"] = out["close"] * out["volume"]
        out = out.dropna().reset_index(drop=True)
        path = os.path.join(OUT_DIR, f"{t}.csv")
        out.to_csv(path, index=False)
        print(f"{t:>5}: {len(out):>4} rows | {out['timestamps'].iloc[0]} -> {out['timestamps'].iloc[-1]} | -> {path}")


if __name__ == "__main__":
    main()
