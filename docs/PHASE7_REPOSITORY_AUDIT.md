# Phase 7 — Repository Audit Report

**Repository:** GaurviDEEP
**Working Branch:** `phase7-research`
**Base Commit:** `c978968ec822aa20453920c8708673fcaa736695` (`chore: checkpoint before Phase 7 implementation`)
**Phase 6 Closure Tag:** `phase6-closed-2026-10-04`
**Audit Timestamp:** 2026-10-05T06:55:00+05:30
**Audit Standard:** Strict pre-registration governance, zero lookahead bias, survivorship-free point-in-time evaluation.

---

## 1. Executive Summary

Phase 6 of the GaurviDEEP research programme formally closed on 2026-10-04 as a **valid, scientifically complete null result** across single-stock 5-day directional classification models. The Phase 6 holdout vault remains 100% sealed with zero access events recorded.

Phase 7 initiates a completely separate, pre-registered quantitative research programme addressing the **cross-sectional ranking of liquid Indian equities** over a 20-trading-day holding horizon, with exposure-controlled portfolio construction and realistic transaction-cost modeling.

This repository audit establishes the empirical baseline, data availability, technical debt, security posture, and governance boundaries before committing any Phase 7 research preregistration.

### Headline Audit Findings:
1. **Repository & Branch Integrity:** The working branch `phase7-research` is active, tracking `origin/phase7-research`, with a clean working tree at commit `c978968`. The Phase 6 closure tag `phase6-closed-2026-10-04` is intact.
2. **Phase 6 Immutability & Vault Isolation:** The existing Phase 6 vault resides strictly outside the repository filesystem (`C:\Users\r_chh\gaurvideep_vault\` and secondary backup at `C:\Users\r_chh\OneDrive - optgbrc\Apps\gaurvideep_vault\`). Both encrypted archives (`window_a_sealed.7z` and `window_b_sealed.7z`) remain uncompromised and untouched. Phase 6 safeguard tests (`test_phase6_safeguards.py`) pass 100% (4/4 tests).
3. **Data Availability & Critical Blockers:**
   - **Historical Nifty 500 PIT Membership:** **ABSENT.** The repository currently possesses only a static 138-ticker list (`features/universe.py` and `data/multi/ticker_sectors.json`), creating severe survivorship bias if used retrospectively.
   - **Price & Turnover Data:** The local dataset (`data/multi/historical_10y_raw.csv`, 302,305 rows) covers 138 tickers from 2016-09-26 to 2025-09-16, but provides **only `Close` prices**. It lacks `Open`, `High`, `Low`, `Volume`, and daily traded value. As a result, liquidity filtering (e.g. 60-day median daily traded value $\ge$ INR 10 crore) and realistic execution modeling ($t+1$ execution) are currently blocked without newly ingested OHLCV data.
   - **Fundamentals & Quality Data:** SUE (Standardized Unexpected Earnings) data is available for 134 tickers (2018–2025) via parsed NSE XBRL filings (`sue_features_quarterly.csv`). Comprehensive balance-sheet, cash-flow, promoter holding, and pledging datasets are absent.
4. **Environment & Dependency Risk:** The active Python runtime is Python 3.14.4 on Windows. While Phase 6 safeguard tests run cleanly, Python 3.14 exhibits a severe C-level access violation in `pandas.core.arrays.datetimes._generate_range` during datetime sequence generation. A stable Python environment (Python 3.11 or 3.12, matching CI) must be pinned for numerical consistency.
5. **Phase 7 Readiness Verdict:** **PROCEED TO MILESTONE 1 (PREREGISTRATION & ARCHITECTURE) ONLY.** The quantitative modeling path (Milestones 5–7) is formally **BLOCKED** on actual market data until point-in-time constituent membership and OHLCV turnover datasets are procured or ingested. Milestone 1 (Preregistration, governance schemas, contracts, boundary tests) can safely proceed.

---

## 2. Repository Structure & Artifacts

The repository contains three primary architectural layers:
```
GaurviDEEP/
├── .github/workflows/          # CI/CD: deploy.yml (Render deploy), refresh_cache.yml (daily EOD cache)
├── data/
│   ├── fundamentals/           # 3,799 files tracked in git: XBRL XMLs, parsed corporate actions, SUE CSV
│   │   ├── corporate_actions/  # 138 per-ticker corporate actions JSONs (splits, bonuses, dividends)
│   │   ├── metadata/           # NSE filing metadata harvests
│   │   ├── parsed/             # Parsed standalone/consolidated filings
│   │   ├── xbrl/               # Machine-readable NSE XBRL XML disclosure files
│   │   └── sue_features_quarterly.csv # 3,550 rows, 134 tickers (2018-05-25 to 2025-02-15)
│   ├── multi/                  # Local uncommitted datasets (ignored by .gitignore)
│   │   ├── historical_10y_raw.csv      # 302,305 rows (Close only), 138 tickers (2016-09-26 to 2025-09-16)
│   │   ├── relative_features_v1.csv   # 302,305 rows (Phase 6 features)
│   │   ├── india_vix_development.csv  # India VIX daily closes up to 2025-09-16
│   │   └── ticker_sectors.json        # Static 138-ticker sector and industry mapping
│   ├── nse_cache/              # Local runtime cache for NSE scraping (empty, ignored)
│   └── raw/market_data.csv     # Legacy snapshot (2026-08-26)
├── docs/                       # Research governance: Phase 6 preregistrations, Gate reports, access log
├── ensemble/artifacts/         # Phase 4/5 experimental artifacts (weights, predictions, calibration)
├── features/                   # Legacy production feature code: data_provider.py, indicators.py, universe.py
├── phase6_artifacts/           # Phase 6 evaluation summaries (gate2_results.json, gate4_results.json)
├── scripts/
│   ├── phase4/, phase5/        # Historical walk-forward and model training scripts
│   ├── phase6/                 # Phase 6 data loader, XBRL parser, CA engine, model trainers
│   └── verification/           # Stress tests (Covid, drawdown, regime checks)
├── service/                    # Production FastAPI application ("Aarambh_Quant Signals" v5.0.0)
│   ├── models/                 # Model binaries (.pkl, .pt, .npz) and cache JSONs tracked in git
│   ├── routes_*.py             # Serving routes (auth, scanner, signals, watchlist, portfolio, etc.)
│   └── app.py                  # Main API server
├── test_*.py                   # Root test scripts (safeguards, feature parity, API endpoint tests)
├── requirements.txt            # Root dependencies
└── render.yaml                 # Render cloud deployment configuration
```

---

## 3. Current Research and Production Architecture

### 3.1 Production Architecture ("Aarambh_Quant Signals")
- **Hosting & Infrastructure:** FastAPI application deployed on Render (`render.yaml`, `Dockerfile`), exposing public routes (`/v1/signal`, `/scanner`, `/signals/history`) and authenticated user tiers (`free`, `pro`, `enterprise` via `service/keys.py` and `service/keys.json`).
- **Inference Pipeline:**
  - Consumes live/cached OHLCV via `features/data_provider.py` (NSE scrape $\to$ Yahoo Finance $\to$ Stooq $\to$ local `ticker_cache.json`).
  - Computes 27 technical indicators via `features/indicators.py` (RSI, MACD, Bollinger Bands, ATR, Stochastics, etc.).
  - Runs an ensemble of models (Logistic Regression, Shallow Random Forest, XGBoost, and optional ticker-specific PyTorch LSTM) loaded from `service/models/`.
  - Applies a 200-SMA regime overlay ($\pm 1.00\%$ hysteresis band) to assign `BULL` / `BEAR` state.
- **Production Persistence:** SQLite database at `service/aarambh.db` logging user registrations, subscriptions, and signal queries (`SignalRecord`).

### 3.2 Coupling Between Research and Production
- **Tight Coupling in `features/universe.py`:** The static list of 138 tickers is imported by both `service/app.py` and batch training scripts (`prepare_enhanced_data.py`).
- **Research vs Production Boundary Violation in CI:** `.github/workflows/deploy.yml` runs `python test_phase6_safeguards.py` alongside API integration tests. If a research test fails, production deployment is blocked.
- **Phase 7 Architectural Mandate:** Phase 7 research code must be strictly quarantined under a dedicated package `phase7/` and must never import or be imported by `service/`. No production endpoints may be modified, and no stock-picking endpoints may be exposed.

---

## 4. Dataset Inventory & Date-Range Assessment

| Dataset Name | Physical Location | Tracked in Git? | Date Range | Security Scope | Fields Present | Missing Critical Fields |
|---|---|---|---|---|---|---|
| `historical_10y_raw.csv` | `data/multi/` | No (`.gitignore`) | 2016-09-26 to 2025-09-16 | 138 tickers | `date`, `ticker`, `Close` | `Open`, `High`, `Low`, `Volume`, Traded Value |
| `relative_features_v1.csv` | `data/multi/` | No (`.gitignore`) | 2016-09-26 to 2025-09-16 | 138 tickers | `date`, `ticker`, `relative_ret_5d`, `relative_ret_5d_vs_index`, `sector_rank_pct` | Target columns, 20d/60d horizons |
| `india_vix_development.csv` | `data/multi/` | No (`.gitignore`) | 2016-09-26 to 2025-09-16 | Macro index | `date`, `vix_close` | Intraday VIX, sector-specific volatility |
| `sue_features_quarterly.csv` | `data/fundamentals/` | Yes | 2018-05-25 to 2025-02-15 | 134 tickers | `ticker`, `effective_date`, `eps_adj`, `sue`, `broadCastDate`, `pat` | Balance sheet, Cash flow, Debt, Margins |
| `corporate_actions/*_ca.json` | `data/fundamentals/` | Yes | ~2000 to 2026-06 | 138 tickers | `symbol`, `exDate`, `recDate`, `subject` (bonus, split, dividend) | Delisting dates, merger share-exchange ratios |
| `ticker_sectors.json` | `data/multi/` | No (`.gitignore`) | Static snapshot | 138 tickers | `sector`, `industry` | Historical sector reclassifications with effective dates |
| Point-in-Time Nifty 500 Constituents | **None** | **None** | **Missing** | Nifty 500 | None | Full index addition/deletion history with effective dates |
| Full Nifty 500 OHLCV Prices | **None** | **None** | **Missing** | Nifty 500 (~500 stocks) | None | Full 10-year OHLCV for all historical constituents |

---

## 5. Point-in-Time Capability Assessment

1. **Constituent Membership:**
   - **Current Capability:** **NONE (Static Retrospective).** The repository only knows a fixed list of 138 tickers. Applying this list across 2016–2025 introduces massive survivorship bias (companies that failed or were removed from the index before 2024 are omitted; companies added recently are projected backward).
   - **Phase 7 Requirement:** Must construct an independent eligible universe per rebalance date using point-in-time constituent membership and liquidity criteria.
2. **Corporate Action Adjustments:**
   - **Current Capability:** **PARTIAL / VALIDATED FOR EPS.** `scripts/phase6/corporate_action_engine.py` correctly parses stock splits and bonus issues from NSE disclosures and computes cumulative adjustment factors for EPS. However, total-return price adjustments (incorporating cash dividends) are not implemented.
   - **Phase 7 Requirement:** Prices and sector benchmarks must use Total Return Index (TRI) accounting or dividend-adjusted returns for $t+1 \to t+20$ target calculation.
3. **Fundamentals Publication Timestamps:**
   - **Current Capability:** **STRONG FOR SUE (2018–2025).** Phase 6 Gate 3 established rigorous publication timestamps (`broadCastDate` / `filingDate`) from official NSE XBRL filings, preventing backward leakage.
   - **Phase 7 Requirement:** Any additional accounting feature (ROCE, Debt/EBITDA, OCF/PAT) must possess verifiable `first_seen_timestamp` or `effective_date` before entering feature matrices.
4. **Analyst Revisions & Consensus:**
   - **Current Capability:** **ZERO.** No consensus earnings estimates or revision histories exist. Capability is marked **BLOCKED**.

---

## 6. Leakage and Survivorship Risk Assessment

| Risk Category | Severity | Current Status in Repo | Phase 7 Control Required |
|---|---|---|---|
| **Retrospective Universe Selection** | **CRITICAL** | High risk: 138 tickers chosen retrospectively. | Require point-in-time constituent membership. Fail closed if membership is unknown. |
| **Look-Ahead Execution Bias** | **HIGH** | Legacy models execute at same-day `Close_t`. | Phase 7 enforces strict $t+1$ execution (next-session open/VWAP/executable price). |
| **Preprocessing Leakage** | **HIGH** | Legacy scripts frequently fit scalers or percentiles on full series. | Preprocessing must be strictly fitted inside each expanding fold. Zero out-of-fold leakage. |
| **Target Leakage into Features** | **HIGH** | Phase 6 used 5-day price shift. | Strict physical decoupling between `phase7/targets/` and `phase7/features/`. |
| **Purge and Embargo Failure** | **HIGH** | Phase 6 used 10-day purge gap. | Phase 7 target horizon is 20 days; purge must be $\ge 20$ trading days, embargo $\ge 5$ trading days. |
| **Vault Boundary Leakage** | **CRITICAL** | Phase 6 vault is external and sealed. | Phase 7 must establish its own distinct vault protocol. Zero access to Phase 6 vault. |

---

## 7. Reusable Components vs Quarantined Code

### Reusable with Adaptation:
- `scripts/phase6/corporate_action_engine.py`: Corporate action parsing logic for splits and bonus multipliers can be refactored into `phase7/data/corporate_actions.py`.
- `scripts/phase6/data_loader.py` architecture: The fail-closed date validation design pattern can be adopted for Phase 7 fold boundaries.
- `data/fundamentals/sue_features_quarterly.csv`: Point-in-time timestamped quarterly EPS dataset (134 tickers, 2018–2025) is valid for fundamental feature engineering.
- Metrics logic: Standard Sharpe, Drawdown, and Rank IC formulas across Phase 4/5/6 scripts.

### Strictly Quarantined (Must NOT be Reused in Phase 7):
- `features/universe.py`: Contains static survivorship-biased 138 tickers.
- `features/indicators.py`: Contains technical indicators forbidden in Phase 7 without preregistered justification.
- `service/models/*`: Binary model artifacts from legacy phases.
- `scripts/phase6/train_gate*.py`: Phase 6 models and workflows targeting single-stock 5-day directional binary labels.
- `scripts/split_data.py`: Legacy split routines that do not enforce expanding walk-forward purge/embargo requirements.

---

## 8. Test and CI Assessment

- **Test Suite Status:**
  - `test_phase6_safeguards.py`: **4 passed in 8.47s.** (Refuses post-cutoff requests, validates docs, verifies no direct CSV bypass, verifies working tree data ends $\le 2025-09-16$).
  - `test_features.py`: **Crashed (Windows access violation)** on Python 3.14.4 during datetime generation.
  - Root `test_app.py`, `test_phase_a.py`, `test_signal.py`: Integration tests for FastAPI service routes.
- **CI Workflows:**
  - `.github/workflows/deploy.yml`: Triggers on push to `main`, tests features and Phase 6 safeguards on Python 3.12, then deploys to Render.
  - `.github/workflows/refresh_cache.yml`: Scheduled daily cron rebuilding market cache and auto-committing `service/aarambh.db` and JSON caches.

---

## 9. Dependency Assessment

- **Runtime Environment:**
  - Active Python: Python 3.14.4 (`C:\Python314\python.exe`).
  - Alternate Python: Python 3.11.9 (`C:\Users\r_chh\AppData\Local\Programs\Python\Python311\python.exe`).
  - Key installed packages: `numpy==2.5.3`, `pandas==2.2.3`, `scikit-learn==1.9.1`, `lightgbm==4.7.0`, `xgboost==3.4.1`, `torch==2.13.0`, `pytest==9.1.1`, `pyyaml==6.0.2`, `pydantic==2.13.4`.
- **Packaging Method:** Flat `requirements.txt` with unpinned dependencies in some sections. No `pyproject.toml` or poetry lock exists.
- **Stability Risk:** Python 3.14 is a pre-release / cutting-edge build in 2026 with known C-extension ABI instabilities with pandas datetime indexing. For Phase 7 reproducibility, Python 3.11 or 3.12 should be adopted for research scripts.

---

## 10. Security and Credential Assessment

- **Secrets Handling:**
  - `.gitignore` properly excludes `.env`, `.env.*`, `*.db`, `*.sqlite`, `*.7z`, `*.gpg`, `vault/`, `*sealed*`.
  - No plaintext credentials, API keys, or vault passwords were found in git history or tracked files.
  - `service/keys.json` contains SHA-256 hashes of API keys, not plaintext.
  - No `.env.example` file exists in the repository. One must be added in Phase 7.
- **External Vault Isolation:**
  - Vault locations (`C:\Users\r_chh\gaurvideep_vault\` and `C:\Users\r_chh\OneDrive - optgbrc\Apps\gaurvideep_vault\`) are physically detached from the repository.
  - Zero vault commands or archive queries have been executed.

---

## 11. Phase 6 Boundary Assessment

- **Tag Verification:** `phase6-closed-2026-10-04` is present on commit `c978968`.
- **File Immutability:** No Phase 6 file under `docs/`, `scripts/phase6/`, or `phase6_artifacts/` has been modified.
- **Safeguard Enforcement:** `test_phase6_safeguards.py` verified and active.
- **Scientific Status:** Phase 6 outcome is confirmed as an immutable, complete, valid null result.

---

## 12. Phase 7 Readiness Verdict

| Dimension | Status | Recommendation |
|---|---|---|
| **Git Working Tree & Branch** | **READY** | Active branch `phase7-research`, clean tree. |
| **Phase 6 Safeguards** | **READY** | Sealed, passing CI, zero vault access. |
| **Milestone 1 Architecture & Preregistration** | **READY** | Can proceed autonomously once approved. |
| **Point-in-Time Nifty 500 Constituent Data** | **BLOCKED** | Missing historical index additions/deletions. |
| **OHLCV & Daily Traded Value Data** | **BLOCKED** | Missing volume and non-Close prices for universe. |
| **Financial Statements (Quality & Valuation)** | **BLOCKED** | Balance sheet/cash flow data missing; SUE only available. |
| **Overall Verdict** | **PROCEED WITH MILESTONE 1; BLOCK DATA-DEPENDENT MODELING** | Complete preregistration, contracts, schemas, and boundary tests in Milestone 1. Enforce fail-closed state for missing data. |
