# Holdout Access Log (Phase 6 Pre-Registration)

**Binding Pre-Registration:** [`docs/RESEARCH_PREREGISTRATION_AMENDMENT_1.md`](docs/RESEARCH_PREREGISTRATION_AMENDMENT_1.md)  
**Governing Standard:** [`docs/RESEARCH_PREREGISTRATION.md`](docs/RESEARCH_PREREGISTRATION.md)  
**Created:** 2026-09-29  
**Owner:** Rakesh Chhabda  

---

## 1. Overview and Blinding Safeguards

In accordance with **Amendment 1 Section C, D, and E**, test-set data for Phase 6 directional alpha research is split into distinct temporal segments. The holdout windows (Window A and Window B) are physically sealed inside password-protected AES-256 archives stored outside the git repository working tree.

- **Password Policy:** Archive passwords are held exclusively by the human owner. Passwords must never be committed to git, recorded in documentation, or provided to any automated agent, CI job, or loader script.
- **Access Protocol:** A holdout window can only be unsealed when the corresponding gate is reached and the model artifact, code commit hash, and variant count are frozen.
- **Audit Requirement:** When any window is unsealed, the "Opened On" and verification fields below must be filled in and committed to the repository before results are analyzed.

---

## 2. Partition Summary

| Segment | Date Range | Trading Days | Rows (Raw) | Rows (Features) | Status / Location |
|---|---|---|---|---|---|
| **Development** | 2016-09-26 to 2025-09-16 | 2,218 | 302,305 | 302,305 | Open (`data/multi/historical_10y_raw.csv`, `data/multi/relative_features_v1.csv`) |
| **Purge Gap** | 2025-09-17 to 2025-09-30 | 10 | 1,380 | 1,380 | Isolated from training labels (10 trading days lookahead purge) |
| **Window A** | 2025-10-01 to 2026-03-31 | 122 | 16,829 | 16,829 | **SEALED** (`window_a_sealed.7z` in external vault) |
| **Window B** | 2026-04-01 to 2026-09-25 | 126 | 17,377 | 17,377 | **SEALED** (`window_b_sealed.7z` in external vault) |
| **Total** | 2016-09-26 to 2026-09-25 | 2,476 | 337,891 | 337,891 | Full 10-year historical dataset |

---

## 3. Sealed Holdout Archives

### Window A (First Test Holdout — Gate 5)

*Window A is opened once only at Gate 5 after all modeling, feature selection, and hyperparameters are frozen.*

- **Status:** SEALED
- **Archive Filename:** `window_a_sealed.7z`
- **Archive SHA-256:** `71d16366ea3b8b7e7388ba1119e7a14f94fdbd19a474e85ed1fcbf829d364b6f`
- **External Storage Location:** `C:\Users\r_chh\gaurvideep_vault\window_a_sealed.7z`
- **Backup Location:** `C:\Users\r_chh\OneDrive - optgbrc\Apps\gaurvideep_vault\window_a_sealed.7z`
- **Date Range:** 2025-10-01 to 2026-03-31 (actual trading dates: 2025-10-01 to 2026-03-30)
- **Trading Days:** 122
- **Contained Files & Uncompressed SHA-256 Hashes:**
  - `historical_10y_raw_window_a.csv`: 16,829 rows  
    `fe5191d0d3259826b2ac630d67c5bf9e258b17f7ab26353643aa7385fd190b6f`
  - `relative_features_v1_window_a.csv`: 16,829 rows  
    `e1c76d0a7ea5383b0981ac79f732404fcfd9473d87256e8a7ff9ba897d6d2614`

#### Window A Access Log
- **Opened On:** 
- **Opened By:** 
- **Reason / Gate:** Gate 5 First Model Evaluation
- **Frozen Git Commit Hash:** 
- **Frozen Model Artifact SHA-256:** 
- **Number of Model Variants Tested:** 
- **Section 1 Criteria Evaluation Results:**
  - Test-set AUC (95% CI): 
  - Test-set Sharpe (net 15bps): 
  - Buy & Hold Sharpe comparison: 
  - Statistical Significance (p-value, adjusted): 
  - Economic Significance (Cohen's d): 
  - Sub-period Stability (Oct-Dec 2025, Jan-Mar 2026): 
  - Verdict (PASS / FAIL): 

---

### Window B (Replication Test Holdout — Gate 6)

*Window B is opened once only at Gate 6, and ONLY if Window A has passed all Section 1 criteria without modification. If Window A fails, Window B remains permanently sealed for this model variant.*

- **Status:** SEALED
- **Archive Filename:** `window_b_sealed.7z`
- **Archive SHA-256:** `2e76ad72536d9df095e352c218c2acd3eee8cacea581d25eb1828795b4a89965`
- **External Storage Location:** `C:\Users\r_chh\gaurvideep_vault\window_b_sealed.7z`
- **Backup Location:** `C:\Users\r_chh\OneDrive - optgbrc\Apps\gaurvideep_vault\window_b_sealed.7z`
- **Date Range:** 2026-04-01 to 2026-09-25
- **Trading Days:** 126
- **Contained Files & Uncompressed SHA-256 Hashes:**
  - `historical_10y_raw_window_b.csv`: 17,377 rows  
    `4ea30c60914f71cad29bf6e747d583b1e7f887352ea3780b767cee066eba75f8`
  - `relative_features_v1_window_b.csv`: 17,377 rows  
    `dc39fcfed587b2a9680800cd090378c68f65862f393a26b6fbd16b476a752223`

#### Window B Access Log
- **Opened On:** 
- **Opened By:** 
- **Reason / Gate:** Gate 6 Replication Evaluation
- **Frozen Git Commit Hash:** 
- **Frozen Model Artifact SHA-256:** 
- **Section 1 Replication Evaluation Results:**
  - Test-set AUC (95% CI): 
  - Test-set Sharpe (net 15bps): 
  - Buy & Hold Sharpe comparison: 
  - Statistical Significance (p-value, adjusted): 
  - Economic Significance (Cohen's d): 
  - Sub-period Stability (Apr-Jun 2026, Jul-Sep 2026): 
  - Verdict (REPLICATED / FAILED): 

---

## 4. Verification Checksums

To verify that the sealed archive has not been modified or corrupted prior to unsealing, execute:
```powershell
Get-FileHash -Algorithm SHA256 "C:\Users\r_chh\gaurvideep_vault\window_a_sealed.7z"
Get-FileHash -Algorithm SHA256 "C:\Users\r_chh\gaurvideep_vault\window_b_sealed.7z"
```
The output must match the SHA-256 hashes recorded above.
