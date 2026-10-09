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
