# Phase 7 Milestone 4.10C-2: PREMIERENE Official Listing Evidence Pilot Report

## 1. Executive Summary

Milestone 4.10C-2 authorized exactly one controlled official listing-date evidence acquisition pilot specifically for `PREMIERENE` (Premier Energies Limited) on the National Stock Exchange of India (NSE).

The pilot executed under strict cryptographic binding, single-use authorization, and fail-closed safety controls. Before any network request was dispatched, the pre-request URL validation check detected that candidate regulatory filing URL `https://www.sebi.gov.in/...` used subdomain `www.sebi.gov.in`, which was not in the authorization marker's bound exact domain whitelist (`['bseindia.com', 'nsearchives.nseindia.com', 'nseindia.com', 'sebi.gov.in']`).

In accordance with strict safety invariants:
- The single-use authorization marker was consumed atomically prior to network dispatch (`listing_evidence_authorization.consumed.20261010T120840Z.json`).
- Network dispatch was immediately aborted.
- Zero network requests were made.
- Zero unapproved domains were reached.
- The pilot exited with exit code 5 (`RETRIEVAL_ERROR` / safety control halt).
- Per the single-use evidence charter, the consumed marker cannot be recreated or reused.
- Listing-date status remains `LISTING_DATE_UNVERIFIED`.
- Retrospective classification remains `EMPTY_RESPONSE_UNEXPLAINED`.

Final Pilot Status:
`PREMIERENE_LISTING_EVIDENCE_PILOT_HALTED_ON_SAFETY_CONTROL`

---

## 2. Governed Baseline Verification

| Baseline Element | Value / Checksum | Verification Status |
|---|---|---|
| Repository Branch | `phase7-research` | Verified |
| Starting HEAD | `a6fba20` | Verified |
| Code Commit | `c471c78` | Verified |
| Python Environment | Python 3.12.10 | Verified |
| Unit Test Baseline | 496 passing tests (447 baseline + 49 new) | Verified |
| Frozen Source Panel | `CURRENT_NIFTY500_09Oct2026_8F4C439F` | Verified |
| Selection Checksum | `60dd03580442b1f874f364206da5d9bf252a4abf1ff93801d4b58e93fdee7b1d` | Verified Immutable |
| Ordered-Symbol Hash | `26e4be7c9cfd366b630b0b714f0afd65a223ffae91edad6e231060e6b95c4ee3` | Verified Immutable |
| Batch Contract Hash | `ed076001b43ab59a740859948edac11e3769ee0baa3660b28d48b5dac61b3427` | Verified Immutable |
| Halted Run Checkpoint | `BATCH_4_10C_HISTORICAL_20STOCK_2024Q1_20261010T112814Z` | Verified Intact |
| Historical Marker | `batch_authorization.consumed.20261010T112814Z.json` | Verified Consumed |
| Active Batch Markers | 0 active batch markers | Verified Zero |
| Historical Price Requests | 0 requests | Strictly Enforced |

---

## 3. Evidence Authorization Marker Provenance

The single-use authorization marker was created outside Git at:
`C:\Users\r_chh\gaurvideep_phase7_staging\nse500\batch_4_10c\listing_evidence\PREMIERENE\authorization\listing_evidence_authorization.json`

Payload details:
```json
{
  "authorization_version": "1.0",
  "milestone": "4.10C-2",
  "scope": "OFFICIAL_LISTING_DATE_EVIDENCE_PILOT",
  "symbol": "PREMIERENE",
  "security_name": "Premier Energies Limited",
  "exchange": "NSE",
  "requested_period_end": "2024-03-31",
  "approved_domains": [
    "bseindia.com",
    "nsearchives.nseindia.com",
    "nseindia.com",
    "sebi.gov.in"
  ],
  "maximum_request_count": 5,
  "staging_root_hash": "212f204efe6f9eb16dab9ca5b44f0ad2562e6a0012f315c31032d77b4406de0c",
  "issued_timestamp": "2026-10-10T12:08:28.530523+00:00",
  "expires_timestamp": "2026-10-10T12:38:28.530523+00:00",
  "single_use": true,
  "nonce": "ff083095-6cb7-46b6-8942-a60f7a1cdc77",
  "authorization_hash": "15ea408312035ab55dd4340a390ad7e1ee5644be501aa472a3ef61e715a62c8f"
}
```

Atomic Consumption:
- Consumed prior to network dispatch to:
  `listing_evidence_authorization.consumed.20261010T120840Z.json`
- Active markers remaining: 0.

---

## 4. Execution Trace and Safety Halt

Command Executed:
```powershell
.venv-phase7\Scripts\python.exe -m phase7.sources.listing_evidence_acquisition `
    --symbol PREMIERENE `
    --security-name "Premier Energies Limited" `
    --exchange NSE `
    --requested-end 2024-03-31 `
    --staging-root "C:\Users\r_chh\gaurvideep_phase7_staging\nse500\batch_4_10c\listing_evidence\PREMIERENE" `
    --authorization-file "C:\Users\r_chh\gaurvideep_phase7_staging\nse500\batch_4_10c\listing_evidence\PREMIERENE\authorization\listing_evidence_authorization.json" `
    --execute-live
```

Execution Output:
```
Authorization marker consumed atomically at: C:\Users\r_chh\gaurvideep_phase7_staging\nse500\batch_4_10c\listing_evidence\PREMIERENE\authorization\listing_evidence_authorization.consumed.20261010T120840Z.json
ERROR: Listing evidence acquisition failed: Unapproved domain 'www.sebi.gov.in' in URL 'https://www.sebi.gov.in/filings/public-issues/aug-2024/premier-energies-limited-prospectus_86360.html'. Permitted domains: ['bseindia.com', 'nsearchives.nseindia.com', 'nseindia.com', 'sebi.gov.in']
Evidence pilot exit code: 5
```

Root Cause Analysis:
- The candidate URL list defined `https://www.sebi.gov.in/...` with subdomain `www.sebi.gov.in`.
- The authorization contract whitelisted `sebi.gov.in` (exact match requirement without automatic subdomain expansion).
- `validate_source_url` performed strict domain matching, preventing any network connection to unapproved exact hostnames.
- Fail-closed execution halted with exit code 5 before any byte was sent across the network.

---

## 5. Safeguards and Blockers Assessment

1. **Safety Enforcement:** The fail-closed domain check functioned as intended, preventing ungoverned network dispatch.
2. **Single-Use Enforcement:** The marker was consumed atomically and is now permanently consumed.
3. **Immutability Invariants:**
   - Frozen selection checksum (`60dd0358...`) is unchanged.
   - Frozen ordered-symbol hash (`26e4be7c...`) is unchanged.
   - Original batch contract (`ed076001...`) is unchanged.
   - Halted batch checkpoint remains immutable.
   - Historical prices requested: 0.
4. **Current Status:**
   - Listing date status: `LISTING_DATE_UNVERIFIED`
   - Verification status: `UNVERIFIED`
   - Retrospective outcome: `EMPTY_RESPONSE_UNEXPLAINED`
   - Final status: `PREMIERENE_LISTING_EVIDENCE_PILOT_HALTED_ON_SAFETY_CONTROL`
