# Phase 7 NSE 500 Pre-Listing Interval Classification Policy

## 1. Governance Context and Objective

During Milestone 4.10C, the governed 20-stock historical batch halted on its first symbol (`PREMIERENE`) because the upstream historical endpoint returned an empty data list (`[]`) for Q1 2024 (`2024-01-01` through `2024-03-31`).

This policy establishes the strict, non-negotiable rules governing:
1. When an empty response may be classified as `NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED`.
2. When an empty response must remain `EMPTY_RESPONSE_UNEXPLAINED` (triggering an immediate, fail-closed batch halt).
3. The prohibition of retrospective sample tampering or ad-hoc ticker replacement.

---

## 2. Core Classification Policy

### Rule 1: Empty Response Disqualification
An empty source response by itself establishes **nothing** regarding the operational or listing state of a security. It could represent an endpoint outage, an upstream parameter error, a network proxy sanitization event, or an unlisted interval. Therefore, an empty response must never be used to infer its own cause.

### Rule 2: Proof of Ineligible Pre-Listing Period
An empty response may be classified as:
`NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED`
**only and strictly when** an independently sourced, cryptographically validated listing-date record proves:
$$\text{listing\_date} > \text{requested\_end\_date}$$
with verification status `VERIFIED_SINGLE_SOURCE` or `VERIFIED_MULTI_SOURCE`.

### Rule 3: Fail-Closed Default
If approved independent listing evidence is absent, conflicting, or indicates $\text{listing\_date} \le \text{requested\_end\_date}$, the empty response must be classified as:
`EMPTY_RESPONSE_UNEXPLAINED`
and must halt the batch immediately with exit code 5 (`RETRIEVAL_ERROR`).

---

## 3. Governed Symbol Outcome Model

Every security in a historical batch must resolve to exactly one of ten governed outcome states:

| Outcome State | Description | Batch Impact |
|---|---|---|
| `DATA_AVAILABLE` | Historical rows retrieved, normalized, and validated | Counts toward completed data |
| `NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED` | Independently verified listing date post-dates requested period | Valid outcome in Mode 2 |
| `EMPTY_RESPONSE_UNEXPLAINED` | 0 rows received without independent listing proof | Fatal halt (Exit Code 5) |
| `SOURCE_DENIED` | Upstream 403 / Access Denied / CAPTCHA | Fatal halt (Exit Code 5) |
| `SOURCE_TIMEOUT` | Upstream network timeout | Fatal halt (Exit Code 5) |
| `SOURCE_ERROR` | Upstream 5xx / Connection reset / Transport drop | Fatal halt (Exit Code 5) |
| `SCHEMA_REJECTED` | Payload schema unparseable or rejected | Fatal halt (Exit Code 6) |
| `PARTIAL_DATA` | Truncated date range or unexpected gaps | Fatal halt (Exit Code 6) |
| `INVALID_DATA` | Invalid OHLC, negative price/volume | Fatal halt (Exit Code 6) |
| `NOT_ATTEMPTED` | Symbol not yet reached prior to batch halt | Retained in checkpoint |

---

## 4. Future Batch Acceptance Modes

### Mode 1: `TWENTY_DATA_BEARING_SECURITIES`
- **Objective:** Acquire historical data for exactly 20 securities with valid price series.
- **Rules:** Pre-listing outcomes do not count toward the 20 securities. Any empty response is fatal. Eligibility must be established before deterministic selection.

### Mode 2: `TWENTY_SELECTED_SECURITY_OUTCOMES`
- **Objective:** Evaluate source coverage for the 20 governed deterministically selected securities from the current snapshot.
- **Rules:** All 20 securities must receive a valid classified outcome. Verified pre-listing securities resolve to `NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED`. Unexplained empty responses remain fatal.
- **Reporting:** Reports separate counts for:
  - `data_bearing_count`
  - `verified_prelisting_count`
  - `source_failure_count`
  - `unresolved_count`

### Phase 7 Recommendation
For Phase 7 source qualification, **Mode 2 (`TWENTY_SELECTED_SECURITY_OUTCOMES`) is preferred**. It preserves the deterministic sample without survivorship-masking filtering, explicitly measuring the gap between current index membership and historical data availability.
