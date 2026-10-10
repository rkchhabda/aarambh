# Phase 7 Protocol: Deterministic 20-Symbol Batch Selection & Freezing

## 1. Overview & Methodology

To avoid sample selection bias, manual cherry-picking, performance optimization, or liquidity snooping, the 20 securities for Milestone 4.10C are selected via a **strictly deterministic, reproducible algorithm** applied to the frozen NIFTY 500 snapshot.

---

## 2. Selection Algorithm Specification

1. **Source Dataset:** Read the frozen normalized snapshot file outside Git:
   `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\snapshot_4_10a\normalized\constituents\NIFTY_500_normalized_20261010T102946Z_8f4c439f.jsonl`
2. **Integrity Check:** Verify SHA-256 matches:
   `8f4c439f35fffc8ec87f107ebc9e03aef00ad26301d0912711d808ac592d117d`
3. **Symbol Extraction:** Extract all unique valid constituent symbols (assert count equals 500).
4. **Lexicographical Sort:** Sort the 500 unique symbols ascending in ASCII order.
5. **Deterministic Hash Scoring:** For each symbol $s$, calculate:
   $$\text{Digest}(s) = \text{SHA256}(\text{panel\_version} \parallel \text{"\|"} \parallel s \parallel \text{"\|MILESTONE\_4\_10B"})$$
   where $\text{panel\_version} = \text{"CURRENT\_NIFTY500\_09Oct2026\_8F4C439F"}$.
6. **Ranking:** Sort candidates ascending by their SHA-256 digest string (breaking ties by symbol ASCII).
7. **Exclusion Filter:** Filter out the five previously tested equities from Milestone 4.9:
   - `RELIANCE`
   - `TCS`
   - `HDFCBANK`
   - `INFY`
   - `ICICIBANK`
8. **Selection:** Select the first 20 remaining candidates.
9. **Sequence Preservation:** Maintain the exact ranked order.
10. **Checksum Generation:** Compute the selection checksum:
    $$\text{Selection Checksum} = \text{SHA256}(\text{newline-separated ordered symbols})$$

---

## 3. Cryptographic & Governance Parameters

- **Source Panel Version:** `CURRENT_NIFTY500_09Oct2026_8F4C439F`
- **Source Snapshot SHA-256:** `8f4c439f35fffc8ec87f107ebc9e03aef00ad26301d0912711d808ac592d117d`
- **Source Constituent Count:** 500
- **Excluded Pilot Symbols Count:** 5
- **Selected Symbol Count:** 20
- **Selection Algorithm:** `SHA256(panel_version|symbol|seed_string)_ASC_EXCLUDE_5`
- **Selection Seed String:** `MILESTONE_4_10B`
- **Selection Checksum (SHA-256):** `60dd03580442b1f874f364206da5d9bf252a4abf1ff93801d4b58e93fdee7b1d`
- **Ordered Symbols Hash (SHA-256):** `26e4be7c9cfd366b630b0b714f0afd65a223ffae91edad6e231060e6b95c4ee3`
- **Dataset Classification:** `DETERMINISTIC_CURRENT_PANEL_OPERATIONAL_SAMPLE`

---

## 4. Storage & Repository Isolation

Per governance directives, the complete 20-symbol list is **not stored in Git**.

All selection evidence is persisted immutably outside Git in:
`C:\Users\r_chh\gaurvideep_phase7_staging\nse500\batch_4_10c\selection\`

- **`selected_symbols.json`:** Contains the ordered sequence and selection metadata.
- **`selection_manifest.json`:** Immutable execution manifest for the selection.
- **`selection_audit.json`:** Comprehensive audit trail detailing algorithm, exclusions, and file paths.

---

## 5. Negative Declarations

The selected operational sample:
- Is **NOT** representative of the NIFTY 500 by sector;
- Is **NOT** representative by market capitalization;
- Is **NOT** survivorship-free;
- Is **NOT** point-in-time;
- Is **NOT** suitable for investment inference, factor evaluation, or alpha testing;
- Does **NOT** constitute a recommended or investable portfolio.
