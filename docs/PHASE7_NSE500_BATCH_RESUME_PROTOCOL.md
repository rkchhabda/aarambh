# Phase 7 Protocol: Batch Checkpointing & Resume Verification

## 1. Overview & Objective

To prevent data loss, unrecorded duplicates, or corrupted multi-symbol acquisition runs during large historical batches, the batch harness implements an **atomic checkpointing and strict resume verification architecture**.

---

## 2. Checkpoint Data Structure

The checkpoint state is tracked in `<staging_root>/checkpoints/batch_checkpoint.json` with the following schema:

```json
{
  "batch_id": "BATCH_4_10C_HISTORICAL_20STOCK_2024Q1",
  "total_symbols": 20,
  "completed_symbols": 0,
  "pending_symbols": 20,
  "failed_symbols": 0,
  "source_rows": 0,
  "normalized_rows": 0,
  "rejected_rows": 0,
  "raw_checksums": {},
  "normalized_checksums": {},
  "manifest_checksums": {},
  "symbol_states": {
    "<SYMBOL>": {
      "symbol": "<SYMBOL>",
      "status": "NOT_STARTED | PENDING | SUCCEEDED | FAILED | HALTED",
      "request_id": "<UUID>",
      "raw_file_path": "<PATH>",
      "normalized_file_path": "<PATH>",
      "manifest_file_path": "<PATH>",
      "raw_checksum": "<SHA256>",
      "normalized_checksum": "<SHA256>",
      "manifest_checksum": "<SHA256>",
      "source_rows": 0,
      "normalized_rows": 0,
      "rejected_rows": 0,
      "error_message": null,
      "last_updated": "<ISO_TIMESTAMP>"
    }
  },
  "start_timestamp": "<ISO_TIMESTAMP>",
  "last_checkpoint_timestamp": "<ISO_TIMESTAMP>",
  "stop_reason": null,
  "final_status": "INITIALIZED | IN_PROGRESS | SUCCEEDED | FAILED | HALTED"
}
```

---

## 3. Strict 10-Point Resume Verification Rules

Before resuming any batch, the orchestrator evaluates all 10 integrity conditions for every completed symbol. A symbol is trusted **only if all 10 conditions pass**:

1. **Manifest File Existence:** The finalized symbol manifest file exists at the specified path.
2. **Manifest Status:** The manifest status is strictly `SUCCEEDED` (or `SUCCESS`).
3. **Raw File Existence:** The raw historical payload JSON file exists on disk outside Git.
4. **Raw Checksum Match:** The raw file SHA-256 matches both the checkpoint entry and the manifest entry.
5. **Normalized File Existence:** The normalized historical JSONL file exists on disk outside Git.
6. **Normalized Checksum Match:** The normalized file SHA-256 matches both the checkpoint entry and the manifest entry.
7. **Row Conservation Integrity:** Conservation strictly holds: $\text{source\_rows} = \text{normalized\_rows} + \text{rejected\_rows}$.
8. **Selection Membership:** The symbol strictly belongs to the governed 20-symbol selection.
9. **Temporal & Interval Match:** The start date (`2024-01-01`), end date (`2024-03-31`), and interval (`1d`) recorded in the manifest match the batch contract.
10. **Schema Version Match:** The schema mapping version matches `NSE_4_0_1_HISTORICAL_CAMELCASE_V1`.

---

## 4. Fail-Closed Handling & Safety Rules

- **Zero Silent Overwrite:** If any check fails, existing evidence is **never overwritten or repaired automatically**.
- **Exception Halt:** An `InvalidResumeCheckpointError` is raised immediately, mapping to exit code `11` (`INVALID_RESUME_CHECKPOINT`).
- **No Automatic Resume:** A batch run will **never automatically resume** after halting or crashing. Resuming requires:
  1. Explicit CLI invocation with `--resume`;
  2. Owner review of prior failure logs;
  3. Creation of a **brand-new, single-use authorization marker** scoped to the batch.
