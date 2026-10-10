# Phase 7 PREMIERENE Listing Evidence Manifest Reference

## 1. Scope and Manifest Pointer

This document records the external staging references and manifest status for Milestone 4.10C-2: PREMIERENE Official Listing Date Evidence Pilot.

External Staging Root:
`C:\Users\r_chh\gaurvideep_phase7_staging\nse500\batch_4_10c\listing_evidence\PREMIERENE`

---

## 2. Authorization Token Reference

| Field | Value |
|---|---|
| Milestone | `4.10C-2` |
| Scope | `OFFICIAL_LISTING_DATE_EVIDENCE_PILOT` |
| Symbol | `PREMIERENE` |
| Security Name | `Premier Energies Limited` |
| Exchange | `NSE` |
| Requested Period End | `2024-03-31` |
| Staging Root Hash | `212f204efe6f9eb16dab9ca5b44f0ad2562e6a0012f315c31032d77b4406de0c` |
| Nonce | `ff083095-6cb7-46b6-8942-a60f7a1cdc77` |
| Authorization Hash | `15ea408312035ab55dd4340a390ad7e1ee5644be501aa472a3ef61e715a62c8f` |
| Issued Timestamp | `2026-10-10T12:08:28.530523+00:00` |
| Consumed Timestamp | `2026-10-10T12:08:40Z` |
| Consumed Marker Path | `authorization/listing_evidence_authorization.consumed.20261010T120840Z.json` |
| Active Markers Remaining | 0 |

---

## 3. Evidence Artifact Status

| Directory | Expected Artifact | Status | Notes |
|---|---|---|---|
| `authorization/` | Consumed Marker | `PRESENT` | Verified consumed atomically |
| `raw/` | Official PDFs / HTML | `NONE` | Network dispatch aborted by domain safety control |
| `extracted/` | Extracted Evidence JSON | `NONE` | Not generated due to pre-request halt |
| `manifests/` | Final Manifest | `NONE` | Pilot halted before evidence finalization |
| `audit/` | Retrospective Record | `NONE` | Existing retrospective classification unchanged |
| `logs/` | Execution Log | `TERMINATED` | Exit code 5 recorded |

---

## 4. Governed Invariants

1. **Git Isolation:** Zero evidence files, downloaded PDFs, or HTML payloads reside within the Git repository.
2. **Single-Use Enforcement:** The authorization marker was consumed atomically prior to any network activity and cannot be reused.
3. **No Market Data Leak:** Zero historical market prices were requested.
4. **Current Status:** Halted on safety control; PREMIERENE listing date remains `LISTING_DATE_UNVERIFIED`.
