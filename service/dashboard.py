"""Monitoring Dashboard for Quant Signal API (Nifty 100)."""

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
try:
    from scripts.phase5.train_multi import (
        load_all_predictions, compute_strategy_returns
    )
except ImportError:
    pass

API_URL = os.getenv("API_URL", "http://localhost:8000")

# Nifty 100 tickers (matching API)
TICKERS = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BPCL.NS", "BHARTIARTL.NS",
    "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DIVISLAB.NS", "DRREDDY.NS",
    "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS",
    "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS",
    "M&M.NS", "MARUTI.NS", "NESTLEIND.NS", "NTPC.NS", "ONGC.NS",
    "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SBIN.NS", "SUNPHARMA.NS",
    "TCS.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "TECHM.NS",
    "TITAN.NS", "ULTRACEMCO.NS", "UPL.NS", "WIPRO.NS", "ADANIGREEN.NS",
    "ADANITRANS.NS", "AMBUJACEM.NS", "APOLLOTYRE.NS", "ASHOKLEY.NS", "ASTRAL.NS",
    "AUROPHARMA.NS", "BALKRISIND.NS", "BANDHANBNK.NS", "BANKBARODA.NS", "BEL.NS",
    "BHEL.NS", "BIOCON.NS", "BOSCHLTD.NS", "CANBK.NS", "CHOLAFIN.NS",
    "COLPAL.NS", "CONCOR.NS", "CROMPTON.NS", "CUMMINSIND.NS", "DABUR.NS",
    "DALBHARAT.NS", "DEEPAKNTR.NS", "DLF.NS", "EDELWEISS.NS", "EMAMILTD.NS",
    "ENDURANCE.NS", "ESCORTS.NS", "EXIDEIND.NS", "FEDERALBNK.NS", "GAIL.NS",
    "GLENMARK.NS", "GMRINFRA.NS", "GODREJCP.NS", "GODREJPROP.NS", "GRANULES.NS",
    "HAVELLS.NS", "HINDPETRO.NS", "ICICIGI.NS", "ICICIPRULI.NS", "IDEA.NS",
    "IDFCFIRSTB.NS", "IGL.NS", "INDIGO.NS", "INDUSTOWER.NS", "JINDALSTEL.NS",
    "JUBLFOOD.NS", "LICHSGFIN.NS", "LTIM.NS", "LUPIN.NS", "MARICO.NS",
    "MAXHEALTH.NS", "MCDOWELL-N.NS", "MFSL.NS", "MOTHERSON.NS", "MPHASIS.NS",
    "MRF.NS", "MUTHOOTFIN.NS", "NAUKRI.NS", "NAVINFLUOR.NS", "NBCC.NS",
    "NMDC.NS", "OBEROIRLTY.NS", "PAGEIND.NS", "PEL.NS", "PERSISTENT.NS",
    "PETRONET.NS", "PFC.NS", "PIDILITIND.NS", "PIIND.NS", "PNB.NS",
    "POLYCAB.NS", "PVRINOX.NS", "RAMCOCEM.NS", "RBLBANK.NS", "RECLTD.NS",
    "SAIL.NS", "SHREECEM.NS", "SIEMENS.NS", "SRF.NS", "SYNGENE.NS",
    "TATACHEM.NS", "TATACOMM.NS", "TATAPOWER.NS", "TORNTPHARM.NS", "TORNTPOWER.NS",
    "TRENT.NS", "TVSMOTOR.NS", "UBL.NS", "UNIONBANK.NS", "VBL.NS",
    "VEDL.NS", "VOLTAS.NS", "WHIRLPOOL.NS", "ZOMATO.NS", "ZYDUSLIFE.NS"
]

st.set_page_config(page_title="Quant Signal Monitor — Nifty 100", layout="wide")


@st.cache_data(ttl=60)
def fetch_live_signals():
    """Fetch live signals from API (no API key needed)."""
    headers = {"Content-Type": "application/json"}
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
    """Recompute equity curve from Phase 5 backtest if available."""
    try:
        from scripts.phase5.backtest_final import load_all, strategy_positions, bt, stats
        data, _ = load_all()
        nets = []
        for t, df in data.items():
            pos = strategy_positions(df, "regime_long")
            net = bt(pos, df["fwd_ret"].values, 5.0)
            nets.append(net)
        port_net = pd.DataFrame(nets).T.mean(axis=1).values
        return pd.Series(port_net)
    except Exception:
        return None


def rolling_sharpe(returns, window=30):
    r = pd.Series(returns)
    ann = r.rolling(window).mean() * 252
    vol = r.rolling(window).std() * np.sqrt(252)
    sr = ann / vol
    return sr


def main():
    st.title("📊 Quant Signal Monitor — Nifty 100")
    st.caption("Ensemble (XGB + RF + LR) + 200-day SMA filter | No API Key Required")

    # --- Ticker Search / Filter ---
    st.subheader("🔔 Live Signals (Real-time)")
    
    # Search box for ticker filtering
    search_term = st.text_input("🔍 Search tickers (e.g., RELIANCE, TCS, HDFC)", "").upper()
    
    # Filter tickers based on search
    if search_term:
        filtered_tickers = [t for t in TICKERS if search_term in t.replace(".NS", "")]
    else:
        filtered_tickers = TICKERS[:50]  # Show first 50 by default for performance
        st.info(f"Showing first 50 of {len(TICKERS)} tickers. Use search to find specific stocks.")

    with st.spinner(f"Fetching signals for {len(filtered_tickers)} tickers..."):
        headers = {"Content-Type": "application/json"}
        signals = {}
        for t in filtered_tickers:
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

    # Build dataframe
    rows = []
    for t, s in signals.items():
        if "error" in s:
            rows.append({"Ticker": t, "Signal": "ERROR", "Confidence": "—", "Regime": "—", "Price": "—", "SMA200": "—", "Detail": s["error"][:50]})
        else:
            rows.append({"Ticker": t, "Signal": s["signal"], "Confidence": f"{s['confidence']:.1%}", "Regime": s["regime"], "Price": f"₹{s['price']:.2f}", "SMA200": f"₹{s['sma_200']:.2f}", "Detail": "OK"})

    sig_df = pd.DataFrame(rows)
    
    # Color code the signals
    def color_signal(val):
        if val == "BUY":
            return "background-color: #d4edda; color: #155724"
        elif val == "HOLD":
            return "background-color: #fff3cd; color: #856404"
        elif val == "ERROR":
            return "background-color: #f8d7da; color: #721c24"
        return ""
    
    styled_df = sig_df.style.applymap(color_signal, subset=["Signal"])
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    # Summary metrics
    buy_count = sum(1 for s in signals.values() if s.get("signal") == "BUY")
    hold_count = sum(1 for s in signals.values() if s.get("signal") == "HOLD")
    error_count = sum(1 for s in signals.values() if "error" in s)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("🟢 BUY Signals", buy_count)
    c2.metric("🟡 HOLD Signals", hold_count)
    c3.metric("🔴 Errors", error_count)

    # --- Historical Equity & Rolling Sharpe ---
    st.subheader("📈 Historical Performance (Backtest)")
    net = load_historical_equity()
    
    if net is not None:
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

        # Alert Check
        latest_sr = rs.dropna().iloc[-1] if rs.dropna().any() else None
        if latest_sr is not None:
            if latest_sr < 0.5:
                st.error(f"🚨 ALERT: Rolling 30-day Sharpe ({latest_sr:.3f}) below 0.5 threshold!")
            else:
                st.success(f"✅ Rolling 30-day Sharpe: {latest_sr:.3f} (threshold 0.5)")

        # Key Metrics
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
    else:
        st.info("Historical backtest data not available. Run Phase 5 backtest first.")

    # --- Auto-refresh ---
    if st.button("🔄 Refresh Signals"):
        st.cache_data.clear()
        st.rerun()


if __name__ == "__main__":
    main()