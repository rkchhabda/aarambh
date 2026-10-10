# Phase 7 Backup and Restore Protocol
**Milestone:** 4.11: Offline Internal Production-Readiness Hardening  
**Status:** GOVERNED OPERATIONAL PROTOCOL  
**Storage Boundary:** Staging Only (Never committed to Git)  

---

## 1. Scope and Durability Objectives
This protocol defines the procedures for creating, validating, and restoring bit-for-bit offline backups of Phase 7 external staging environments.

Governing rules:
1. Backups must reside strictly in external staging directories, never in the Git repository.
2. Backups must preserve raw evidence, normalized evidence, manifests, checkpoints, and contracts bit-for-bit.
3. Every backup must include a signed `backup_inventory.json` recording the SHA-256 digest and size of each file.
4. Active temporary files (`.tmp.*`) and sensitive session/cookie files are strictly excluded from backup archives.
5. Restoration must be verified cryptographically against the inventory before evidence can be consumed.

---

## 2. File Exclusion Policy
To prevent archive pollution and credential leakage, the backup generator (`create_offline_backup`) applies the following exclusion rules:

```python
EXCLUDED_PATTERNS = {
    ".tmp.",           # Active or stale temporary files
    ".process_lock",   # Local process locking tokens
    "cookie",          # Session cookies
    "session",         # Ephemeral HTTP sessions
    ".cache",          # Python bytecode or runtime cache
}
```

---

## 3. Inventory Schema (`backup_inventory.json`)
The root of each backup archive contains a deterministic inventory:

```json
{
  "backup_id": "BK_20261010T120000Z",
  "created_at_utc": "2026-10-10T12:00:00+00:00",
  "source_dir": "C:/Users/.../staging",
  "file_count": 5,
  "files": [
    {
      "relative_path": "batch_contract.json",
      "sha256": "ed076001b43ab59a740859948edac11e3769ee0baa3660b28d48b5dac61b3427",
      "size_bytes": 1024
    },
    {
      "relative_path": "raw/raw_SYN0001.json",
      "sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
      "size_bytes": 12500
    }
  ]
}
```

---

## 4. Restoration and Verification Protocol
When restoring from a backup archive:
1. `restore_and_verify_backup` reads `backup_inventory.json`.
2. All archived files are restored to the target destination path.
3. Every restored file is measured for byte size and re-hashed with SHA-256.
4. If any file is missing, size differs, or SHA-256 mismatches, the restoration is flagged as `FAILED` and an error list is returned.
5. Zero network requests are made during creation or restoration.
