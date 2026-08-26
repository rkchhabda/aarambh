"""Monitoring Dashboard for Quant Signal API (Scenario 2/2b)."""

import os
import sys
import json
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

# Add workspace to path
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WORKSPACE)
from scripts.phase5.train_multi import (
    load_all_predictions, compute_strategy_returns
)

API_URL = os.getenv("API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "qs_hvw4wTe3mRaRruyVXxmT1fcgWRiZKXG-1aMbeOO9")
TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

st.set_page_config(page_title="Quant Signal Monitor", layout="wide")


@st.cache_data(ttl=60)
def fetch_live_signals():
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
    signals = {}
    for t in TICKERS:
        try:
            resp = requests.post(
                f"{API_URL}/v1/signal",
                json={"ticker": t},
                headers=headers,
                timeout=10,
            )
            if resp.status_code == 200:
                signals[t] = resp.json()
            else:
                signals[t] = {"error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as e:
            signals[t] = {"error": str(e)}
    return signals


@st.cache_data(ttl=3600)
def load_historical_equity():
    """Recompute equity curve for Scenario 2/2b from Phase 5 backtest."""
    from scripts.phase5.backtest_final import load_all, strategy_positions, bt, stats
    data, _ = load_all()
    nets = []
    for t, df in data.items():
        pos = strategy_positions(df, "regime_long")  # Scenario 2/2b
        net = bt(pos, df["fwd_ret"].values, 5.0)  # 5 bps
        nets.append(net)
    port_net = pd.DataFrame(nets).T.mean(axis=1).values
    return pd.Series(port_net)


def rolling_sharpe(returns, window=30):
    r = pd.Series(returns)
    ann = r.rolling(window).mean() * 252
    vol = r.rolling(window).std() * np.sqrt(252)
    sr = ann / vol
    return sr


def main():
    st.title("📊 Quant Signal Monitor — Scenario 2/2b")
    st.caption("Multi-ticker Long-only + 200-day SMA filter | Paper Trading Mode")

    # --- Live Signals Table ---
    st.subheader("🔔 Live Signals (Real-time)")
    with st.spinner("Fetching from API..."):
        signals = fetch_live_signals()

    rows = []
    for t, s in signals.items():
        if "error" in s:
            rows.append({"Ticker": t, "Signal": "ERROR", "Confidence": "—", "Regime": "—", "Price": "—", "SMA200": "—", "Detail": s["error"][:50]})
        else:
            rows.append({"Ticker": t, "Signal": s["signal"], "Confidence": f"{s['confidence']:.1%}", "Regime": s["regime"], "Price": f"${s['price']:.2f}", "SMA200": f"${s['sma_200']:.2f}", "Detail": "OK"})

    sig_df = pd.DataFrame(rows)
    st.dataframe(sig_df, use_container_width=True, hide_index=True)

    # --- Historical Equity & Rolling Sharpe ---
    st.subheader("📈 Historical Performance (Backtest, Scenario 2/2b)")
    net = load_historical_equity()
    equity = (1 + pd.Series(net)).cumprod()

    col1, col2 = st.columns([2, 1])
    with col1:
        fig_eq = go.Figure()
        fig_eq.add_trace(go.Scatter(x=list(range(len(equity))), y=equity.values, mode='lines', name='Equity', line=dict(color='#1f77b4')))
        fig_eq.update_layout(title="Portfolio Equity Curve (Net of 5bps)", xaxis_title="Trading Day", yaxis_title="Cumulative Return", height=350, template="plotly_white")
        st.plotly_chart(fig_eq, use_container_width=True)

    with col2:
        rs = rolling_sharpe(net, 30)
        fig_sr = go.Figure()
        fig_sr.add_trace(go.Scatter(x=list(range(len(rs))), y=rs.values, mode='lines', name='30d Rolling Sharpe', line=dict(color='#ff7f0e')))
        fig_sr.add_hline(y=0.5, line_dash="dash", line_color="red", annotation_text="Alert Threshold (0.5)")
        fig_sr.add_hline(y=0, line_dash="dot", line_color="gray")
        fig_sr.update_layout(title="Rolling 30-Day Sharpe", xaxis_title="Trading Day", yaxis_title="Sharpe Ratio", height=350, template="plotly_white")
        st.plotly_chart(fig_sr, use_container_width=True)

    # --- Alert Check ---
    latest_sr = rs.dropna().iloc[-1] if rs.dropna().any() else None
    if latest_sr is not None:
        if latest_sr < 0.5:
            st.error(f"🚨 ALERT: Rolling 30-day Sharpe ({latest_sr:.3f}) below 0.5 threshold!")
        else:
            st.success(f"✅ Rolling 30-day Sharpe: {latest_sr:.3f} (threshold 0.5)")

    # --- Key Metrics ---
    st.subheader("📋 Key Metrics (Full Backtest)")
    from scripts.phase5.backtest_final import load_all, strategy_positions, bt, stats
    data, _ = load_all()
    nets = []
    for t, df in data.items():
        pos = strategy_positions(df, "regime_long")
        net = bt(pos, df["fwd_ret"].values, 5.0)
        nets.append(net)
    port_net = pd.DataFrame(nets).T.mean(axis=1).values
    port_pos = pd.DataFrame([strategy_positions(data[t], "regime_long") for t in data]).T.mean(axis=1).values
    s = stats(port_net, port_pos)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Return", f"{s['total_ret_pct']:.2f}%")
    c2.metric("Sharpe Ratio", f"{s['sharpe']:.3f}")
    c3.metric("Max Drawdown", f"{s['max_dd_pct']:.2f}%")
    c4.metric("Win Rate (Active)", f"{s['win_rate_pct']:.1f}%")

    # --- Auto-refresh ---
    st_autorefresh = st.empty()
    st_autorefresh.button("🔄 Refresh Signals", key="refresh")


if __name__ == "__main__":
    main()