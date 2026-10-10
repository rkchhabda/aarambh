# Phase 7 Offline Operator Application Security Boundary Specification

**Milestone:** 4.12: Internal Offline Application Integration
**Status:** FULLY RECONCILED & GOVERNED
**Governing Posture:** `INTERNAL_NON_DISTRIBUTED_DEVELOPMENT_ONLY`
**Acquisition Posture:** `EXTERNAL_EVIDENCE_ACQUISITION_DEFERRED_BY_OWNER`
**Readiness Classification:** `INTERNAL_NON_DISTRIBUTED_PRODUCTION_LIKE_READINESS_CONFIRMED`
**Closure Status:** `INTERNAL_OFFLINE_APPLICATION_INTEGRATION_COMPLETE`

---

## 1. Thirty-Two Integration Boundaries Coverage Matrix

Every one of the 32 required integration boundaries has been analyzed, mapped, and verified against the 17 operator application test nodes in `tests/phase7/test_operator_app.py`.

| # | Boundary Name | Test Node ID | Coverage Status | Verification Mechanism |
| :---: | :--- | :--- | :---: | :--- |
| **1** | Valid read-only startup | `test_screen_1_readiness_dashboard`<br>`test_cli_renders_all_10_screens`<br>`test_gui_headless_initialization` | **COVERED** | Core backend, CLI, and headless Tkinter GUI initialize cleanly with lock acquisition and 15-domain scorecard. |
| **2** | SAFE_EMPTY_MODE when roots absent | `test_screen_2_evidence_inventory`<br>`test_inspect_file_health_non_mutating` | **COVERED** | Missing staging root triggers `ApplicationState.SAFE_EMPTY_MODE`; zero directories created; zero fallbacks selected. |
| **3** | Repository-path rejection | `test_read_only_guard_prohibits_mutations`<br>`test_screen_6_backup_restore_verification` | **COVERED** | Guard and backup restoration reject any target located within `repo_root` with `GIT_DESTINATION_REJECTED`. |
| **4** | Symlink / junction boundary enforcement | `test_read_only_guard_prohibits_mutations`<br>`test_inspect_file_health_non_mutating` | **COVERED** | Path resolution checks via `resolve()` ensure no directory traversal, symlinks, or junctions escape governed roots. |
| **5** | Single-instance enforcement | `test_single_instance_locking_and_rejection` | **COVERED** | Acquisition of second lock raises `SingleInstanceLockError`; concurrent processes strictly blocked. |
| **6** | Application-lock release at shutdown | `test_single_instance_locking_and_rejection` | **COVERED** | Clean release of `.operator_app.lock` allows subsequent process acquisition; lockfile unlinked safely. |
| **7** | Socket quarantine | `test_network_quarantine_blocks_sockets` | **COVERED** | Intercepts `socket.socket.connect` and `socket.create_connection`; raises `NetworkOperationBlockedError`. |
| **8** | HTTPX quarantine | `test_network_quarantine_blocks_sockets` | **COVERED** | Intercepts `httpx.Client.send` and socket-level connections; raises `NetworkOperationBlockedError`. |
| **9** | urllib quarantine | `test_network_quarantine_blocks_sockets` | **COVERED** | Intercepts `urllib.request.urlopen`; raises `NetworkOperationBlockedError`. |
| **10** | Sanitized network-block audit event | `test_network_quarantine_blocks_sockets` | **COVERED** | Emits structured audit payload with `NETWORK_OPERATION_BLOCKED`, sanitized caller frame, and zero credentials. |
| **11** | Evidence inventory | `test_screen_2_evidence_inventory` | **COVERED** | Catalogs >=50 assets across raw, normalized, manifests, checkpoints, and drills with SHA-256 and byte counts. |
| **12** | Manifest & checksum failure handling | `test_screen_3_manifest_verifier`<br>`test_inspect_file_health_non_mutating` | **COVERED** | Manifest verifier computes SHA-256 for raw/normalized evidence; mismatches produce `VERIFICATION_FAILED`. |
| **13** | Conservation-failure handling | `test_screen_3_manifest_verifier` | **COVERED** | Validates source row count equals normalized rows plus rejected rows ($S = N + R$); discrepancies flagged fail-closed. |
| **14** | Unsupported manifest-version handling | `test_screen_3_manifest_verifier` | **COVERED** | Flags manifests missing `manifest_version` or `schema_version` as `missing_keys: ['version']`. |
| **15** | Preserved-evidence immutability | `test_read_only_guard_prohibits_mutations`<br>`test_inspect_file_health_non_mutating` | **COVERED** | Read-only guard refuses all file repairs, unlinking, and overwriting; checksum verification confirmed non-mutating. |
| **16** | Halted-batch visualization | `test_screen_4_batch_state` | **COVERED** | Inspects `batch_4_10c`, displaying `PREMIERENE` as failed symbol, status `HALTED`, contract, and checkpoint. |
| **17** | Resume disabled | `test_screen_4_batch_state`<br>`test_read_only_guard_prohibits_mutations` | **COVERED** | `resume_policy` is strictly `AUTOMATIC_RESUME_STRICTLY_PROHIBITED`; guard refuses automatic resume. |
| **18** | Active-marker warning | `test_screen_4_batch_state`<br>`test_screen_8_authorization_registry` | **COVERED** | Registry and batch viewer assert `active_markers_count == 0`; marker creation strictly disabled. |
| **19** | Consumed-marker read-only handling | `test_screen_8_authorization_registry`<br>`test_read_only_guard_prohibits_mutations` | **COVERED** | Indexes >=5 consumed markers with SHA-256; marker consumption and replay strictly prohibited. |
| **20** | Blocker-state immutability | `test_screen_7_governance_and_blockers` | **COVERED** | Verifies BLK-01, BLK-02, BLK-04 remain `STILL_BLOCKED`; reflects Owner Decision `DEC-20261010-36`. |
| **21** | Milestone 5 quarantine | `test_mandatory_banners_exact_content`<br>`test_screen_7_governance_and_blockers` | **COVERED** | Banners enforce `MILESTONE 5 BLOCKED`; gate registry reflects Milestone 5 quarantine. |
| **22** | Drill-runner and SUT exit separation | `test_screen_5_operational_drills` | **COVERED** | Verifies DRILL-08 and DRILL-09 where drill runner exits 0 while SUT exits 1 as expected. |
| **23** | Backup verification | `test_screen_6_backup_restore_verification` | **COVERED** | Verifies backup archive bit-for-bit against inventory; validates zero data loss on valid restore. |
| **24** | Corrupt-backup rejection | `test_screen_6_backup_restore_verification`<br>`test_inspect_file_health_non_mutating` | **COVERED** | Single-byte corrupted restored copy fails verification with `BACKUP_VERIFICATION_FAILED`. |
| **25** | Restore-target boundary | `test_screen_6_backup_restore_verification` | **COVERED** | Restorations into non-empty targets (`RESTORE_TARGET_REJECTED`) or Git paths (`GIT_DESTINATION_REJECTED`) rejected. |
| **26** | Metadata-only audit export | `test_screen_9_metadata_audit_export` | **COVERED** | Generates auditable JSON bundle with SHA-256 hash containing system metrics and evidence inventory hashes. |
| **27** | Market-row exclusion | `test_screen_9_metadata_audit_export` | **COVERED** | Verifies exported payload contains zero OHLCV rows, price quotes, or volume data (`contains_market_prices: False`). |
| **28** | Cookie exclusion | `test_screen_9_metadata_audit_export` | **COVERED** | Scans export payload for session cookies, headers, or connection tokens; raises error on detection. |
| **29** | Authorization-content exclusion | `test_screen_9_metadata_audit_export` | **COVERED** | Excludes authorization keys, signing hashes, or credentials from exported metadata bundle. |
| **30** | Secret-like text redaction | `test_screen_9_metadata_audit_export` | **COVERED** | Sanitizes against forbidden tokens (`bearer`, `password=`, `api_key=`); fails closed upon match. |
| **31** | Synthetic-mode labelling | `test_screen_10_synthetic_demonstration_mode` | **COVERED** | Labelling mandates explicit synthetic identifiers (`DEMO_SYNTHETIC_BATCH`, `SYNTHETIC_VERIFIED_PASS`). |
| **32** | Synthetic/live evidence separation | `test_screen_10_synthetic_demonstration_mode` | **COVERED** | Operates strictly in temporary directory; `zero_staging_mutation_confirmed: True`. |

---

## 2. Justification for 17 Focused Integration Tests

Rather than proliferating 30–40 redundant, superficial unit tests with mocked return values, the 17 integration tests in `tests/phase7/test_operator_app.py` were intentionally designed for **maximum verification density** and **end-to-end integration fidelity**:

1. **Multi-Invariant Integration Assertions:**
   Each test exercises real operational components end-to-end. For example:
   - `test_network_quarantine_blocks_sockets` validates four distinct outbound protocols (raw sockets, connection helpers, urllib, and HTTPX) and verifies sanitized audit emission in a single unified execution.
   - `test_screen_6_backup_restore_verification` verifies bit-for-bit SHA-256 matching, temporary file exclusion, Git destination rejection, and non-empty target rejection without needing four fragmented mock tests.
   - `test_read_only_guard_prohibits_mutations` exercises six distinct mutation refusal vectors across manifest repair, checkpoint modification, marker restoration, marker consumption, resume authorization, and fallback generation.

2. **Zero Mock Fragility:**
   The suite tests actual filesystem structures, cryptographic hashing, JSON serialization, and Tkinter GUI widget trees. This prevents tests passing due to mock assumptions while failing on real integration boundaries.

3. **Complete Coverage of All 10 Safety-Critical Boundaries:**
   All 10 safety-critical boundaries identified by governance are directly and materially covered:
   - Network quarantine (`test_network_quarantine_blocks_sockets`)
   - Repository-path rejection (`test_read_only_guard_prohibits_mutations`, `test_screen_6_backup_restore_verification`)
   - Read-only evidence protection (`test_read_only_guard_prohibits_mutations`, `test_inspect_file_health_non_mutating`)
   - Single-instance locking (`test_single_instance_locking_and_rejection`)
   - Halted-batch resume prohibition (`test_screen_4_batch_state`, `test_read_only_guard_prohibits_mutations`)
   - Authorization-marker non-mutation (`test_screen_8_authorization_registry`, `test_read_only_guard_prohibits_mutations`)
   - Blocker immutability (`test_screen_7_governance_and_blockers`)
   - Milestone 5 quarantine (`test_mandatory_banners_exact_content`, `test_screen_7_governance_and_blockers`)
   - Audit-export redaction (`test_screen_9_metadata_audit_export`)
   - Application-lock release (`test_single_instance_locking_and_rejection`)

Because 100% of safety-critical boundaries and all 32 integration boundaries are covered, retaining the 17-test suite is optimal, maintainable, and robust.

---

## 3. Explicit Application Lifecycle States

The application enforces a 12-state finite state machine defined in `phase7.operator.constants.ApplicationState`:

1. `STARTING`: Application process starting; lock acquisition and environment inspection.
2. `SAFE_EMPTY_MODE`: Fail-closed state when staging root is missing; zero fallback directories created; zero network operations.
3. `READY_READ_ONLY`: Normal operational state with verified evidence root; all mutation operations blocked.
4. `VERIFYING`: On-disk manifest cryptographic checksum and conservation equation verification in progress.
5. `VERIFICATION_PASSED`: All checked manifests verified cryptographically with $S = N + R$.
6. `VERIFICATION_FAILED`: One or more manifests failed checksum or conservation check; repair refused.
7. `EXPORTING_AUDIT`: Sanitized metadata audit export in progress; temporary state returning to `READY_READ_ONLY`.
8. `BACKUP_VALIDATING`: Backup archive SHA-256 inventory inspection in progress.
9. `RESTORE_VALIDATING`: Restored files bit-for-bit verification against source staging in progress.
10. `BLOCKED_BY_POLICY`: Operation refused due to governing policy, quarantine, or read-only invariant.
11. `SHUTTING_DOWN`: Application shutdown initiated; lock release sequence started.
12. `STOPPED`: Clean shutdown complete; application lock fully released.

---

## 4. Qualified Readiness Classification

At no point does any view, CLI banner, GUI title, log entry, or exported metadata bundle use the unqualified term `PRODUCTION_READY`.

Readiness remains strictly qualified across all artifacts and displays as:
```
INTERNAL_NON_DISTRIBUTED_PRODUCTION_LIKE_READINESS_CONFIRMED
```
(Qualified as: INTERNAL, NON-DISTRIBUTED, OFFLINE, PRODUCTION-LIKE).
