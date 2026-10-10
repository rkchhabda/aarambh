# Phase 7 NSE 500 20-Stock Batch Limitations and Methodological Constraints

## 1. Scope of Limitations

This document formally records the methodological limitations and structural constraints identified during the 20-stock historical batch pilot under Milestones 4.10B, 4.10C, 4.10C-1, and 4.10C-2.

---

## 2. Identified Structural Limitations

### 2.1 Current Snapshot Survivorship & Inception Bias
- **Finding:** The frozen snapshot `CURRENT_NIFTY500_09Oct2026_8F4C439F` represents survivorship-conditioned index constituents on October 9, 2026.
- **Impact:** It contains securities listed subsequent to historical evaluation periods (such as Q1 2024). Querying historical data for these constituents inevitably produces empty returns for periods preceding their exchange listing.
- **Governance Mandate:** The snapshot remains classified as `CURRENT_SNAPSHOT_ONLY` and cannot be treated as effective-dated or point-in-time constituent membership.

### 2.2 Inability to Establish Listing Date from Empty Responses
- **Finding:** Upstream endpoints return an empty list `[]` for both unlisted intervals and endpoint coverage gaps.
- **Impact:** An empty response cannot self-authenticate its reason.
- **Governance Mandate:** An empty response must be treated as `EMPTY_RESPONSE_UNEXPLAINED` and halt the batch unless supported by independent, verified listing evidence from the approved hierarchy.

### 2.3 Prohibition of Ad-Hoc Sample Replacement
- **Finding:** Discarding failed symbols (e.g. replacing `PREMIERENE` with an arbitrary alternative) introduces look-ahead selection bias.
- **Governance Mandate:** The deterministic 20-symbol sample is frozen under checksum `60dd0358...` and cannot be altered retrospectively. Any filtered sample requires a new batch ID, selection algorithm, and explicit survivorship-bias classification.

### 2.4 Mode 1 vs Mode 2 Trade-Off
- **Mode 1 (`TWENTY_DATA_BEARING_SECURITIES`):** Forces pre-selection eligibility filtering, which excludes newly listed securities and risks introducing survivorship bias into the selection process.
- **Mode 2 (`TWENTY_SELECTED_SECURITY_OUTCOMES`):** Preserves the raw deterministic sample from the current panel and explicitly reports pre-listing intervals as `NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED`. This mode accurately measures the data coverage of the current panel.

### 2.5 Official Listing-Date Evidence Acquisition Boundaries
- **Finding:** In Milestone 4.10C-2, controlled official evidence acquisition was authorized for `PREMIERENE`. Prior to network dispatch, pre-request domain safety validation detected that candidate URL `https://www.sebi.gov.in/...` carried subdomain `www.sebi.gov.in`, which differed from exact domain `sebi.gov.in` in the single-use marker whitelist.
- **Impact:** In accordance with fail-closed governance, execution halted immediately with exit code 5, consuming the single-use token and blocking all network activity.
- **Governance Mandate:** The marker is single-use and cannot be recreated or reused. Without acquired official documentary proof, PREMIERENE remains `LISTING_DATE_UNVERIFIED` and `EMPTY_RESPONSE_UNEXPLAINED`.

---

## 3. Relationship to Phase 7 Blockers

These limitations directly confirm why:
- **BLK-01 (`Point-in-Time Index Constituents`):** Remains `STILL_BLOCKED`.
- **BLK-02 (`Historical Survivorship Bias`):** Remains `PILOT_CAPABILITY_CONFIRMED_GATE1_NOT_PASSED`.
- **BLK-04 (`Unadjusted vs Corporate-Action-Adjusted Prices`):** Remains `STILL_BLOCKED`.
- **Milestone 5:** Remains unopened and strictly quarantined.
