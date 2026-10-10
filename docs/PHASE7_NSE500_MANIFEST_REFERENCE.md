# Phase 7 — Milestone 4.7: NSE 500 Manifest Reference & Staging Ledger

**Repository:** GaurviDEEP
**Working Branch:** `phase7-research`
**Governing Milestone:** Milestone 4.7 (Existing Connector NIFTY 500 Data Acquisition & Safety Audit)
**Execution Timestamp:** 2026-10-10T06:05:00 UTC

---

## 1. External Staging Directory Architecture

All prospective data acquisition artifacts, raw responses, normalized tables, and audit logs are isolated strictly outside the repository to prevent git contamination and working-tree pollution:

```
C:\Users\r_chh\gaurvideep_phase7_staging\nse500\
├── audit\                      # Structural audits, schema validation logs, anomaly reports
├── manifests\                  # Checksum manifests, version manifests, run metadata
├── normalized\                 # Canonical Phase 7 parquet / CSV tables
│   ├── current_constituents\   # Extracted NIFTY 500 constituent lists
│   ├── eod\                    # Canonical DailyPriceRecord instances
│   └── pilot\                  # Normalized 5-security pilot records
├── raw\                        # Immutable raw source responses (JSON / XML / CSV)
│   ├── constituents\           # Raw response from equity-stock-indices API
│   ├── corporate_actions\      # Raw JSON responses from corporateActions API
│   ├── eod\                    # Raw individual or bulk Bhavcopy files
│   └── pilot\                  # Raw pilot HTTP responses
└── rejected\                   # Rejected-record ledgers with failure reason codes
```

---

## 2. Manifest Specifications & Schemas

### 2.1 Ingestion Run Manifest (`manifests/ingestion_run_manifest.json`)
Records the operational metadata of any data retrieval execution:

```json
{
  "run_id": "RUN-20261010-060500",
  "milestone": "MILESTONE_4.7",
  "timestamp_utc": "2026-10-10T06:05:00Z",
  "status": "NSE_CONNECTOR_PILOT_FAILED",
  "runtime_interpreter": ".venv-phase7\\Scripts\\python.exe",
  "runtime_version": "Python 3.12.10",
  "staging_root": "C:\\Users\\r_chh\\gaurvideep_phase7_staging\\nse500",
  "requested_symbols": ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"],
  "requested_period": {
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  },
  "summary_counts": {
    "raw_files_downloaded": 0,
    "normalized_records_written": 0,
    "rejected_records": 5,
    "http_200_count": 0,
    "http_error_count": 0,
    "timeout_count": 0,
    "rate_limit_count": 0
  },
  "termination_reason": "Existing connector failed import in .venv-phase7 and hardcodes trailing-only dates; pilot failed preconditions."
}
```

### 2.2 SHA-256 Checksum Manifest (`manifests/checksum_manifest.sha256`)
Every file written to the external staging directory must have an immutable, deterministic SHA-256 checksum recorded in canonical GNU format:

```text
# SHA256 Checksum Manifest - Milestone 4.7
# Generated: 2026-10-10T06:05:00Z
# Format: <hash>  <relative_path>
```

*(Zero data files were downloaded during Milestone 4.7 due to pilot failure; checksum count: 0).*

### 2.3 Rejected Record Ledger (`rejected/rejected_records.jsonl`)
Any symbol or row that fails validation, schema checks, or network retrieval is written to an append-only JSON Lines ledger with an explicit reason code:

```json
{"timestamp": "2026-10-10T06:05:00Z", "symbol": "RELIANCE", "reason_code": "CONNECTOR_RUNTIME_IMPORT_ERROR", "details": "ModuleNotFoundError: No module named 'requests' in .venv-phase7"}
{"timestamp": "2026-10-10T06:05:00Z", "symbol": "TCS", "reason_code": "CONNECTOR_RUNTIME_IMPORT_ERROR", "details": "ModuleNotFoundError: No module named 'requests' in .venv-phase7"}
{"timestamp": "2026-10-10T06:05:00Z", "symbol": "HDFCBANK", "reason_code": "CONNECTOR_RUNTIME_IMPORT_ERROR", "details": "ModuleNotFoundError: No module named 'requests' in .venv-phase7"}
{"timestamp": "2026-10-10T06:05:00Z", "symbol": "INFY", "reason_code": "CONNECTOR_RUNTIME_IMPORT_ERROR", "details": "ModuleNotFoundError: No module named 'requests' in .venv-phase7"}
{"timestamp": "2026-10-10T06:05:00Z", "symbol": "ICICIBANK", "reason_code": "CONNECTOR_RUNTIME_IMPORT_ERROR", "details": "ModuleNotFoundError: No module named 'requests' in .venv-phase7"}
```

---

## 3. Git Isolation & Working-Tree Boundary

1. **Zero Git Tracking:** The staging directory `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\` resides entirely outside the workspace path `C:\Users\r_chh\OneDrive - optgbrc\Apps\GaurviDEEP\`.
2. **Repository Cleanliness:** No raw market data, temporary caches, or staging JSON files will ever be tracked, committed, or pushed to the `phase7-research` branch.
3. **Audit Immutability:** Any future data ingestion passes must write strictly to the staging directory and generate verification manifests before Gate 1 acceptance can be considered.
