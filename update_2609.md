# GaurviDEEP Platform Update Report

**Date:** 2026-09-26  
**File:** `update_2609.md`  
**Status:** Complete & Deployed to Production (`origin/main`)

---

## Executive Summary

On September 26, 2026, major milestones were achieved across the **data ingestion pipeline**, **live UI presentation**, **backtest reporting architecture**, and **regulatory/methodology documentation**:

1. **Tier 0 NSE Direct Pipeline Restored**: Resolved the HTTP/2 dependency failure (`h2`), implemented persistent session reuse across all 138 tickers, added a 0.35s rate-limit delay, and achieved **100% Tier 0 success (138/138 tickers)** in 3.86 minutes with zero fallbacks.
2. **Backtests Page Redesign for Density**: Streamlined the Backtests view from ~5 printed pages down to ~2 printed pages, introducing a unified side-by-side comparison table (Horizon 1 4-year cycle vs. Horizon 2 9-year multi-cycle) and moving detailed COVID-19 stress tests and rolling window tables into a collapsible drawer without removing any metrics or disclaimers.
3. **Live Cache & Methodology Alignment**: Synced methodology metrics to verified values (1.61x MaxDD reduction, +57.67% return, ±1.00% hysteresis), added HTTP `no-cache` headers to `/app` to eliminate stale CDN/browser caches, and added seamless cross-tab navigation links.
4. **Plain-English Glossary Addition**: Added a comprehensive, collapsible glossary (`📖 Glossary — Plain-English Definitions`) covering 32 core terms across Regime Mechanics, Backtest Performance, and Signal Page fields with explicit model caveats.
5. **Signals Page Bug Fixes & Disclaimers**: Resolved key UI rendering bugs (`quant_score` object parsing, percentage scaling, `stop_loss_estimate_pct`), eliminated tab switching blank flash, and embedded prominent research disclaimers regarding unvalidated predictive edge.

---

## 1. Data Ingestion & Cache Pipeline (Tier 0 NSE Direct)

### Issues Resolved
- **HTTP/2 Dependency Error**: Prior batch runs failed on Tier 0 with `Using http2=True, but the 'h2' package is not installed`.
- **Session Churn**: A new HTTP session was previously created per ticker, triggering intermittent rate-limiting and connection resets.

### Changes Implemented
- **Dependency Update**: Added `nse[server]>=4.0.0` to both `requirements.txt` and `requirements-render.txt`.
- **Persistent Session Reuse**: Refactored `rebuild_cache_v2.py` to initialize a single persistent `NSE` client reused sequentially across all tickers.
- **Rate-Limiting**: Enforced a `0.35s` sleep between ticker requests in the EOD historical rebuild loop.
- **Boundary Preservation**: Left live quotes and WebSocket interfaces untouched, limiting changes strictly to historical EOD rebuilds.

### Verification & Performance
- **Success Rate**: **138 / 138 tickers (100.0%)** succeeded on Tier 0 NSE Direct.
- **Fallback Count**: **0** tickers required Tier 1 or Tier 2 fallback.
- **Wall-Clock Duration**: **231.8 seconds (3.86 minutes)** total run time across all 138 tickers.
- **Live Deployment Check**: Confirmed live Render `/scanner` serves fresh Tier 0 data directly (e.g., ADANIENT @ 2916.5 / 14.18% SMA distance, RELIANCE @ 1226.0 / -10.56%, TCS @ 2082.0 / -18.07%).

---

## 2. Methodology & Plain-English Glossary

### Methodology Alignment (`9fb7f70`, `a28ba6f`)
- Updated drawdown reduction figures to match verified backtests: **1.61x peak reduction (-13.11% MaxDD vs. -21.15% B&H)**.
- Aligned hysteresis buffer documentation to **±1.00%**.
- Added an in-text link to the 9-year multi-cycle backtests highlighting performance during the 2020 COVID shock alongside the single-event caveat.

### Glossary Integration (`c37c5bf`)
- Inserted a new collapsible section (`<details>/<summary>`) titled **`📖 Glossary — Plain-English Definitions`** at the bottom of `#page-methodology`.
- Formatted with `.method-section` typography and bullet styling, collapsed by default.
- Contains 32 exact, reviewed definitions grouped into 3 categories:
  1. **Regime & Signal Mechanics**: 200-Day SMA, RISK-ON, RISK-OFF, SMA Distance (%), Hysteresis Band.
  2. **Backtest & Performance**: Backtest, Out-of-Sample, Buy & Hold (B&H) Benchmark, Maximum Drawdown (MaxDD), Drawdown Reduction Ratio, Cumulative Return, Annualized Return, Sharpe Ratio, Sortino Ratio, Calmar Ratio, Ulcer Index, Avg Market Exposure, Total Trades / Signals Fired, Basis Points (bps), Rolling Window, Single-Event Caveat.
  3. **Signal Detail Page**: Italic caveat line clarifying lack of validated predictive edge, followed by definitions for Quant Score, Confidence, ATR %, Stop-Loss Estimate, RSI, MACD, Bollinger Band Position, CCI, Williams %R, ROC, and OBV Slope.

---

## 3. Backtests Tab Redesign for Density (`035da48`)

### Architecture & Layout
- **Target Achieved**: Compact layout fitting ~2 printed pages (down from ~5).
- **Side-by-Side Comparison Table**: Unified Horizon 1 (4-Year Cycle, 2022–2026) and Horizon 2 (9-Year Multi-Cycle, 2017–2026) into a 4-column matrix:
  - *Horizon 1 Filter (15 bps)* vs. *Horizon 1 B&H Benchmark*
  - *Horizon 2 Filter (15 bps)* vs. *Horizon 2 B&H Benchmark*
- **Collapsible Audit Drawer**: Relegated the 103-window rolling audit and the COVID-19 crash vs. full-year recovery tables into a secondary `<details>` disclosure to reduce visual clutter.
- **Content Preservation Guarantee**: Every number, the Single-Event Caveat, and SEBI research disclaimers were preserved verbatim without softening or omission.

---

## 4. Signals UI Enhancements & Bug Fixes

### Bug Fixes
- **`quant_score` Extraction**: Corrected component path parsing to read `quant_score.components` accurately across all tickers.
- **Confidence Display**: Corrected decimal percentage multiplier so confidence displays properly as `0–100%`.
- **Field Name Alignment**: Fixed `stop_loss_estimate_pct` field binding.
- **Tab Switching Blank Flash**: Modified tab initialization to hide empty states immediately and show the loading spinner/panel when switching tabs.
- **Static Baseline**: Set baseline reference close to real EOD values (`23,140.50`).

### Transparency & Compliance
- Added prominent disclaimers on signal cards highlighting model track record (Sharpe -0.399, lack of demonstrated outperformance over buy-and-hold).
- Enforced clear demarcation that technical signals are educational indicators rather than SEBI-regulated advice.

---

## 5. Commit Log Summary (2026-09-26)

| Commit Hash | Description |
|:---|:---|
| [`c37c5bf`](https://github.com/rkchhabda/aarambh/commit/c37c5bf) | `docs(methodology): add collapsible plain-english glossary section` |
| [`06e281b`](https://github.com/rkchhabda/aarambh/commit/06e281b) | `chore(data): update ticker_cache.json with 138 tickers from Tier 0 NSE Direct rebuild` |
| [`94aee1d`](https://github.com/rkchhabda/aarambh/commit/94aee1d) | `fix(data_provider): add nse[server] http2 support, persistent NSE session reuse, and 0.35s delay in cache rebuild` |
| [`a28ba6f`](https://github.com/rkchhabda/aarambh/commit/a28ba6f) | `docs(methodology): add link to 9-year multi-cycle backtests and single-event caveat` |
| [`9fb7f70`](https://github.com/rkchhabda/aarambh/commit/9fb7f70) | `fix(methodology,cache): align methodology tab with 1.61x/-13.11% and +/-1.00% hysteresis; add no-cache headers to /app` |
| [`035da48`](https://github.com/rkchhabda/aarambh/commit/035da48) | `refactor(ui/backtests): redesign Backtests tab for density with unified comparison table, collapsible methodology, and consolidated disclosures` |
| [`18e8e72`](https://github.com/rkchhabda/aarambh/commit/18e8e72) | `feat(ui/backtests): update backtest tab with dual-horizon results, COVID-19 audit, live hysteresis alignment, single-event caveat, and SEBI disclaimer` |
| [`94765c4`](https://github.com/rkchhabda/aarambh/commit/94765c4) | `fix(ui/signals): correct component path, flatten factor_analysis arrays, add heuristic disclaimers` |
| [`e1e69ef`](https://github.com/rkchhabda/aarambh/commit/e1e69ef) | `feat(ui/signals): add prominent backtest disclaimer on signal card (Sharpe -0.399, SEBI advisor warning)` |
| [`732b61a`](https://github.com/rkchhabda/aarambh/commit/732b61a) | `fix(ui/signals): correct 3 rendering bugs affecting all tickers (quant_score, confidence, stop loss)` |
| [`4c637ab`](https://github.com/rkchhabda/aarambh/commit/4c637ab) | `fix(ui/signals): hide empty-state immediately on tab open to eliminate blank flash` |
| [`d84c14f`](https://github.com/rkchhabda/aarambh/commit/d84c14f) | `fix(indices,ui): update static baseline to real EOD close (23140.50) and auto-load default ticker` |
| [`754d8f1`](https://github.com/rkchhabda/aarambh/commit/754d8f1) | `fix(ui): bind dashboard telemetry and regime breakdown directly to /scanner metrics` |

---

## 6. Current System Status

- **Branch**: `main` (synchronized with `origin/main`).
- **Live Deployment**: Render hosting live at `https://aarambh-jxji.onrender.com/app/`.
- **EOD Pipeline**: Automated via Tier 0 NSE Direct (`0.35s` throttle, persistent session, full 138 tickers).
- **Methodology & Backtest**: In sync with verified multi-horizon empirical results and plain-English glossary.
