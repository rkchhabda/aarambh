# Phase 7 Protocol: Five-Stock NSE Live Pilot (Milestone 4.9 / 4.9A / 4.9B)

## 1. Pilot Scope and Purpose

The Five-Stock NSE Live Pilot is designed to verify the end-to-end operational viability, payload integrity, and schema compliance of real upstream NSE retrieval under strict isolation.

**Milestone 4.9B Status:** The client factory interface mismatch has been **CORRECTED**. The factory protocol and signature have been canonicalized to `create_real_nse_client(download_folder: Path, server: bool = True, timeout: int = 15) -> NSEClientProtocol`. The pilot invocation strictly passes canonical keyword parameters without obsolete aliases (`data_dir`, `server_mode`). Client construction errors are sanitized to `CLIENT_FACTORY_PARAMETER_MISMATCH_HALT`. **LIVE EXECUTION REMAINS UNAUTHORIZED** until explicit owner re-authorization.

---

## 2. Frozen Pilot Parameters

| Parameter | Frozen Value | Enforcement |
| :--- | :--- | :--- |
| **Approved Universe** | `RELIANCE`, `TCS`, `HDFCBANK`, `INFY`, `ICICIBANK` | Governed set and strict sequence validation |
| **Stock Count** | Exactly 5 securities | Rejection on any additions, omissions, or order alterations |
| **Historical Period** | `2024-01-01` through `2024-01-31` | Exact date match required |
| **Data Frequency** | Daily End-of-Day (EOD) | `1d` interval strictly enforced |
| **External Staging Root**| `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9` | Must be strictly external to Git repository |
| **Authorization Marker** | `<staging-root>\authorization\pilot_authorization.json` | Single-use JSON marker outside Git; zero secrets |
| **Consumed Marker** | `pilot_authorization.consumed.<UTC_TIMESTAMP>.json` | Atomic rename prior to client creation |
| **Repository Writes** | **STRICTLY ZERO** | Prohibited; fails validation if path inside repo |

---

## 3. Dedicated Authorization Marker Creation

Single-use authorization markers are generated outside Git via a dedicated CLI without network access or client creation:

```powershell
.venv-phase7\Scripts\python.exe -m phase7.sources.authorization create `
    --staging-root "C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9" `
    --expires-minutes 30
```

### Marker Invariants
1. **Zero Secret Content:** Contains no passwords, API keys, cookies, bearer tokens, or owner phrases.
2. **Immutable Scope Binding:** Strictly binds `milestone="4.9"`, `scope="FIVE_STOCK_NSE_LIVE_PILOT"`, the 5 approved symbols, start date `2024-01-01`, end date `2024-01-31`, and interval `1d`.
3. **Staging Binding:** Cryptographically hashes the resolved staging root path into `staging_root_hash`.
4. **Single-Use Enforcement:** `single_use=True` is mandatory; marker is atomically renamed upon consumption.
5. **Deterministic SHA-256 Hash:** Recomputed and verified during pre-flight checks.

---

## 4. Dedicated Pilot CLI Entry Point

The canonical pilot command uses the single-use authorization file:

```powershell
.venv-phase7\Scripts\python.exe -m phase7.sources.pilot `
    --symbols RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK `
    --start 2024-01-01 `
    --end 2024-01-31 `
    --interval 1d `
    --staging-root "C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9" `
    --authorization-file "C:\Users\r_chh\gaurvideep_phase7_staging\nse500\pilot_4_9\authorization\pilot_authorization.json" `
    --execute-live
```

### Pre-Flight and Atomic Consumption Order
1. Parse CLI arguments.
2. Validate `--execute-live`.
3. Validate exact pilot scope (5 symbols, exact dates, 1d interval).
4. Validate staging root (strictly external to Git).
5. Load and validate authorization marker (scope, staging hash, expiry, single_use=True, SHA-256 hash).
6. Atomically rename `pilot_authorization.json` to `pilot_authorization.consumed.<UTC_TIMESTAMP>.json`.
7. Verify active marker no longer exists.
8. Verify consumed marker exists in external staging.
9. Build the download folder under external staging (`<staging-root>/raw`).
10. Invoke `create_real_nse_client(download_folder=download_folder, server=True, timeout=15)` using canonical keywords.
11. Convert any client-construction `TypeError` into sanitized `CLIENT_FACTORY_PARAMETER_MISMATCH_HALT`.
12. Only then permit the first network request.

If consumption fails, execution aborts with `AUTHORIZATION_CONSUMPTION_FAILED` and zero network requests occur.

### Canonical Client Factory Protocol Contract
- **Protocol:** `NSEClientFactoryProtocol(download_folder: Path, server: bool = True, timeout: int = 15) -> NSEClientProtocol`.
- **`download_folder`**: Absolute `pathlib.Path` strictly outside the Git repository.
- **`server`**: Strict boolean `True` for governed pilot execution.
- **`timeout`**: Strict integer `15` seconds.
- **Rejection of Unknown Keywords**: The factory rejects `data_dir`, `server_mode`, and any unexpected keyword arguments without `**kwargs` masking.
- **Zero Module-Import Invocation**: Factory is strictly invoked at runtime inside an authorized context; never on import or `--help`.

---

## 5. Execution Guardrails & Safety Invariants

1. **Sequential Execution Lock:** Requests are executed strictly one at a time under a thread lock.
2. **Mandatory Rate-Limiting Delay:** Minimum `2.0 seconds` delay enforced between successive network requests.
3. **Zero Automated Retries on Denial:**
   - HTTP 401 (Unauthorized) -> Immediate abort.
   - HTTP 403 (Forbidden / Access Denied) -> Immediate abort.
   - HTTP 429 (Rate Limit / Throttling) -> Immediate abort.
4. **Content Safety Inspection:**
   - HTML returned instead of structured data -> Immediate rejection.
   - CAPTCHA or WAF block strings -> Immediate rejection.
   - Response exceeding `15 MB` -> Immediate rejection.
5. **Immutable Audit Manifests:**
   - Every symbol request generates a cryptographic `RequestManifest` with SHA-256 checksums of the raw payload and normalized records.
   - Staged to `<staging-root>/manifests/<symbol>_<request_id>.json`.
   - Manifests strictly exclude authorization data, audit nonces, and secrets.
6. **Rejection Ledgers:**
   - Any rejected symbols or rows are appended to `<staging-root>/rejections/`.

---

## 6. Verification Checklist for Live Pilot Execution

Upon completion of live pilot retrieval in the future re-authorized checkpoint, verify:
- [ ] Exactly 5 symbols processed.
- [ ] Trading dates strictly within January 2024.
- [ ] Interval strictly 1d.
- [ ] Authorization marker atomically consumed to `pilot_authorization.consumed.<UTC_TIMESTAMP>.json`.
- [ ] Staging files located exclusively in `gaurvideep_phase7_staging`.
- [ ] Repository working tree remains 100% clean (no data files written).
- [ ] Checksum verification passes for all 5 manifests.
- [ ] Zero Phase 6 vault or target generation modules accessed.
