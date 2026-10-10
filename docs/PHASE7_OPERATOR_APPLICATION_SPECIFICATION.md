# Phase 7 Internal Offline Operator Application Specification

**Milestone:** 4.12: Internal Offline Application Integration  
**Status:** IMPLEMENTED & VERIFIED  
**Governing Posture:** `INTERNAL_NON_DISTRIBUTED_DEVELOPMENT_ONLY`  
**Acquisition Posture:** `EXTERNAL_EVIDENCE_ACQUISITION_DEFERRED_BY_OWNER`  
**Readiness Classification:** `INTERNAL_NON_DISTRIBUTED_PRODUCTION_LIKE_READINESS_CONFIRMED`  

---

## 1. Executive Objective & Boundaries

Milestone 4.12 establishes a unified, read-only, offline operator console integrating the verified Phase 7 evidence-management and acquisition-control framework.

### Governing Operational Invariants:
1. **Local and Offline:** Zero network binding, zero external requests, zero sockets.
2. **Internal & Non-Distributed:** Dedicated exclusively to internal pipeline monitoring and governance audit.
3. **Fail-Closed & Single-Instance:** Enforces exclusive process lock preventing concurrent execution.
4. **Read-Only on Preserved Evidence:** Strictly refuses file edits, unlinking, renaming, overwriting, automatic repairs, or fallback generation.
5. **No Production API:** Strictly prohibited from starting FastAPI, Uvicorn, or exposing any network interface.
6. **Milestone 5 Blocked:** Zero model training, zero target generation, zero financial metrics.

---

## 2. Mandatory Governance Banners

Every screen, view, CLI output, and GUI window prominently displays the four mandatory governance banners:

```
[BANNER] INTERNAL NON-DISTRIBUTED USE ONLY
[BANNER] EXTERNAL ACQUISITION DEFERRED BY OWNER
[BANNER] GATE 1 NOT PASSED
[BANNER] MILESTONE 5 BLOCKED
```

---

## 3. Network Quarantine Architecture

The application enforces runtime network quarantine via `NetworkQuarantineManager` in [phase7/operator/network_quarantine.py](file:///c:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/phase7/operator/network_quarantine.py):
- **Intercepted Interfaces:**
  - `socket.socket.connect`
  - `socket.create_connection`
  - `httpx.Client.send`
  - `urllib.request.urlopen`
  - `requests.Session.send` (if installed)
  - `asyncio.BaseEventLoop.create_connection`
- **Enforcement Action:**
  - Raises `NetworkOperationBlockedError`: `"NETWORK_OPERATION_BLOCKED_BY_INTERNAL_OFFLINE_POLICY"`
  - Emits sanitized audit record: captures timestamp UTC, caller location, and target.
  - Performs zero retries.
  - Leaves the application in strict read-only mode.

---

## 4. Single-Instance Process Locking

Single-instance protection is implemented via `SingleInstanceLock` in [phase7/operator/single_instance.py](file:///c:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/phase7/operator/single_instance.py):
- Leverages `DirectoryProcessLock` to acquire exclusive filesystem ownership.
- Refuses concurrent application launches with `SingleInstanceLockError`.
- Cleanly releases lock upon normal exit or exception handling.

---

## 5. Read-Only Evidence Guarantees

Preserved evidence immutability is guarded by `ReadOnlyEvidenceGuard` in [phase7/operator/read_only_guard.py](file:///c:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/phase7/operator/read_only_guard.py):
- **Protected Staging Domains:** `pilot_4_9`, `snapshot_4_10a`, `batch_4_10c`, `production_readiness_4_11`.
- **Prohibited Operations:**
  - File editing, renaming, unlinking, or overwrite (`ReadOnlyViolationError`).
  - Checksum replacement or manifest repair (`refuse_manifest_repair`).
  - Checkpoint repair (`refuse_checkpoint_repair`).
  - Marker restoration or consumption (`refuse_marker_restoration`, `refuse_marker_consumption`).
  - Automatic batch resume (`refuse_automatic_resume`).
  - Fallback synthetic data generation (`refuse_fallback_generation`).
- **Inspection Invariant:** Missing or corrupted files produce visible fail-closed statuses (`EVIDENCE_MISSING`, `CHECKSUM_MISMATCH_CORRUPT`) without attempting repair.

---

## 6. Specification of the 10 Governed Views

The operator console implements 10 views coordinated by `OperatorCore` in [phase7/operator/core.py](file:///c:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/phase7/operator/core.py):

| # | Screen / View | Domain | Core Implementation & Features |
|---|---|---|---|
| **01** | **Readiness Dashboard** | Readiness Status | Displays overall classification `INTERNAL_NON_DISTRIBUTED_PRODUCTION_LIKE_READINESS_CONFIRMED`, test counts (794 passing: 544 baseline + 250 new), drill counts (16/16), and the 15-domain scorecard table. |
| **02** | **Evidence Inventory** | External Evidence | Discovers, categorizes, and indexes all 98 preserved evidence assets across external staging, calculating SHA-256 digests and immutability flags. |
| **03** | **Manifest Verifier** | Manifest & Checksums | Cryptographically verifies on-disk manifests, checks evidence existence and hashes, and verifies row conservation equation ($S = N + R$) without automatic repair. |
| **04** | **Batch-State Viewer** | Batch Progress | Visualizes halted batch `batch_4_10c`, contract metadata, checkpoint progress (0 completed, 1 failed, 19 pending), and enforces non-resume policy. |
| **05** | **Operational-Drill Viewer** | Operational Drills | Inspects all 16 drills (`DRILL-01` to `DRILL-16`), showing runner exit code (0), SUT exit code (1, 28, 13, 9, 0), pass status, and disambiguates runner vs SUT semantics. |
| **06** | **Backup & Restore Verifier** | Disaster Recovery | Verifies backup archive `BK-D15` bit-for-bit against source evidence, confirms zero data loss, and verifies temporary file exclusion (`.tmp.*`). |
| **07** | **Governance & Blockers** | Governance Status | Displays Owner Decision `DEC-20261010-36`, Gate 1 `NOT_PASSED`, Milestone 5 `BLOCKED`, and active blocker statuses (`BLK-01`, `BLK-02`, `BLK-04` STILL_BLOCKED, `BLK-03` RESOLVED). |
| **08** | **Authorization Registry** | Acquisition Gates | Catalogs all consumed markers, verifies 0 active markers, and strictly prohibits marker generation or replay. |
| **09** | **Metadata Audit Export** | Compliance Audit | Exports sanitized JSON bundle containing inventory hashes, scorecard, and blockers; verifies zero trade prices, quotes, or secrets are exported. |
| **10** | **Synthetic Demo Mode** | Demonstration Mode | Runs an isolated 5-ticker synthetic demonstration outside staging, demonstrating clean processing and fail-closed tamper detection. |

---

## 7. Dual-Interface Capabilities

The application supports dual presentation modes:
1. **Standard-Library CLI/TUI ([phase7/operator/cli.py](file:///c:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/phase7/operator/cli.py)):**
   - Headless navigation via `--screen 1..10`, `--all`, `--demo`, `--export`.
   - Interactive terminal menu via `--interactive`.
   - Formatted ASCII tables with all 4 mandatory banners.
2. **Tkinter Desktop GUI ([phase7/operator/gui.py](file:///c:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/phase7/operator/gui.py)):**
   - Launched via `--gui`.
   - Bold banner header, tabbed notebook navigation (`ttk.Notebook`), Treeview grids.
   - Built-in "Simulate Network Call" button to verify quarantine dialog.

---

## 8. Verification Results

- **Operator Test Battery:** 17 tests added in [tests/phase7/test_operator_app.py](file:///c:/Users/r_chh/OneDrive%20-%20optgbrc/Apps/GaurviDEEP/tests/phase7/test_operator_app.py) (100% passing).
- **Total Test Suite:** **811 of 811 passing** (`544 baseline + 250 Milestone 4.11 + 17 Milestone 4.12`).
- **Dependencies:** Clean (`pip check` verified).
- **Network Requests:** Exactly 0.
- **Repository Market Data Writes:** Exactly 0.
