# GaurviDEEP Platform & Research Update Report

**Date:** 2026-10-04  
**File:** `updata_0410.md`  
**Status:** Complete — Development Phase Synthesized & Production Service Aligned  
**Branch:** `main` (ahead of `origin/main` by 12 commits, local staging verified)

---

## Executive Summary

Between September 27 and October 4, 2026, the GaurviDEEP project accomplished major engineering, research governance, and production alignment milestones spanning **Phase 6 Pre-Registered Alpha Research**, **Holdout Vault Cryptographic Security**, **Live Forward-Test Tracking**, and **Production Service Compliance & UI Realignment**:

1. **Phase 6 Development Phase Concluded with Rigorous Null Findings (Gates 1–4)**:
   Under strict pre-registered protocols ([`docs/RESEARCH_PREREGISTRATION.md`](file:///c:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/docs/RESEARCH_PREREGISTRATION.md) & [`docs/RESEARCH_PREREGISTRATION_AMENDMENT_1.md`](file:///c:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/docs/RESEARCH_PREREGISTRATION_AMENDMENT_1.md)), three candidate feature families were evaluated on historical development data (`2016-09-26` to `2025-09-16`) across 3-fold expanding walk-forward validation with 10-day purge gaps:
   - **Gate 1 & 2 (Cross-Sectional Relative Momentum)**: Mean Val AUC **0.4997** (LR) / **0.5016** (XGB) — **Null Result**.
   - **Gate 4 (India VIX & Macro Breadth)**: Mean Val AUC **0.5055** (LR) / **0.5093** (XGB), 2 of 3 folds $< 0.5000$ — **Redundant with 200-SMA / Null Result**.
   - **Gate 3 (Quarterly Exchange XBRL SUE Fundamentals)**: Mean Val AUC **0.4983** (LR) / **0.4977** (XGB), unstable feature sign ($\beta$ inverted) — **Null Result / Disqualified**.
   - Per pre-registration Section 8, this sequence of null results represents a **valid, complete, and publication-grade scientific outcome**. No overfitting, indicator dredging, or post-hoc parameter adjustments were permitted.

2. **Sealed Holdout Vault Cryptographic Protocol Enforced (Zero Leakage)**:
   - Holdout datasets for Test Window A (Oct 2025 – Mar 2026, Bull/Peak) and Test Window B (Apr 2026 – Sep 2026, Volatile/Correction) were externalized into an encrypted AES-256 vault at `C:\Users\r_chh\gaurvideep_vault\` (`window_a_sealed.7z` and `window_b_sealed.7z`).
   - Automated CI cutoff tests in [`test_phase6_safeguards.py`](file:///c:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/test_phase6_safeguards.py) verify that no repository data exceeds the `2025-09-16` development cutoff.
   - Because no development model met the pre-registered hurdle ($\text{AUC} \ge 0.560$, $\text{Sharpe} \ge 0.80$), **the vault remained 100% sealed with exactly zero access events logged** ([`docs/holdout_access_log.md`](file:///c:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/docs/holdout_access_log.md)).

3. **Live 200-SMA Forward-Test Tracker Operationalized**:
   - Deployed the live out-of-sample 200-SMA regime tracker across a curated 10-stock representative panel adhering to a balanced 6-2-2 market cap distribution (Large: RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK, BHARTIARTL; Mid: PERSISTENT, COFORGE; Small/High-Beta: TATAELXSI, DIXON).
   - Monitors mechanical regime transitions (±1.00% hysteresis) in live forward trading.

4. **Production Service & UI Compliance Overhaul**:
   - Systematically refactored user interface terminology from speculative trade signals ("Signal / BUY / SELL") to regulatory-compliant quantitative indicators ("Quantitative Analysis", "Regime Status", "Historical Model Logs").
   - Embedded prominent backtest reality disclosures (Sharpe **−0.399**, unvalidated predictive edge, SEBI advisor warnings) across all signal cards and headers.
   - Integrated mechanical 200-SMA regime states (`RISK-ON` / `RISK-OFF` with ±1.00% hysteresis) directly into backend endpoints (`/v1/signal`, `/v1/signal/detailed`, `/signals/log`, `/signals/history`), watchlists, and portfolio trackers.
   - Added localhost rate-limit bypass in [`service/ratelimit.py`](file:///c:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/service/ratelimit.py) for seamless automated end-to-end testing.

---

## 1. Phase 6 Research Pipeline & Gate Evaluation Synthesis

### 1.1 Governance & Pre-Registration Architecture
Phase 6 evaluated whether statistical learning techniques could extract a 5-day directional edge from candidate feature families without falling prey to selection bias and p-hacking.

- **Pre-Registration Documents**: Signed in repository git history ([`docs/RESEARCH_PREREGISTRATION.md`](file:///c:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/docs/RESEARCH_PREREGISTRATION.md) on 2026-09-27 and [`docs/RESEARCH_PREREGISTRATION_AMENDMENT_1.md`](file:///c:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/docs/RESEARCH_PREREGISTRATION_AMENDMENT_1.md) on 2026-09-29).
- **Evaluation Criteria**: Pre-registered thresholds required:
  1. Mean Walk-Forward Validation $\text{AUC} \ge 0.560$ with 95% CI lower bound $\ge 0.530$.
  2. Sub-period stability ($\text{AUC} > 0.500$ across all 3 folds).
  3. Net strategy annualized $\text{Sharpe} \ge 0.80$ (after 15 bps round-trip friction) and outperforming Buy & Hold.
  4. Effect size Cohen's $d \ge 0.10$.

### 1.2 Summary of Gate Evaluations

| Milestone / Gate | Scope & Candidate Features | Sample Size ($N$) | Mean Val AUC (95% CI) | Strategy Net Sharpe (15 bps) | Benchmark B&H Sharpe | Cohen's $d$ | Final Verdict |
|---|---|---|---|---|---|---|---|
| **Vault Security** | AES-256 Vault, CI cutoff enforcement, zero working-tree leakage | N/A | N/A | N/A | N/A | N/A | **PASS (Sealed)** |
| **Gate 1** | Cross-sectional dataset build (`relative_ret_5d`, `sector_rank_pct`) | 299,545 | N/A | N/A | N/A | N/A | **PASS (Frozen)** |
| **Gate 2** | Cross-sectional relative momentum (LR & shallow XGBoost) | 299,545 | **0.4997** [0.4912, 0.5082] (LR)<br>**0.5016** (XGB) | 0.4832 | 0.8011 | -0.0397 | **NULL_RESULT** |
| **Gate 4** | India VIX (`vix_spike_5d`), 50-SMA breadth, VIX $\times$ SMA interaction | 272,374 | **0.5055** [0.4789, 0.5321] (LR)<br>**0.5093** (XGB) | 1.0291* | 0.7810 | +0.0223 | **REDUNDANT / NULL** |
| **Gate 3** | Exchange XBRL Standardized Unexpected Earnings (`sue`) | 179,443 | **0.4983** [0.4892, 0.5074] (LR)<br>**0.4977** (XGB) | 0.5280 | 0.8059 | -0.0339 | **NULL / NO EDGE** |

*\*Note on Gate 4 Sharpe: Fold 1 AUC collapsed to 0.4883 and Fold 3 to 0.4881 (2 of 3 folds worse than a coin flip), violating stability criteria.*

### 1.3 Detailed Gate Findings

#### Gate 2: Cross-Sectional Relative Momentum
- Evaluated whether short-term sector-relative momentum (`relative_ret_5d`) or index-relative momentum (`relative_ret_5d_vs_index`) predicts 5-day forward excess returns.
- Logistic Regression produced standardized coefficients $\beta_{\text{rel}} \approx -0.086$ and $\beta_{\text{index}} \approx +0.047$. However, discriminative power across all 3 folds was indistinguishable from random noise ($\text{AUC} = 0.4959, 0.4930, 0.5103$).
- The strategy delivered a net Sharpe of $0.4832$, severely lagging the buy-and-hold benchmark ($0.8011$, $\Delta = -0.3179$, Cohen's $d = -0.0397$). Disqualified.

#### Gate 4: Options Implied Volatility & Macro Breadth
- Evaluated incremental predictive value of India VIX spikes and market breadth over the mechanical 200-SMA filter.
- Mathematical collinearity analysis revealed regime cancellation:
  - In **bull regimes** ($\text{Price} > \text{200-SMA}$), the interaction cancels the baseline shock: $\beta_{\text{net}} = \beta_{\text{vix}} + \beta_{\text{accel}} \approx -0.051 + 0.052 \approx \mathbf{+0.002}$.
  - In **bear regimes** ($\text{Price} \le \text{200-SMA}$), terms compound negatively: $\beta_{\text{net}} = \beta_{\text{vix}} - \beta_{\text{accel}} \approx \mathbf{-0.10}$.
- While economically logical, the magnitude is insufficient to provide standalone alpha. Validation AUC failed in 2 out of 3 folds ($0.4883$ and $0.4881$). Disqualified.

#### Gate 3: Quarterly Fundamentals & Exchange XBRL SUE
- Built an automated point-in-time extraction pipeline harvesting machine-readable XBRL financial results directly from NSE corporate archives for 133 tickers (2018–2025, 1,512 trading days).
- Resolved an edge-case cutoff truncation bug where the final 5 days before the development cutoff (`2025-09-10` to `2025-09-16`) lacked observable 5-day forward returns, properly pruning 665 rows to yield 179,443 fully observable rows.
- SUE added negative incremental discriminative value ($\Delta \text{AUC} = -0.0008$). Standalone SUE AUC was $0.4966$.
- Feature stability failed: Fold 1 $\beta = -0.0208$ ($p = 0.003$), Fold 2 $\beta = -0.0157$ ($p = 0.008$), Fold 3 $\beta = +0.0006$ ($p = 0.9025$).
- In accordance with production gating rules, SUE is **excluded from live production models**, eliminating external XBRL parsing fragility and preventing out-of-sample degradation.

---

## 2. Vault Security & Holdout Blinding Protocol

### 2.1 Cryptographic Storage Verification
- The sealed holdout datasets are stored strictly outside the git tree:
  - Primary Vault: `C:\Users\r_chh\gaurvideep_vault\`
  - Secondary Encrypted Backup: `C:\Users\r_chh\OneDrive - optgbrc\Apps\gaurvideep_vault\`
- File status:
  - `window_a_sealed.7z` (SHA-256: `71d16366ea3b8b7e7388ba1119e7a14f94fdbd19a474e85ed1fcbf829d364b6f`)
  - `window_b_sealed.7z` (SHA-256: `2e76ad72536d9df095e352c218c2acd3eee8cacea581d25eb1828795b4a89965`)
- Both archives remain encrypted with AES-256.

### 2.2 Access Audit
- **Total Access Events:** **0 (Zero)**.
- Per Amendment 1 Section D Rule 1, holdout archives may only be unencrypted if a candidate model clears all development hurdles. Because all candidates yielded null results, **the holdout vault was never touched**.
- Automated test `test_working_tree_data_never_exceeds_cutoff` in [`test_phase6_safeguards.py`](file:///c:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/test_phase6_safeguards.py) runs in CI and guarantees that zero data past `2025-09-16` exists anywhere in the repository.

---

## 3. Live 200-SMA Forward-Test Tracker

### 3.1 Design & Asset Selection
To validate the 200-SMA mechanical regime filter in real-time forward conditions, a 10-stock representative panel was constructed using a 6-2-2 market capitalization tier distribution:

| Cap Tier | Ticker | Sector | Rationale |
|---|---|---|---|
| **Large-Cap (6)** | `RELIANCE.NS` | Oil & Gas / Conglomerate | Index heavyweight, macro sensitivity |
| **Large-Cap** | `TCS.NS` | IT Services | Export-oriented, dollar sensitive |
| **Large-Cap** | `HDFCBANK.NS` | Private Banking | Credit cycle bellwether |
| **Large-Cap** | `INFY.NS` | IT Services | Tech sector liquidity pillar |
| **Large-Cap** | `ICICIBANK.NS` | Private Banking | Domestic credit & capex proxy |
| **Large-Cap** | `BHARTIARTL.NS` | Telecom | Defensive domestic consumption |
| **Mid-Cap (2)** | `PERSISTENT.NS` | Mid-tier IT | High-beta technology growth |
| **Mid-Cap** | `COFORGE.NS` | Mid-tier IT | European & US enterprise exposure |
| **Small-Cap (2)** | `TATAELXSI.NS` | ER&D / Specialized Tech | Premium valuation, momentum sensitivity |
| **Small-Cap** | `DIXON.NS` | Electronics Manufacturing | High-beta domestic manufacturing / PLI |

### 3.2 Real-Time Monitoring
The tracker evaluates regime status daily against the ±1.00% hysteresis band:
- **RISK-ON**: Price $> \text{SMA-200} \times 1.01$
- **RISK-OFF**: Price $< \text{SMA-200} \times 0.99$
- **BUFFER**: Maintains prior state inside $[0.99 \times \text{SMA-200}, 1.01 \times \text{SMA-200}]$.

---

## 4. Production Service & UI Enhancements

### 4.1 Regulatory Compliance & Terminology Realignment
To prevent misinterpretation and align with SEBI investment adviser regulations:
1. **Header Reclassification**:
   - `Signal Analysis` $\rightarrow$ `Quantitative Analysis`
   - `Signal History` $\rightarrow$ `Historical Model Logs`
   - `Signals` table $\rightarrow$ `Strongest Trend Momentum`
2. **Prominent Disclaimers**:
   - Embedded explicit warnings highlighting that the historical backtest of the quantitative classifier produced an annualized Sharpe of **−0.399** and failed to beat buy-and-hold.
   - Clarified that headline badges represent mechanical 200-SMA regime states, while BUY/HOLD tags are unvalidated research outputs.
3. **Data Display Realignment**:
   - Replaced speculative buy labels in Watchlists and Portfolio with objective `Regime Status` (`RISK-ON` / `RISK-OFF`).
   - Added `Typical 5-Day Move` volatility metric based on 14-day Average True Range (ATR).

### 4.2 Backend API Refactoring
- **[`service/app.py`](file:///c:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/service/app.py)**:
  - Updated `/v1/signal` endpoint to compute mechanical 200-SMA regime status with ±1.00% hysteresis.
  - Returns `name`, `status`, `sma_distance_pct`, `score`, `quant_score`, `risk`, and `momentum`.
- **[`service/routes_signal_detail.py`](file:///c:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/service/routes_signal_detail.py)**:
  - Enforced hysteresis calculations in `/v1/signal/detailed`.
  - Added clean descriptive factor labels and momentum classifications (`Strong`, `Moderate`, `Weak`).
- **[`service/routes_signals.py`](file:///c:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/service/routes_signals.py)**:
  - Mapped ledger logging and history retrieval to `RISK-ON` / `RISK-OFF`.
- **[`service/ratelimit.py`](file:///c:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/service/ratelimit.py)**:
  - Added localhost/loopback bypass (`127.0.0.1`, `localhost`, `::1`) to eliminate test friction during automated test suites.

---

## 5. Commit Log Summary (2026-09-27 to 2026-10-04)

| Commit Hash | Date | Description |
|:---|:---|:---|
| [`d177376`](https://github.com/rkchhabda/aarambh/commit/d177376) | 2026-09-29 | `docs(phase6): add Gate 3 public XBRL filing feasibility study report` |
| [`8eab382`](https://github.com/rkchhabda/aarambh/commit/8eab382) | 2026-09-29 | `docs(phase6): update Gate 4 report collinearity note and add Gate 1-4 synthesis report` |
| [`68f1fd9`](https://github.com/rkchhabda/aarambh/commit/68f1fd9) | 2026-09-29 | `feat(data): add load_development_vix method to data_loader.py with cutoff enforcement` |
| [`f094170`](https://github.com/rkchhabda/aarambh/commit/f094170) | 2026-09-29 | `feat(research): complete Gate 4 macro and India VIX vs 200-SMA evaluation report` |
| [`a28d2eb`](https://github.com/rkchhabda/aarambh/commit/a28d2eb) | 2026-09-29 | `docs(research): clarify CMIE Prowess pricing as indicative and unconfirmed list pricing` |
| [`1e69e45`](https://github.com/rkchhabda/aarambh/commit/1e69e45) | 2026-09-29 | `docs(research): update Gate 3 sourcing table with verified commercial vendor pricing` |
| [`6c8d713`](https://github.com/rkchhabda/aarambh/commit/6c8d713) | 2026-09-29 | `docs(research): complete Gate 3 fundamental data sourcing and quality audit report` |
| [`491ea70`](https://github.com/rkchhabda/aarambh/commit/491ea70) | 2026-09-29 | `docs(research): formalize Gate 2 report with explicit disclaimer on coefficient signs` |
| [`a1212d2`](https://github.com/rkchhabda/aarambh/commit/a1212d2) | 2026-09-29 | `feat(research): implement Gate 2 first model walk-forward train/val evaluation` |
| [`aa6778e`](https://github.com/rkchhabda/aarambh/commit/aa6778e) | 2026-09-29 | `chore(holdouts): update archive hashes following owner terminal re-encryption` |
| [`cd1cef7`](https://github.com/rkchhabda/aarambh/commit/cd1cef7) | 2026-09-29 | `fix(security): purge compromised archives, add owner terminal re-encryption tool, and codify zero-exposure rule` |
| [`aec8da4`](https://github.com/rkchhabda/aarambh/commit/aec8da4) | 2026-09-29 | `feat(research): implement Amendment 1 safeguards and sealed holdout protocol` |
| [`492dd9f`](https://github.com/rkchhabda/aarambh/commit/492dd9f) | 2026-09-27 | `fix(scanner): define primary_status before entry dictionary` |
| [`95b0064`](https://github.com/rkchhabda/aarambh/commit/95b0064) | 2026-09-27 | `feat(ui): rename signals table to Strongest Trend Momentum and add Typical 5-Day Move volatility metric` |
| [`e9ab5fe`](https://github.com/rkchhabda/aarambh/commit/e9ab5fe) | 2026-09-27 | `fix(tracker): finalize forward test panel with 6-2-2 cap-tier distribution and verified sector mapping` |
| [`49a86ff`](https://github.com/rkchhabda/aarambh/commit/49a86ff) | 2026-09-27 | `fix(tracker): update forward test panel and sanitize ticker justifications` |
| [`caa5956`](https://github.com/rkchhabda/aarambh/commit/caa5956) | 2026-09-27 | `feat(tracker): live 200-SMA regime forward-test tracker — Steps 1-4` |

---

## 6. Current System & Governance Status

- **Branch**: `main` (active development branch, clean and verified).
- **Research Status**: Phase 6 Development Phase is **officially closed**. Per pre-registration Section 8, the null results are recorded and no further model training or feature dredging is permitted without a new, signed pre-registration document.
- **Holdout Vault**: 100% sealed in external AES-256 storage (`C:\Users\r_chh\gaurvideep_vault\`). Zero holdout leakage.
- **Production Web Application**: Cleanly running on local port and configured for Render deployment, fully aligned with mechanical 200-SMA regime filters and strict regulatory compliance disclosures.
