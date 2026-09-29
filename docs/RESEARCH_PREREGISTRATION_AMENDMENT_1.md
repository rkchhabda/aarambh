# Amendment 1 to Research Pre-Registration (Phase 6)

**Amends:** `docs/RESEARCH_PREREGISTRATION.md` (signed 27.09.2026)
**Amendment date:** 29.09.2026
**Owner:** Rakesh Chhabda
**Status:** DRAFT until signed below

Append this file to the repo as `docs/RESEARCH_PREREGISTRATION_AMENDMENT_1.md`.
Do NOT edit the original signed document. The original stays intact in git
history; this amendment sits beside it, so the audit trail shows exactly what
changed, when, and why.

---

## A. What this amendment changes, and what it does not

**Changed:** the timeline and test-data rules in Section 4 ("Test data must
not be touched before Month 5", and the implicit assumption that the test
period is future data only).

**Unchanged (binding exactly as originally signed):**
- Section 1: all success criteria and thresholds
- Section 2: what does not count as progress
- Section 3: data sources in scope
- Section 5: statistical test specification, including the multiple-comparisons rule
- Section 7: separation from the live product
- Section 8: null-result handling

No threshold in this amendment was set or adjusted after looking at any
result from this research track.

## B. Rationale

Nine years of history already exist on disk. Waiting for future calendar time
before testing costs months and adds no statistical rigor by itself. The
original plan preferred future-only data for one reason: it cannot be peeked
at. This amendment keeps that protection by sealing already-elapsed data
instead, and adds a genuine forward-data confirmation for anything customers
will see.

## C. New data partition

| Segment | Dates | Use |
|---|---|---|
| Development (train + validation, walk-forward inside) | 2016-09-26 to 2025-09-30, minus purge gap | All feature selection, tuning, thresholds. Fully open. |
| Purge gap | Last 10 trading days before Window A | Excluded from training labels (labels look 5 days forward). |
| **Window A** (sealed) | 2025-10-01 to 2026-03-31 | First test. Opened once. |
| **Window B** (sealed) | 2026-04-01 to 2026-09-25 (dataset end) | Replication test. Opened once, only if Window A passes. |
| **Window C** (forward) | 2026-09-29 onward (live pipeline) | Confirmation required before any customer-facing claim. |

Sub-period mapping for the Section 1 stability criterion: the four
non-overlapping test sub-periods are Oct-Dec 2025, Jan-Mar 2026, Apr-Jun 2026,
and Jul-Sep 2026. At least 3 of 4 must satisfy the criterion.

## D. Rules for opening the windows

1. **Freeze first.** Before Window A is opened, the model, features,
   hyperparameters, thresholds, and the number of variants tested are frozen.
   Record the git commit hash of the frozen code and the SHA-256 of the model
   artifact in `docs/holdout_access_log.md`.
2. **Window A opens once.** Evaluate all Section 1 criteria. Record the result
   exactly as observed.
3. **If Window A fails,** the variant has failed. Window B stays sealed and
   remains available for a future, separately pre-registered attempt. No
   retuning and re-testing on Window A.
4. **If Window A passes,** the model stays frozen. Any change after seeing
   Window A turns Window B into a development set, and the result is
   reported as null under Section 8.
5. **Window B opens once,** after Window A is logged. It must replicate the
   Section 1 criteria.
6. **Window C (forward confirmation).** A customer-facing claim requires
   Windows A and B both passed, plus at least 60 trading days of live forward
   data in which the result does not contradict the earlier finding (same
   sign, not significantly worse). Sixty days cannot establish significance
   on its own; it exists to catch a result that only worked on already-elapsed
   history.

## E. Physical safeguards (and their limits)

- Sealed files are stored outside the repository working tree as a
  password-protected archive. The password is held by the owner only.
- The repository stores only the SHA-256 hashes, row counts, and date ranges
  of the sealed files, never the data.
- All Phase 6 development code loads data through a single module that
  refuses any row dated after the development cutoff.
- A CI check fails if Phase 6 code reads the raw historical or feature CSVs
  directly.
- Every window opening is written to `docs/holdout_access_log.md` and committed.

**Honest limit:** these measures prevent accidental reads and make deliberate
reads visible. They do not make peeking impossible. A person or tool with full
disk access can always read a file. The log and hashes exist so a breach would
be detectable and disclosed, not so it is inconceivable.

## F. Prior exposure disclosure

Windows A and B are historical data, so blinding is weaker than with future
data. Known exposure to disclose:

1. Month 1 distribution statistics (mean, std, range) for the relative-return
   features were computed over the full period, including dates that now fall
   in Windows A and B. This was descriptive only, with no outcome variable and
   no model fitting.
2. The owner has seen 2026 market behavior in aggregate: live dashboards,
   backtests through August 2026, and the 309,739-observation SMA-band
   analysis, which included 2026 forward returns.

Because of this, Windows A and B are treated as historical holdouts with
known partial exposure. This is why Window C is mandatory for any public claim.

## G. Timeline

The monthly schedule in Section 4 is replaced by sequential gates. Calendar
duration is a target, not a required wait.

| Gate | Milestone | Requirement |
|---|---|---|
| 1 | Cross-sectional feature build | Done (Month 1). |
| 2 | First model, cross-sectional features only | Development data only. |
| 3 | Fundamental data integration (if sourced) | Development data only. |
| 4 | Options/macro features (if sourced), refinement, FREEZE | Log hashes and variant count. |
| 5 | Open Window A | Once. Full Section 1 table reported. |
| 6 | Open Window B | Only if Gate 5 passes. |
| 7 | Window C accrual | 60+ trading days before any public claim. |

---

## Sign-off

By committing this amendment, the owner agrees that Sections D and E bind all
subsequent work, and that a result from any window is reported as observed,
whether positive or null.

**Signed off by:** Rakesh Chhabda
**Date:** 29.09.2026
