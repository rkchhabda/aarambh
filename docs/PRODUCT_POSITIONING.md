# Product Positioning & Verified Performance Specification

## Executive Core Claim

> "This strategy is not designed to beat the market in calm conditions — its value is concentrated in protecting capital during severe, infrequent market shocks, as shown by the 2020 COVID crash test. Over the recent 4-year cycle (2022–2026, calmer trending markets), the filter reduced drawdown by 1.61x (-13.1% vs. -21.2%), but Buy & Hold delivered superior cumulative returns (+101.1% vs. +57.7%) as well as higher Sharpe and Sortino ratios; only the Calmar ratio favored the filter. However, across a full 9-year cycle including systemic crisis (2017–2026), the filter improved Sharpe, Sortino, Calmar, and Ulcer Index simultaneously, driven primarily by avoiding ~72% of the COVID crash drawdown while retaining ~77% of the subsequent recovery's upside. **Critical Caveat**: This 9-year multi-metric outperformance is demonstrated by **one single historical crisis event** (the 2020 COVID liquidity shock), not a pattern verified across multiple distinct crisis types. It does not guarantee identical efficacy in different downturn topologies (such as a slow, multi-year grinding bear market rather than a sharp V-shaped collapse). All results reflect the exact ±1.00% hysteresis logic deployed in the live scanner, net of 15 bps retail transaction frictions."

---

## 1. What This Tool IS and IS NOT

### What It IS
* **A Systematic Capital Preservation & Tail-Risk Filter**: Applies a non-discretionary 200-day simple moving average with a stateful ±1.00% hysteresis buffer across liquid Indian equities (Nifty 100 universe, 138 constituent tickers).
* **A Crisis Drawdown Dampener**: Mechanically shifts assets to flat/cash defensive postures during secular downtrends, capping severe portfolio impairment.
* **Evidence-Based & Cost-Realistic**: All backtest figures reflect the actual deployed signal logic net of 15 bps round-trip retail execution drag.

### What It IS NOT
* **NOT a Return-Enhancement Strategy**: It does not seek alpha or attempt to beat Buy & Hold on total return during sustained bull runs.
* **NOT a Broad "Risk-Adjusted Return" Enhancer in Normal Markets**: During calm or range-bound conditions, cash-drag and whipsaw costs cause Sharpe and Sortino ratios to trail buy-and-hold.
* **NOT Predictive or Frictionless**: It lags sharp inflection points and incurs frictional transaction costs during sideways chop.

---

## 2. Verified Performance: Two Separate Market Horizons

All metrics evaluated on canonical Nifty 100 Indian Equities (`features/universe.py`), net of 15 bps retail transaction costs.  
*Source Artifacts*: `data/multi/historical_10y_raw.csv`, `scripts/verification/covid_stress_test_results.json`.  
*Engine Alignment*: Uses the exact same stateful ±1.00% hysteresis buffer deployed in `service/routes_scanner.py`.

### Horizon A: Recent 4-Year Cycle (2022-08-04 to 2026-08-27 &bull; 1,006 Trading Sessions)
*Characterized by post-correction recovery, sustained bull runs, and late-cycle chop — without systemic crisis.*

| Metric | Passive Buy & Hold | 200-SMA Filter (15bps) | Relative Advantage | Interpretation |
| :--- | :---: | :---: | :---: | :--- |
| **Cumulative Net Return** | **+101.06%** | +57.67% | **B&H (+43.4%)** | Filter surrendered upside by holding defensive cash ~34% of days |
| **Annualized Return** | **18.58%** | 11.86% | **B&H (+6.7%)** | Long-term growth drag from defensive positioning |
| **Maximum Drawdown** | -21.15% | **-13.11%** | **Filter (1.61x lower)** | Significant tail-drawdown dampening |
| **Sharpe Ratio** | **1.267** | 1.252 | **B&H favors slightly** | Cash drag slightly outweighs volatility reduction |
| **Sortino Ratio** | **1.119** | 1.068 | **B&H favors slightly** | Downside volatility reduction does not overcome return drag |
| **Calmar Ratio** | 0.879 | **0.905** | **Filter favors** | Only return-to-drawdown ratio improves |
| **Ulcer Index** | **6.214** | 7.163 | **B&H favors slightly** | Frictional drag during chop creates prolonged shallow underwater time |
| **Total Trades Fired** | 170 | 2,420 | 45.8% fewer than raw | Hysteresis buffer successfully filtered ~2,000 noise flips |

> **Key 4-Year Takeaway**: In calmer conditions without deep crises, Sharpe and Sortino favor passive Buy & Hold. The filter's merit is strictly limited to improving the return-to-drawdown (Calmar) ratio. Do not claim broad "risk-adjusted return improvement" for this period.

---

### Horizon B: Full 9-Year Multi-Cycle Including COVID (2017-07-18 to 2026-09-25 &bull; 2,276 Trading Sessions)
*Spans pre-COVID consolidation, the severe 2020 liquidity shock, the post-COVID liquidity rally, and 2024–2026 late-cycle volatility.*

| Metric | Passive Buy & Hold | 200-SMA Filter (15bps) | Relative Advantage | Interpretation |
| :--- | :---: | :---: | :---: | :--- |
| **Cumulative Net Return** | **+355.35%** | +163.45% | **B&H (+191.9%)** | Long-term passive compounding remains higher |
| **Annualized Return** | **18.33%** | 11.20% | **B&H (+7.1%)** | Cost of permanent structural insurance |
| **Maximum Drawdown** | -37.82% | **-13.84%** | **Filter (2.73x lower)** | Avoided catastrophic multi-year impairment |
| **Sharpe Ratio** | 1.048 | **1.150** | **Filter (+9.7%)** | Risk-adjusted return improved over full cycle |
| **Sortino Ratio** | 0.920 | **0.999** | **Filter (+8.6%)** | Downside risk-adjusted return improved |
| **Calmar Ratio** | 0.485 | **0.810** | **Filter (+67.0%)** | Substantial return-to-drawdown outperformance |
| **Ulcer Index** | 7.308 | **6.945** | **Filter (lower distress)** | Lower cumulative depth and duration of underwater stress |
| **Total Trades Fired** | 176 | 5,764 | 43.8% turnover reduction | Whipsaws eliminated by live ±1.00% hysteresis band |

> **Critical Single-Event Caveat**: The full-cycle outperformance across Sharpe, Sortino, Calmar, and Ulcer Index is demonstrated by **ONE historical crisis event** (the 2020 COVID crash). It is not a generalized pattern confirmed across multiple crisis topologies. Investors must not assume the filter will deliver identical multi-metric advantages in a slow, grinding multi-year bear market (e.g. 2000–2003 tech bust or prolonged stagflation) where gradual downward drift could trigger repeated whipsaw re-entries.

---

### The Catalyst: Anatomy of the 2020 COVID Stress Window

The divergent results between the 4-year and 9-year horizons are directly explained by the filter's mechanical response during the 2020 crash and recovery:

| Strategy | COVID Crash (Jan–Apr 2020) MaxDD | COVID Crash Net Return | Full Year 2020 Net Return | Full Year 2020 Sharpe | Full Year 2020 Calmar | Full Year 2020 Ulcer Index |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Buy & Hold** | -38.04% | -21.25% | **+33.88%** | 1.155 | 0.890 | 12.996 |
| **Filter (15bps)** | **-10.84%** | **-5.01%** | +25.93% | **2.197** | **2.206** | **4.437** |
| **Net Difference** | **3.51x lower DD** | **+16.2% saved** | *Captured ~77% upside* | **+90% Sharpe** | **+148% Calmar** | **2.93x lower stress** |

1. **Crash Defense**: The filter cut maximum drawdown from -38.04% to -10.84% (avoiding 71.5% of the collapse) and contained capital loss to -5.01% vs. -21.25%.
2. **Upside Capture**: Despite lagging the bottom, the filter re-entered the subsequent bull market in time to capture +25.93% of the year's total +33.88% rebound.
3. **Compound Effect**: Avoiding catastrophic impairment while participating in the bulk of the subsequent recovery allowed full-cycle Sharpe, Sortino, Calmar, and Ulcer Index to all favor the filter across the 9-year span.

---

## 3. Rolling Window Rigor & Statistical Independence

To avoid cherry-picking specific start/end dates, performance was audited using rolling 126-day windows (approx. 6 months) stepped every 21 trading days (approx. 1 month):

* **Evaluated Scope**: **103 rolling windows** tested across 9 years.
* **Underlying Market Independence**: Overlapping windows captured **73 distinct drawdown episodes** (not 103 independent events).
* **Consistency**: The filter reduced maximum drawdown in **103 of 103 windows (100.0%) across all 73 distinct drawdown episodes**.
* **Distribution of Drawdown Reduction**:
  * **Mean Ratio**: 1.815x
  * **Median Ratio**: 1.619x
  * **25th Percentile (Q1)**: 1.279x
  * **75th Percentile (Q3)**: 2.172x
  * **Min / Max Range**: 1.029x to 6.324x

---

## 4. Ideal User Profile

* **Target Audience**: Capital-preservation-focused investors, retirees, and family offices who cannot psychologically or operationally tolerate a >20% portfolio collapse and are willing to sacrifice bull-market upside in calm years in exchange for verified catastrophe insurance during systemic shocks.
* **Unsuitable Audience**: Growth-seeking investors, aggressive indexers, alpha seekers, or anyone expecting to outperform the market during quiet or rising regimes.

---

## 5. Regulatory & Educational Disclaimer

> **Research & Educational Use Only**: Aarambh is a quantitative research platform. All signals, models, and backtest results are rules-based empirical simulations provided solely for informational and educational purposes. They do not constitute personalized investment advice, financial planning, or portfolio management services. Historical backtests—even when verified out-of-sample across multi-year cycles—do not guarantee future returns or drawdown bounds. Always consult a SEBI-registered financial advisor before committing capital.
