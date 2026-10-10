# Phase 7 Manifest Reference: Current NIFTY 500 Constituent Snapshot

## 1. Manifest Identification

- **Request ID:** `c7924d69-aa86-4caa-a647-3cafeefdbb2f`
- **Manifest File:** `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\snapshot_4_10a\manifests\manifest_NIFTY_500_c7924d69-aa86-4caa-a647-3cafeefdbb2f.json`
- **Creation Timestamp:** `2026-10-10T10:29:46.079682+00:00`
- **Schema Version:** `phase7-constituents-snapshot-v1.0`
- **Panel Version ID:** `CURRENT_NIFTY500_09Oct2026_8F4C439F`
- **Status:** `SUCCEEDED`

---

## 2. Manifest Payload Details

```json
{
  "classification": "CURRENT_SNAPSHOT_ONLY",
  "client_version": "nse-4.0.1",
  "duplicate_isins": 0,
  "duplicate_symbols": 0,
  "duration_seconds": 1.0347845554351807,
  "failure_reason": null,
  "index_name": "NIFTY 500",
  "missing_industries": 500,
  "missing_isins": 500,
  "missing_sectors": 500,
  "missing_series": 0,
  "missing_symbols": 0,
  "normalized_checksum": "8f4c439f35fffc8ec87f107ebc9e03aef00ad26301d0912711d808ac592d117d",
  "normalized_file_path": "C:\\Users\\r_chh\\gaurvideep_phase7_staging\\nse500\\snapshot_4_10a\\normalized\\constituents\\NIFTY_500_normalized_20261010T102946Z_8f4c439f.jsonl",
  "normalized_row_count": 500,
  "panel_version_id": "CURRENT_NIFTY500_09Oct2026_8F4C439F",
  "raw_checksum": "37f6e829e79b8658d34eca431fc94fb697516f4ff0e227d690a99a4650b070a5",
  "raw_file_path": "C:\\Users\\r_chh\\gaurvideep_phase7_staging\\nse500\\snapshot_4_10a\\raw\\constituents\\NIFTY_500_snapshot_20261010T102946Z_37f6e829.json",
  "rejected_row_count": 1,
  "request_id": "c7924d69-aa86-4caa-a647-3cafeefdbb2f",
  "retrieval_timestamp": "2026-10-10T10:29:46.079682+00:00",
  "schema_version": "phase7-constituents-snapshot-v1.0",
  "source_identifier": "NSEDataFetcher",
  "source_row_count": 501,
  "status": "SUCCEEDED",
  "unique_isins": 0,
  "unique_symbols": 500
}
```

---

## 3. Storage Traceability

| Artifact Description | Storage Location Outside Git |
|---|---|
| **Raw Ingestion Payload** | `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\snapshot_4_10a\raw\constituents\NIFTY_500_snapshot_20261010T102946Z_37f6e829.json` |
| **Normalized JSONL** | `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\snapshot_4_10a\normalized\constituents\NIFTY_500_normalized_20261010T102946Z_8f4c439f.jsonl` |
| **Rejected Rows Log** | `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\snapshot_4_10a\rejected\constituents\NIFTY_500_rejected_20261010T102946Z.jsonl` |
| **Consumed Authorization Marker** | `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\snapshot_4_10a\authorization\snapshot_authorization.consumed.20261010T102946Z.json` |
| **Final Manifest** | `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\snapshot_4_10a\manifests\manifest_NIFTY_500_c7924d69-aa86-4caa-a647-3cafeefdbb2f.json` |
