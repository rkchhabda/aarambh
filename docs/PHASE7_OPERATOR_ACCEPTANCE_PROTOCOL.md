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

---

## 7. Milestone 4.13B Two-Phase Real Operator Session Lifecycle

Under Project Owner Directive **Milestone 4.13B: Implement Two-Phase Real Operator Session Lifecycle**, the acceptance runner provides an interactive, stateful, auditable two-phase lifecycle CLI to establish genuine non-overlapping operator sessions lasting at least 1,800 measured seconds.

### 7.1 Architecture & Governed CLI Subcommands
The CLI entry point is invoked via:
`.venv-phase7\Scripts\python.exe -m phase7.operator.acceptance_runner <subcommand>`

The runner exposes six governed subcommands:
1. `start-session`: Validates session parameters, acquires the single-instance session process lock, captures internal UTC and monotonic start timestamps, host identity, boot timestamp, and git HEAD, and atomically creates an immutable active in-progress state (`.active.json`).
2. `status`: Displays governed metadata for active sessions, including elapsed seconds, application state, network quarantine state, and eligibility for finalization (`MINIMUM_REAL_DURATION_NOT_YET_MET` displayed if $< 1,800$s).
3. `finalize-session`: Validates the active in-progress record checksum, session lock, verifies wall-clock and monotonic duration ($\ge 1,800$s for `PASS`, material divergence $\le 5$s), verifies zero network requests/evidence mutations/active markers, sanitizes observations and defect references, atomically persists the final record to `real_sessions/`, clears in-progress state and lock, and recomputes the master summary.
4. `abort-session`: Aborts an active session with reason code, captures end timestamp internally, preserves elapsed operating seconds and in-progress audit history, marks record as `status: ABORTED`, releases lock, and updates master summary without contributing to passed totals.
5. `validate-session`: Cryptographically and structurally validates on-disk session records against the real session schema and governance invariants.
6. `summarize`: Recomputes the master acceptance summary strictly partitioning `REAL_OPERATOR_SESSION` passed records from dry-run, simulated, or aborted records.

### 7.2 Governed Exit Codes
All CLI commands return stable, standardized numeric exit codes:
- `0`: Command completed successfully (`SUCCESS`).
- `2`: Argument or schema validation failure (`SCHEMA_VALIDATION_ERROR`).
- `3`: Session lifecycle conflict (`LIFECYCLE_CONFLICT`).
- `4`: Session lock acquisition or release failure (`LOCK_FAILURE`).
- `5`: Timestamp or duration validation failure (`TIMESTAMP_OR_DURATION_FAILURE`).
- `6`: Integrity or checksum validation failure (`INTEGRITY_FAILURE`).
- `7`: Governance boundary violation (`GOVERNANCE_BOUNDARY_FAILURE`).
- `8`: Session incomplete or minimum duration not met (`SESSION_INCOMPLETE_OR_MINIMUM_DURATION_NOT_MET`).
- `9`: Network or evidence-mutation safety failure (`NETWORK_OR_EVIDENCE_MUTATION_FAILURE`).
- `10`: Unexpected internal error (`UNEXPECTED_INTERNAL_ERROR`).

### 7.3 Governed Identifier & Schema Contracts
1. **Session Identifiers:** Must match regex `^REAL-S[0-9]{2}$` (`REAL-S01` through `REAL-S99`). Arbitrary strings, paths, and URLs are rejected.
2. **Operator Roles:** Strictly restricted to `OWNER` and `AUTHORIZED_INTERNAL_OPERATOR`.
3. **Interface Modes:** Permitted modes are `CLI` and `GUI` (with `CORE` restricted to dry-run/synthetic harnesses).
4. **Governed Workflows:** Restricted to approved workflow enums:
   - `READINESS_DASHBOARD_AND_LIFECYCLE` (Bound to `REAL-S01`)
   - `EVIDENCE_INVENTORY_AND_FILE_HEALTH` (Bound to `REAL-S02`)
   - `GUI_READINESS_AFTER_RESTART`
   - `MANIFEST_AND_CHECKSUM_VERIFICATION`
   - `HALTED_BATCH_INSPECTION`
   - `OPERATIONAL_DRILL_REVIEW`
   - `BACKUP_AND_RESTORE_VERIFICATION`
   - `GOVERNANCE_BLOCKERS_AND_AUTHORIZATION`
   - `METADATA_ONLY_AUDIT_EXPORT`
   - `FULL_APPLICATION_QUARANTINE_AND_SHUTDOWN`
5. **Defect References:** Governed defect identifiers must match `^OPACC-[0-9]{8}-[0-9]{3,}$` (e.g. `OPACC-20261013-001`).
6. **Operator Observations:** Length-limited (maximum 1,024 characters), stripped of control characters, tokens, passwords, and raw trade/market rows.

### 7.4 External Directory Layout
All session artifacts reside strictly outside the Git repository in external staging:
```
<acceptance_root>\
    in_progress\
        REAL-S01.active.json
    real_sessions\
        REAL-S01.final.json
    locks\
        REAL-S01.lock
    audit\
        session_lifecycle.jsonl
    sessions\
        session_s01.json ... session_s10.json (preserved 10 dry-run records)
    acceptance_master_summary.json
```
