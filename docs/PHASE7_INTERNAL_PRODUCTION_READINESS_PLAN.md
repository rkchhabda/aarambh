# Phase 7 Internal Production-Readiness Plan
**Milestone:** 4.11: Offline Internal Production-Readiness Hardening  
**Status:** APPROVED & EXECUTED  
**Governing Posture:** `INTERNAL_NON_DISTRIBUTED_DEVELOPMENT_ONLY`  
**Acquisition State:** `EXTERNAL_EVIDENCE_ACQUISITION_DEFERRED_BY_OWNER`  

---

## 1. Executive Objective
Milestone 4.11 executes comprehensive offline internal production-readiness hardening across the Phase 7 source, persistence, manifest, checkpoint, authorization, and batch subsystems.

The objective is to establish industrial-grade fault resilience, durability, and operational security without issuing any network request, without acquiring additional external data, and strictly preserving all existing frozen evidence and Phase 6 archival vaults.

---

## 2. Hardening Scope & Workstream Matrix

| Workstream | Domain | Target Tests | Implemented Tests | Primary Protection |
|---|---|:---:|:---:|---|
| **Workstream A** | Filesystem, Atomic Persistence & Durability | ~35 | 38 | Atomic file swaps via parent temp file, fsync, Windows reserved name checks, overwrite refusal. |
| **Workstream B** | Checkpoint, Manifest & Checksum Integrity | ~35 | 35 | Cryptographic SHA-256 verification, row conservation ($S = N + R$), duplicate detection, contract matching. |
| **Workstream C** | Crash Recovery & Resume Authorization | ~30 | 30 | Fail-closed lifecycle halts across 20 points, mandatory active marker, replay refusal, corrupted evidence halts. |
| **Workstream D** | Concurrency, Process Locking & Race Conditions | ~25 | 25 | Single-writer directory locking (`.process_lock.raw`), stale lock detection, single-request semaphore ($=1$). |
| **Workstream E** | Security Boundaries & Hostile Inputs | ~40 | 51 | Shell injection, PowerShell metacharacters, path traversal, NTFS streams, Unicode bidi/slashes, NaN/Inf guard. |
| **Workstream F** | Synthetic Scale, Memory & Performance | ~25 | 25 | Deterministic synthetic universes (20, 100, 500 tickers $\times$ 65, 252, 3000 sessions), bounded peak memory (<25MB). |
| **Workstream G** | Logging, Auditability & Redaction | ~15 | 15 | Structured JSONL audit trail, token/cookie/header regex redaction, CRLF log-splitting defense. |
| **Workstream H** | Backup, Restoration & Disaster Recovery | ~15 | 15 | Bit-for-bit offline backup and restore, SHA-256 inventory verification, temporary/session file filtering. |
| **Operational Drills** | Governed Operational Drills | 16 | 16 | 16 controlled failure injection drills (DRILL-01 to DRILL-16) executed against external staging. |
| **Total Suite** | **New Automated Tests** | **~220** | **250** | **100% Passing ($38+35+30+25+51+25+15+15+16=250$; 794 total passing tests across Phase 7 & Phase 6)** |

> [!NOTE]
> **Arithmetic Reconciliation Note:** Prior draft narrative estimates had penciled Workstream A at 45 and Workstream E at 49 (which summed to 255). The exact collected test counts per module are 38 for Workstream A (`test_prod_atomic_persistence.py`) and 51 for Workstream E (`test_prod_hostile_inputs.py`). All other modules match exactly (35, 30, 25, 25, 15, 15, 16), yielding exactly 250 new tests and 794 total passing tests ($544 + 250 = 794$).

---

## 3. Core Architectural Modules (`phase7/operations/`)

1. **`phase7/operations/atomic_io.py`**:
   - Production-hardened atomic file writes via parent-directory temporary file.
   - Forced `flush()` and `os.fsync()` durability.
   - SHA-256 verification post-write.
   - Refusal of overwrite for immutable final files (`FileOverwriteRefusedError`).
   - Rejection of relative paths, repo paths, UNC paths, device paths, and NTFS stream colons.
   - Stale temporary file purger (`cleanup_stale_temporary_files`).

2. **`phase7/operations/file_lock.py`**:
   - Single-writer exclusive directory locking (`DirectoryProcessLock`).
   - Platform OS locking via `msvcrt.locking` on Windows CRT and `fcntl.flock` on POSIX.
   - Separation of low-level OS file descriptor (`.process_lock.raw`) from readable JSON metadata (`.process_lock`).
   - Stale lock detection with conservative alive PID verification (`is_pid_alive`).
   - Single-request concurrency gate (`SingleRequestGate`).

3. **`phase7/operations/integrity.py`**:
   - Manifest integrity verification (`validate_manifest_integrity`).
   - Checkpoint summary reconciliation (`validate_checkpoint_integrity`).
   - Mathematical row-count conservation ($S = N + R$).
   - Contract parameter matching (`validate_batch_contract_match`).

4. **`phase7/operations/recovery.py`**:
   - Read-only inspection of halted run directories (`inspect_run_state`).
   - Resume prerequisites validator (`validate_resume_prerequisites`).
   - Strict requirement of explicit, unconsumed authorization marker for every resume.
   - Recognition of completed valid evidence without re-downloading.

5. **`phase7/operations/backup_restore.py`**:
   - Offline bit-for-bit backup generator (`create_offline_backup`).
   - Mandatory exclusion of active temporary files (`.tmp.*`) and session/cookie files.
   - SHA-256 backup inventory manifest generation.
   - Complete restoration and cryptographic audit (`restore_and_verify_backup`).

6. **`phase7/operations/fault_injection.py`**:
   - Controlled lifecycle crash hook framework (`FaultController`, `armed_fault`).
   - Deterministic checksum corruption helper (`corrupt_file_checksum`).
   - Simulation of disk full (ENOSPC / Error 28) and permission denied (EACCES / Error 13).

7. **`phase7/operations/security_validation.py`**:
   - Ticker symbol sanitization (`validate_symbol_security`).
   - Recursive JSON depth limit guard (`validate_json_payload_depth`).
   - Non-finite numeric guard (`sanitize_numeric_values`).
   - HTML / CAPTCHA masquerade detector (`detect_html_or_captcha_masquerade`).
   - Sensitive credential and cookie redaction (`redact_sensitive_data`).

8. **`phase7/operations/scale_simulation.py`**:
   - Synthetic universe generators (`generate_synthetic_symbols`, `generate_synthetic_series`).
   - Deterministic SHA-256 series hashing (`compute_series_checksum`).
   - Memory tracking harness (`MemoryTracker`).

9. **`phase7/operations/audit_reconciliation.py`**:
   - Structured JSONL audit logger (`StructuredAuditLogger`).
   - Log injection sanitizer (`sanitize_log_message`).
   - Cross-reconciliation of audit trail with manifests and checkpoints (`reconcile_audit_trail`).

10. **`phase7/operations/drill_runner.py`**:
    - Governed executor for DRILL-01 through DRILL-16 (`OperationalDrillRunner`).
    - Staging-only output logging (`C:\Users\r_chh\gaurvideep_phase7_staging\nse500\production_readiness_4_11\drills\`).

11. **`phase7/operations/readiness_report.py`**:
    - 15-domain engineering readiness scorecard generator (`ReadinessScorecard`).

---

## 4. Governed Execution Rules
1. **Zero Outbound Sockets:** OS-level network denial fixture active across the entire test suite.
2. **Zero Commercial Deployment:** Development remains strictly internal and non-distributed.
3. **Zero Milestone 5 Activity:** Model training, target generation, and financial metrics remain prohibited.
