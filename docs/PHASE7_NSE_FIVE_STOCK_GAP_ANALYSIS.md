# Phase 7 Gap Analysis: Milestone 4.9 Five-Stock NSE Pilot

## 1. Blocker Status Re-Evaluation

The halt of the Milestone 4.9 live pilot leaves the core research blockers in their formal, fail-closed state:

| Blocker ID | Description | Pre-Milestone Status | Post-Milestone Status | Technical Capability Status |
| :---: | :--- | :--- | :--- | :---: |
| **BLK-01** | Point-in-Time NIFTY 500 Constituent Membership History | `OPEN` | **OPEN / STILL BLOCKED** | `SOURCE_UNAVAILABLE` |
| **BLK-02** | Historical OHLCV Prices and Daily Traded Value (Turnover) | `OPEN` | **OPEN / STILL BLOCKED** | `PILOT_HALTED_ON_SAFETY_CONTROL` |
| **BLK-04** | Point-in-Time Sector Classification History | `OPEN` | **OPEN / STILL BLOCKED** | `SOURCE_UNAVAILABLE` |

### Detailed Assessment:
1. **BLK-01 (PIT Constituents):** `NSEDataFetcher` contains no constituent methods. The adapter strictly classifies constituent retrieval as `SOURCE_UNAVAILABLE`. Survivorship-biased fallbacks remain strictly prohibited.
2. **BLK-02 (Historical OHLCV):** Although `NSEDataFetcher.get_historical_data` supports explicit calendar boundaries in static inspection, real data acquisition has not occurred. The live pilot was halted prior to issuing network requests due to the CLI reusable-token requirement defect. Real OHLCV data remains unprocured.
3. **BLK-04 (Sector Classification):** The data fetcher provides only live snapshot industry tags without historical reclassification timestamps. Point-in-time sector-relative target research remains blocked.

---

## 2. Technical Gap & Defect Analysis

```mermaid
flowchart TD
    D1[Defect: Reusable Authorization Token on CLI] --> H1[Milestone 4.9 Execution Halt]
    H1 --> B1[BLK-02 Remains Unresolved Live]
    H1 --> B2[Live Data Not Downloaded]
    
    G1[Gap: Missing Constituent History] --> B3[BLK-01 Remains Blocked]
    G2[Gap: Missing Sector History] --> B4[BLK-04 Remains Blocked]
    
    style D1 fill:#ffcccc,stroke:#cc0000
    style H1 fill:#fff2cc,stroke:#d6b656
    style B1 fill:#f8cecc,stroke:#b85450
    style B3 fill:#f8cecc,stroke:#b85450
    style B4 fill:#f8cecc,stroke:#b85450
```

### 2.1 The Reusable Command-Line Authorization Defect
- **Observation:** In Milestone 4.8, `phase7.sources.pilot` was written with:
  ```python
  if execute_live:
      if owner_authorization != REQUIRED_PILOT_PHRASE:
          raise PermissionError(...)
  ```
- **Problem:** This design required the owner authorization phrase to be stored as a CLI argument string (`--owner-authorization "..."`), functioning as a reusable token.
- **Milestone 4.9 Instruction:** The owner explicitly directed that the phrase must not be supplied on the command line, and that the agent must halt if the code still mandates it.
- **Remediation Completed in Milestone 4.9A:** `phase7/sources/pilot.py` and `phase7/sources/pilot_guard.py` completely removed `--owner-authorization` and all secret phrase comparisons. Implemented single-use scope-bound authorization marker management (`phase7.sources.authorization`) storing markers strictly outside Git and enforcing atomic consumption prior to client instantiation.

### 2.2 Single-Use Authorization Security Architecture
- **No Reusable Secrets:** The marker contains zero passwords, bearer tokens, cookies, or owner phrases.
- **Strict Scope Binding:** Binds milestone 4.9, FIVE_STOCK_NSE_LIVE_PILOT scope, approved 5 symbols in governed order, Jan 2024 dates, 1d interval, and external staging root hash.
- **Atomic Pre-Client Consumption:** Consumed via `os.replace` to `pilot_authorization.consumed.<timestamp>.json` before client initialization. Zero network requests occur if validation or consumption fails.
- **Fail-Closed Guarantees:** Tampering, expiration, reuse, relative paths, or repository locations are rejected.

---

## 3. Recommended Next Actions

1. **Re-authorize Milestone 4.9 Live Pilot:**
   Following the completed Milestone 4.9A authorization guard remediation, request owner re-authorization (`RE-AUTHORIZE MILESTONE 4.9: FIVE-STOCK NSE LIVE PILOT`) to create the external marker and execute the live pilot retrieval.
2. **Milestone 5 Quarantine:**
   Milestone 5 (model training and target generation) remains strictly blocked until real data is procured, ingested, and verified through Gate 1.
