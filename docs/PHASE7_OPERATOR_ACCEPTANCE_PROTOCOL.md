# Phase 7 — Offline Operator Acceptance Protocol

**Milestone:** 4.13: Internal Offline Operator Acceptance
**Authorized Start Date:** 2026-10-12
**Minimum Duration:** 5 working days (2026-10-12 through 2026-10-16)
**Minimum Operational Sessions:** 10 sessions (2 sessions per working day)
**Minimum Operating Time:** 5 cumulative hours (300 minutes)
**Permitted Operational Mode:** Offline, read-only, internal, non-distributed
**External Network:** Strictly Prohibited
**External Evidence Acquisition:** Strictly Prohibited
**Milestone 5:** Strictly Blocked
**Acceptance Status:** `INTERNAL_OFFLINE_OPERATOR_ACCEPTANCE_IN_PROGRESS`
**Readiness Classification:** `INTERNAL_NON_DISTRIBUTED_PRODUCTION_LIKE_READINESS_CONFIRMED`

---

## 1. Executive Mandate & Purpose

This protocol governs the execution of **Milestone 4.13: Internal Offline Operator Acceptance**, authorizing a structured five-working-day evaluation exercise for the Phase 7 unified offline operator console (`phase7.operator`).

The objective is to validate that the operator application functions reliably, securely, and fail-closed across extended operational sessions without software regressions, memory leakage, lock contention, or security boundary violations.

### Strict Governance Constraints
1. **Zero External Network Operations:** All socket, HTTP/2, urllib, and HTTPX operations remain intercepted by runtime quarantine.
2. **Zero Evidence Mutation:** Preserved evidence in staging remains bit-for-bit immutable; file edits, unlinks, and overwrites are refused.
3. **Zero Active Authorization Tokens:** Marker generation and replay remain disabled; active token count is strictly zero.
4. **Milestone 5 Quarantine:** Model training, forward return prediction, cross-sectional ranking, backtesting, and Phase 6 vaults remain sealed and unaccessed.
5. **No Unqualified Terminology:** At no time may the unqualified term `PRODUCTION_READY` be used. All readiness remains qualified as `INTERNAL_NON_DISTRIBUTED_PRODUCTION_LIKE_READINESS_CONFIRMED`.
6. **External Evidence Isolation:** All session logs, audit traces, and acceptance records reside exclusively in external staging (`C:\Users\r_chh\gaurvideep_phase7_staging\nse500\acceptance_4_13\`). Zero session data is written into Git.

---

## 2. Evaluation Surfaces & Screen Coverage

The acceptance exercise exercises and inspects all ten governed screens of the operator console:

| Screen # | Governed View Title | Subsystem Evaluated | Acceptance Invariant |
| :---: | :--- | :--- | :--- |
| **1** | Readiness Dashboard | 15-Domain Non-Investment Scorecard | Confirms all 15 domains PASS; 811 tests passing; 16 drills passing. |
| **2** | Evidence Inventory | External Staging Filesystem Scanner | Catalogs >=50 assets across raw, normalized, manifests, checkpoints; computes SHA-256. |
| **3** | Manifest Verifier | Cryptographic Integrity & Row Conservation | Verifies row conservation equation $S = N + R$; flags zero-row and checksum drift fail-closed. |
| **4** | Batch-State Viewer | Halted Batch (`batch_4_10c`) Inspection | Displays `PREMIERENE` halt, unverified listing date, and strict non-resume policy. |
| **5** | Operational-Drill Viewer | 16 Fault-Injection Drill Records | Disambiguates drill runner exit 0 from system under test exits (1, 28, 13, 9, 0). |
| **6** | Backup & Restore Verifier | Disaster Recovery Archive Integrity | Bit-for-bit SHA-256 verification of BK-D15; temporary file exclusion; Git target rejection. |
| **7** | Governance & Blockers | Owner Decision & Blocker Registry | Displays `DEC-20261010-36`; Gate 1 NOT PASSED; Milestone 5 BLOCKED; BLK-01/02/04 open. |
| **8** | Authorization Registry | Consumed Marker Registry | Indexes >=5 consumed markers; enforces zero active markers; creation disabled. |
| **9** | Metadata-Only Audit Export | Sanitized Audit Exporter | Exports JSON audit bundle; verifies exclusion of trade prices, quotes, and credentials. |
| **10** | Synthetic Demonstration | Isolated Simulation & Tamper Detection | Runs 5-symbol simulation; flips 1 byte; verifies fail-closed halt and zero staging mutation. |

---

## 3. Five-Working-Day Session Schedule & Matrix

The exercise requires a minimum of **10 distinct operational sessions** distributed across **5 working days**, totaling at least **5.0 operating hours** (300 minutes):

| Day | Target Date | Session ID | Session Focus & Operational Scope | Min Operating Time |
| :---: | :---: | :---: | :--- | :---: |
| **Day 1** | 2026-10-12 | **S01** | Application Lifecycle, Startup & Single-Instance Lock Concurrency | 30 minutes |
| **Day 1** | 2026-10-12 | **S02** | Screen 1: Readiness Dashboard & 15-Domain Scorecard Integrity | 30 minutes |
| **Day 2** | 2026-10-13 | **S03** | Screen 2: Evidence Inventory Indexing & Preserved Checksum Stability | 30 minutes |
| **Day 2** | 2026-10-13 | **S04** | Screen 3: Manifest Cryptographic Verification & Row Conservation ($S = N + R$) | 30 minutes |
| **Day 3** | 2026-10-14 | **S05** | Screen 4: Halted-Batch Invariant Inspection & Resume Prohibition | 30 minutes |
| **Day 3** | 2026-10-14 | **S06** | Screen 5: Operational Drill Verification & Exit-Code Separation | 30 minutes |
| **Day 4** | 2026-10-15 | **S07** | Screen 6: Backup & Restore Disaster Recovery Verification | 30 minutes |
| **Day 4** | 2026-10-15 | **S08** | Screen 7: Governance Blockers & Owner Decision Quarantine | 30 minutes |
| **Day 5** | 2026-10-16 | **S09** | Screen 8: Authorization Registry & Zero Active Marker Verification | 30 minutes |
| **Day 5** | 2026-10-16 | **S10** | Screen 9: Metadata Audit Bundle Export & Screen 10 Synthetic Demo | 30 minutes |
| **Total** | **5 Days** | **10 Sessions** | **Cumulative Minimum Operating Evaluation Time** | **300 minutes (5.0 hrs)** |

---

## 4. Quantitative Acceptance Thresholds & Quality Gates

Each session must satisfy 100% of the following quantitative acceptance criteria:

| Metric ID | Criterion Description | Required Value | Severity if Breached |
| :--- | :--- | :---: | :---: |
| **ACC-MET-01** | Session Pass Rate | $100.0\%$ (10 of 10) | Critical Fail |
| **ACC-MET-02** | Cumulative Operating Time | $\ge 300\text{ minutes}$ (5.0 hrs) | Critical Fail |
| **ACC-MET-03** | External Network Requests | Exactly 0 | Critical Fail |
| **ACC-MET-04** | Evidence Modifications / Mutations | Exactly 0 | Critical Fail |
| **ACC-MET-05** | Active Authorization Markers Created | Exactly 0 | Critical Fail |
| **ACC-MET-06** | Single-Instance Lock Release Rate | $100.0\%$ (all sessions released) | Critical Fail |
| **ACC-MET-07** | Git Repository Market Data Writes | Exactly 0 | Critical Fail |
| **ACC-MET-08** | Secret Redaction Compliance | $100.0\%$ (0 credentials leaked) | Critical Fail |
| **ACC-MET-09** | Test Suite Regressions | Exactly 0 (all 811 pass) | Critical Fail |
| **ACC-MET-10** | Dependency Breakages (`pip check`) | Exactly 0 | Critical Fail |

---

## 5. Session Evidence Logging Specification

All acceptance evidence is persisted outside Git under:
`C:\Users\r_chh\gaurvideep_phase7_staging\nse500\acceptance_4_13\sessions\`

### JSON Record Schema per Session (`session_<ID>.json`):
```json
{
  "session_id": "S01",
  "day": 1,
  "date_utc": "2026-10-12",
  "start_timestamp_utc": "2026-10-12T06:50:00Z",
  "end_timestamp_utc": "2026-10-12T07:20:00Z",
  "operating_time_seconds": 1800,
  "operating_time_minutes": 30.0,
  "screens_evaluated": [1, 2],
  "starting_state": "STARTING",
  "final_state": "READY_READ_ONLY",
  "single_instance_lock_acquired": true,
  "single_instance_lock_released": true,
  "network_quarantine_active": true,
  "network_request_count": 0,
  "evidence_mutation_count": 0,
  "active_markers_count": 0,
  "session_exit_code": 0,
  "status": "PASS"
}
```

Upon completion of all 10 sessions, a master reconciliation summary (`acceptance_master_summary.json`) aggregates the cumulative operational hours, verification checks, and final acceptance verdict.

---

## 6. Milestone 4.13A Real-Time Acceptance Evidence Semantics

Under Project Owner Directive **Milestone 4.13A: Correct Operator Acceptance Evidence Semantics**, the acceptance harness and evaluation engine enforce strict real-time audit semantics.

### 6.1 Session Classification Semantics
To prevent dry-run workflows or pre-written artifacts from masquerading as completed acceptance proof, all sessions are strictly typed:
1. `ACCEPTANCE_HARNESS_DRY_RUN`: Harness validation and dry-run workflow demonstrations. Preserved in external staging but excluded from acceptance totals.
2. `SIMULATED_SESSION`: Simulated execution records. Strictly excluded from acceptance totals.
3. `REAL_OPERATOR_SESSION`: Genuine real-time operator sessions executed on live dates. Only these records contribute to acceptance totals.

### 6.2 Strict Governance Invariants
The evaluation engine (`OperatorAcceptanceEvaluator`) enforces:
1. **Measured Duration from Actual Timestamps:** Duration is calculated strictly as `(end_timestamp - start_timestamp).total_seconds()`. Caller-declared duration is rejected as proof of acceptance (`DURATION_MISMATCH_REJECTED`).
2. **Future Timestamp Rejection:** Any session record or summary dated in the future relative to system execution time is rejected (`FUTURE_TIMESTAMP_REJECTED`).
3. **Dry-Run & Simulated Exclusion:** Dry-run and simulated sessions are tracked separately and excluded from totals.
4. **Overlapping Session Interval Rejection:** Overlapping session intervals are rejected (`OVERLAPPING_SESSION_REJECTED`).
5. **Duplicate Session ID Rejection:** Duplicate session identifiers are rejected (`DUPLICATE_SESSION_REJECTED`).
6. **Five Distinct Working Dates Required:** Acceptance requires sessions across at least 5 distinct working calendar dates (`FIVE_DISTINCT_DATES_REQUIRED`).
7. **Ten Real Sessions Required:** Acceptance requires at least 10 `REAL_OPERATOR_SESSION` records (`TEN_REAL_SESSIONS_REQUIRED`).
8. **18,000 Seconds (5.0 Hours) Required:** Total measured operating time across real sessions must reach at least 18,000.0 seconds (`FIVE_HOURS_REQUIRED`).
9. **Two Verified Post-Restart Sessions Required:** At least 2 genuine post-restart sessions must be verified (`POST_RESTART_SESSIONS_REQUIRED`).
10. **Prohibition of Premature Closure:** The acceptance exercise cannot be closed before the authorized end date `2026-10-16` (`PREMATURE_CLOSURE_REJECTED`).

### 6.3 Current Acceptance Status
As of **2026-10-12**, existing harness demonstration sessions have been preserved and reclassified as `ACCEPTANCE_HARNESS_DRY_RUN`. The acceptance master summary records:
- `acceptance_status`: **`INTERNAL_OFFLINE_OPERATOR_ACCEPTANCE_IN_PROGRESS`**
- `acceptance_passed`: **`false`**
- `real_operator_sessions_count`: **`0`**
- `dry_run_sessions_count`: **`10`**
- `total_real_operating_seconds`: **`0.0`**

The final status may become:
**`INTERNAL_OFFLINE_OPERATOR_ACCEPTANCE_PASSED`**
strictly on or after **2026-10-16**, after five actual working dates, ten real sessions, five measured operating hours, and two verified post-restart sessions are genuinely completed. Pre-writing or fabricating future sessions is strictly prohibited.
