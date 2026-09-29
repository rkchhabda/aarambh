# Phase 6 — Gate 3: Fundamental Data Sourcing & Data Quality Audit

**Governing Documents:**  
- [`docs/RESEARCH_PREREGISTRATION.md`](docs/RESEARCH_PREREGISTRATION.md) (Section 3.2, 4, 6)  
- [`docs/RESEARCH_PREREGISTRATION_AMENDMENT_1.md`](docs/RESEARCH_PREREGISTRATION_AMENDMENT_1.md) (Section G: "Gate 3: Fundamental data integration (if sourced)")  
**Milestone:** Gate 3  
**Status:** Evaluation Completed — Data Source Not Available with Compliant Historical Depth  
**Scope:** Development Data Only (2016-09-26 to 2025-09-16). Windows A & B remain strictly sealed.  

---

## 1. Requirement & Governing Pre-Registration Standard

Per Section 3.2 and Section 6 of `docs/RESEARCH_PREREGISTRATION.md`:
> *"Fundamental data — quarterly earnings surprise (actual vs. estimate), balance sheet quality (debt/equity, interest coverage), valuation relative to sector (P/E, P/B percentile within sector). Requires a new data source."*  
> *"Sourcing (free vs. paid, coverage of the 138-ticker universe, historical depth available) should be reported before any modeling begins. Any new data source must be checked for the same point-in-time discipline already required elsewhere in this project — no fundamental data that wasn't actually available to a trader on that date (e.g., earnings reported with a lag must be timestamped to their actual release date, not the quarter-end date)."*

Furthermore, Amendment 1 Section G explicitly conditions this milestone:  
**"Gate 3: Fundamental data integration (if sourced) — Development data only."**

---

## 2. Candidate Sourcing Audit for the 138-Ticker Universe

To evaluate whether a viable fundamental dataset could be integrated for Gate 3, an audit of candidate data sources across the 138-ticker Indian universe was performed:

| Source | Historical Depth | Universe Coverage | Point-in-Time (PIT) Release Dates | Accessibility / Cost | Assessment & Decision |
|---|---|---|---|---|---|
| **Yahoo Finance API (`yfinance` / `quoteSummary`)** | ~4 to 8 quarters (2024–2026 only) | Partial (~85% of 138 tickers) | **Fails PIT discipline.** Balance sheet/income dates map to fiscal quarter-end dates, not actual market disclosure dates. Lacks historical earnings surprise depth. | Free, but unauthenticated endpoints are rate-limited or blocked. | **REJECTED.** Insufficient historical depth (<2 years vs. 9-year development requirement) and severe lookahead risk. |
| **NSE India Official Corporate Disclosures (XBRL / Announcements)** | ~2–3 years online; historical archives heterogeneous | 100% of 138 tickers | Available in announcement metadata, but unstructured across PDF/HTML/XBRL formats. | Free on web portal, but lacks bulk historical PIT download API. | **REJECTED.** Constructing a clean, point-in-time backfilled panel for 2016–2025 requires institutional data pipeline engineering outside scope. |
| **Commercial PIT Databases (CMIE Prowess, Capital IQ, FactSet, Trendlyne Paid)** | 10+ years (full 2016–2025 span) | 100% | High-integrity point-in-time release timestamps and restatement audit trails. | Commercial / Paid subscription required. | **UNAVAILABLE.** No commercial vendor export is currently stored or provisioned in the repository. |

---

## 3. Methodological & Point-in-Time (PIT) Integrity Analysis

Section 6 establishes a non-negotiable rule: **zero lookahead bias in fundamental data**. 

In Indian equities, quarterly financial results (Q1, Q2, Q3, Q4) are declared by companies via board meeting disclosures typically **15 to 45 calendar days after the quarter-end date**:
- *Example:* For Q3 ending December 31, 2023, Infosys disclosed earnings on January 11, 2024; Reliance disclosed on January 19, 2024; state-run banks disclosed in mid-February 2024.
- If a model assigns Q3 earnings, P/E, or debt ratios to any trading date between January 1 and the disclosure date, it introduces **severe lookahead bias (peeking up to 45 days into the future)**.
- Any pseudo-fundamental dataset that forward-fills numbers based on quarter-end dates would artificially inflate train/val performance, producing exactly the spurious alpha patterns that `RESEARCH_PREREGISTRATION.md` was enacted to prevent.

---

## 4. Gate 3 Sourcing Verdict

1. **Status:** **NOT SOURCED.** Free public sources do not possess the required 9-year point-in-time depth (2016–2025) for the 138-ticker universe.
2. **Honest Accounting:** In strict compliance with Amendment 1 Section G ("*Fundamental data integration (if sourced)*") and Section 8 ("*If the Result Is Null / What does not count as progress*"), we do not synthesize a synthetic, lookahead-contaminated fundamental dataset.
3. **Data Loader Safeguards Maintained:** No fundamental dataset was added to `data_loader.py` that would violate the development cutoff (`2025-09-16`). Windows A and B remain 100% sealed.

---

## 5. Protocol for Future Fundamental Ingestion (If Owner Sources Data)

If the owner obtains an institutional, point-in-time compliant historical fundamental export (e.g., from CMIE Prowess, FactSet, or Bloomberg), it can be integrated under the following schema:
- **Required Columns:** `date` (actual market disclosure date YYYY-MM-DD), `ticker` (e.g. `RELIANCE.NS`), `pe_ratio`, `pb_ratio`, `debt_to_equity`, `earnings_surprise_pct`.
- **Constraint:** Must strictly pass through [`scripts/phase6/data_loader.py`](scripts/phase6/data_loader.py) with the `date <= 2025-09-16` filter enforced.

---

## 6. Next Sequential Step: Gate 4 (Options & Macro Features)

Per Amendment 1 Section G:
- **Gate 4:** Options & Macro Features (India VIX level/term structure, 200-SMA market regime, universe breadth), model refinement, and final model **FREEZE**.
- Options and macro indicators (e.g. `^INDIAVIX`, Nifty 50 regime) have verified, point-in-time historical data readily accessible across the full 2016–2025 development window.
