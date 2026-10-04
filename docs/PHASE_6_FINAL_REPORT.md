# Phase 6 Final Closeout Report: Development Phase Synthesis (Gates 1–4)

**Repository:** GaurviDEEP  
**Phase:** Phase 6 (Pre-Registered Alpha Evaluation)  
**Execution Dates:** 2026-09-27 to 2026-09-30  
**Governing Documents:**  
- [`docs/RESEARCH_PREREGISTRATION.md`](RESEARCH_PREREGISTRATION.md) (Signed 2026-09-27)  
- [`docs/RESEARCH_PREREGISTRATION_AMENDMENT_1.md`](RESEARCH_PREREGISTRATION_AMENDMENT_1.md) (Signed 2026-09-29)  
- [`docs/GATE_1_AUDIT.md`](GATE_1_AUDIT.md)  
- [`docs/GATE_2_REPORT.md`](GATE_2_REPORT.md)  
- [`docs/GATE_3_SOURCING_REPORT.md`](GATE_3_SOURCING_REPORT.md)  
- [`docs/GATE_4_REPORT.md`](GATE_4_REPORT.md)  
**Dataset Scope:** Strictly development data (`2016-09-26` to `2025-09-16`; narrowed to `2018-01-01` to `2025-09-16` for fundamentals per pre-registered scope amendment).  

---

## 1. Synthesis of Evaluated Feature Families

Across Phase 6, three distinct feature families were formally evaluated on development data under strict walk-forward cross-validation architectures with 10-day purge gaps and zero lookahead bias. All three yielded **statistically null results**, failing the Section 1 pre-registration criteria:

### Headline Performance Summary Table

| Milestone / Gate | Description & Scope | Core Features / Deliverables | Models Tested | Mean Val AUC (95% CI) | Strategy Net Sharpe (15 bps) | Benchmark Buy & Hold Sharpe | Cohen's $d$ Effect Size | Final Verdict |
|---|---|---|---|---|---|---|---|---|
| **Amendment 1 Setup** | **Vault Infrastructure & Blinding Protocol** (Sections D & E) | External AES-256 encrypted vault, CI cutoff tests, cryptographic hash locks | N/A (Infrastructure) | N/A | N/A | N/A | N/A | **PASS (Vault Sealed)** |
| **Gate 1** | **Cross-Sectional Feature Build** (Month 1 per Section G) | `relative_ret_5d`, `relative_ret_5d_vs_index`, `sector_rank_pct` | Feature Pipeline (Point-in-time development data) | N/A | N/A | N/A | N/A | **PASS (Dataset Frozen)** |
| **Gate 2** | **First Model: Cross-Sectional Features Only** | `relative_ret_5d`, `relative_ret_5d_vs_index`, `sector_rank_pct` | Logistic Regression, Shallow XGBoost (depth 3) | **0.4997** [0.4912, 0.5082] (LR)<br>**0.5016** (XGB) | **0.4832** | **0.8011** ($\Delta = -0.3179$) | **-0.0397** | **NULL_RESULT / DISQUALIFIED** |
| **Gate 4** | **Options Implied Volatility & Macro Breadth** | `vix_spike_5d`, `pct_universe_above_50sma`, `vix_accel_x_sma_regime` (over 200-SMA baseline) | Logistic Regression, Shallow XGBoost (depth 3) | **0.5055** [0.4789, 0.5321] (LR)<br>**0.5093** (XGB) | **1.0291** | **0.7810** ($\Delta = +0.2481$)* | **+0.0223** | **REDUNDANT_WITH_200SMA_NULL_RESULT** |
| **Gate 3** | **Exchange Corporate Fundamentals (SUE)** | Standardized Unexpected Earnings (`sue`) from machine-readable NSE XBRL disclosures | Logistic Regression, Shallow XGBoost (depth 3) | **0.4983** [0.4892, 0.5074] (LR)<br>**0.4977** (XGB) | **0.5280** | **0.8059** ($\Delta = -0.2779$) | **-0.0339** | **NULL / NO EDGE** |

*\*Note on Gate 4 Sharpe:* While Gate 4 generated a positive net Sharpe over Buy & Hold during the 2023–2024 bull run, its validation AUC collapsed to $<0.5000$ in 2 out of 3 folds (Fold 1: $0.4883$, Fold 3: $0.4881$), violating pre-registered AUC ($\ge 0.560$) and sub-period stability requirements.

---

## 2. Scientific Status of the Outcome

Per Section 8 ("Publication and Archival Discipline") of [`docs/RESEARCH_PREREGISTRATION.md`](RESEARCH_PREREGISTRATION.md):

> **This is a valid, complete, and scientifically honest outcome.**

In quantitative finance and statistical learning, a sequence of well-controlled null results is a primary objective of pre-registration:
1. **Capital Preservation:** Confirming that short-term price momentum, implied volatility breadth, and quarterly XBRL earnings surprises do not produce a 5-day directional edge prevents allocating capital to false discoveries driven by backtest overfitting.
2. **Elimination of P-Hacking:** No post-hoc parameter adjustments, threshold searching, or metric re-definitions were permitted. Every evaluation was conducted against immutable thresholds decided prior to seeing the data.
3. **Disqualification of Features:** In accordance with pre-registered rules, **no further tweaking, feature recombination, or model retraining using these three feature families is authorized**. These hypotheses are officially closed on this development window.

---

## 3. Final Vault Status, Location Audit & Blinding Integrity

### 3.1 Vault Filesystem Reconciliation & Verification
The reference in preliminary notes to `data/vault/*.parquet.enc` was a mislabeling. An exhaustive filesystem and git audit confirms:
1. **Actual Vault Location (Outside Git Working Tree):**
   - The sealed holdout files are stored strictly **outside the repository working tree** at:
     ```
     C:\Users\r_chh\gaurvideep_vault\
     ```
     *(with secondary encrypted backup at `C:\Users\r_chh\OneDrive - optgbrc\Apps\gaurvideep_vault\` per [`scripts/reencrypt_vault.py`](../scripts/reencrypt_vault.py)).*
   - Verified filesystem listing:
     ```
     Mode    LastWriteTime         Length   Name
     ----    -------------         ------   ----
     -a---   29-09-2026 05:59      992610   window_a_sealed.7z
     -a---   29-09-2026 05:59      999361   window_b_sealed.7z
     ```
2. **Format & Encryption Standards:**
   - Both archives are encrypted with **AES-256** using py7zr (`window_a_sealed.7z` and `window_b_sealed.7z`).
   - Verified SHA-256 archive hashes:
     - **Window A:** `71d16366ea3b8b7e7388ba1119e7a14f94fdbd19a474e85ed1fcbf829d364b6f`
     - **Window B:** `2e76ad72536d9df095e352c218c2acd3eee8cacea581d25eb1828795b4a89965`
3. **Git History & Working Tree Absence:**
   - The path `data/vault/` **does not exist** in the repository (`Test-Path data\vault` returns `False`).
   - `git ls-files` confirms **zero** holdout files, `.7z` archives, or `.enc` files are tracked by git.
   - `git log --all --full-history` confirms **no holdout data has ever been committed** in the repository history.
   - Automated CI test `test_working_tree_data_never_exceeds_cutoff` in [`test_phase6_safeguards.py`](../test_phase6_safeguards.py) confirms that all repository-internal CSVs (`data/multi/historical_10y_raw.csv` and `relative_features_v1.csv`) strictly truncate on or before `2025-09-16` (the development cutoff).

### 3.2 Holdout Access Audit
- **Holdout Windows A and B Status:** **100% SEALED.**
- **Access Events:** **ZERO (0).**
- **Amendment 1 Section D Rule 1 Compliance:**
  > *"Test Window A and Test Window B remain sealed in an external vault. They may ONLY be accessed if a candidate model clears all development hurdles."*
- Because no candidate model from Gates 2, 3, or 4 met the pre-registered development hurdle (Validation $\text{AUC} \ge 0.560$, 95% CI lower bound $\ge 0.530$, $\text{Sharpe} \ge 0.80$, Cohen's $d \ge 0.10$), the external vault was **never opened, unencrypted, or queried**. Both holdout datasets remain completely uncompromised.

---

## 4. Explicit Inventory of Untested Hypotheses & Data Domains

The null findings of Phase 6 apply strictly to the free public data sources and feature formulations tested. The following data categories remain **genuinely untested**, for the specific reasons recorded below:

1. **Paid Commercial Fundamentals Data (Blocked by Cost, Not Evidence):**
   - High-quality, point-in-time commercial databases (e.g., Bloomberg, FactSet, S&P Capital IQ, CMIE Prowess IQ, Capitaline) provide standardized balance sheet line items, cash flow statement metrics, enterprise valuation ratios, and forward consensus analyst revisions.
   - These were not evaluated because access requires paid enterprise subscriptions, which were ruled out by project budget constraints.
2. **BSE-Sourced Data (Blocked by Access, Not Evidence):**
   - BSE corporate filing archives contain disclosures for companies not actively reporting machine-readable XBRL on NSE, as well as distinct filing timestamps.
   - These were not evaluated because BSE's web infrastructure enforces strict HTTP 403 bot-detection (Cloudflare), and the pre-registration protocol explicitly prohibited circumvention or non-compliant scraping.
3. **Unidentified / Unexplored Data Sources:**
   - Alternative data (e.g., supply chain graphs, satellite imagery, web traffic).
   - High-frequency order book microstructure (bid-ask imbalance, order flow toxicity, tick-level trade dynamics).
   - Regulatory insider disclosures (SEBI Prohibition of Insider Trading disclosures, share pledge filings).
   - These sources have not been ingested, mapped, or tested.

---

## 5. Technical Closeout Policy

Per the governance of this project:
- **No next steps, follow-on architectures, or further modeling directions are proposed or recommended in this document.** Strategic resource allocation and future research priorities are strictly business decisions for the repository owner.
- **Phase 6 development is officially closed.**
- **No further model training is permitted within this repository until a new, signed pre-registration document is formally approved for a genuinely new hypothesis or newly sourced dataset.**
