# Phase 7 NSE 500 Listing Evidence Acquisition Protocol

## 1. Objective and Governance Scope

This protocol establishes the immutable criteria and governed acquisition pipeline for obtaining, verifying, and preserving official documentary listing-date evidence for securities selected from the current NIFTY 500 snapshot.

Under Milestone 4.10C-1 and 4.10C-2 governance:
- An empty source response by itself must **never** establish a listing date or pre-listing status.
- Listing status cannot be inferred from current index membership, company name, ticker pattern, search-engine snippets, or portfolio holdings.
- An empty response may only be classified as `NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED` when an independently sourced, cryptographically hashed, and verified official listing date proves $\text{listing\_date} > \text{requested\_end\_date}$ (e.g. 2024-03-31).
- If only an expected or proposed trading commencement date is obtained from an official source (e.g. prospectus indicative timetable), it is classified as `PRELISTING_AFTER_PERIOD_PROVISIONALLY_CONFIRMED`.
- All evidence must remain strictly outside Git in external staging.

---

## 2. Approved Source Hierarchy

Listing-date evidence must be acquired strictly according to the following priority hierarchy:

### Priority 1: Official Exchange Records
1. Official NSE Circulars / Listing Notices announcing admission to dealings and commencement of trading.
2. Official NSE Security Master (`security_master.csv` / official exchange master file).
3. Official Exchange Security-Information web records with confirmed listing date.

### Priority 2: Regulatory Filings
1. SEBI-hosted Final Offer Document / Prospectus confirming allotment and listing schedule.
2. Issuer-filed official exchange disclosures confirming listing date.

### Priority 3: Cross-Exchange Records
1. BSE official security master or notice where the exact **NSE listing date** is explicitly and independently declared.

### Strictly Disallowed Sources
The following sources are ungoverned and **strictly prohibited** as evidence:
- Financial news articles and media releases
- Community or corporate blogs
- Third-party market screeners (e.g. Screener.in, Trendlyne)
- Wikipedia or crowd-sourced databases
- Brokerage summaries
- Search-engine snippets
- AI-generated responses (e.g. ChatGPT, Perplexity)
- Manually typed dates without primary document attachment

---

## 3. Date-Semantic Classification Taxonomy

Every date statement extracted from an official source is classified into exactly one semantic category:

| Semantic Classification | Criteria / Phrase Matching | Evidentiary Weight |
|---|---|---|
| `CONFIRMED_TRADING_COMMENCEMENT_DATE` | "admitted to dealings", "shall be listed and admitted to dealings w.e.f.", "trading shall commence" in official exchange circular | Supports `NOT_LISTED_DURING_REQUESTED_PERIOD_VERIFIED` |
| `EXPECTED_TRADING_COMMENCEMENT_DATE` | "trading is expected to commence", "tentative timetable", "indicative schedule", "proposed listing date" | Supports `PRELISTING_AFTER_PERIOD_PROVISIONALLY_CONFIRMED` |
| `LISTING_APPROVAL_DATE` | Exchange in-principle or final listing approval notice | Ancillary record |
| `PROSPECTUS_DATE` | "Prospectus dated ... filed with ROC" | Filing date record |
| `ALLOTMENT_DATE` | "Basis of allotment approved / finalised on" | Ancillary offer record |
| `OFFER_OPEN_DATE` | "Bid/Offer opens on" | Ancillary offer record |
| `OFFER_CLOSE_DATE` | "Bid/Offer closes on" | Ancillary offer record |
| `UNCLASSIFIED_DATE` | Other dates not matching governed operational categories | Non-probative |

Expected and confirmed trading commencement dates must **never** be conflated. An expected date must never be silently converted into an actual confirmed trading date.

---

## 4. Single-Use Authorization Protocol

Evidence acquisition requires an explicit, single-use, scope-bound authorization marker:
- **Milestone:** `4.10C-2`
- **Scope:** `OFFICIAL_LISTING_DATE_EVIDENCE_PILOT`
- **Target Symbol:** Bound to target security (e.g. `PREMIERENE`)
- **Approved Domains:** Strictly whitelisted (`nsearchives.nseindia.com`, `nseindia.com`, `sebi.gov.in`, `bseindia.com`)
- **Ceiling:** Maximum 5 requests total
- **Concurrency:** Maximum 1 request at a time
- **Pacing:** Minimum 2.0 seconds between consecutive requests
- **Automatic Retries:** 0 (strictly fail-closed on first error)
- **Consumption:** Atomic rename to `.consumed.<UTC_TIMESTAMP>.json` **prior** to the first network request.

---

## 5. Storage Layout Outside Git

Evidence files are saved externally under:
`C:\Users\r_chh\gaurvideep_phase7_staging\nse500\batch_4_10c\listing_evidence\<SYMBOL>\`

Directory layout:
- `authorization/`: Single-use active and consumed authorization markers
- `raw/`: Unaltered official source documents (PDFs, HTML files) with SHA-256 integrity
- `extracted/`: Sanitized, structured extraction records (identities, dates, statement hashes)
- `manifests/`: Finalized evidence manifest with cryptographic digest
- `audit/`: Retrospective classification records
- `logs/`: Operational execution logs

Requirements:
1. Immutable filenames.
2. Atomic writes via temporary files.
3. No overwrite of existing files.
4. SHA-256 for every downloaded source.
5. Strict sanitization: zero cookies, session headers, or tokens in stored files.
6. Zero evidence files or downloaded PDFs/HTML in the Git repository.
