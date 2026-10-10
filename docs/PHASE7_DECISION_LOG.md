# Phase 7 — Research Decision & Governance Log

**Repository:** GaurviDEEP
**Working Branch:** `phase7-research`
**Governing Standard:** Non-Negotiable Safety and Governance Rules (Rule 17: *"All trials and decisions must remain in an append-only registry."*)
**Status Date:** 2026-10-05

---

## 1. Decision Ledger Overview

This document serves as an immutable, append-only record of all architectural, scientific, and governance decisions authorized by the project owner or research governance officers during Phase 7.

No decision recorded herein may be deleted, retroactively edited, or overwritten. Amendments must be recorded sequentially as new entries.

---

## 2. Immutable Decision Entries

### DEC-20261004-01: Phase 6 Formal Closeout & Vault Blinding Preservation
- **Date:** 2026-10-04
- **Decision Authority:** Project Owner
- **Decision:**
  1. Accept Phase 6 Gate 1–4 synthesis as a complete, valid, and scientifically honest null result for 5-day single-stock directional alpha.
  2. Confirm that Phase 6 holdout vaults (`window_a_sealed.7z`, `window_b_sealed.7z` in `gaurvideep_vault`) remain 100% sealed with zero access events recorded.
  3. Seal Phase 6 with git tag `phase6-closed-2026-10-04` at commit `c978968ec822aa20453920c8708673fcaa736695`.
  4. Design Phase 7 as an entirely independent research programme focused on 20-day cross-sectional stock ranking.

---

### DEC-20261005-02: Authorization & Scope of Milestone 0 (Repository Audit)
- **Date:** 2026-10-05
- **Decision Authority:** Project Owner & Lead Quantitative Research Engineer
- **Decision:**
  1. Mandate strict read-only audit before any Phase 7 code or preregistration is written.
  2. Forbid modifying any Phase 6 files or querying external vault directories.
  3. Produce three foundation documents:
     - `docs/PHASE7_REPOSITORY_AUDIT.md`
     - `docs/PHASE7_BLOCKERS.md`
     - `docs/PHASE7_IMPLEMENTATION_MAP.md`
  4. Identified critical blockers: `BLK-01` (Missing Point-in-Time Nifty 500 membership) and `BLK-02` (Missing OHLCV turnover data).

---

### DEC-20261005-03: Authorization of Milestone 1 (Preregistration & Governance Configuration)
- **Date:** 2026-10-05
- **Decision Authority:** Project Owner (`APPROVE MILESTONE 1`)
- **Key Binding Directives:**
  1. **Runtime Standardization:** Standardize Phase 7 research execution on Python 3.12 under dedicated virtual environment `.venv-phase7`. Document requirement in `requirements-phase7.txt` without modifying system Python during Milestone 1.
  2. **Phase 6 Immutability:** External Phase 6 vaults remain strictly quarantined; zero queries or tool calls targeting `gaurvideep_vault` or sealed archives.
  3. **Initial Feature Scope Permitted:**
     - Medium-term momentum.
     - Sector-relative momentum.
     - Residual momentum when benchmark is available.
     - Existing SUE data strictly as a standalone hypothesis under 20-day / 60-day ranking.
     - Quality and valuation features only when verified point-in-time publication records are provided.
  4. **Feature Scope Deferred (Requires Future Signed Amendments):**
     - Historical analyst consensus estimates and revisions.
     - Corporate announcement NLP.
     - Management guidance extraction.
     - Promoter holding and pledge changes.
     - Unverified balance sheet / cash flow line items lacking exchange publication timestamps.
  5. **Data Blocker Governance:** `BLK-01` and `BLK-02` remain critical. Milestone 1 may proceed with governance and schemas, but no quantitative baseline evaluation or model training may start until data blockers are resolved.
   6. **Universe Boundary:** The static legacy universe is prohibited as a Phase 7 universe provider and protected by automated boundary tests.
   7. **Holdout Status:** No Phase 7 holdout exists; none is created during Milestone 1.

---

### DEC-20261005-04: Authorization & Execution of Milestone 2 (Data Contracts and Point-in-Time Universe)
- **Date:** 2026-10-05
- **Decision Authority:** Project Owner (`APPROVE MILESTONE 2`)
- **Context & Motivation:** Establish canonical data contracts, strict point-in-time universe construction interfaces, fail-closed data loaders, corporate action adjustment logic, and exclusion codes prior to any modeling or feature engineering.
- **Exact Decision:**
  1. **Canonical Frozen Contracts:** Implement immutable dataclasses (`DailyPriceRecord`, `PITMembershipRecord`, `PITSectorClassificationRecord`, `CorporateActionRecord`, `EligibilitySuspensionRecord`, `PITFinancialStatementRecord`, `EligibleSecurityRecord`, `PITUniverseSnapshot`, `DatasetAuditSummary`) with Decimal financial fields, timezone-aware UTC datetime timestamps, and deterministic SHA-256 row hashes.
  2. **Corporate Action Adjustment Engine:** Implement split, bonus, and cash dividend adjustments. Reject double adjustment on `TOTAL_RETURN_ADJUSTED` data; fail closed (`MANUAL_REVIEW`) on complex restructuring events. Require positive reference price for cash dividends and reject dividends equal to or exceeding price.
  3. **Point-in-Time Universe Builder:** Implement dynamic universe builder with minimum 252-day history, 60-day MDTV $\ge$ INR 10 crore, and price $\ge$ INR 20 filters. Preserve explicit multi-reason exclusion codes. If real constituent data or price turnover data are missing, builder must output explicit `is_real_data_blocked=True` (`REAL_DATA_BLOCKED`).
  4. **Fail-Closed Loaders & Audit Reports:** Implement streaming CSV and JSONL loaders tracking 1-based row numbers and rejection reasons without silent coercion to zero. Dataset audit utility must capture structural statistics with strict prohibition against reporting return or alpha metrics.
  5. **Data Blocker Governance:** `BLK-01` and `BLK-02` remain CRITICAL. Readiness status is explicitly recorded as `CONTRACT_READY_REAL_DATA_BLOCKED`. Gate 1 cannot pass on real data until genuine point-in-time constituent and turnover datasets are provided.
  6. **Vault & Phase 6 Immutability:** External Phase 6 vaults remain sealed and immutable; zero queries, tools, or operations targeting `gaurvideep_vault` or sealed archives.
  7. **Research Scope Bound:** No model training, feature generation, target calculation, backtesting, or live deployment may take place in Milestone 2.
- **Impacted Modules:**
  - `phase7/data/contracts.py`
  - `phase7/data/corporate_actions.py`
  - `phase7/data/universe.py`
  - `phase7/data/loaders.py`
  - `phase7/data/audit.py`
  - `tests/phase7/test_point_in_time_integrity.py`
  - `tests/phase7/test_no_future_features.py`
  - `tests/phase7/test_universe_survivorship.py`
  - `tests/phase7/test_corporate_action_adjustments.py`
  - `tests/phase7/test_data_loaders.py`
- **Verification Criteria:** Full unit test suite passes (45/45 Phase 7 tests, 4/4 Phase 6 safeguard tests); static boundary analysis confirms zero forbidden imports or vault references; data audit reports contain zero investment performance metrics.

---

### DEC-20261005-05: Milestone 2 Conformance Alignment & Corrective Realignment
- **Date:** 2026-10-05
- **Decision Authority:** Project Owner & Lead Quantitative Research Engineer
- **Context & Motivation:** Comprehensive conformance audit of Milestone 2 deliverables against preregistration contracts, fail-closed safeguards, and explicit owner review requirements.
- **Exact Decision:**
  1. **ExclusionReason Canonicalization:** Standardize full set of canonical exclusion reasons (`NOT_IN_PIT_UNIVERSE`, `MISSING_MEMBERSHIP_HISTORY`, `MISSING_ISIN`, `BELOW_MIN_PRICE`, `INSUFFICIENT_HISTORY`, `MISSING_PRICE_HISTORY`, `MISSING_LIQUIDITY_HISTORY`, `BELOW_MIN_LIQUIDITY`, `MISSING_SECTOR_CLASSIFICATION`, `CONFLICTING_SECTOR_CLASSIFICATION`, `SUSPENDED`, `PROLONGED_NON_TRADING`, `RESTRICTED_SECURITY`, `INVALID_CORPORATE_ACTION_HISTORY`, `UNKNOWN_POINT_IN_TIME_STATUS`, `DUPLICATE_SECURITY_RECORD`, `FUTURE_DATA_DETECTED`) with backward compatibility aliases.
  2. **Corporate Action Normalization & Review:** Implement canonical source aliases (`RIGHTS_ISSUE`, `AMALGAMATION`, `SPINOFF`, `FACE_VALUE_SPLIT`). Explicitly route complex and structural events (`RIGHTS`, `MERGER`, `DEMERGER`, `SYMBOL_CHANGE`, `DELISTING`) to `MANUAL_REVIEW` pending approved research policies.
  3. **Turnover Derivation Safeguards:** Prohibit deriving traded value from Close alone (`CLOSE_X_VOLUME`), prohibit derivation method on `EXCHANGE_REPORTED` status, and require recorded derivation method for derived turnover.
  4. **Granular Universe Build Status:** Expand `UniverseBuildStatus` into distinct granular statuses (`SUCCESS`, `BLOCKED_MISSING_MEMBERSHIP`, `BLOCKED_MISSING_PRICE_LIQUIDITY`, `BLOCKED_MISSING_SECTOR_HISTORY`, `VALID_EMPTY_UNIVERSE`, `DATA_VALIDATION_FAILURE`) with `BLOCKED` compatibility alias and `is_real_data_blocked` property.
  5. **Membership Event Conversion:** Implement `PITMembershipEventRecord` and streaming parser `parse_membership_event_row` with strict event-to-interval conversion (`convert_membership_events_to_intervals`) enforcing fail-closed error handling on duplicate additions, removals without additions, conflicting timestamps, and future events.
  6. **Mandatory Governance Phrasing:** Formally record exact mandatory phrasing for the legacy universe boundary (*"The static legacy universe is prohibited as a Phase 7 universe provider and protected by automated boundary tests."*) and sector classification (*"Static current sector mappings may be used only in explicitly labelled synthetic tests or non-historical display contexts. Historical sector-relative research fails closed without valid point-in-time sector classification."*).
  7. **Research Readiness:** Overall research package readiness status remains strictly `CONTRACT_READY_REAL_DATA_BLOCKED`.
- **Impacted Modules:**
  - `phase7/data/__init__.py`
  - `phase7/data/contracts.py`
  - `phase7/data/loaders.py`
  - `phase7/data/universe.py`
  - `phase7/data/corporate_actions.py`
  - `phase7/data/audit.py`
  - `tests/phase7/test_point_in_time_integrity.py`
  - `tests/phase7/test_no_future_features.py`
  - `tests/phase7/test_universe_survivorship.py`
  - `tests/phase7/test_corporate_action_adjustments.py`
  - `tests/phase7/test_data_loaders.py`
  - `tests/phase7/test_phase6_boundary.py`
  - `docs/PHASE7_DATA_DICTIONARY.md`
  - `docs/PHASE7_BLOCKERS.md`
  - `docs/PHASE7_DECISION_LOG.md`
  - `docs/PHASE7_IMPLEMENTATION_MAP.md`
- **Verification Criteria:**
  - 69/69 automated tests pass in CI without errors.
  - Zero vault access events; zero forbidden imports.
  - Data contracts reject illegal states, non-UTC timestamps, unrecorded derived turnover, and Close-alone derivation.

---

### DEC-20261005-06: Final Milestone 2 Data Contract Conformance & Security/Build Status Separation
- **Date:** 2026-10-05
- **Decision Authority:** Project Owner & Lead Quantitative Research Engineer
- **Context & Motivation:** Address final conformance findings on Milestone 2 data contracts, ensuring strict separation between security-level and build-level failure semantics, rigorous future-data accounting, explicit turnover status differentiation, ISIN structural-format precision, and blocker scope boundaries.
- **Exact Decision:**
  1. **Canonical Exclusion Reason `DATA_VALIDATION_FAILURE`:** Formally incorporate `ExclusionReason.DATA_VALIDATION_FAILURE = "DATA_VALIDATION_FAILURE"` into the canonical `ExclusionReason` enumeration for per-security structural input validation failures (e.g. malformed records or invalid price/turnover state).
  2. **Security vs. Build Status Disambiguation:** Strictly preserve the architectural distinction between security-level exclusion (`ExclusionReason.DATA_VALIDATION_FAILURE`) and dataset/system-level failure (`UniverseBuildStatus.DATA_VALIDATION_FAILURE`). Neither status is aliased to `UNKNOWN_POINT_IN_TIME_STATUS` or treated as interchangeable.
  3. **Future Data Tracking & Audit Auditing:** Mandate that future data records relative to prediction timestamp are never silently dropped; they must never qualify an earlier prediction, must increment the audit counter (`future_records_count`), and must be recorded under `FUTURE_DATA_DETECTED` and in audit evidence logs. Both universe builder and dataset auditor record future observation metrics.
  4. **Turnover Status Differentiation:** Enforce explicit enumeration distinctions across `TradedValueStatus.EXCHANGE_REPORTED`, `DERIVED_FROM_PRICE_VOLUME`, `MISSING`, and `INVALID`. Require that zero turnover with `MISSING` status yields `MISSING_LIQUIDITY_HISTORY`, whereas zero turnover with `INVALID` status additionally records `DATA_VALIDATION_FAILURE`. Loader audits record status distributions separately.
  5. **ISIN Structural Validation Scope:** Explicitly define and document ISIN validation as 12-character structural-format regex validation (`^[A-Z]{2}[A-Z0-9]{9}[0-9]$`). Disclaim full ISO 6166 modulus-10 check-digit computation to prevent false claims of international registration verification.
  6. **BLK-03 Blocker Scope Clarification:** Restore BLK-03 with status `OPEN / DEFERRED FROM INITIAL MODEL SCOPE`. Explicitly document that existing quarterly SUE features do not resolve missing point-in-time comprehensive balance-sheet, cash-flow, and debt statements, and that comprehensive accounting feature families remain deferred from the initial model development cycle.
  7. **Research Readiness Status:** Maintain research package readiness status strictly at `CONTRACT_READY_REAL_DATA_BLOCKED`.
- **Impacted Modules:**
  - `phase7/data/contracts.py`
  - `phase7/data/universe.py`
  - `phase7/data/audit.py`
  - `tests/phase7/test_point_in_time_integrity.py`
  - `tests/phase7/test_universe_survivorship.py`
  - `tests/phase7/test_data_loaders.py`
  - `docs/PHASE7_DATA_DICTIONARY.md`
  - `docs/PHASE7_BLOCKERS.md`
  - `docs/PHASE7_DECISION_LOG.md`
  - `docs/PHASE7_IMPLEMENTATION_MAP.md`
- **Verification Criteria:**
  - Full automated test suite passes (70/70 Phase 7 unit tests, 4/4 Phase 6 safeguard tests; 74/74 total).
  - Explicit tests prove `ExclusionReason.DATA_VALIDATION_FAILURE` vs `UniverseBuildStatus.DATA_VALIDATION_FAILURE` independence.
  - Audit reports verify future record tracking and separate turnover status reporting.
  - Zero Phase 6 vault access events and zero forbidden legacy imports.

---

### DEC-20261006-01: Phase 7 Isolated Python 3.12 Research Environment Creation & Stability Verification
- **Date:** 2026-10-06
- **Decision Authority:** Project Owner & Lead Quantitative Research Engineer
- **Context & Motivation:** Create, validate, document, and freeze an isolated Python 3.12 research virtual environment (`.venv-phase7`) to eliminate runtime C-level access violations observed under development Python 3.14.4 (BLK-06) and prepare an immutable execution baseline for Phase 7 research.
- **Exact Decision:**
  1. **Runtime Standardization:** Formally standardize the Phase 7 research environment on Python 3.12.10 (64-bit AMD64 WindowsPE) installed at `.venv-phase7`.
  2. **Strict Dependency Baseline:** All dependencies installed exclusively from `requirements-phase7.txt` without modification to pins or manual package additions. Verified via `pip check` reporting zero broken requirements.
  3. **Verification Results:** Full Phase 7 governance and Phase 6 boundary test suites passed without failure or error (74/74 tests, 100% pass rate in 8.49s). Narrow pandas datetime checks (`pd.date_range` for 5,000 daily and 1,000 business days) completed normally without access violations.
  4. **BLK-06 Status Determination:** In accordance with the preregistered BLK-06 decision rule, set BLK-06 status to `ENVIRONMENT STABLE; LEGACY TEST FAILURES REQUIRE REVIEW`. The fatal C-level datetime access violation is eliminated, while legacy suites (`test_features.py`, `test_nifty.py`) fail at collection due to quarantined legacy dependencies (`ta`, `fastapi`).
  5. **Mandatory Execution Path:** All future Phase 7 research commands, tests, scripts, and notebooks must explicitly invoke `.venv-phase7\Scripts\python.exe`.
  6. **Zero Research Execution:** Explicitly confirm that zero model training, target generation, feature matrix computation, external market data procurement, Phase 6 vault querying, or Milestone 3 activity occurred during this checkpoint.
- **Impacted Modules:**
  - `.gitignore`
  - `.venv-phase7`
  - `docs/PHASE7_ENVIRONMENT_VERIFICATION.md`
  - `docs/PHASE7_BLOCKERS.md`
  - `docs/PHASE7_DECISION_LOG.md`
  - `docs/PHASE7_IMPLEMENTATION_MAP.md`
- **Verification Criteria:**
  - `.venv-phase7\Scripts\python.exe -m pytest tests/phase7/ test_phase6_safeguards.py -v` passes 74/74 tests.
  - `pip check` reports no broken requirements.
  - `git check-ignore -v .venv-phase7` confirms active exclusion.
  - Zero vault access events; zero unauthorized file modifications.

---

### DEC-20261006-02: Milestone 3 Target Engine Delivery & Terminal Policy Standard
- **Date:** 2026-10-06
- **Decision Authority:** Project Owner & Lead Quantitative Research Engineer
- **Context & Motivation:** Deliver canonical target contracts and calculation logic for Phase 7 (20-day sector-relative and 60-day beta-adjusted residual targets) using synthetic fixtures, establishing rigorous point-in-time temporal boundaries, terminal event handling, and audit quality invariants prior to feature engineering or model training.
- **Exact Decision:**
  1. **Canonical Immutable Contracts:** Author frozen dataclasses with deterministic SHA-256 row hashing (`TargetSpecificationRecord`, `PredictionEventRecord`, `ForwardPriceObservationRecord`, `SectorBenchmarkObservationRecord`, `BetaInputRecord`, `TargetResultRecord`, `TargetAuditRecord`) and strict enumerations (`TargetStatus`, `TargetReasonCode`).
  2. **T+1 Alignment Engine:** Enforce strict execution lag ($\ge 1$ trading day); observation 1 is $t+1$ and observation $H$ is $t+H$. Prohibit same-day entry at prediction instant $t$ (`SAME_DAY_ENTRY_PROHIBITED`). Count forward trading sessions sequentially, skipping weekends and exchange holidays. Reject duplicate observation dates (`DUPLICATE_DATE_OBSERVATION`) and enforce symbol/ISIN identity matching (`DATA_VALIDATION_FAILURE`).
  3. **20-Day Sector-Relative Target Engine:** Implement $y_{i, t}^{\text{20d\_sector\_rel}} = R_{\text{stock}, t+1 \to t+20} - R_{\text{sector}, t+1 \to t+20}$. Mandate identical trading dates for stock and sector benchmark. Resolve sector classification strictly point-in-time as of $t$ without static fallback; missing classifications return status `BLOCKED` (`MISSING_PIT_SECTOR`), overlapping conflicts return `CONFLICTING_PIT_SECTOR`, and future classifications return `FUTURE_SECTOR_DETECTED`.
  4. **60-Day Beta-Adjusted Residual Target Engine:** Implement $y_{i, t}^{\text{60d\_residual}} = R_{\text{stock}, t+1 \to t+60} - (\beta_{i, \le t} \cdot R_{\text{market}, t+1 \to t+60})$. Preserve stock return, market return, and beta separately in `TargetResultRecord`. Enforce point-in-time beta provenance ($\text{estimation\_end\_timestamp} \le t$), rejecting future beta estimates (`FUTURE_BETA_DETECTED`) and benchmark identifier mismatches (`INVALID_BENCHMARK`).
  5. **Terminal Observation Policies:** Mandate fail-closed invalidation for any terminal event occurring during the forward horizon $[t+1, t+H]$: regulatory suspensions return `SUSPENDED_DURING_HORIZON`, delisting returns `DELISTED_DURING_HORIZON`, complex corporate actions (mergers, demergers, rights) return `CORPORATE_ACTION_REVIEW_REQUIRED`, and incompatible price states return `INVALID_ADJUSTMENT_STATE`. Target values for invalidated records must be strictly `None` (preventing silent 0.0 fabrication or stale price carry-forward).
  6. **Zero Performance Metrics Invariant:** TargetAuditRecord and audit routines must never compute or expose investment performance/alpha metrics (Sharpe, Sortino, Calmar, Alpha, Rank IC, Drawdown). Auditing is strictly confined to data quality, failure distributions, future record counts, and label overlap.
  7. **Research Execution Guardrail:** Maintain target engine readiness status strictly at `TARGET_ENGINE_READY_REAL_DATA_BLOCKED`. Real historical target generation on repository market data is prohibited pending formal resolution of BLK-01, BLK-02, and BLK-04. Milestone 4 (Feature Research) must not begin without explicit owner authorization.
- **Impacted Modules:**
  - `phase7/targets/__init__.py`
  - `phase7/targets/contracts.py`
  - `phase7/targets/returns.py`
  - `phase7/targets/alignment.py`
  - `phase7/targets/sector_relative.py`
  - `phase7/targets/residual.py`
  - `phase7/targets/audit.py`
  - `tests/phase7/test_target_contracts.py`
  - `tests/phase7/test_target_isolation.py`
  - `tests/phase7/test_target_alignment.py`
  - `tests/phase7/test_sector_relative_targets.py`
  - `tests/phase7/test_residual_targets.py`
  - `tests/phase7/test_target_terminal_handling.py`
  - `docs/PHASE7_DATA_DICTIONARY.md`
  - `docs/PHASE7_BLOCKERS.md`
  - `docs/PHASE7_DECISION_LOG.md`
  - `docs/PHASE7_IMPLEMENTATION_MAP.md`
  - `docs/PHASE7_EXECUTION_PLAN.md`
- **Verification Criteria:**
  - 112/112 tests pass in `.venv-phase7` (108 Phase 7 tests, 4 Phase 6 safeguards).
  - Target isolation test confirms zero imports of feature generation, models, backtests, or Phase 6 vaults.
  - Zero repository data modified; zero real targets generated; zero external network requests.

---

### DEC-20261009-01: Milestone 3 Target Engine Governance, Truncation, Overlap & Readiness Gate Finalization
- **Date:** 2026-10-09
- **Decision Authority:** Project Owner & Lead Quantitative Research Engineer
- **Context & Motivation:** Complete the full conformance audit and corrective controls for Milestone 3, establishing formal cutoff truncation, forward window overlap tracking, real-data readiness gating, provenance hashing, and explicit endpoint semantics before initiating Milestone 4 walk-forward framework.
- **Exact Decision:**
  1. **Readiness Status Standard:** Formally establish `TARGET_ENGINE_READY_REAL_DATA_BLOCKED` as the canonical readiness status for Milestone 3. Preserve `CONTRACT_READY_REAL_DATA_BLOCKED` for historical Milestone 2 data contract records.
  2. **Frozen Endpoint Semantics:** Formally document and lock the forward endpoint convention:
     - $t+1$ is the first post-prediction observation session.
     - $t+20$ is the twentieth post-prediction observation session.
     - $t+60$ is the sixtieth post-prediction observation session.
     - The window $[t+1, t+20]$ contains 20 discrete observations and 19 close-to-close intervals.
     - The window $[t+1, t+60]$ contains 60 discrete observations and 59 close-to-close intervals.
     - `horizon_trading_days` identifies the numbered forward endpoint under the frozen Phase 7 convention. Same-day observation $t$ is strictly excluded.
  3. **Cutoff Truncation Engine (`phase7/targets/truncation.py`):** Author immutable `CutoffTruncationResult` enforcing discrete session counting without forward-filling or calendar extrapolation. Block outcomes extending past the authorized cutoff (`OUTCOME_EXCEEDS_AUTHORIZED_CUTOFF`) and fail closed on insufficient forward observations (`INSUFFICIENT_FORWARD_OBSERVATIONS`). Preserve blocked events in audit metrics.
  4. **Overlap Detection Engine (`phase7/targets/overlap.py`):** Author immutable `TargetOverlapMetadata` and `detect_target_overlaps`. Retain all target records without premature purging or embargoing. Enforce security isolation (never group distinct securities). Under the closed holding window convention $[entry, exit]$, boundary-touching windows where $entry_B = exit_A$ are classified as overlapping. Connected components of chained overlaps are grouped into deterministic, order-independent group identifiers. Zero statistical or model metrics are computed.
  5. **Real-Data Readiness Gate (`phase7/targets/readiness.py`):** Author immutable `TargetReadinessResult` and `evaluate_target_readiness`. Simultaneously preserve individual and compound blocker statuses (`BLOCKED_BLK_01_MEMBERSHIP`, `BLOCKED_BLK_02_OHLCV_LIQUIDITY`, `BLOCKED_BLK_04_SECTOR_HISTORY`). Fail closed if dataset version is missing (`DATA_VALIDATION_FAILURE`). Strictly prohibit reporting an empty generated real-data output as success.
  6. **Comprehensive Target Hashing:** Incorporate `universe_hash` into `TargetResultRecord` provenance. Assert hash sensitivity to values, statuses, reason codes, dataset versions, universe hashes, and dates. Verify target hash self-exclusion and canonical dictionary ordering.
  7. **Complete Quality Audit Record:** Expand `TargetAuditRecord` and `audit_target_results` to track `corporate_action_review_count`, `missing_benchmark_count`, and `overlap_count` alongside conservation of inputs across accepted, rejected, and blocked totals. Re-verify strict absence of investment performance or alpha fields.
  8. **Comprehensive Target Isolation:** Expand static analysis and behavioral tests asserting zero imports of `phase7.features`, `scripts.phase6`, `service`, `models`, `portfolio`, and `backtest`, zero mutation of inputs, zero writes to `data/`, zero vault references, and strict separation of feature cutoff timestamps from target outcomes.
- **Impacted Modules:**
  - `phase7/targets/__init__.py`
  - `phase7/targets/contracts.py`
  - `phase7/targets/alignment.py`
  - `phase7/targets/audit.py`
  - `phase7/targets/truncation.py`
  - `phase7/targets/overlap.py`
  - `phase7/targets/readiness.py`
  - `phase7/targets/sector_relative.py`
  - `phase7/targets/residual.py`
  - `tests/phase7/test_target_cutoff_truncation.py`
  - `tests/phase7/test_target_overlap.py`
  - `tests/phase7/test_target_readiness.py`
  - `tests/phase7/test_target_audit.py`
  - `tests/phase7/test_target_hashing.py`
  - `tests/phase7/test_target_alignment.py`
  - `tests/phase7/test_target_isolation.py`
  - `tests/phase7/test_target_contracts.py`
  - `tests/phase7/test_target_terminal_handling.py`
  - `docs/PHASE7_DATA_DICTIONARY.md`
  - `docs/PHASE7_BLOCKERS.md`
  - `docs/PHASE7_DECISION_LOG.md`
  - `docs/PHASE7_IMPLEMENTATION_MAP.md`
  - `docs/PHASE7_EXECUTION_PLAN.md`
- **Verification Criteria:**
  - 156/156 automated tests passing in `.venv-phase7` (152 Phase 7 tests, 4 Phase 6 safeguards).
  - Target readiness status verified as `TARGET_ENGINE_READY_REAL_DATA_BLOCKED`.
  - Zero Phase 6 file changes; zero real target generation; zero model training; zero dependency changes.

---

### DEC-20261009-02: Milestone 4 Expanding Walk-Forward Validation, Purge/Embargo Invariants & Fold-Local Preprocessing
- **Date:** 2026-10-09
- **Decision Authority:** Project Owner & Lead Quantitative Research Engineer
- **Context & Motivation:** Establish the complete validation framework for Milestone 4 following explicit owner approval (`APPROVE MILESTONE 4`), ensuring minimum 10 expanding windows, strict trading session purge gap, post-test embargo, mathematical zero label leakage, fold-local preprocessing parameter isolation, and validation governance auditing.
- **Exact Decision:**
  1. **Expanding Walk-Forward Geometry (`phase7/validation/walk_forward.py`):** Enforce minimum 10 sequential expanding windows ($K \ge 10$) where initial training start date is invariant across all folds ($Train_0 \subset Train_1 \subset \dots \subset Train_{K-1}$). Test windows are sequential, out-of-sample ($Train_k \cap Test_k = \emptyset$), and pairwise disjoint ($Test_i \cap Test_j = \emptyset$).
  2. **Purge Gap Enforcement (`phase7/validation/purge_embargo.py`):** Enforce discrete trading session purge gaps: $\ge 20$ trading sessions for primary 20d target and $\ge 60$ trading sessions for secondary 60d target. Calendar calculations advance strictly in trading sessions, skipping weekends and holidays.
  3. **Embargo Interval Enforcement:** Enforce post-test embargo: $\ge 5$ trading sessions for primary 20d target and $\ge 10$ trading sessions for secondary 60d target to guard against autoregressive feature leakage and serial correlation.
  4. **Zero Label Leakage Verification Theorem:** Mathematically verify for every training observation $t_{\text{train}}$ that its forward return outcome window $[t_{\text{train}}+1, t_{\text{train}}+H]$ never reaches or intersects any test date in the fold. Violations fail closed with `ValidationLeakageError`.
  5. **Fold-Local Preprocessing Mandate (`phase7/validation/preprocessing.py`):** All scaling (StandardScaler, RobustScaler), winsorization (1st/99th percentiles), and imputation statistics must be fitted strictly inside training folds. Parameters are frozen upon fitting; test data is transformed without modifying fitted parameters. Mathematical proof demonstrates that global preprocessing leaks test distribution into training data, while fold-local preprocessing isolates training representations.
  6. **Cross-Sectional Ranking:** Percentile ranking operations partition strictly by trading session date ($t$) without multi-session pooling.
  7. **Canonical Hashing & Provenance:** Fitted transformer parameters and fold boundaries compute deterministic SHA-256 hashes using Decimal-normalized serialization (`PreprocessingParameterRecord`, `WalkForwardFold`, `PurgeEmbargoInterval`, `ValidationAuditRecord`).
  8. **Strict Module Isolation:** `phase7/validation/` imports zero modules from `features`, `models`, `portfolio`, `service`, or `scripts.phase6`, references zero Phase 6 vaults, and performs zero write operations to `data/`.
- **Impacted Modules:**
  - `phase7/validation/__init__.py`
  - `phase7/validation/contracts.py`
  - `phase7/validation/purge_embargo.py`
  - `phase7/validation/walk_forward.py`
  - `phase7/validation/preprocessing.py`
  - `tests/phase7/test_purge_embargo.py`
  - `tests/phase7/test_fold_local_preprocessing.py`
  - `tests/phase7/test_walk_forward.py`
  - `tests/phase7/test_validation_isolation.py`
  - `docs/PHASE7_DATA_DICTIONARY.md`
  - `docs/PHASE7_DECISION_LOG.md`
  - `docs/PHASE7_IMPLEMENTATION_MAP.md`
  - `docs/PHASE7_EXECUTION_PLAN.md`
- **Verification Criteria:**
  - 184/184 automated tests passing in `.venv-phase7` (180 Phase 7 tests, 4 Phase 6 safeguards).
  - Milestone 4 readiness status verified as `VALIDATION_FRAMEWORK_READY_REAL_DATA_BLOCKED`.
  - Historical Milestone 2 status preserved as `CONTRACT_READY_REAL_DATA_BLOCKED`.
  - Historical Milestone 3 status preserved as `TARGET_ENGINE_READY_REAL_DATA_BLOCKED`.
  - Validation boundary invariants verified: primary purge $\ge 20$d, primary embargo $\ge 5$d, secondary purge $\ge 60$d, secondary embargo $\ge 10$d, discrete ordered trading sessions, zero label leakage, fold-local preprocessing parameter isolation, deterministic fold hashing, and session-date cross-sectional ranking.
  - Zero real fold calendar generated while BLK-01, BLK-02, and BLK-04 remain open.
  - Zero Phase 6 file changes; zero real target generation; zero model training; zero dependency changes.

---

### DEC-20261009-03: Milestone 4.5 Gate 1 Data Readiness Specification and Procurement Governance
- **Date:** 2026-10-09
- **Decision Authority:** Project Owner & Lead Quantitative Research Engineer (`AUTHORIZE MILESTONE 4.5: GATE 1 DATA READINESS SPECIFICATION`)
- **Context & Motivation:** Prior to commencing Milestone 5 (Baselines & Modeling) or ingesting real market data, establish rigorous technical, legal, and operational specifications for resolving BLK-01 (PIT Nifty 500 Membership), BLK-02 (Daily OHLCV & Traded Value), and BLK-04 (PIT Sector Classification). Define explicit vendor evaluation standards, technical due diligence checklists, licensing verification criteria, and Gate 1 data acceptance protocols without downloading unverified data, contracting vendors, or training models.
- **Exact Decision:**
  1. **Historical Research Window Definition:** Specify active evaluation window as 2015-01-01 through 2025-09-16, with mandatory warm-up commencing on or before 2014-01-01 to support 252-session history filters, 12-minus-1 momentum, rolling beta, and 200-SMA calculations.
  2. **Canonical Data Specification (`docs/PHASE7_DATA_ACQUISITION_SPECIFICATION.md`):** Formally define field schemas, primary keys, and event coverage for 5 core tables:
     - Table A: Historical PIT Nifty 500 Index Membership (Additions, Deletions, Re-additions, Symbol/ISIN changes, Mergers, Delistings; backward projection of current constituents strictly prohibited).
     - Table B: Historical Daily Market Data (OHLCV, exchange-reported turnover in INR, trades, deliverable quantity, suspension status; derived turnover must retain explicit `DERIVED_FROM_PRICE_VOLUME` provenance).
     - Table C: Corporate Actions (Splits, bonuses, dividends, rights, mergers, spin-offs; complex restructurings subject to manual review).
     - Table D: Historical PIT Sector & Industry Classification (Effective-dated intervals; static current fallback strictly prohibited; BLK-04 remains open if PIT sector history is unavailable).
     - Table E: Security Identifier Master (Permanent internal security ID mapping NSE symbols, ISINs, and corporate action links across time).
  3. **Vendor Evaluation Matrix (`docs/PHASE7_VENDOR_EVALUATION_MATRIX.md`):** Evaluate 8 candidate sources (NSE Indices, NSE Data & Analytics, Bloomberg, FactSet, LSEG/Refinitiv, S&P Capital IQ, CMIE Prowess, Approved Internal Warehouse) across 30 dimensions using exclusively `VERIFIED`, `UNVERIFIED`, `NOT AVAILABLE`, and `REQUIRES VENDOR CONFIRMATION`. Unverified sources prohibited from claiming verified status without documentary proof.
  4. **Data Licensing Checklist (`docs/PHASE7_DATA_LICENSING_CHECKLIST.md`):** Mandate written confirmation of quantitative research rights, ML/AI model training rights, derived analytics IP ownership, application display rights, post-termination retention, cloud hosting, and regulatory reporting. Disclaimers rejected as substitutes for licensing.
  5. **Gate 1 Acceptance Protocol (`docs/PHASE7_GATE1_ACCEPTANCE_PROTOCOL.md`):** Define quantitative acceptance thresholds ($\ge 99.5\%$ membership & session coverage, $100\%$ ISIN coverage for eligible records, zero duplicate natural keys, zero contradictory intervals, zero future timestamps, zero corporate action conflicts, $< 0.5\%$ missing sector classifications). Define required manifests (checksums, version, provenance, licensing, rejected records) and 5 distinct outcomes: `GATE1_PASS`, `GATE1_CONDITIONAL_PASS`, `GATE1_REMEDIATE`, `GATE1_FAIL`, `DATASET_REJECTED`.
  6. **Technical Due Diligence Checklist (`docs/PHASE7_DATA_SOURCE_DUE_DILIGENCE_CHECKLIST.md`):** Standardize engineering requirements across sample files, schemas, keys, file naming, compression (Parquet/zstd/gzip), encoding (strict UTF-8 without BOM), ISO 8601 dates/timestamps, and append-only restatement policies.
  7. **Strict Non-Commencement of Milestone 5:** Milestone 5 remains strictly BLOCKED. BLK-01, BLK-02, and BLK-04 remain OPEN. Zero market data downloaded or scraped; zero vendor accounts created; zero models trained.
- **Impacted Modules:**
  - `docs/PHASE7_DATA_ACQUISITION_SPECIFICATION.md`
  - `docs/PHASE7_VENDOR_EVALUATION_MATRIX.md`
  - `docs/PHASE7_GATE1_ACCEPTANCE_PROTOCOL.md`
  - `docs/PHASE7_DATA_SOURCE_DUE_DILIGENCE_CHECKLIST.md`
  - `docs/PHASE7_DATA_LICENSING_CHECKLIST.md`
  - `docs/PHASE7_BLOCKERS.md`
  - `docs/PHASE7_DECISION_LOG.md`
  - `docs/PHASE7_EXECUTION_PLAN.md`
  - `docs/PHASE7_IMPLEMENTATION_MAP.md`
- **Verification Criteria:**
  - Full test baseline preserved: 184/184 automated tests passing in `.venv-phase7`.
  - Zero code modifications to `phase7/` or `tests/`.
  - Zero changes to `config/phase7.yaml` or `requirements-phase7.txt`.
  - Clean working-tree documentation commit.

---

### DEC-20261010-01: Milestone 4.7 Existing Connector NIFTY 500 Capability Audit & Pilot Failure
- **Date:** 2026-10-10
- **Decision Authority:** Project Owner & Lead Quantitative Research Engineer (AUTHORIZE MILESTONE 4.7: EXISTING CONNECTOR NIFTY 500 DATA ACQUISITION)
- **Context & Motivation:** Prior to pursuing external commercial vendor procurement, conduct an empirical capability audit and tightly controlled 5-security pilot of GaurviDEEP's existing data connectors (`features/data_provider.py`, `scripts/phase6/harvest_corporate_actions.py`, etc.) to determine whether they can safely retrieve the NIFTY 500 dataset from NSE-compatible sources in compliance with Phase 7 Gate 1 standards.
- **Exact Decision:**
  1. **Audit Phase A (Connector Discovery):** Confirmed that GaurviDEEP possesses **zero** internal application functions or classes for retrieving NIFTY 500 constituents. The application contains only a static 138-stock list (`features/universe.py`), which is strictly forbidden from being substituted for historical or current NIFTY 500 membership.
  2. **Audit Phase B (Connector Safety Review):** Existing connectors violate multiple mandatory safety rules: excessive retries (3 vs max 2), insufficient delay (1.0s vs min 2.0s), zero exponential backoff, silent failover to unadjusted third-party sources on errors instead of failing closed on HTTP 401/403/429/CAPTCHA, zero SHA-256 checksum generation, and lack of schema validation.
  3. **Runtime Incompatibility:** Existing connectors require `requests` and `nse`, which are not installed in `.venv-phase7` (Python 3.12.10). Attempted imports raise `ModuleNotFoundError`. Modifying `requirements-phase7.txt` or installing packages is strictly prohibited.
  4. **Phase D Pilot Evaluation Outcome:** Five-security pilot (RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK) for 2024-01-01 to 2024-01-31 failed all preconditions and safety gates. Existing connectors hardcode trailing-only dates (days=365) and omit turnover in INR and VWAP.
  5. **Halt of Full Acquisition:** In strict accordance with the pilot acceptance protocol, Phase E full-dataset acquisition was **halted**. Zero raw market data was downloaded into the repository.
  6. **Blocker & Milestone Status:** BLK-01, BLK-02, and BLK-04 remain OPEN (STILL_BLOCKED). Milestone 5 remains strictly BLOCKED. Research status set to `NSE_CONNECTOR_PILOT_FAILED`.
- **Impacted Modules:**
  - `docs/PHASE7_NSE500_PULL_REPORT.md`
  - `docs/PHASE7_NSE500_STRUCTURAL_AUDIT.md`
  - `docs/PHASE7_NSE500_COVERAGE_REPORT.md`
  - `docs/PHASE7_NSE500_GAP_ANALYSIS.md`
  - `docs/PHASE7_NSE500_MANIFEST_REFERENCE.md`
  - `tests/phase7/test_nse500_structural_audit.py`
  - `docs/PHASE7_BLOCKERS.md`
  - `docs/PHASE7_DECISION_LOG.md`
  - `docs/PHASE7_EXECUTION_PLAN.md`
  - `docs/PHASE7_IMPLEMENTATION_MAP.md`
- **Verification Criteria:**
  - 189/189 automated tests passing in `.venv-phase7` (185 Phase 7 tests, 4 Phase 6 safeguards).
  - External staging path created and preserved outside repository.
  - Zero Phase 6 file changes; zero production code changes; zero market data committed.

### DEC-20261010-02: Milestone 4.8B NSE Dependency Approval (nse==4.0.1)
- **Date:** 2026-10-10
- **Decision Authority:** Project Owner & Lead Quantitative Research Engineer (AUTHORIZE MILESTONE 4.8B: NSE DEPENDENCY APPROVAL AND FAIL-CLOSED SOURCE ADAPTER)
- **Context & Motivation:** Following the static audit of `connector_review/nse_data_service.py` confirming explicit historical date range capability, the project owner authorized evaluation and installation of `nse==4.0.1` inside `.venv-phase7` strictly for internal, non-distributed Phase 7 feasibility research.
- **Exact Decision:**
  1. **Strict Dependency Pin:** Exactly `nse==4.0.1` is added to `requirements-phase7.txt`. Unpinned releases or 5.x releases are strictly prohibited.
  2. **Licensing Boundary (GPLv3):** Acknowledged that `nse` is licensed under GPLv3. Approved exclusively for internal, non-distributed feasibility research. Commercial distribution, proprietary production integration, or public API deployment is strictly prohibited without prior legal review (`LEGAL_REVIEW_REQUIRED_BEFORE_DISTRIBUTION`).
  3. **Architectural Isolation:** Direct top-level imports of `nse` in research modeling modules are forbidden. The library must be accessed only through an isolated client protocol and runtime factory within `phase7/sources/`.
  4. **Installation & Clean Resolution:** Installed into `.venv-phase7` (Python 3.12.10) with direct dependencies `httpx==0.28.1` and `mthrottle==0.0.2`. Verified with `pip check` reporting zero broken requirements.
  5. **Zero Live Requests:** Installation completed without issuing any live network requests to NSE or market data endpoints.
- **Impacted Modules:**
  - `requirements-phase7.txt`
  - `docs/PHASE7_ENVIRONMENT_VERIFICATION.md`
  - `docs/PHASE7_NSE_DATA_FETCHER_DEPENDENCY_MAP.md`
  - `docs/PHASE7_DECISION_LOG.md`
- **Verification Criteria:**
  - `pip check` returns exit code 0 ("No broken requirements found.").
  - Existing 189 automated tests continue to pass in `.venv-phase7`.
  - Zero live network requests executed; zero market data downloaded.

---

### DEC-20261010-18: Safe Adapter Architecture for NSEDataFetcher (Milestone 4.8)
- **Date:** 2026-10-10
- **Decision Authority:** Project Owner & Lead Quantitative Research Engineer
- **Context & Motivation:** Implementation of the isolated, fail-closed Phase 7 adapter wrapping `NSEDataFetcher` (`phase7/sources/`) following the static source audit.
- **Exact Decision:**
  1. **Isolated Package (`phase7/sources/`):** Primary adapter implemented in `NSEDataFetcherAdapter` wrapping `NSEDataFetcherProtocol` with dependency injection.
  2. **Fail-Closed Safety Status:** Adapter marked `UNSAFE_FOR_LIVE_PILOT` due to upstream HTTP status code encapsulation in `nse==4.0.1`.
  3. **Constituent Handling:** `phase7.sources.nse_constituents` strictly returns `SOURCE_UNAVAILABLE` when fetcher lacks constituent method; zero fallback to `features.universe` or legacy 138-stock lists.
  4. **Output Normalization:** Canonical conversion to `HistoricalEODRecord` with turnover never inferred from Close, ISIN never inferred, adjustment state never invented, and deterministic SHA-256 row hashes.
  5. **Live Pilot Preparation:** Prepared dedicated CLI `phase7.sources.pilot` requiring exact authorization phrase `'AUTHORIZE MILESTONE 4.9: FIVE-STOCK NSE LIVE PILOT'`. Live execution not performed in Milestone 4.8.
  6. **Completion Status:** `NSE_DATA_FETCHER_ADAPTED_LIVE_PILOT_NOT_AUTHORIZED`.
- **Impacted Modules:**
  - `phase7/sources/__init__.py`
  - `phase7/sources/contracts.py`
  - `phase7/sources/http_client.py`
  - `phase7/sources/nse_data_fetcher_adapter.py`
  - `phase7/sources/nse_constituents.py`
  - `phase7/sources/nse_eod.py`
  - `phase7/sources/nse_corporate_actions.py`
  - `phase7/sources/normalization.py`
  - `phase7/sources/manifest.py`
  - `phase7/sources/pilot.py`
  - `phase7/sources/audit.py`
  - `docs/PHASE7_NSE_DATA_FETCHER_AUDIT.md`
  - `docs/PHASE7_NSE_DATA_FETCHER_ADAPTER.md`
  - `docs/PHASE7_NSE_LIVE_PILOT_PROTOCOL.md`
  - `docs/PHASE7_FASTAPI_NSE_WRAPPER_SECURITY_REVIEW.md`
- **Verification Criteria:**
  - All 248 automated tests pass offline in `.venv-phase7`.
  - Zero live network requests executed; zero market data written to repository.

---

### DEC-20261010-19: Milestone 4.9 Five-Stock Pilot Halted on Reusable Token Requirement Defect
- **Date:** 2026-10-10
- **Decision Authority:** Project Owner & Lead Quantitative Research Engineer
- **Context & Motivation:** During Milestone 4.9 live pilot execution, the canonical command was run without passing the owner-authorization phrase on the CLI in accordance with strict owner directives. The CLI halted with exit code 1 because `phase7.sources.pilot` mandates `--owner-authorization`.
- **Exact Decision:**
  1. **Strict Fail-Closed Halt:** Adhere to owner instruction ("If the implementation still requires the phrase as a command-line argument: Do not execute. Report that the reusable authorization-token design remains present. Stop and request a corrective patch.").
  2. **Zero Code Modification in Checkpoint:** In accordance with milestone rules ("Do not repair it during this milestone. Document the defect."), no source code in `phase7/sources/` was modified.
  3. **Zero Network Requests:** Exactly 0 live network calls were made to NSE.
  4. **Document Defect & Status:** Record the defect in audit documentation and mark the milestone `NSE_FIVE_STOCK_PILOT_HALTED_ON_SAFETY_CONTROL`.
  5. **Corrective Patch Required:** Subsequent milestone must authorize a corrective patch to decouple live pilot execution from reusable CLI string tokens.
- **Impacted Modules:**
  - `docs/PHASE7_NSE_FIVE_STOCK_PILOT_REPORT.md`
  - `docs/PHASE7_NSE_FIVE_STOCK_STRUCTURAL_AUDIT.md`
  - `docs/PHASE7_NSE_FIVE_STOCK_GAP_ANALYSIS.md`
  - `docs/PHASE7_BLOCKERS.md`
  - `docs/PHASE7_DECISION_LOG.md`
- **Verification Criteria:**
  - Working tree remains clean after documentation commit.
---

### DEC-20261010-20: Milestone 4.9A Single-Use Scope-Bound Pilot Authorization Guard
- **Date:** 2026-10-10
- **Decision Authority:** Project Owner & Lead Quantitative Research Engineer
- **Context & Motivation:** Remediation of the reusable authorization token defect recorded in DEC-20261010-19. Replace CLI `--owner-authorization` option and secret phrase string comparisons with an immutable, single-use, scope-bound authorization marker stored strictly outside Git.
- **Exact Decision:**
  1. **Removal of Reusable CLI Token:** Completely removed `--owner-authorization` option, phrase comparisons, phrase variables, and phrase logging from `phase7.sources.pilot` and `phase7.sources.pilot_guard`.
  2. **Single-Use Authorization Marker Architecture:** Created `phase7.sources.authorization` with `PilotAuthorizationRecord` (`authorization_version="1.0"`, `milestone="4.9"`, `scope="FIVE_STOCK_NSE_LIVE_PILOT"`, approved symbols `["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"]`, dates `2024-01-01` to `2024-01-31`, `interval="1d"`, `single_use=True`, `staging_root_hash`, `issued_timestamp`, `expires_timestamp`, `nonce`, and `authorization_hash`).
  3. **Location & Path Boundary Enforcement:** Marker exists exclusively outside Git under `<staging-root>/authorization/pilot_authorization.json`. In-repo paths, relative paths, and symlinks/junctions into repo are strictly rejected.
  4. **Atomic Consumption Protocol:** Enforced atomic rename of `pilot_authorization.json` to `pilot_authorization.consumed.<UTC_TIMESTAMP>.json` via `os.replace` prior to client instantiation. If consumption fails, client is never created and process aborts with `AUTHORIZATION_CONSUMPTION_FAILED`.
  5. **Zero Live Pilot Execution:** Live execution was not authorized and did not execute during Milestone 4.9A. Zero live network requests occurred.
  6. **Readiness Status:** `NSE_PILOT_AUTHORIZATION_GUARD_CORRECTED_LIVE_EXECUTION_NOT_AUTHORIZED`.
- **Impacted Modules:**
  - `phase7/sources/contracts.py`
  - `phase7/sources/authorization.py`
  - `phase7/sources/pilot_guard.py`
  - `phase7/sources/pilot.py`
  - `phase7/sources/__init__.py`
  - `tests/phase7/test_source_authorization.py`
  - `tests/phase7/test_source_pilot_guard.py`
  - `tests/phase7/test_source_pilot_guardrails.py`
  - `tests/phase7/test_source_isolation.py`
  - `docs/PHASE7_NSE_LIVE_PILOT_PROTOCOL.md`
  - `docs/PHASE7_NSE_DATA_FETCHER_ADAPTER.md`
  - `docs/PHASE7_DECISION_LOG.md`
  - `docs/PHASE7_IMPLEMENTATION_MAP.md`
  - `docs/PHASE7_NSE_FIVE_STOCK_GAP_ANALYSIS.md`
- **Verification Criteria:**
  - All 263 tests pass in `.venv-phase7` (248 baseline + 15 new tests).
  - Source scan confirms zero occurrences of `owner-authorization`, `AUTHORIZE MILESTONE`, `password`, `api_key`, `bearer`, or `cookie` in `phase7/sources/`.
  - `pip check` reports no broken requirements.
  - Zero live network requests executed; working tree clean.

---

### DEC-20261010-21: Re-Authorized Milestone 4.9 Five-Stock Pilot Halted on Client Factory Signature Mismatch
- **Date:** 2026-10-10
- **Decision Authority:** Project Owner & Lead Quantitative Research Engineer
- **Context & Motivation:** During re-authorized single execution of the five-stock live pilot in Milestone 4.9, the single-use marker was created outside Git and consumed atomically before client initialization. Execution safely halted on a client factory parameter mismatch (`create_real_nse_client() got an unexpected keyword argument 'data_dir'`).
- **Exact Decision:**
  1. **Fail-Closed Halt Prior to Client Creation:** Adhere strictly to governance directives ("If a connector defect is discovered: Document it. Do not fix it. Stop if it affects safety or validity. If the program crashes after consuming the marker: Do not restore the marker. Do not rerun. Document the failure. Stop.").
  2. **Zero Code Modification in Checkpoint:** No source code in `phase7/sources/` was modified.
  3. **Zero Network Requests:** Exactly 0 live network calls made to NSE.
  4. **Document Defect & Status:** Record the defect in audit documentation and mark the milestone `NSE_FIVE_STOCK_PILOT_HALTED_ON_SAFETY_CONTROL`.
  5. **Corrective Patch Required:** Subsequent milestone must authorize a corrective patch to align calling arguments between `phase7/sources/pilot.py` and `phase7/sources/client_factory.py`.
- **Impacted Modules:**
  - `docs/PHASE7_NSE_FIVE_STOCK_PILOT_REPORT.md`
  - `docs/PHASE7_NSE_FIVE_STOCK_STRUCTURAL_AUDIT.md`
  - `docs/PHASE7_NSE_FIVE_STOCK_GAP_ANALYSIS.md`
  - `docs/PHASE7_BLOCKERS.md`
  - `docs/PHASE7_DECISION_LOG.md`
- **Verification Criteria:**
  - Working tree remains clean after documentation commit.
  - All 263 tests continue to pass in `.venv-phase7`.
  - Zero market data files in repository.

---

### DEC-20261010-22: Milestone 4.9B Alignment of NSE Pilot Client Factory Interface
- **Date:** 2026-10-10
- **Decision Authority:** Project Owner & Lead Quantitative Research Engineer
- **Context & Motivation:** Remediation of the client factory interface mismatch (`CLIENT_FACTORY_PARAMETER_MISMATCH_HALT`: `TypeError: create_real_nse_client() got an unexpected keyword argument 'data_dir'`) observed during Milestone 4.9 re-authorization. The pilot invocation passed legacy parameters `data_dir` and `server_mode`, whereas the factory defined `create_real_nse_client(download_folder: Path, server: bool = True, timeout: int = 15)`.
- **Exact Decision:**
  1. **Canonical Factory Signature & Contract:** Formalized one canonical factory signature:
     `create_real_nse_client(download_folder: Path, server: bool = True, timeout: int = 15) -> NSEClientProtocol`.
     - `download_folder`: Must be an absolute `pathlib.Path` strictly outside the Git repository.
     - `server`: Must be strictly boolean `True` for governed pilot execution.
     - `timeout`: Must be strictly integer `15` seconds.
     - Explicit parameter binding without `**kwargs` to prevent silent parameter masking; unexpected keyword arguments raise `TypeError`.
  2. **Protocol Definition:** Defined and exported `@runtime_checkable class NSEClientFactoryProtocol(Protocol)` in `phase7.sources.client_protocol` and `phase7.sources.__init__`.
  3. **Pilot Invocation Alignment:** Updated `phase7.sources.pilot` to invoke `client_factory(download_folder=valid_staging / "raw", server=True, timeout=15)`.
  4. **Sanitized Error Handling:** Client-construction `TypeError` exceptions are caught in `phase7.sources.pilot` and converted into `RuntimeError("CLIENT_FACTORY_PARAMETER_MISMATCH_HALT: ...")`.
  5. **Removal of Obsolete Keywords:** Scanned `phase7/sources/` confirming zero occurrences of `data_dir=` or `server_mode=`.
  6. **Consumed Marker Protection:** The prior consumed marker `pilot_authorization.consumed.20261010T063226Z.json` remains safely consumed. No replacement marker was generated.
  7. **Zero Live Execution & Network Calls:** Live execution was not authorized and did not execute. Exactly 0 network requests occurred.
  8. **Readiness Status:** `NSE_PILOT_CLIENT_FACTORY_ALIGNED_LIVE_EXECUTION_NOT_AUTHORIZED`.
- **Impacted Modules:**
  - `phase7/sources/client_protocol.py`
  - `phase7/sources/client_factory.py`
  - `phase7/sources/pilot.py`
  - `phase7/sources/__init__.py`
  - `tests/phase7/test_source_client_factory_contract.py`
  - `tests/phase7/test_source_authorization.py`
  - `docs/PHASE7_NSE_LIVE_PILOT_PROTOCOL.md`
  - `docs/PHASE7_NSE_DATA_FETCHER_ADAPTER.md`
  - `docs/PHASE7_DECISION_LOG.md`
  - `docs/PHASE7_IMPLEMENTATION_MAP.md`
  - `docs/PHASE7_NSE_FIVE_STOCK_GAP_ANALYSIS.md`
- **Verification Criteria:**
  - Full pytest suite passes in `.venv-phase7` (276 passing tests, including 13 new contract and regression tests).
  - `pip check` reports no broken requirements.
  - CLI `phase7.sources.pilot --help` exits cleanly with zero side-effects.
  - Consumed authorization marker remains consumed. Zero new markers generated.
  - Zero market data files in repository.

---

### DEC-20261010-23: Re-Authorized Milestone 4.9 Five-Stock Pilot Halted on Upstream Dependency Defect (`httpx[http2]`)
- **Date:** 2026-10-10
- **Decision Authority:** Project Owner & Lead Quantitative Research Engineer
- **Context & Motivation:** Following the client factory interface alignment in `30265b5`, a single execution of the five-stock live pilot was re-authorized. A fresh single-use marker (`a24805c88651d347aaf643c79fa38aee11465845e9ecc19fb6cac1d3bf86ea84`) was created outside Git and atomically consumed. The pilot invoked `create_real_nse_client(download_folder=staging/"raw", server=True, timeout=15)` using canonical keywords. Client initialization safely halted inside `nse.NSE.__init__` due to missing `h2` dependency required by `httpx[http2]`.
- **Exact Decision:**
  1. **Fail-Closed Halt Prior to Socket Creation:** Adhere strictly to governance directives ("If a connector defect is discovered: Document it. Do not fix it. Stop if it affects safety or validity. If the program crashes after consuming the marker: Do not restore the marker. Do not rerun. Document the failure. Stop.").
  2. **Zero Code Modification in Checkpoint:** No source code in `phase7/sources/` was modified during execution.
  3. **Zero Network Requests:** Exactly 0 live network calls made to NSE.
  4. **Document Defect & Status:** Record the defect in audit documentation and mark the milestone `NSE_FIVE_STOCK_PILOT_HALTED_ON_SAFETY_CONTROL`.
  5. **Dependency Evaluation Required:** Subsequent milestone must request owner authorization to evaluate installing `h2` (or resolving `httpx[http2]`) in `.venv-phase7`.
- **Impacted Modules:**
  - `docs/PHASE7_NSE_FIVE_STOCK_PILOT_REPORT.md`
  - `docs/PHASE7_NSE_FIVE_STOCK_STRUCTURAL_AUDIT.md`
  - `docs/PHASE7_NSE_FIVE_STOCK_GAP_ANALYSIS.md`
  - `docs/PHASE7_BLOCKERS.md`
  - `docs/PHASE7_DECISION_LOG.md`
  - `docs/PHASE7_IMPLEMENTATION_MAP.md`
- **Verification Criteria:**
  - Working tree remains clean after documentation commit.
  - All 276 tests continue to pass in `.venv-phase7`.
  - Zero market data files in repository.

---

### DEC-20261010-24: Milestone 4.9C Addition of Required NSE HTTP/2 Runtime Dependencies
- **Date:** 2026-10-10
- **Decision Authority:** Project Owner & Lead Quantitative Research Engineer
- **Context & Motivation:** Remediation of the runtime dependency blocker observed in Attempt 2 (`UPSTREAM_DEPENDENCY_DEFECT_HALT`: `Using http2=True, but the 'h2' package is not installed. Make sure to install httpx using 'pip install httpx[http2]'`). The client factory requires `server=True` for governed pilot execution, which requires HTTP/2 transport support inside upstream `nse==4.0.1`.
- **Exact Decision:**
  1. **Requirement Pin Update:** Replaced `nse==4.0.1` with `nse[server]==4.0.1` in `requirements-phase7.txt`. Pinned version remains 4.0.1 without unpinned packages or version upgrades.
  2. **Dependency Installation:** Installed through `.venv-phase7\Scripts\python.exe -m pip install -r requirements-phase7.txt`. Resolved `h2==4.4.1`, `hpack==4.2.0`, `hyperframe==6.1.0`. Maintained `httpx==0.28.1` and `nse==4.0.1`.
  3. **Licensing & Copyleft Retained:** `h2`, `hpack`, and `hyperframe` are MIT licensed. `LEGAL_REVIEW_REQUIRED_BEFORE_DISTRIBUTION` retained; installing optional extras does not alter the GPLv3 boundary associated with `nse==4.0.1`.
  4. **Client Construction Verification:** Verified that `create_real_nse_client(download_folder=..., server=True, timeout=15)` instantiates and closes without the missing-`h2` error when network transport is intercepted. Result: `CLIENT_CONSTRUCTION_SUCCEEDED_ZERO_NETWORK_REQUESTS`.
  5. **Zero Live Pilot Execution:** Live execution was not authorized and did not execute. Exactly 0 network requests occurred.
  6. **Readiness Status:** `NSE_HTTP2_RUNTIME_DEPENDENCIES_READY_LIVE_EXECUTION_NOT_AUTHORIZED`.
- **Impacted Modules:**
  - `requirements-phase7.txt`
  - `tests/phase7/test_source_runtime_dependencies.py`
  - `docs/PHASE7_ENVIRONMENT_VERIFICATION.md`
  - `docs/PHASE7_NSE_DATA_FETCHER_DEPENDENCY_MAP.md`
  - `docs/PHASE7_DECISION_LOG.md`
  - `docs/PHASE7_NSE_FIVE_STOCK_GAP_ANALYSIS.md`
- **Verification Criteria:**
  - Full pytest suite passes in `.venv-phase7` (285 passing tests, including 9 new runtime dependency tests).
  - `pip check` reports no broken requirements.
  - Zero market data files in repository.
  - Zero live network calls made to NSE.

---

### DEC-20261010-25: Re-Authorized Milestone 4.9 Five-Stock Pilot Failed on Incomplete Retrieval Loop in Pilot CLI
- **Date:** 2026-10-10
- **Decision Authority:** Project Owner & Lead Quantitative Research Engineer
- **Context & Motivation:** Following HTTP/2 runtime dependency resolution in `3f49367`, a third single execution of the five-stock live pilot was re-authorized. A fresh single-use marker (`b6f65c768dc00545bc7322b5560cbd3d95d62f8dd5a79bd815e266e2b938ef7c`) was created outside Git and consumed atomically (`pilot_authorization.consumed.20261010T072920Z.json`). Client initialized cleanly over HTTP/2, saving initial session cookies in staging (`raw/nse_cookies_httpx.json`). However, `phase7.sources.pilot` exited at Step 14 without invoking the per-symbol historical retrieval pipeline.
- **Exact Decision:**
  1. **Document Defect & Record Status:** Adhere strictly to governance directives ("Do not modify source code during this execution. If another defect is found: Document it. Do not repair it during this execution."). Record outcome as `NSE_FIVE_STOCK_PILOT_FAILED` based on 0/5 securities completed and 0.0% date coverage.
  2. **Zero Code Modification in Checkpoint:** No source code was modified during pilot execution.
  3. **Zero Market Data In Repository:** Zero market data was written to repository or staged.
  4. **Marker Remains Consumed:** The marker remains consumed; zero marker reuse permitted.
  5. **Wiring Patch Required:** Subsequent checkpoint must authorize wiring the sequential symbol retrieval loop into `phase7.sources.pilot` before pilot re-authorization.
- **Impacted Modules:**
  - `docs/PHASE7_NSE_FIVE_STOCK_PILOT_REPORT.md`
  - `docs/PHASE7_NSE_FIVE_STOCK_STRUCTURAL_AUDIT.md`
  - `docs/PHASE7_NSE_FIVE_STOCK_GAP_ANALYSIS.md`
  - `docs/PHASE7_BLOCKERS.md`
  - `docs/PHASE7_DECISION_LOG.md`
  - `docs/PHASE7_IMPLEMENTATION_MAP.md`
- **Verification Criteria:**
  - Working tree remains clean after documentation commit.
  - All 285 tests continue to pass in `.venv-phase7`.
---

### DEC-20261010-26: Milestone 4.9D Wiring of Governed Five-Stock Historical Retrieval Pipeline
- **Date:** 2026-10-10
- **Decision Authority:** Project Owner & Lead Quantitative Research Engineer
- **Context & Motivation:** Attempt 3 of the Milestone 4.9 live pilot initialized the governed NSE client cleanly over HTTP/2, saving external session credentials, but exited at Step 14 without invoking the per-symbol historical retrieval loop (`PILOT_SYMBOL_RETRIEVAL_PIPELINE_NOT_WIRED`). Checkpoint 4.9D authorizes code correction, persistence wiring, manifest lifecycle controls, and comprehensive mocked tests offline. Live requests remain strictly unauthorized.
- **Exact Decision:**
  1. **Canonical Sequential Retrieval Loop:** Wire sequential historical data retrieval for strictly 5 approved symbols (`RELIANCE`, `TCS`, `HDFCBANK`, `INFY`, `ICICIBANK`) into `phase7.sources.pilot`.
  2. **Rate Pacing & Single Active Request:** Enforce single active request lock and minimum 2.0-second delay between sequential network requests.
  3. **External Immutable Persistence:** Write raw payloads to `<staging>/raw/historical/` and normalized records in JSONL format to `<staging>/normalized/historical/` outside Git. Overwriting existing files is strictly prohibited.
  4. **Strict RequestManifest Lifecycle:** Write `PENDING` manifest before retrieval. Finalize manifest exactly once upon processing. Enforce invariants: status `SUCCEEDED` requires `> 0` normalized rows, valid raw SHA-256, and valid normalized SHA-256.
  5. **Conservation Invariant:** Strictly enforce `source_row_count = normalized_row_count + rejected_row_count`. Conservation failure halts pilot with `AUDIT_CONSERVATION_FAILURE`.
  6. **Rejection Ledgers:** Record malformed rows with sanitized reason codes, request identifiers, row indices, and non-sensitive row hashes. Session credentials and authorization tokens are strictly scrubbed.
  7. **Deterministic Client Closure:** Wrap retrieval loop in `try ... finally` block ensuring client session closure (`client.exit()`). If closure fails, return exit code 9 (`CLIENT_CLOSE_ERROR`).
  8. **Strict Exit Code Contract:** Enforce 0 (success for all 5 symbols), 2 (argument error), 3 (authorization error), 4 (client construction error), 5 (retrieval connectivity error), 6 (payload safety / schema normalization error), 7 (persistence / manifest / audit error), 8 (incomplete execution / fewer than 5 symbols), 9 (client close failure), 10 (unexpected internal error).
  9. **Regression Test:** Add `test_client_initialization_without_symbol_loop_cannot_succeed` reproducing and permanently preventing false success on client initialization alone.
  10. **Zero Live Calls Authorized:** No live requests, no active authorization marker created.
- **Impacted Modules:**
  - `phase7/sources/pilot.py`
  - `phase7/sources/contracts.py`
  - `phase7/sources/client_protocol.py`
  - `phase7/sources/manifest.py`
  - `phase7/sources/normalization.py`
  - `phase7/sources/rejections.py`
  - `phase7/sources/persistence.py`
  - `tests/phase7/test_source_pilot_execution.py`
  - `tests/phase7/test_source_persistence.py`
  - `tests/phase7/test_source_exit_codes.py`
  - `docs/PHASE7_NSE_LIVE_PILOT_PROTOCOL.md`
  - `docs/PHASE7_NSE_DATA_FETCHER_ADAPTER.md`
  - `docs/PHASE7_NSE_FIVE_STOCK_PILOT_REPORT.md`
  - `docs/PHASE7_DECISION_LOG.md`
  - `docs/PHASE7_IMPLEMENTATION_MAP.md`
- **Verification Criteria:**
  - Full test suite passes offline (318 passing tests, including 33 new mocked tests).
  - `pip check` reports no broken requirements.
  - `git diff --check` reports zero whitespace errors.
  - Zero live network requests issued.
  - Zero market data files in repository.

---

### DEC-20261010-27: Milestone 4.9 Five-Stock NSE Live Pilot Attempt 4 Outcome & Normalization Schema Disparity
- **Date:** 2026-10-10
- **Decision Authority:** Project Owner & Lead Quantitative Research Engineer
- **Context & Motivation:** Following pipeline wiring in `1dec29b`, a fourth single execution of the five-stock live pilot was authorized. A fresh single-use marker (`860461fd7227519c6e724dada2baf4122390d5477aa08bd6dc20faac41628e38`) was created outside Git and consumed atomically (`pilot_authorization.consumed.20261010T081013Z.json`). Governed client initialized over HTTP/2 and requested Symbol 1 (`RELIANCE`). Upstream NSE returned 22 daily trading records for Jan 2024. Raw JSON was persisted outside Git (`raw/historical/RELIANCE_...json`) with SHA-256 hash `59af0e392d7bb9073a49603115e11150a8adbab59e0619c6a0608d19ffcbef63`. However, normalization rejected all 22 rows due to field key casing (`mtimestamp` vs `mTIMESTAMP`), triggering safety halt on `PARTIAL` manifest, clean client disposal, and exit code 6.
- **Exact Decision:**
  1. **Document Defect & Record Status:** Adhere strictly to governance directives ("Do not modify source code during this execution. If another defect is found: Document it. Do not repair it during this execution."). Record outcome as `NSE_FIVE_STOCK_PILOT_HALTED_ON_SAFETY_CONTROL`.
  2. **Raw Retrieval Milestone Achievement:** First successful end-to-end historical data retrieval from NSE in Phase 7. 22 real daily rows acquired, validated safe (no HTML/CAPTCHA), and persisted outside Git.
  3. **Zero Code Modification in Checkpoint:** No source code was modified during pilot execution.
  4. **Zero Market Data In Repository:** Zero market data was written to repository or staged in Git.
  5. **Marker Remains Consumed:** The marker remains consumed; zero marker reuse permitted.
  6. **Schema Normalization Patch Required:** Subsequent checkpoint (Milestone 4.9E) must authorize aligning `phase7/sources/normalization.py` field key extraction (`mtimestamp`, `chOpeningPrice`, etc.) before pilot re-authorization.
- **Impacted Modules:**
  - `docs/PHASE7_NSE_FIVE_STOCK_PILOT_REPORT.md`
  - `docs/PHASE7_NSE_FIVE_STOCK_STRUCTURAL_AUDIT.md`
  - `docs/PHASE7_NSE_FIVE_STOCK_GAP_ANALYSIS.md`
  - `docs/PHASE7_BLOCKERS.md`
  - `docs/PHASE7_DECISION_LOG.md`
  - `docs/PHASE7_IMPLEMENTATION_MAP.md`
- **Verification Criteria:**
  - Working tree remains clean after documentation commit.
  - All 318 tests continue to pass in `.venv-phase7`.
  - Staging area contains 4 consumed markers and 1 raw historical payload outside Git.

---

### DEC-20261010-28: Milestone 4.9E NSE 4.0.1 Historical Payload Schema Alignment & Offline Replay Verification
- **Date:** 2026-10-10
- **Decision Authority:** Project Owner & Lead Quantitative Research Engineer
- **Context & Motivation:** Live pilot Attempt 4 halted with exit code 6 because `phase7/sources/normalization.py` did not recognize lowercase `mtimestamp` or camelCase keys (`chOpeningPrice`, etc.) returned by `nse==4.0.1`. Checkpoint 4.9E authorizes explicit source mapping, locale-independent date parsing, and offline replay validation over the preserved RELIANCE raw payload (`59af0e39...`) without network requests.
- **Exact Decision:**
  1. **Source Schema Versioning:** Implement versioned mapping `NSE_4_0_1_HISTORICAL_CAMELCASE_V1` in `phase7/sources/schema_mappings.py`.
  2. **Locale-Independent Date Parser:** Author `parse_nse_d_b_y` mapping English month names (`%d-%b-%Y`) deterministically to ISO `YYYY-MM-DD` without depending on C runtime locale.
  3. **Strict Zero-Inference Invariants:** Preserve non-inference of turnover, ISIN (`None`), delivery (`None`), and adjustment state (`AdjustmentState.UNKNOWN` for nse 4.0.1).
  4. **Strict Numeric Validation:** Reject NaN, Infinity, negative prices, and negative quantities across float and integer parsers.
  5. **Offline Replay Execution:** Verify 22/22 rows of preserved RELIANCE payload normalize with 0 rejections, 100% date coverage, zero duplicates, and conserved totals ($22 = 22 + 0$).
  6. **Evidence Integrity:** Staged replay output strictly under `<staging>/offline_replay_4_9e/` outside Git; live raw payload and live manifest remain unchanged.
- **Impacted Modules:**
  - `phase7/sources/schema_mappings.py`
  - `phase7/sources/normalization.py`
  - `phase7/sources/contracts.py`
  - `phase7/sources/manifest.py`
  - `phase7/sources/audit.py`
  - `phase7/sources/__init__.py`
  - `tests/phase7/test_source_nse_401_schema.py`
  - `tests/phase7/test_source_offline_replay.py`
  - `docs/PHASE7_NSE_DATA_FETCHER_ADAPTER.md`
  - `docs/PHASE7_NSE_FIVE_STOCK_PILOT_REPORT.md`
  - `docs/PHASE7_NSE_FIVE_STOCK_STRUCTURAL_AUDIT.md`
  - `docs/PHASE7_NSE_FIVE_STOCK_GAP_ANALYSIS.md`
  - `docs/PHASE7_DECISION_LOG.md`
  - `docs/PHASE7_IMPLEMENTATION_MAP.md`
- **Verification Criteria:**
  - Full test suite passes offline (339 passing tests).
  - `pip check` clean.
  - `git diff --check` clean.
  - Offline replay verified 22/22 rows normalized with 0 rejections.

---

### DEC-20261010-29: Milestone 4.9 Five-Stock NSE Live Pilot Closure & Classification
- **Date:** 2026-10-10
- **Decision Authority:** Project Owner (`AUTHORIZE MILESTONE 4.9 CLOSURE: RECORD SUCCESSFUL FIVE-STOCK NSE PILOT`)
- **Context & Motivation:** Live five-stock pilot Attempt 5 executed cleanly following `NSE_4_0_1_HISTORICAL_CAMELCASE_V1` schema alignment and offline replay verification. The pilot acquired, normalized, and persisted all 5 authorized equities (`RELIANCE`, `TCS`, `HDFCBANK`, `INFY`, `ICICIBANK`) across January 2024 with zero rejections, zero duplicates, zero invalid OHLC bounds, and 100% session coverage.
- **Exact Decision:**
  1. **Milestone Closure:** Formally close Milestone 4.9 with status `NSE_FIVE_STOCK_PILOT_CLOSED_SUCCESSFULLY`.
  2. **Dataset Classification:** Classify the acquired 110-row dataset strictly as `FIVE_STOCK_LIVE_CAPABILITY_SAMPLE_NOT_RESEARCH_DATASET`.
  3. **Strict Negative Claims:** Under Non-Negotiable Rules and Gate 1 Data Integrity standards, the pilot dataset:
     - Is NOT survivorship-free;
     - Is NOT a point-in-time NIFTY 500 panel;
     - DOES NOT pass Gate 1;
     - Is NOT production-ready;
     - DOES NOT constitute validated alpha;
     - Is NOT suitable for model training, feature extraction, or walk-forward cross-validation;
     - DOES NOT provide evidence of investment performance or strategy returns.
  4. **Preservation of Evidence:** Preserve all 5 immutable raw files, 5 normalized files, 5 manifests, and 5 consumed markers outside Git in `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9`.
  5. **Blocker Registry Update:**
     - BLK-01 (PIT NIFTY 500 Membership): `STILL_BLOCKED`
     - BLK-02 (Historical Daily OHLCV & Turnover): `PILOT_CAPABILITY_CONFIRMED_GATE1_NOT_PASSED`
     - BLK-04 (PIT Sector Classification): `STILL_BLOCKED`
  6. **Next Authorized Milestone:** Authorize preparation for `MILESTONE 4.10A: CURRENT NIFTY 500 CONSTITUENT SNAPSHOT PILOT` (static audit and single snapshot capability evaluation).
  7. **Milestone 5 Quarantine:** Milestone 5 (non-ML baselines and model training) remains strictly blocked until authentic point-in-time panel data passes Gate 1.
- **Impacted Modules:**
  - `docs/PHASE7_NSE_FIVE_STOCK_PILOT_REPORT.md`
  - `docs/PHASE7_NSE_FIVE_STOCK_STRUCTURAL_AUDIT.md`
  - `docs/PHASE7_NSE_FIVE_STOCK_GAP_ANALYSIS.md`
  - `docs/PHASE7_BLOCKERS.md`
  - `docs/PHASE7_DECISION_LOG.md`
  - `docs/PHASE7_EXECUTION_PLAN.md`
  - `docs/PHASE7_IMPLEMENTATION_MAP.md`
- **Verification Criteria:**
  - Process exit code 0 (`NSE_FIVE_STOCK_PILOT_PASSED`).
  - 5/5 manifests report `status: SUCCEEDED`.
  - Conservation verified: $110 = 110 + 0$.
  - All 339 tests pass offline.
  - Zero market-data files inside Git working tree.

---

### DEC-20261010-30: Milestone 4.10A Current NIFTY 500 Constituent Snapshot Pilot Execution & Freezing
- **Date:** 2026-10-10
- **Decision Authority:** Project Owner (`AUTHORIZE MILESTONE 4.10A: CURRENT NIFTY 500 CONSTITUENT SNAPSHOT PILOT`)
- **Context & Motivation:** Authorized single controlled attempt to retrieve, validate, normalize, checksum, and freeze a current NIFTY 500 constituent snapshot via `nse==4.0.1` method `listEquityStocksByIndex(index="NIFTY 500")` to test upstream constituent acquisition capability.
- **Exact Decision:**
  1. **Pilot Outcome & Exit Code:** Formally record outcome `NSE_CURRENT_NIFTY500_SNAPSHOT_PILOT_PASSED` with process exit code 0.
  2. **Dataset Classification:** Classify the acquired 500-constituent dataset strictly as `CURRENT_SNAPSHOT_ONLY`.
  3. **Panel Version Identifier:** Freeze snapshot identifier as `CURRENT_NIFTY500_09Oct2026_8F4C439F` based on source report date `09-Oct-2026` and normalized checksum prefix `8F4C439F`.
  4. **Strict Negative Declarations:** Under Non-Negotiable Rules and Gate 1 Data Integrity standards, this constituent list:
     - Is NOT historical NIFTY 500 membership;
     - Is NOT point-in-time membership;
     - Is NOT survivorship-free membership;
     - Is NOT effective-dated index history;
     - DOES NOT resolve `BLK-01`;
     - DOES NOT satisfy Gate 1;
     - DOES NOT authorize model training or feature generation.
  5. **Blocker Registry Update:**
     - `BLK-01` (PIT NIFTY 500 Membership): Remains `STILL_BLOCKED`.
     - Capability Label: `CURRENT_NIFTY500_SNAPSHOT_CAPABILITY_CONFIRMED` granted.
     - `BLK-02` (Historical OHLCV & Turnover): Remains `PILOT_CAPABILITY_CONFIRMED_GATE1_NOT_PASSED`.
     - `BLK-04` (PIT Sector Classification): Remains `STILL_BLOCKED`.
  6. **External Staging & Checksums:** Raw payload SHA-256 (`37f6e829...`) and normalized JSONL SHA-256 (`8f4c439f...`) preserved immutably in `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\snapshot_4_10a` outside Git.
  7. **Milestone 5 Quarantine:** Milestone 5 remains strictly blocked until authentic point-in-time membership data is ingested and Gate 1 passes.
- **Impacted Modules:**
  - `phase7/sources/contracts.py`
  - `phase7/sources/nse_constituents.py`
  - `phase7/sources/constituent_authorization.py`
  - `phase7/sources/constituent_persistence.py`
  - `phase7/sources/constituent_pilot.py`
  - `docs/PHASE7_NSE500_CURRENT_SNAPSHOT_PILOT_REPORT.md`
  - `docs/PHASE7_NSE500_CURRENT_SNAPSHOT_STRUCTURAL_AUDIT.md`
  - `docs/PHASE7_NSE500_CURRENT_SNAPSHOT_MANIFEST_REFERENCE.md`
  - `docs/PHASE7_NSE500_CURRENT_SNAPSHOT_LIMITATIONS.md`
  - `docs/PHASE7_BLOCKERS.md`
  - `docs/PHASE7_DECISION_LOG.md`
  - `docs/PHASE7_EXECUTION_PLAN.md`
  - `docs/PHASE7_IMPLEMENTATION_MAP.md`
- **Verification Criteria:**
  - Process exit code 0 (`SnapshotPilotExitCode.SUCCESS`).
  - Exactly 1 network request dispatched.
  - Manifest finalized with `status: SUCCEEDED`.
  - Conservation holds: $501 = 500 + 1$.
  - 500 unique valid symbols present; 0 duplicate symbols.
  - All 389 tests pass offline.
  - Zero market data in Git repository.

---

## 3. Log Schema for Future Amendments

All future amendments to this decision log must adhere to the following schema:
```markdown
### DEC-YYYYMMDD-XX: [Title of Decision]
- **Date:** YYYY-MM-DD
- **Decision Authority:** [Project Owner / Research Governance Officer]
- **Context & Motivation:** [Why the decision was taken]
- **Exact Decision:** [Binding operational, mathematical, or gating directives]
- **Impacted Modules:** [List of files, configurations, or preregistration sections]
- **Verification Criteria:** [How compliance with this decision is verified]
```
