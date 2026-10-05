# Phase 7 — Sealed Historical Holdout Protocol

**Repository:** GaurviDEEP
**Working Branch:** `phase7-research`
**Governing Document:** [`docs/PHASE7_RESEARCH_PREREGISTRATION.md`](PHASE7_RESEARCH_PREREGISTRATION.md)
**Standard Environment:** Python 3.12 (`.venv-phase7`)
**Status:** PROTOCOL PRE-REGISTERED (Vault Uncreated)
**Effective Date:** 2026-10-05

---

## 1. Governance Principles & Strict Isolation

### 1.1 Absolute Phase 6 Vault Quarantine
In strict compliance with **Non-Negotiable Rule 1 and Rule 3**:
- The existing Phase 6 vaults located at `C:\Users\r_chh\gaurvideep_vault\` and `C:\Users\r_chh\OneDrive - optgbrc\Apps\gaurvideep_vault\`, containing `window_a_sealed.7z` and `window_b_sealed.7z`, remain **permanently sealed and immutable**.
- Zero commands may access, decrypt, inspect, copy, move, hash, or query Phase 6 archives.
- The Phase 6 access count remains **ZERO**.

### 1.2 Separation of Phase 7 Holdout
The Phase 7 holdout is a completely new, distinct dataset covering a dedicated temporal out-of-sample window. It does not exist at Milestone 1 and will **never** be placed inside or merged with the Phase 6 vault directory.

---

## 2. Mandatory Holdout Prerequisites (Gate 4)

No Phase 7 holdout dataset may be created, encrypted, unsealed, or evaluated until all of the following conditions are met and verified:
1. **Gate 1 Data Integrity:** Passed and verified by automated audit tests.
2. **Gate 2 Development Walk-Forward Validation:** All predictive and economic thresholds passed on development data.
3. **Gate 3 Robustness & Anti-Overfitting:** Passed across 6 regimes, sector stability, jackknife stress tests, and Deflated Sharpe probability ($\ge 90\%$).
4. **Milestone 10 Candidate Freeze:**
   - Candidate model code commit hash frozen.
   - Candidate model binary SHA-256 hash locked.
   - Pinned hyperparameter dictionary committed.
   - Model Card (`docs/PHASE7_CANDIDATE_MODEL_CARD.md`) completed and signed.
5. **Explicit Owner Authorization:**
   - The repository owner must explicitly grant authorization using the exact phrase:
     ```
     AUTHORIZE PHASE 7 HOLDOUT EVALUATION
     ```

---

## 3. Holdout Partitioning & Temporal Specification

- **Holdout Temporal Span:** The Phase 7 holdout will comprise a contiguous out-of-sample temporal block separated from the development cutoff by at least a **20-trading-day purge gap**.
- **Physical Partitioning:** The holdout data will be stored externally in an AES-256 encrypted archive in a dedicated Phase 7 storage path (e.g. `C:\Users\r_chh\gaurvideep_phase7_vault\holdout_phase7_sealed.7z`).
- **Cryptographic Key Management:** The decryption key will be held exclusively by the human project owner and must never be committed to git, written to disk within the repository, or passed to automated CI scripts.

---

## 4. Single-Run Evaluation Protocol

1. **Pre-Evaluation Logging:** Before unsealing, log the authorized access event in `docs/PHASE7_HOLDOUT_ACCESS_LOG.md` recording:
   - Date and UTC timestamp.
   - Frozen code commit hash.
   - Frozen candidate model artifact SHA-256.
   - Owner authorization phrase confirmation.
2. **Single Execution:** The frozen model candidate is executed exactly once against the unsealed Phase 7 holdout data.
3. **Immutability of Results:**
   - Results are written directly to an append-only holdout evaluation record.
   - **Zero Post-Hoc Tuning:** No hyperparameter adjustments, feature additions, threshold changes, or re-runs are permitted after observing holdout results.
   - If the candidate fails any Gate 4 criterion, the verdict is recorded as **FAIL** or **VALID_NULL_RESULT**.

---

## 5. Gate 4 Holdout Success Thresholds

| Metric | Minimum Required Gate 4 Threshold |
|---|---|
| **Holdout 20-Day Rank IC** | $\ge \mathbf{0.020}$ |
| **Positive Monthly Rank IC %** | $\ge \mathbf{55.0\%}$ of holdout months |
| **Holdout Net Sharpe Ratio** | $\ge \mathbf{0.60}$ (at 25 bps base cost) |
| **Benchmark-Relative Net Return** | Positive ($\alpha_{\text{net}} > 0$) |
| **Maximum Drawdown Limit** | $\le \mathbf{25.0\%}$ |
| **Quintile Return Spread (Q5 - Q1)** | Positive realized spread |
| **Conservative Cost Survivability** | Positive net performance at 50 bps round trip |
| **Capacity & Concentration** | No stock weight $> 5\%$, no sector weight $> 25\%$, no trade $> 5\%$ MDTV |

---

## 6. Scientific Outcome Definitions

- **ADVANCE_TO_LIVE_SHADOW (PASS):** Candidate model clears all Gate 4 predictive, economic, and risk thresholds without exception. Triggers Milestone 12 Live Shadow Portfolio.
- **SCREENING_UTILITY_ONLY:** Candidate demonstrates statistically significant Rank IC ($\ge 0.020$) but fails economic hurdles after transaction costs. Model may be used only as a non-tradable universe filter.
- **VALID_NULL_RESULT (FAIL):** Candidate fails Rank IC or economic criteria. Research track is formally closed. No parameter tweaking is permitted without a new preregistration.
