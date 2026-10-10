# Phase 7 Offline Fault-Injection Protocol
**Milestone:** 4.11: Offline Internal Production-Readiness Hardening  
**Status:** GOVERNED PROTOCOL  
**Isolation Boundary:** Synthetic External Staging Only  

---

## 1. Overview and Invariants
This protocol governs fault-injection and crash simulation procedures across Phase 7 batch acquisition and normalization pipelines.

All fault injection tests operate strictly offline against temporary synthetic data in external staging. No injection is permitted to touch:
- Frozen five-stock capability sample (`pilot_4_9`);
- Frozen NIFTY 500 snapshot (`snapshot_4_10a`);
- Frozen 20-stock batch run evidence (`batch_4_10c`);
- Git repository code trees or Phase 6 vaults.

---

## 2. Injection Lifecycle Taxonomy
The pipeline exposes 20 discrete lifecycle points where controlled faults may be triggered:

```
[Init]
  │
  ├─► crash_before_marker_consumption
  ├─► crash_during_marker_consumption
  ├─► crash_after_marker_consumption
  │
  ├─► crash_before_client_creation
  ├─► crash_after_client_creation
  │
  ├─► crash_before_first_request
  ├─► crash_after_request_dispatch
  ├─► crash_after_response_receipt
  │
  ├─► crash_before_raw_persistence
  ├─► crash_after_raw_persistence
  ├─► crash_before_raw_checksum_recording
  │
  ├─► crash_during_normalization
  ├─► crash_after_normalized_persistence
  ├─► crash_before_normalized_checksum_recording
  │
  ├─► crash_before_manifest_finalization
  ├─► crash_after_manifest_finalization
  │
  ├─► crash_before_checkpoint_update
  ├─► crash_after_checkpoint_update
  │
  ├─► crash_before_client_close
  └─► crash_during_client_close
```

---

## 3. Supported Fault Classes
1. **Uncaught Crash (`InjectedFaultError`):**
   Simulates immediate process termination (SIGKILL, unhandled exception, power loss). Verifies that the on-disk state remains uncorrupted and inspectable.
2. **Disk Full (`InjectedDiskFullError` / Errno 28):**
   Simulates `ENOSPC` during stream write or flush. Verifies that the temporary file is unlinked, no corrupt partial final file is created, and exit code 28 is emitted.
3. **Permission Denied (`InjectedPermissionDeniedError` / Errno 13):**
   Simulates `EACCES` during file open or rename. Verifies fail-closed halt without false success.
4. **Client Close Failure (`InjectedClientCloseError`):**
   Simulates network transport closure errors. Enforces governed exit code 9 and prevents batch completion from being recorded as `SUCCEEDED`.
5. **Checksum Corruption (`corrupt_file_checksum`):**
   Deterministically flips a byte in a persisted evidence file. Verifies that resume validation detects corruption and halts immediately.

---

## 4. Governed Recovery Requirements
- **No Automatic Resume:** Resume execution must never be triggered implicitly or automatically.
- **Mandatory New Marker:** Resuming requires an explicit, active new authorization marker.
- **Replay Refusal:** Replaying a previously consumed marker is strictly rejected.
- **Immutability of Valid Evidence:** Completed evidence with verified checksums is preserved and never re-downloaded or overwritten.
- **Corrupted Evidence Halts:** Any tampered or corrupted evidence file immediately halts the resume process (exit code 1).
