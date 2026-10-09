# Phase 7 — Vendor Evaluation Matrix

**Repository:** GaurviDEEP  
**Working Branch:** `phase7-research`  
**Governing Milestone:** Milestone 4.5 (Gate 1 Data Readiness Specification)  
**Status Date:** 2026-10-09  
**Status:** DRAFT EVALUATION FRAMEWORK (PRE-CONTACT CHECKPOINT)  

---

> [!IMPORTANT]
> **Strict Governance Rules:**
> 1. No vendor contact, enquiry form submission, email outreach, account registration, or commercial subscription has occurred.
> 2. No coverage, pricing, or licensing terms are invented or assumed.
> 3. Every entry in this matrix uses strictly one of the four mandatory status codes:
>    - `VERIFIED`: Confirmed by documentary evidence in repository or verified contract ledger.
>    - `UNVERIFIED`: Claimed by public vendor documentation or general market knowledge, but not verified by repository inspection or legal confirmation.
>    - `NOT AVAILABLE`: Confirmed not provided or explicitly outside vendor capability.
>    - `REQUIRES VENDOR CONFIRMATION`: Unknown or contract-dependent; requires formal vendor proposal.
> 4. In accordance with Rule 18, zero entries are marked `VERIFIED` without explicit evidence currently present in the repository.

---

## 1. Candidate Provider Overview

The following eight candidate data providers represent potential sources for resolving BLK-01 (PIT Nifty 500 Membership), BLK-02 (OHLCV & Traded Value Turnover), and BLK-04 (PIT Sector Classification):

1. **NSE Indices Limited:** Primary official index authority for Nifty 500, publishes historical reconstitution circulars and index changes.
2. **NSE Data & Analytics Limited:** Commercial market data arm of the National Stock Exchange of India, supplying raw historical daily trade and quote feeds.
3. **Bloomberg (B-PIPE / Core Terminal):** Global institutional financial data provider supplying historical pricing, corporate actions, and index memberships.
4. **FactSet:** Institutional quantitative feed provider with workstation, Open:FactSet marketplace, and historical point-in-time constituent coverage.
5. **LSEG / Refinitiv (DataScope / Workspace):** Global market data provider supplying Tick History, Pricing (Datascope), and Point-in-Time equity fundamentals.
6. **S&P Capital IQ (Xpressfeed):** Institutional fundamental and market data feed provider with historical point-in-time index memberships and corporate action tables.
7. **CMIE Prowess (Centre for Monitoring Indian Economy):** Specialized Indian financial database providing comprehensive corporate histories, financial statements, and historical equity listings.
8. **Approved Internal Provider (GaurviDEEP Internal Data Warehouse):** Local repository stores and verified historical archives currently present in GaurviDEEP.

---

## 2. Comprehensive 30-Dimension Evaluation Matrix

| # | Evaluation Dimension | NSE Indices Ltd | NSE Data & Analytics | Bloomberg | FactSet | LSEG / Refinitiv | S&P Capital IQ | CMIE Prowess | Internal Provider |
|---|---|---|---|---|---|---|---|---|---|
| **1** | **Historical Nifty 500 Membership** | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | NOT AVAILABLE |
| **2** | **Addition & Deletion Events** | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | NOT AVAILABLE |
| **3** | **Removed-Security Coverage** | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | NOT AVAILABLE |
| **4** | **Delisted-Security Coverage** | REQUIRES VENDOR CONFIRMATION | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | NOT AVAILABLE |
| **5** | **Effective-Dated Sector Classification** | UNVERIFIED | REQUIRES VENDOR CONFIRMATION | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | NOT AVAILABLE |
| **6** | **Daily OHLCV History** | NOT AVAILABLE | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | NOT AVAILABLE |
| **7** | **Exchange-Reported Traded Value** | NOT AVAILABLE | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | NOT AVAILABLE |
| **8** | **Volume-Weighted Avg Price (VWAP)** | NOT AVAILABLE | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | NOT AVAILABLE |
| **9** | **Deliverable Quantity & %** | NOT AVAILABLE | UNVERIFIED | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | NOT AVAILABLE |
| **10** | **Corporate Actions (Splits, Bonus, Div)** | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED |
| **11** | **Symbol & ISIN Historical Mapping** | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | NOT AVAILABLE |
| **12** | **Trading Suspension Status** | REQUIRES VENDOR CONFIRMATION | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | NOT AVAILABLE |
| **13** | **Audit Source Timestamps** | REQUIRES VENDOR CONFIRMATION | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | REQUIRES VENDOR CONFIRMATION | NOT AVAILABLE |
| **14** | **Restatement & Revision History** | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | REQUIRES VENDOR CONFIRMATION | NOT AVAILABLE |
| **15** | **Delivery Format (CSV, Parquet, API)** | REQUIRES VENDOR CONFIRMATION | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED |
| **16** | **API Availability** | NOT AVAILABLE | REQUIRES VENDOR CONFIRMATION | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | NOT AVAILABLE | NOT AVAILABLE |
| **17** | **Bulk-File Delivery** | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED |
| **18** | **Update Cadence (Daily/Intraday)** | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | NOT AVAILABLE |
| **19** | **Historical Depth ($\ge 10$ Years)** | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | NOT AVAILABLE |
| **20** | **Internal Research Rights** | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | VERIFIED |
| **21** | **Derived Analytics Rights** | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | VERIFIED |
| **22** | **Commercial Application Rights** | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION |
| **23** | **Display Rights in SaaS UI** | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION |
| **24** | **Redistribution Restrictions** | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION |
| **25** | **Model-Training Rights** | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | VERIFIED |
| **26** | **Post-Termination Retention Rights** | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | VERIFIED |
| **27** | **Support SLA & Latency Guarantee** | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | NOT AVAILABLE |
| **28** | **Indicative Pricing Status** | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | NOT AVAILABLE |
| **29** | **Procurement Lead Time** | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | NOT AVAILABLE |
| **30** | **Data Quality Dispute Process** | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | REQUIRES VENDOR CONFIRMATION | NOT AVAILABLE |

---

## 3. Evaluation Analysis by Candidate Provider

### 3.1 NSE Indices Limited
- **Strengths:** Primary authoritative creator of Nifty 500 index methodology, constituent additions, deletions, and semi-annual rebalancing notices.
- **Gaps:** Does not distribute raw equity OHLCV prices, volume, or traded value turnover.
- **Status:** Candidate for resolving BLK-01 (Index Membership) via direct circulars or index subscription.

### 3.2 NSE Data & Analytics Limited
- **Strengths:** Primary official exchange data arm. Offers official historical daily Bhavcopy, trading volumes, traded value turnover, and security masters directly from NSE matching engines.
- **Gaps:** Requires separate licensing for index constituent histories. Bulk historic procurement requires formal data agreement.
- **Status:** Primary candidate for resolving BLK-02 (OHLCV & Traded Value).

### 3.3 Bloomberg (B-PIPE / Terminal)
- **Strengths:** Comprehensive global equity database with deep historical coverage of Indian equities (`EQUITY IN`), corporate actions (`CACS`), point-in-time index memberships (`MEMB`), and AMFI/GICS classifications.
- **Gaps:** High annual subscription costs; strict terminal redistribution covenants; post-termination data deletion clauses.
- **Status:** Requires written confirmation regarding derived model ranking rights.

### 3.4 FactSet (Open:FactSet)
- **Strengths:** Excellent point-in-time constituent handling, symbiotic bulk data feeds, clear corporate action adjustment methodologies.
- **Gaps:** Institutional pricing structure; requires formal onboarding and enterprise licensing.
- **Status:** Viable institutional candidate for BLK-01, BLK-02, and BLK-04.

### 3.5 LSEG / Refinitiv (DataScope Select)
- **Strengths:** Deep historical Tick and Daily Pricing history (`Datascope`), corporate actions, and point-in-time index constituents.
- **Gaps:** Complex licensing schedules; variable pricing tiers based on field count and security universe size.
- **Status:** Viable institutional candidate for multi-table procurement.

### 3.6 S&P Capital IQ (Xpressfeed)
- **Strengths:** Standard institutional feed for quantitative researchers; robust survivorship-bias-free historical constituent feeds and GICS sector mappings.
- **Gaps:** High minimum commitment; long procurement lead times.
- **Status:** Viable enterprise candidate.

### 3.7 CMIE Prowess
- **Strengths:** The academic and institutional standard for Indian corporate history and financial reporting; comprehensive coverage of listed and unlisted Indian companies over 30+ years.
- **Gaps:** Stronger on fundamentals than high-frequency market microstructure; daily OHLCV and volume fields require separate market-data module confirmation.
- **Status:** Highly relevant for fundamental disclosures and delisted company identification.

### 3.8 GaurviDEEP Internal Data Warehouse
- **Strengths:** 100% verified internal research and model training rights; zero incremental financial cost.
- **Gaps:** Current repository files (`historical_10y_raw.csv`) contain only 138 tickers and lack Open, High, Low, Volume, and Traded Value (BLK-02); static universe list lacks addition/deletion circular dates (BLK-01); static sector mappings lack effective dates (BLK-04).
- **Status:** Cannot resolve BLK-01, BLK-02, or BLK-04 without external raw data procurement.

---

## 4. Next Actions for Research Sponsor

1. Authorize formal Request for Information (RFI) to primary candidates (NSE Data & Analytics, FactSet, or LSEG).
2. Request written terms specifically addressing model-training rights, derived analytics IP ownership, and post-termination retention.
3. Review sample delivery files against [`docs/PHASE7_DATA_SOURCE_DUE_DILIGENCE_CHECKLIST.md`](PHASE7_DATA_SOURCE_DUE_DILIGENCE_CHECKLIST.md).
