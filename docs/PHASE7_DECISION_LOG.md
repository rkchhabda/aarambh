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
