# Phase 7 — Data Source Technical Due Diligence Checklist

## 1. Executive Summary & Purpose

This checklist governs the technical due diligence process required prior to procuring, licensing, or ingesting any historical market data for GaurviDEEP Phase 7. It provides quantitative and engineering verification criteria to evaluate data vendor technical feeds, file deliveries, data architecture, and consistency.

Every candidate data source submitted to resolve **BLK-01** (Point-in-Time Nifty 500 Index Membership), **BLK-02** (Daily OHLCV & Traded Value), or **BLK-04** (Point-in-Time Sector Classification) must complete this technical review before Gate 1 acceptance testing.

---

## 2. Technical Due Diligence Dimensions

### 2.1 Sample Files Evaluation
- [ ] **Sample Depth**: Vendor provides multi-year sample files (minimum 2 full calendar years, including at least one major market volatility period such as March 2020 or demonetization November 2016).
- [ ] **Boundary Testing**: Samples include dates of major corporate actions (e.g., Reliance Industries rights issue 2020, Tata Steel split 2022).
- [ ] **Delisted Entities Included**: Sample explicitly contains delisted, merged, or bankrupt companies (e.g., DHFL, Reliance Communications, Jet Airways, Yes Bank reconstitution) during their active tenures.
- [ ] **End-of-Day File Completeness**: Sample includes complete constituent lists for designated dates, matching total exchange count.

### 2.2 Data Dictionary & Schema Specification
- [ ] **Formal Schema Documentation**: Complete field-by-field data dictionary supplied with explicit type signatures, allowed ranges, and nullability constraints.
- [ ] **Field Semantics Defined**: Precise financial and exchange definitions provided for all columns (e.g., difference between `close`, `last_price`, and `vwap`).
- [ ] **Turnover Definitions**: Clarification of whether turnover represents exchange-reported gross traded value in INR or derived turnover ($P \times V$).
- [ ] **Corporate Action Adjustment Flag**: Explicit definition of price adjustment states (`RAW_UNADJUSTED`, `SPLIT_ADJUSTED`, `TOTAL_RETURN_ADJUSTED`).
- [ ] **Series Clarification**: Complete enumeration of traded exchange series (`EQ`, `BE`, `SM`, etc.) and inclusion criteria.

### 2.3 Natural Keys & Uniqueness Constraints
- [ ] **Composite Key Definition**: Natural key explicitly identified for each entity table:
  - Daily Market Data: `(trading_date, isin)` or `(trading_date, symbol, exchange_series)`
  - Index Membership: `(index_code, isin, effective_from)`
  - Corporate Actions: `(isin, action_type, ex_date)`
  - Sector Classification: `(isin, classification_standard, effective_from)`
- [ ] **Zero Uniqueness Violations**: No duplicate natural keys present in any historical file delivery.
- [ ] **Key Immutability**: ISIN format conforms strictly to ISO 6166 (12 alphanumeric characters, starting with `IN` for Indian securities).

### 2.4 File Naming & Partitioning Conventions
- [ ] **Deterministic File Names**: Files follow standardized, deterministic naming patterns without spaces or unpredictable hashes (e.g., `nse_cm_bhavcopy_YYYYMMDD.csv` or `nifty500_membership_YYYYMMDD.parquet`).
- [ ] **Partitioning Strategy**: Bulk files organized predictably (by year `YYYY/` or by month `YYYY/MM/` or by table domain).
- [ ] **Idempotent Ingestion**: Re-downloading or re-processing the same file yields identical content and identical SHA-256 hashes.

### 2.5 Compression & File Format
- [ ] **Supported Formats**: Deliveries supplied in standardized, production-grade formats:
  - Columnar: Apache Parquet (preferred for analytical bulk data)
  - Delimited: CSV or TSV with quoted strings
- [ ] **Standard Compression**: Standard compression codecs employed: `zstd`, `gzip`, or `snappy`. Non-standard proprietary compression formats rejected.
- [ ] **Archive Integrity**: Tar/Zip archives unpack without corruption, path traversal vulnerabilities, or missing end-of-file markers.

### 2.6 Character Encoding & Delimiters
- [ ] **Character Set**: Strict `UTF-8` encoding across all files.
- [ ] **Byte Order Mark (BOM)**: No unexpected UTF-8 BOM (`\xef\xbb\xbf`) header artifacts that disrupt streaming parsers.
- [ ] **Line Terminators**: Deterministic line terminators (`\n` Unix LF preferred, or consistent `\r\n` Windows CRLF). Mixed line terminators prohibited.
- [ ] **Delimiter Escaping**: Embedded commas or quotes in security names properly escaped or encapsulated in double-quotes.

### 2.7 Date Formatting Standards
- [ ] **ISO 8601 Standard**: All trading dates, effective dates, and corporate action dates conform strictly to `YYYY-MM-DD`.
- [ ] **Zero Padding**: Single-digit months and days must be zero-padded (`2024-04-05`, not `2024-4-5`).
- [ ] **No Ambiguous Formats**: Formats like `DD/MM/YYYY`, `MM/DD/YYYY`, or `DD-Mon-YY` strictly disallowed or transformed via verified deterministic pre-processors.

### 2.8 Timestamp Precision & Timezone Semantics
- [ ] **Explicit Timezone Offsets**: All timestamp fields must include explicit timezone offsets conforming to ISO 8601:
  - IST timestamps: `YYYY-MM-DDTHH:MM:SS+05:30`
  - UTC timestamps: `YYYY-MM-DDTHH:MM:SSZ`
- [ ] **Source vs Ingestion Timestamps**: Clear differentiation between:
  - `source_timestamp`: When the exchange or vendor published/recorded the event.
  - `ingestion_timestamp`: When the pipeline ingested the record.
- [ ] **Temporal Causality**: No `source_timestamp` may exceed the cutoff timestamp (EOD 15:30 IST) for a given observation date $T$.

### 2.9 Missing Value Representation
- [ ] **Standardized Nulls**: Explicit definition of missing values. Nulls must appear as empty string `""` or explicit JSON `null`, never sentinel numeric values (e.g., `-999`, `999999`, `-1.0`).
- [ ] **Zero vs Missing**: Strict differentiation between genuine zero values (e.g., zero volume on a non-traded illiquid day) and missing/unreported values.
- [ ] **Price Non-Zero Invariant**: High, Low, Open, Close prices must strictly be positive ($> 0.0$) for active trading sessions.

### 2.10 Numeric Precision & Scaling
- [ ] **Floating Point vs Decimal**: Currency amounts and prices maintained with at least 2 decimal places (4 decimal places preferred for adjusted prices).
- [ ] **Volume Fields**: Traded quantities and trade counts represented as exact 64-bit unsigned integers (`uint64`), not truncated floats.
- [ ] **Turnover Precision**: Total traded value in INR stored with exact 64-bit precision (floating or decimal) without unit scaling ambiguity (clarify if values are in INR units, lakhs, or crores).

### 2.11 Restatements, Revisions, and Back-corrections
- [ ] **Restatement Policy**: Vendor provides written documentation on how historical trade cancellations, erroneous ticks, or retrospective index composition updates are handled.
- [ ] **Immutable History**: Historical files must remain immutable; corrections must be delivered via explicit revision feeds or delta ledgers with `revision_status` flags.
- [ ] **Notification SLA**: Vendor provides advance notice or automated feeds for historical revision announcements.

### 2.12 Delivery Mechanisms & Automation
- [ ] **Supported Protocols**: Secure, automated transfer options available:
  - Secure S3 / Cloud Bucket replication
  - SFTP with SSH key authentication
  - Programmatic REST / WebSocket API with batch endpoints
- [ ] **SLA & Uptime**: Vendor guarantees delivery schedule (e.g., daily Bhavcopy available by 18:30 IST on trading days).
- [ ] **Rate Limits & Bandwidth**: API rate limits sufficient to ingest the full 11-year historical dataset without artificial throttling delays.

### 2.13 Provenance & Audit Trail
- [ ] **Source Identification**: Every record traces directly back to exchange circulars, exchange Bhavcopy archives, or vendor corporate filings.
- [ ] **Document Linking**: Unique identifier linking corporate action events to exchange announcement documents or circular IDs.
- [ ] **Row Hashing**: Ingested datasets maintain an idempotent cryptographic SHA-256 row hash for end-to-end verification.

---

## 3. Due Diligence Scoring & Recommendation Matrix

| Section | Evaluation Area | Weight | Pass Criteria | Status |
| :--- | :--- | :---: | :--- | :---: |
| 2.1 | Sample Files | 10% | Representative 2-year sample with delistings & splits | PENDING REVIEW |
| 2.2 | Data Dictionary | 10% | Complete schema with unambiguous turnover and adjustments | PENDING REVIEW |
| 2.3 | Natural Keys | 15% | Zero duplicates, 100% valid ISO 6166 ISINs | PENDING REVIEW |
| 2.4 | File Naming & Partitioning | 5% | Deterministic, idempotent naming | PENDING REVIEW |
| 2.5 | Compression & Format | 5% | Standard Parquet/CSV, zstd/gzip compression | PENDING REVIEW |
| 2.6 | Character Encoding | 5% | Strict UTF-8 without BOM, clean delimiters | PENDING REVIEW |
| 2.7 | Date Formatting | 10% | Strict ISO 8601 `YYYY-MM-DD` | PENDING REVIEW |
| 2.8 | Timestamp Precision | 10% | Explicit IST/UTC offsets, causality preserved | PENDING REVIEW |
| 2.9 | Missing Values | 5% | No sentinel codes, distinct zero vs null | PENDING REVIEW |
| 2.10 | Numeric Precision | 5% | Int64 volume, Dec/Float64 prices, clear INR scale | PENDING REVIEW |
| 2.11 | Restatement Policy | 5% | Explicit append-only revision semantics | PENDING REVIEW |
| 2.12 | Delivery & Automation | 10% | Automated S3/SFTP/API, reliable SLA | PENDING REVIEW |
| 2.13 | Provenance & Audit Trail | 5% | Traceable to exchange circulars, cryptographic hashes | PENDING REVIEW |
| **Total** | **Comprehensive Technical Due Diligence** | **100%** | **Overall Score $\ge 95\%$ with no Critical Fails** | **PENDING REVIEW** |
