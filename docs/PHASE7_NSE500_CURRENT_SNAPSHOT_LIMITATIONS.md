# Phase 7 Governance Limitations: Current NIFTY 500 Constituent Snapshot

## 1. Dataset Classification

This dataset is formally classified as:
```
CURRENT_SNAPSHOT_ONLY
```

Its governing capability label is:
```
CURRENT_NIFTY500_SNAPSHOT_CAPABILITY_CONFIRMED
```

---

## 2. Binding Negative Declarations

Under Non-Negotiable Rules 5, 10, 17, and 18, and Gate 1 Data Integrity requirements, this snapshot list:

1. **MUST NEVER** be represented as historical NIFTY 500 membership.
2. **MUST NEVER** be represented as point-in-time membership.
3. **MUST NEVER** be represented as survivorship-free membership.
4. **MUST NEVER** be represented as effective-dated index history.
5. **MUST NEVER** be cited as evidence resolving blocker `BLK-01`.
6. **MUST NEVER** be cited as satisfying Gate 1 Data Integrity requirements.
7. **MUST NEVER** be used to filter or form universes for historical dates prior to its observation date (`09-Oct-2026`).
8. **MUST NEVER** be used as an authorization or foundation for model training, feature extraction, or backtesting.

---

## 3. Methodological Rationale

Applying a single current snapshot of index constituents retrospectively to historical backtests introduces severe **survivorship bias** and **forward-looking selection leakage**:
- Companies that grew rapidly and entered the NIFTY 500 in recent years will be artificially included in early historical periods when they were small or unlisted.
- Companies that suffered financial distress, bankruptcy, or declining market capitalization and were removed from the NIFTY 500 will be completely excluded from historical tests.
- Backtested returns derived from such a universe would be artificially inflated, leading to false discovery of trading alpha.

Authentic resolution of `BLK-01` requires point-in-time constituent history (semi-annual rebalancing additions, deletions, and effective dates) spanning the full research period (2016–2026).

---

## 4. Operational Boundaries

- **No Retrospective Application:** The snapshot may only be used for forward-looking operational tracking or live shadow monitoring on or after `09-Oct-2026`.
- **Zero Fallback Substitution:** It is strictly prohibited to fall back to `features/universe.py`, the legacy 138-ticker list, or manually supplemented lists.
- **Milestone 5 Quarantine:** Milestone 5 (baseline models and model training) remains strictly locked until authentic point-in-time historical membership datasets are procured and accepted.
