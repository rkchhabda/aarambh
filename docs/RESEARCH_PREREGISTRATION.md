# Research Pre-Registration: 5-Day Directional Alpha, Phase 6

**Status:** DRAFT — pending sign-off before any modeling work begins
**Registered on:** [27.09.2026]
**Owner:** [Rakesh Chhabda]
**Repo:** GaurviDEEP

---

## 0. Why this document exists

Every prior modeling effort in this project (XGBoost, LSTM, Kronos, ARIMA, the
production ensemble, and the 309,739-observation historical band analysis)
found no directional edge on 5-day-horizon technical indicators for this
universe, net of realistic costs. Several of those efforts also produced
numbers that looked promising before verification and turned out not to hold
up — a spliced Sharpe ratio, a collapsed LSTM reporting inflated accuracy, a
"calibration improvement" that was really base-rate exploitation.

This document exists to prevent that pattern from recurring. Its rules are
binding for the full 6-month research window. **Success criteria are fixed
before any new data is touched.** They are not to be loosened, reinterpreted,
or renegotiated after seeing results. If a result doesn't meet the bar set
here, the honest outcome is "no edge found," not a redefinition of the bar.

---

## 1. Success Criteria (fixed, pre-registered)

A model is considered to have found a real, usable edge **only if all of the
following hold simultaneously**, measured on genuinely held-out data as
defined in Section 3:

| Criterion | Threshold |
|---|---|
| Test-set AUC | ≥ 0.56, with 95% CI lower bound ≥ 0.53 |
| Test-set Sharpe (net of 15bps round-trip costs) | ≥ 0.8, and must exceed Buy & Hold Sharpe on the same test period |
| Statistical significance | p < 0.01 on a pre-specified test (Section 5), correcting for multiple comparisons across however many model variants were tried |
| Economic significance | Effect size (Cohen's d or equivalent) ≥ 0.10 — NOT just statistically significant at large N |
| Stability | Result holds (same sign, broadly similar magnitude) across at least 3 of 4 non-overlapping test sub-periods, not concentrated in one window |
| Out-of-sample discipline | Test period never touched during feature selection, hyperparameter tuning, or threshold selection |

If any single criterion fails, the model does not clear the bar, full stop —
no averaging across criteria, no "close enough."

## 2. What does NOT count as progress

To avoid the failure modes already seen in this project:

- Re-weighting or re-combining the existing 12–27 technical indicators
  (`ret_1`, `rsi_14`, `macd`, `bb_pos`, `atr_14`, `obv_slope`, `sma_ratio`,
  etc.) is **not in scope**. This feature set has already had a rigorous,
  honest test (309,739 observations) and shown no edge. Time here should go
  to genuinely new information, not re-tuning what's already been ruled out.
- A backtest AUC or Sharpe that improves only on the *training* or
  *validation* split does not count, regardless of how large the
  improvement looks.
- A result found after trying many model/feature/threshold combinations does
  not count unless the multiple-comparisons correction in Section 5 is
  applied and the result still clears the bar.
- Statistical significance alone (small p-value driven by large N) does not
  count without the economic-significance threshold also being met — this
  is the exact distinction that killed the "Potential Gain" column proposal.

## 3. Data Sources In Scope (new information, not re-tuning)

Ranked by expected effort-to-signal ratio, cheapest/most-promising first:

1. **Cross-sectional / relative signals** — a stock's return relative to its
   sector or to the Nifty 100 index, rather than its own price history in
   isolation. Not yet tried anywhere in this project. Cheapest to implement
   using data already on hand.
2. **Fundamental data** — quarterly earnings surprise (actual vs. estimate),
   balance sheet quality (debt/equity, interest coverage), valuation
   relative to sector (P/E, P/B percentile within sector). Requires a new
   data source (see Section 6).
3. **Options-market signals** — India VIX level and term structure,
   put/call ratio where available for liquid names. Requires a new data
   source; may only be available for a subset of the 138-ticker universe.
4. **Macro/regime features** — beyond the existing 200-SMA regime flag:
   sector rotation indicators, FII/DII flow data if obtainable.

Anything not on this list requires updating this document (with a dated,
written rationale) before being added — not a silent scope expansion.

## 4. Timeline & Monthly Checkpoints

Six months, with mandatory checkpoints — not one long effort tested once at
the end. Each checkpoint uses fresh out-of-sample data not seen in any prior
checkpoint.

| Month | Milestone | Checkpoint Requirement |
|---|---|---|
| 1 | Data sourcing + cross-sectional/relative feature build | Report data availability, coverage gaps, feature distributions. No modeling yet. |
| 2 | First model iteration (cross-sectional features only) | Report train/val metrics only. Test set still untouched. |
| 3 | Fundamental data integration (if sourced) | Report data quality/coverage. Model iteration continues on train/val only. |
| 4 | Options/macro features (if sourced) + model refinement | Train/val metrics only. First checkpoint where feature selection/thresholds should be considered FROZEN going forward. |
| 5 | First and only look at held-out test data | Report full Section 1 criteria table, honestly, regardless of outcome. |
| 6 | Stability check on a second, later out-of-sample slice | Confirm (or fail to confirm) Month 5's result holds. Final go/no-go decision. |

**Test data must not be touched before Month 5.** Any earlier peek
invalidates the out-of-sample claim for the rest of the project.

## 5. Statistical Test Specification (fixed in advance)

- Primary test: Welch's t-test on strategy returns vs. Buy & Hold returns
  over the test period, two-sided, α = 0.01.
- Multiple-comparisons correction: Bonferroni correction applied across the
  total number of distinct model/feature-set variants evaluated against the
  test set at Month 5 (if more than one variant is tested, the significance
  bar rises accordingly — decide and log the number of variants BEFORE
  testing).
- Confidence intervals on AUC via bootstrap (1,000 resamples) on the test
  set.

## 6. Data Sourcing Notes

- Fundamental and options data sources are not yet identified as of this
  document's drafting. Sourcing (free vs. paid, coverage of the 138-ticker
  universe, historical depth available) should be the first concrete task
  in Month 1, reported before any modeling begins.
- Any new data source must be checked for the same point-in-time discipline
  already required elsewhere in this project — no fundamental data that
  wasn't actually available to a trader on that date (e.g., earnings
  reported with a lag must be timestamped to their actual release date, not
  the quarter-end date).

## 7. Separation from the Live Product

This research track runs entirely separately from the production platform:

- No results from this track are referenced in `PRODUCT_POSITIONING.md`,
  the Backtests page, the Signals page, or any customer-facing copy until
  they clear every criterion in Section 1 AND pass Month 6's stability
  check.
- The Live Forward Tracker (`regime_forward_log`, `FORWARD_TEST_PANEL`)
  continues unaffected and is not modified by this work.
- If a genuine edge is found, it becomes a new, separate, honestly-labeled
  feature — it does not retroactively validate or get merged into the
  existing Quant Score / Confidence output, which remains labeled as
  unvalidated regardless of this track's outcome.

## 8. If the Result Is Null

A null result at Month 5 or 6 is a valid, complete, useful outcome — not a
failure requiring another round. If that happens:

- Report it as plainly as the 309,739-observation band analysis did.
- Document what was tried and ruled out, so future work doesn't repeat it.
- No further "tweaking" of this research track's models without a new,
  separately-justified pre-registration document.

---

## Sign-off

By committing this document, the following is agreed: the criteria in
Section 1 will not be changed after this date, and any result — positive or
null — will be reported per Section 8's standard.

**Signed off by:** Rakesh Chhabda
**Date:** 27.09.2026
