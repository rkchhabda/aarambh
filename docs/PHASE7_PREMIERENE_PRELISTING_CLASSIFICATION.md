# Phase 7 PREMIERENE Pre-Listing Classification Record

## 1. Security Overview

| Attribute | Governed Value |
|---|---|
| Symbol | `PREMIERENE` |
| Security Name | `Premier Energies Limited` |
| Exchange | `NSE` |
| Requested Historical Window | `2024-01-01` through `2024-03-31` (Q1 2024) |
| Source Panel Version | `CURRENT_NIFTY500_09Oct2026_8F4C439F` |
| Observed Historical Rows | 0 (empty response `[]`) |

---

## 2. Retrospective Classification Evaluation

Under Phase 7 governance rules:
1. **Rule 1 (Empty Response Inadequacy):** An empty upstream response alone cannot establish listing date, pre-listing status, or delisting.
2. **Rule 2 (Independent Proof Requirement):** Pre-listing status (`NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED`) strictly requires verified documentary listing evidence establishing $\text{listing\_date} > \text{requested\_end\_date}$ (`2024-03-31`).
3. **Rule 3 (Current Evidence Pilot Result):** Milestone 4.10C-2 evidence acquisition halted on a pre-request domain safety check (`PREMIERENE_LISTING_EVIDENCE_PILOT_HALTED_ON_SAFETY_CONTROL`). The single-use authorization marker was consumed without network transmission.
4. **Current Status:** In the absence of verified documentary evidence, the classification falls back fail-closed to:
   - **Listing Date Status:** `LISTING_DATE_UNVERIFIED`
   - **Verification Status:** `UNVERIFIED`
   - **Retrospective Outcome:** `EMPTY_RESPONSE_UNEXPLAINED`
5. **Domain Validation Correction (Milestone 4.10C-3):** Canonical exact-host validation was corrected and regression-tested to recognize `www.sebi.gov.in` alongside `nsearchives.nseindia.com`. Candidate URLs verified statically as `ACCEPTED`. Awaiting owner re-authorization (`RE-AUTHORIZE MILESTONE 4.10C-2 AFTER DOMAIN VALIDATION FIX`) with a new single-use marker.

---

## 3. Governance Constraints and Invariants

- The halted Milestone 4.10C batch run remains immutable at symbol index 0 (`PREMIERENE`).
- Zero ad-hoc symbol replacements or exclusions are permitted.
- Selection checksum (`60dd0358...`) and ordered-symbol hash (`26e4be7c...`) remain frozen.
- Milestone 5 remains strictly quarantined.
- BLK-02 remains gated pending official evidence alignment.
