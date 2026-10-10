# Phase 7 NSE 500 Listing Evidence Acquisition Protocol

## 1. Objective and Governance Scope

This protocol establishes the immutable criteria and 15-point acquisition plan for obtaining, verifying, and preserving official listing-date evidence across securities selected from the current NIFTY 500 snapshot.

Under Milestone 4.10C-1 governance:
- An empty source response by itself must **never** establish a listing date.
- Listing status cannot be inferred from current index membership, company name, ticker pattern, search-engine snippets, or portfolio holdings.
- An empty response may only be classified as `NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED` when an independently sourced, cryptographically hashed, and verified listing date proves `listing_date > requested_end_date`.
- All evidence must remain strictly outside Git.

---

## 2. Approved Source Hierarchy

Listing-date evidence must be acquired strictly according to the following priority hierarchy:

### Priority 1: Official Exchange Records
1. Official NSE Security Master (`security_master.csv` / official exchange master file).
2. Official NSE Circulars / Listing Notices announcing commencement of trading.
3. Official Exchange Security-Information web records with confirmed listing date.

### Priority 2: Regulatory Filings
1. SEBI-hosted Final Offer Document / Prospectus confirming allotment and listing schedule.
2. Issuer-filed official exchange disclosures confirming listing date.

### Priority 3: Cross-Exchange Records
1. BSE official security master or notice where the exact **NSE listing date** is explicitly and independently declared.

### Strictly Disallowed Sources
The following sources are ungoverned and **strictly prohibited** as standalone evidence:
- Financial news articles and media releases
- Community or corporate blogs
- Third-party market screeners (e.g. Screener.in, Trendlyne)
- Wikipedia or crowd-sourced databases
- Brokerage summaries
- Search-engine snippets
- AI-generated responses (e.g. ChatGPT, Perplexity)
- Manually typed dates without primary document attachment

---

## 3. 15-Point Governed Acquisition Plan

1. **Approved Sources:** Restricted to Priority 1 (NSE official), Priority 2 (SEBI filing), Priority 3 (Explicit cross-exchange).
2. **Expected Record / Document:** Machine-readable official CSV, JSON, circular text, or official PDF prospectus with confirmed commencement date.
3. **Required Fields:** `symbol`, `security_name`, `exchange`, `listing_date` (YYYY-MM-DD), `source_identifier`, `source_type`.
4. **Identifier Matching Rules:** Exact uppercase ASCII symbol match; no fuzzy matching or heuristic ticker substitution.
5. **Symbol-Renaming Handling:** Requires manual provenance review and official exchange change notice; automated name aliasing is prohibited.
6. **ISIN Utilization:** Governed ISIN matching (12-character alphanumeric, e.g. `INE0K8D01017`) is required when reported by source.
7. **Conflict Resolution:** If disparate sources declare differing listing dates, the record status is set to `CONFLICT` and classification falls back to `LISTING_DATE_UNVERIFIED`.
8. **Missing-Date Handling:** If listing date is absent or not reported, record is classified `NOT_PROVIDED` / `LISTING_DATE_UNVERIFIED`. Batch halts remain intact.
9. **Cryptographic Checksum:** Every evidence artifact must have an immutable SHA-256 digest recorded in the manifest.
10. **External Staging Root:** `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\batch_4_10c\listing_evidence\` (outside Git).
11. **Reviewer Status:** Every record requires explicit provenance classification (`GOVERNED_SYSTEM` or `PEER_REVIEWED`).
12. **Update Frequency:** Static per batch milestone; no continuous background polling.
13. **Licensing & Terms:** Strictly non-commercial research use in accordance with official exchange data policies.
14. **Maximum Request Ceiling:** Maximum 1 request per selected security (total 20 requests).
15. **Halt Conditions:** Network connection timeout, HTTP non-200, schema divergence, or CAPTCHA immediately halts the evidence pilot.

---

## 4. Evidence Persistence Format

Evidence files are saved externally as:
`listing_evidence/<SYMBOL>_listing_evidence.json`

Example Schema:
```json
{
  "symbol": "PREMIERENE",
  "security_name": "Premier Energies Limited",
  "exchange": "NSE",
  "listing_date": "2024-09-03",
  "listing_date_status": "SOURCE_REPORTED",
  "source_type": "NSE_SECURITY_MASTER",
  "source_identifier": "NSE_CIRCULAR_LISTING_20240903",
  "source_document_date": "2024-09-03",
  "retrieval_timestamp": "2026-10-10T12:00:00Z",
  "evidence_file_reference": "listing_evidence/PREMIERENE_circular.pdf",
  "evidence_sha256": "8f...",
  "source_row_hash": "a1...",
  "verification_status": "VERIFIED_SINGLE_SOURCE",
  "reviewer_status": "GOVERNED_SYSTEM",
  "notes": "Verified against official exchange commencement notice",
  "isin": "INE0K8D01017"
}
```
