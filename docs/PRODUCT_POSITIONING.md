# Product Positioning & Verified Performance Specification

## Executive Core Claim

> "A systematic 200-day trend filter reduces Nifty 100 portfolio drawdown by roughly 1.1x-2.1x depending on market regime (average ~1.6x over a 4-year full cycle, verified out-of-sample, 15bps retail costs), with the strongest effect during corrections and sideways markets. This comes at a real cost: over the same 4-year period, cumulative return was 55.7% vs. 101.1% for buy-and-hold — the filter gives up meaningful upside, particularly in strong bull markets, and its lagging nature means it can underperform on raw return even during the correction it's designed to cushion (see Window 3), because late re-entry after a bottom adds whipsaw cost. This is a downside-protection tool for investors who prioritize smoother drawdowns over maximizing total return, not a return-enhancement strategy."

---

## 1. What This Tool IS and IS NOT

### What It IS
* **A Systematic Capital Preservation & Trend-Following Filter**: Applies a non-discretionary 200-day simple moving average rule across liquid Indian equities (Nifty 100 target universe, 138 constituent tickers).
* **A Downside Risk Dampener**: Designed to transition assets to cash/flat positions during secular downtrends, mitigating severe multi-month drawdown phases.
* **An Evidence-Based Risk Allocation System**: Provides transparent, fully traceable historical behavior net of retail execution friction (15 bps round-trip transaction costs).

### What It IS NOT
* **NOT a Return-Enhancement Strategy**: It does **not** generate alpha or beat Buy & Hold on total return over a full market cycle.
* **NOT a Market-Timing or Predictive AI Signal**: It does **not** predict short-term turning points, price bottoms, or daily directional probabilities.
* **NOT a Stock-Picking Engine**: It does **not** identify individual high-flying stocks or select outperforming equities.
* **NOT Frictionless**: In sideways or choppy markets, repeated exits and re-entries cause whipsaw friction that degrades equity.

---

## 2. Verified Full-Cycle Performance Specification

* **Universe**: Canonical Nifty 100 Indian Equities (`features/universe.py`, 138 tickers evaluated).
* **Evaluation Window**: 2022-08-04 to 2026-08-27 (1,006 consecutive post-warmup trading sessions).
* **Friction Applied**: 15 bps (0.15%) round-trip retail transaction cost on all rebalancing turns.
* **Source Artifact**: `scripts/verification/drawdown_stress_test_results.json` (lines 11–261).

### Verified Multi-Regime Breakdown Table

| Evaluation Window | Market Regime Context | Trading Sessions | Benchmark Return | Strategy Return (15bps) | Benchmark MaxDD | Strategy MaxDD (15bps) | Drawdown Reduction Factor | Benchmark Sharpe | Strategy Sharpe (15bps) | Strategy Avg Exposure | Strategy Total Trades |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Window 1** (2022-08-04 to 2023-08-09) | Post-Correction / Breakout | 251 | **+25.52%** | +13.59% | **-10.17%** | **-7.11%** | **1.43x** | **1.952** | 1.630 | 67.2% | 1,227 |
| **Window 2** (2023-08-10 to 2024-08-21) | Sustained Multi-Cap Bull Rally | 251 | **+55.65%** | +46.78% | **-6.47%** | **-5.85%** | **1.11x** | **2.905** | 2.855 | 86.5% | 837 |
| **Window 3** (2024-08-22 to 2025-08-22) | Market Peak & Severe Correction | 251 | **-2.97%** | -7.98% | **-21.15%** | **-12.90%** | **1.64x** | -0.110 | -1.155 | 51.3% | 1,397 |
| **Window 4** (2025-08-25 to 2026-08-27) | Late-Cycle Sideways / Chop | 253 | **+6.05%** | +1.10% | **-13.55%** | **-6.58%** | **2.06x** | **0.478** | 0.196 | 55.6% | 1,336 |
| **Full Multi-Year Cycle** (2022-08-04 to 2026-08-27) | **Complete 4-Year Full Cycle** | **1,006** | **+101.05%** | **+55.67%** | **-21.15%** | **-12.90%** | **1.64x** | **1.267** | **1.224** | **65.1%** | **4,464** |

---

## 3. Structural Mechanics & Honest Risk Disclosures

### A. The Drawdown Protection Mechanism
Across all four regimes and the aggregate 4-year cycle, the strategy successfully dampened peak-to-trough drawdowns:
* In the severe market correction of **Window 3**, passive buy-and-hold crashed by **-21.15%**; the regime filter limited the drawdown to **-12.90%** (a 1.64x risk reduction).
* In the late-cycle sideways chop of **Window 4**, passive drawdown was **-13.55%**, while the regime filter held drawdown to **-6.58%** (a 2.06x risk reduction).

### B. The Lag & Opportunity Cost (Return Drag)
Investors must understand the structural price of this downside protection:
1. **Upside Sacrifice in Bull Markets**: Because the strategy held cash on ~35% of days across the 4-year cycle (average exposure of 65.13%), it captured only **+55.67% cumulative return compared to +101.05%** for passive buy-and-hold.
2. **Whipsaw Underperformance During Choppy Corrections (Window 3)**: During Window 3, although max drawdown was reduced from -21.15% to -12.90%, the strategy finished with **worse net total return (-7.98% vs. -2.97%)**. Moving averages lag turning points: the filter exited after prices had already declined and re-entered after prices had already rebounded, generating 1,397 transactions that incurred friction without capturing the inflection.
3. **Recovery Time Parity**: The filter took **478 trading days** to recover to new equity highs following its peak drawdown, compared to **458 trading days** for the passive benchmark. It spends 86.6% of trading sessions in some state of drawdown vs. 84.6% for buy-and-hold.

---

## 4. Ideal User Profile
* **Target Audience**: Capital-preservation-oriented investors, family offices, or retirees who cannot psychologically or operationally tolerate a >20% portfolio collapse and are willing to forgo substantial long-term market upside in exchange for a hard ceiling on portfolio drawdowns.
* **Unsuitable Audience**: Aggressive growth investors, alpha seekers, high-frequency traders, or individuals seeking market-beating returns.
