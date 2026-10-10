# Phase 7 Protocol: Five-Stock NSE Live Pilot (Milestone 4.9)

## 1. Pilot Scope and Purpose

The Five-Stock NSE Live Pilot is designed to verify the end-to-end operational viability, payload integrity, and schema compliance of real upstream NSE retrieval under strict isolation.

**Milestone 4.8 Status:** The live pilot is **PREPARED BUT NOT EXECUTED**. Execution is strictly unauthorized until Milestone 4.9 is explicitly authorized by the owner.

---

## 2. Frozen Pilot Parameters

| Parameter | Frozen Value | Enforcement |
| :--- | :--- | :--- |
| **Approved Universe** | `RELIANCE`, `TCS`, `HDFCBANK`, `INFY`, `ICICIBANK` | Strict allowlist check in `PilotGuard` |
| **Stock Count** | Exactly 5 securities | Rejection on any additions or omissions |
| **Historical Period** | `2024-01-01` through `2024-01-31` | Exact date match required |
| **Data Frequency** | Daily End-of-Day (EOD) | `1d` interval |
| **External Staging Root**| `C:\Users\r_chh\gaurvideep_phase7_staging\nse500\` | Must be strictly external to Git repository |
| **Repository Writes** | **STRICTLY ZERO** | Prohibited; fails validation if path inside repo |

---

## 3. Dedicated CLI Entry Point

The pilot uses a dedicated, isolated entry point (`phase7.sources.pilot`), completely decoupled from the production FastAPI application:

```powershell
.venv-phase7\Scripts\python.exe -m phase7.sources.pilot `
    --symbols RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK `
    --start 2024-01-01 `
    --end 2024-01-31 `
    --staging-root "C:\Users\r_chh\gaurvideep_phase7_staging\nse500" `
    --execute-live `
    --owner-authorization "AUTHORIZE MILESTONE 4.9: FIVE-STOCK NSE LIVE PILOT"
```

### Authorization Enforcement
- The flag `--execute-live` enables live network calls.
- The argument `--owner-authorization` must match **EXACTLY**:
  `"AUTHORIZE MILESTONE 4.9: FIVE-STOCK NSE LIVE PILOT"`
- If `--execute-live` is set without the exact phrase, the CLI raises `PermissionError` and exits immediately with code 1.
- No hardcoded bypass tokens exist.

---

## 4. Execution Guardrails & Safety Invariants

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
6. **Rejection Ledgers:**
   - Any rejected symbols or rows are appended to `<staging-root>/rejections/`.

---

## 5. Verification Checklist for Milestone 4.9

Upon completion of live pilot retrieval in Milestone 4.9, the following checks must be verified:
- [ ] Exactly 5 symbols processed.
- [ ] Trading dates strictly within January 2024.
- [ ] Staging files located exclusively in `gaurvideep_phase7_staging`.
- [ ] Repository working tree remains 100% clean (no data files written).
- [ ] Checksum verification passes for all 5 manifests.
- [ ] No Phase 6 vault or target generation modules accessed.
