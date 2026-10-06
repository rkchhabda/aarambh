# Phase 7 — Technical Implementation Map

**Repository:** GaurviDEEP
**Working Branch:** `phase7-research`
**Base Commit:** `c978968ec822aa20453920c8708673fcaa736695`
**Governing Standard:** Pre-registered, modular, fail-closed quantitative research architecture.
**Created:** 2026-10-05

---

## 1. Architectural Architecture & Module Mapping

```mermaid
flowchart TD
    subgraph Phase7Package["Dedicated Phase 7 Package (phase7/)"]
        subgraph Data["1. Data Engine (phase7/data/)"]
            Contracts["contracts.py<br/>(Pydantic Schemas & Hashes)"]
            Universe["universe.py<br/>(PIT Nifty 500 Builder)"]
            Loaders["loaders.py<br/>(Cutoff-Enforced Loaders)"]
            CAEngine["corporate_actions.py<br/>(Splits & Bonuses)"]
        end

        subgraph Targets["2. Target Engine (phase7/targets/)"]
            T20["engine.py<br/>(20d Sector-Relative & 60d Residual)"]
        end

        subgraph Validation["3. Validation (phase7/validation/)"]
            WF["walk_forward.py<br/>(10 Expanding Folds)"]
            PE["purge_embargo.py<br/>(Purge >=20d, Embargo >=5d)"]
        end

        subgraph Features["4. Features (phase7/features/)"]
            Mom["momentum.py<br/>(12-1m, 6m Rel, 3m Res)"]
            Qual["quality.py<br/>(SUE, Cash Flow, Dilution)"]
            Val["valuation.py<br/>(Percentiles, Yields)"]
        end

        subgraph Models["5. Models (phase7/models/)"]
            Baselines["baselines.py<br/>(EW, Sector-Neutral, Momentum)"]
            Linear["linear.py<br/>(Ridge, ElasticNet)"]
            Trees["tree.py<br/>(LightGBM, XGBoost)"]
            Rankers["ranking.py<br/>(LambdaRank)"]
        end

        subgraph Portfolio["6. Portfolio & Execution (phase7/portfolio/)"]
            Cons["construction.py<br/>(Top 20 Long-Only, EW)"]
            Costs["costs.py<br/>(25, 50, 75 bps Staged Costs)"]
            Risk["constraints.py<br/>(Max 5% Stock, 25% Sector)"]
        end

        subgraph Metrics["7. Metrics & Robustness (phase7/metrics/)"]
            RankIC["ranking.py<br/>(Rank IC, Monotonicity)"]
            Perf["performance.py<br/>(Sharpe, Sortino, Calmar, MaxDD)"]
            Robust["deflated_sharpe.py<br/>(Bootstrap, DSR, PBO)"]
        end

        subgraph Gov["8. Governance & Auditing (phase7/governance/)"]
            Reg["registry.py<br/>(Append-Only Experiment Store)"]
            DecLog["decision_log.py<br/>(Decision Ledger)"]
            Bound["boundary.py<br/>(Phase 6 Vault Defense)"]
        end

        subgraph Shadow["9. Live Shadow (phase7/live_shadow/)"]
            Ledger["ledger.py<br/>(Append-Only Predictions)"]
            Eval["evaluator.py<br/>(T+1 Executable Returns)"]
        end
    end

    Data --> Targets
    Data --> Features
    Targets --> Validation
    Features --> Validation
    Validation --> Models
    Models --> Portfolio
    Portfolio --> Metrics
    Metrics --> Gov
    Gov --> Shadow
```

---

## 2. Existing Modules to Reuse vs Quarantined Code

### 2.1 Existing Modules to Reuse (with Adaptation)
1. **`scripts/phase6/corporate_action_engine.py` $\to$ `phase7/data/corporate_actions.py`:**
   - Reuse verified regex parsing for NSE bonus and split circulars (`bonus N:D`, `split from X to Y`).
   - Enhance to handle cash dividends and compute cumulative Total Return adjustment factors.
2. **`scripts/phase6/data_loader.py` Pattern $\to$ `phase7/data/loaders.py`:**
   - Adopt the strict fail-closed boundary enforcement pattern (`_validate_date_bounds`, `PreRegistrationDataLeakError`).
   - Reconfigure for Phase 7 temporal split boundaries and multi-table schemas.
3. **`data/fundamentals/sue_features_quarterly.csv`:**
   - Ingest as verified historical point-in-time standardized unexpected earnings data for 134 equities (2018–2025).
4. **`scripts/verification/*_stress_test.py` $\to$ `phase7/metrics/robustness.py`:**
   - Reuse calculation logic for maximum drawdowns, underwater series, and Covid-period regime stress slicing.

### 2.2 Modules Requiring Complete Isolation or Quarantining
1. **`features/universe.py`:**
   - **Status:** The static legacy universe is prohibited as a Phase 7 universe provider and protected by automated boundary tests.
   - **Phase 7 Replacement:** `phase7/data/universe.py` constructs dynamic, point-in-time universes per date.
2. **`features/indicators.py`:**
   - **Quarantine:** Contains 27 legacy technical indicators (RSI, MACD, Stochastics, Williams %R) which are not authorized in Phase 7 without an approved preregistered amendment.
3. **`service/app.py` & `service/routes_*.py`:**
   - **Quarantine:** Production API endpoints. Phase 7 research code must have zero runtime coupling with FastAPI service routes.
4. **`service/models/*`:**
   - **Quarantine:** Legacy model weights (`.pt`, `.pkl`) and cached states must never be loaded into Phase 7 pipelines.
5. **Phase 6 Scripts (`scripts/phase6/*`):**
   - **Quarantine:** Phase 6 models evaluated single-stock 5-day directional binary labels. Must remain untouched as historical records.

---

## 3. Proposed Phase 7 Package Structure

```
GaurviDEEP/
├── config/
│   └── phase7.yaml                     # Frozen Phase 7 research configuration
├── phase7/
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── contracts.py                # Pydantic schemas, column validators, hash checkers
│   │   ├── universe.py                 # Point-in-time eligible universe builder & filters
│   │   ├── loaders.py                  # Strict time-bounded data loaders with fail-closed checks
│   │   └── corporate_actions.py        # Corporate action split/bonus/dividend adjustment engine
│   ├── targets/
│   │   ├── __init__.py
│   │   └── engine.py                   # 20d sector-relative and 60d residual return calculators
│   ├── features/
│   │   ├── __init__.py
│   │   ├── momentum.py                 # 12-1m, 6m sector-rel, 3m residual, 52w high distance
│   │   ├── quality.py                  # SUE, cash flow, debt, margin, and dilution metrics
│   │   └── valuation.py                # Sector-relative valuation percentiles and yields
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── walk_forward.py             # >=10 expanding walk-forward fold generator
│   │   └── purge_embargo.py            # Purge (>=20d) and embargo (>=5d) interval masking
│   ├── models/
│   │   ├── __init__.py
│   │   ├── baselines.py                # EW universe, Sector-neutral EW, 12-1 Momentum, Composites
│   │   ├── linear.py                   # Fold-local Ridge regression, ElasticNet
│   │   ├── tree.py                     # Constrained LightGBM & XGBoost regressors
│   │   └── ranking.py                  # LightGBM LambdaRank & XGBoost pairwise ranking
│   ├── portfolio/
│   │   ├── __init__.py
│   │   ├── construction.py             # Top 20 long-only, weekly rebalance, equal-weight allocation
│   │   ├── costs.py                    # Granular transaction-cost engine (STT, GST, spread, impact)
│   │   └── constraints.py              # Max 5% stock, 25% sector, liquidity cap (<=5% 60d MDTV)
│   ├── metrics/
│   │   ├── __init__.py
│   │   ├── ranking.py                  # Cross-sectional Rank IC, monotonicity, quintile spreads
│   │   ├── performance.py              # Net Sharpe, Sortino, Calmar, Max Drawdown, Turnover
│   │   └── deflated_sharpe.py          # Block-bootstrap CIs, Deflated Sharpe, PBO estimation
│   ├── governance/
│   │   ├── __init__.py
│   │   ├── registry.py                 # Append-only experiment trial ledger (JSONL/Parquet)
│   │   ├── decision_log.py             # Preregistration amendment and decision logging
│   │   ├── boundary.py                 # Guard tests asserting zero Phase 6 vault intrusion
│   │   └── schemas.py                  # JSON schema validation for phase7.yaml
│   └── live_shadow/
│       ├── __init__.py
│       ├── ledger.py                   # Append-only live prediction recording (SELECT/WATCH/NO_OPP)
│       └── evaluator.py                # T+1 executable price outcome grader & health auditor
├── tests/phase7/
│   ├── __init__.py
│   ├── test_point_in_time_integrity.py
│   ├── test_no_future_features.py
│   ├── test_universe_survivorship.py
│   ├── test_target_isolation.py
│   ├── test_purge_embargo.py
│   ├── test_fold_local_preprocessing.py
│   ├── test_corporate_action_adjustments.py
│   ├── test_transaction_costs.py
│   ├── test_portfolio_constraints.py
│   ├── test_experiment_registry.py
│   ├── test_prediction_immutability.py
│   ├── test_phase6_boundary.py
│   └── test_config_schema.py
└── artifacts/phase7/
    └── .gitkeep
```

---

## 4. Proposed Implementation by Milestone

| Milestone | Key Deliverables | Code & Configuration Modules | Unit & Guard Tests |
|---|---|---|---|
| **M1: Preregistration & Config** | Preregistration document, execution plan, data dictionary, model card template, YAML config, boundary guard | `config/phase7.yaml`, `phase7/__init__.py`, `phase7/governance/__init__.py`, `phase7/governance/schemas.py` | `tests/phase7/test_phase6_boundary.py`, `tests/phase7/test_config_schema.py` |
| **M2: Data Contracts & Universe** | Data contracts, PIT universe builder, exclusion codes, CA engine | `phase7/data/contracts.py`, `phase7/data/universe.py`, `phase7/data/loaders.py`, `phase7/data/corporate_actions.py` | `tests/phase7/test_point_in_time_integrity.py`, `tests/phase7/test_universe_survivorship.py`, `tests/phase7/test_corporate_action_adjustments.py` |
| **M3: Target Engine** | 20d sector-relative target, 60d residual target, next-session execution | `phase7/targets/engine.py` | `tests/phase7/test_target_isolation.py`, `tests/phase7/test_execution_delay.py` |
| **M4: Walk-Forward Validation** | 10 expanding folds, purge ($\ge 20$d), embargo ($\ge 5$d), fold-local scaling | `phase7/validation/walk_forward.py`, `phase7/validation/purge_embargo.py` | `tests/phase7/test_purge_embargo.py`, `tests/phase7/test_fold_local_preprocessing.py` |
| **M5: Non-ML Baselines** | EW universe, Sector-neutral EW, 12-1 Momentum, Multi-factor composite | `phase7/models/baselines.py`, `phase7/metrics/ranking.py`, `phase7/metrics/performance.py` | `tests/phase7/test_baselines_reproducibility.py` |
| **M6: Linear Models** | Ridge regression, ElasticNet, append-only experiment logging | `phase7/models/linear.py`, `phase7/governance/registry.py` | `tests/phase7/test_linear_models.py`, `tests/phase7/test_experiment_registry.py` |
| **M7: Tree & Ranking Models** | Constrained LightGBM, XGBoost, LambdaRank, feature stability | `phase7/models/tree.py`, `phase7/models/ranking.py` | `tests/phase7/test_ranking_models.py` |
| **M8: Portfolio & Cost Engine** | Top 20 allocation, constraints (5% stock, 25% sector), 25/50/75 bps costs | `phase7/portfolio/construction.py`, `phase7/portfolio/costs.py`, `phase7/portfolio/constraints.py` | `tests/phase7/test_transaction_costs.py`, `tests/phase7/test_portfolio_constraints.py` |
| **M9: Robustness & Multiple Testing** | 6 regimes, sector attribution, jackknife (drop best month/5 trades), DSR, PBO | `phase7/metrics/deflated_sharpe.py`, `phase7/metrics/robustness.py` | `tests/phase7/test_deflated_sharpe.py`, `tests/phase7/test_regime_stability.py` |
| **M10: Development Freeze** | Candidate model card, freeze manifest, environment lock, holdout procedure | `docs/PHASE7_CANDIDATE_MODEL_CARD.md`, `artifacts/phase7/freeze_manifest.json` | Full test suite verification |
| **M11: Sealed Holdout Evaluation** | Single holdout run on new Phase 7 vault, immutable results log | `phase7/governance/holdout_audit.py` | `tests/phase7/test_holdout_access_integrity.py` |
| **M12: Live Shadow Portfolio** | Append-only shadow ledger, weekly predictions, $t+1$ tracking | `phase7/live_shadow/ledger.py`, `phase7/live_shadow/evaluator.py` | `tests/phase7/test_prediction_immutability.py` |

---

## 5. Data Flow and Integrity Architecture

```
Point-in-Time Data Sources
  ├── NSE Historical Daily OHLCV + Turnover (Adjusted for splits/bonuses)
  ├── Point-in-Time Nifty 500 Additions/Deletions with Effective Dates
  ├── Sector & Industry Reclassification Master with Effective Dates
  └── Corporate Disclosures with broadCastDate / first_seen_timestamp
       │
       ▼
[phase7.data.loaders & contracts]
  ├── Validates row hashes, monotonic timestamps, schema types
  └── Refuses any row with timestamp > fold_cutoff_timestamp
       │
       ▼
[phase7.targets.engine] ─── (Isolated from Feature Engine)
  ├── target_20d_sector_relative = stock_ret(t+1 -> t+20) - sector_ret(t+1 -> t+20)
  └── target_60d_residual = stock_ret(t+1 -> t+60) - beta * market_ret(t+1 -> t+60)
       │
       ▼
[phase7.validation.walk_forward]
  ├── Defines Fold k: Train[t0 -> tk], Test[tk + Purge + Embargo -> tk + Window]
  ├── Fits Preprocessing (imputation, winsorization, rank-scaling) STRICTLY on Train fold
  └── Evaluates Cross-Sectional Rank IC & Monotonicity on Out-of-Sample Test fold
       │
       ▼
[phase7.portfolio.construction & costs]
  ├── Ranks eligible universe cross-sectionally
  ├── Filters: Liquidity >= INR 10 cr MDTV, Price >= INR 20, 252d history
  ├── Selects Top 20 stocks; weights: min(equal_weight, 5% max stock weight)
  ├── Bounds sector exposure <= 25%
  └── Simulates execution at next-session executable price with 25/50/75 bps cost deduction
       │
       ▼
[phase7.governance.registry]
  └── Appends immutable trial record (hashes, parameters, IC, Sharpe, Drawdown, decision)
```

---

## 6. Dependency Plan & Environment Strategy

1. **Python Runtime Resolution (BLK-06):**
   - The current default host Python runtime (Python 3.14.4) encounters fatal Windows memory access violations in pandas datetime indexing.
   - For all Phase 7 research execution and testing, configure execution under Python 3.11 (`C:\Users\r_chh\AppData\Local\Programs\Python\Python311\python.exe`) or Python 3.12 (matching GitHub Actions).
2. **Package Version Pinning:**
   - Standardize dependencies via an explicit `requirements-phase7.txt` referencing pinned versions:
     - `numpy==2.2.*` or `numpy>=1.26,<3`
     - `pandas>=2.2,<3`
     - `scikit-learn>=1.5,<2`
     - `lightgbm>=4.5`
     - `xgboost>=3.0`
     - `scipy>=1.14`
     - `pyyaml>=6.0`
     - `pydantic>=2.10`
     - `pytest>=8.0`

---

## 7. Explicit List of Files Proposed for Milestone 1

Upon receiving explicit owner approval (`APPROVE MILESTONE 1`), Milestone 1 will author and commit exactly the following set of governance, documentation, and configuration files:

### Documentation Deliverables:
1. `docs/PHASE7_RESEARCH_PREREGISTRATION.md` (Formal binding preregistration document).
2. `docs/PHASE7_EXECUTION_PLAN.md` (Step-by-step operational research protocol).
3. `docs/PHASE7_DATA_DICTIONARY.md` (Formal schemas, column definitions, units, and timestamps).
4. `docs/PHASE7_MODEL_CARD_TEMPLATE.md` (Standardized reporting card for candidate models).
5. `docs/PHASE7_HOLDOUT_PROTOCOL.md` (Sealed holdout partitioning, blinding, and verification rules).
6. `docs/PHASE7_LIVE_SHADOW_PROTOCOL.md` (Paper trading ledger, execution delay, and audit standards).
7. `docs/PHASE7_DECISION_LOG.md` (Append-only record of all research decisions and amendments).

### Configuration & Schema Deliverables:
8. `config/phase7.yaml` (Machine-readable configuration specifying targets, folds, universe, features, costs).
9. `phase7/__init__.py` (Phase 7 top-level package initialisation).
10. `phase7/governance/__init__.py` (Governance package initialisation).
11. `phase7/governance/schemas.py` (Pydantic / JSON schema validator for `config/phase7.yaml`).

### Guard Tests:
12. `tests/phase7/__init__.py`
13. `tests/phase7/test_phase6_boundary.py` (Automated CI test asserting zero intrusion on Phase 6 vaults or files).
14. `tests/phase7/test_config_schema.py` (Automated CI test verifying validity of `config/phase7.yaml`).

No quantitative models will be trained, and no market data will be ingested during Milestone 1.

---

## 8. Milestone 2 Delivered Artifacts & Requirements-to-Tests Matrix

Milestone 2 delivered canonical data contracts, point-in-time universe interfaces, corporate action adjustments, and fail-closed loaders under the status **`CONTRACT_READY_REAL_DATA_BLOCKED`**:

### Delivered Modules (`phase7/data/`):
1. `phase7/data/__init__.py`: Package export initialization.
2. `phase7/data/contracts.py`: Frozen dataclasses (`DailyPriceRecord`, `PITMembershipRecord`, `PITMembershipEventRecord`, `PITSectorClassificationRecord`, `CorporateActionAdjustmentRecord`, `EligibilitySuspensionRecord`, `PITFinancialStatementRecord`, `PITCorporateAnnouncementRecord`, `PITShareholdingRecord`), enums (`TradedValueStatus`, `PriceAdjustmentState`, `CorporateActionType`, `ExclusionReason`), event-to-interval conversion (`convert_membership_events_to_intervals`), and deterministic SHA-256 `compute_row_hash`.
3. `phase7/data/corporate_actions.py`: `CorporateActionEngine` handling splits, bonuses, cash dividends, total-return factor adjustments, canonical alias mapping, double-adjustment rejection, and fail-closed routing for complex actions (`MANUAL_REVIEW`).
4. `phase7/data/universe.py`: `PointInTimeUniverseBuilder` implementing 252-day history, 60-day MDTV $\ge$ INR 10 crore, and price $\ge$ INR 20 filters, multi-reason exclusion codes, deterministic universe hash, and granular status outputs (`SUCCESS`, `BLOCKED_MISSING_MEMBERSHIP`, `BLOCKED_MISSING_PRICE_LIQUIDITY`, `BLOCKED_MISSING_SECTOR_HISTORY`, `VALID_EMPTY_UNIVERSE`).
5. `phase7/data/loaders.py`: Streaming fail-closed CSV and JSONL loaders (`CSVDataLoader`, `JSONLinesDataLoader`, `parse_membership_event_row`) tracking 1-based row numbers, rejection reasons, non-zero coercion of malformed values, and duplicate key detection.
6. `phase7/data/audit.py`: Dataset audit report generator capturing structural summary and explicitly prohibiting return or alpha reporting.

### Delivered Test Suites (`tests/phase7/`):
1. `tests/phase7/test_point_in_time_integrity.py`: 23 tests verifying deterministic SHA-256 hashing, UTC normalization, open-ended intervals, point-in-time membership boundaries, event-to-interval conversion edge cases, sector temporal intervals, gated interface timestamp distinctions, hash tampering detection, and ISIN structural-format validation.
2. `tests/phase7/test_no_future_features.py`: 4 tests verifying future price isolation, future sector backfill prevention, future source timestamp rejection, and quarterly period-end vs availability date separation.
3. `tests/phase7/test_universe_survivorship.py`: 17 tests verifying survivorship filters, 252-day history, liquidity thresholding, multi-reason exclusion tracking, trading suspension handling, turnover derivation rules, granular universe build statuses, deterministic sorting/hashing, security-level vs build-level data validation failures, future data accounting and audit counters, and missing vs invalid turnover differentiation.
4. `tests/phase7/test_corporate_action_adjustments.py`: 8 tests verifying stock split ratios, bonus ratios, cash dividend total return adjustments, canonical alias mappings, double-adjustment rejection, and manual review routing for complex/restructuring actions.
5. `tests/phase7/test_data_loaders.py`: 5 tests verifying 1-based CSV row tracking, rejection reason preservation, non-zero coercion, zero investment performance reporting in audit reports, audit future-record tracking and turnover status separation, and zero forbidden imports.
6. `tests/phase7/test_phase6_boundary.py`: 6 tests verifying Phase 6 vault defense, static universe provider prohibition, and governance documentation integrity.
7. `tests/phase7/test_config_schema.py`: 7 tests verifying configuration schema, basis points enforcement, negative cost prevention, and execution delay.
8. `test_phase6_safeguards.py`: 4 tests verifying Phase 6 development cutoff and data access boundaries.

### Requirements-to-Tests Traceability Matrix

| Requirement Area | Detailed Specification | Test Module | Test Method(s) | Status |
|---|---|---|---|---|
| **Data Contracts & Hashing** | Frozen dataclasses, Decimal fields, ISO UTC timestamps, deterministic SHA-256 row hash | `tests/phase7/test_point_in_time_integrity.py` | `test_deterministic_row_hash_identical_records`, `test_equivalent_utc_instants_normalize_consistently`, `test_field_order_difference_does_not_change_hash`, `test_material_field_change_alters_hash`, `test_row_hash_field_itself_excluded`, `test_supplied_hash_mismatch_detected`, `test_timezone_naive_timestamp_rejected` | **VERIFIED** |
| **ISIN Structural Validation** | Strict 12-char alphanumeric regex (`^[A-Z]{2}[A-Z0-9]{9}[0-9]$`), check-digit calculation disclaimed | `tests/phase7/test_point_in_time_integrity.py` | `test_missing_or_invalid_isin_raises_error`, `test_isin_structural_format_validation` | **VERIFIED** |
| **Membership Event Conversion** | Interval synthesis from ADD/REMOVE events, fail-closed on duplicate add, remove-without-add, conflicting timestamps | `tests/phase7/test_point_in_time_integrity.py` | `test_membership_conversion_normal_add_then_remove`, `test_membership_conversion_open_ended_addition`, `test_membership_conversion_re_addition_after_removal`, `test_membership_conversion_duplicate_addition_fails_closed`, `test_membership_conversion_removal_without_prior_addition_fails_closed`, `test_membership_conversion_same_time_conflicting_events`, `test_membership_conversion_future_events_ignored_at_prediction_time` | **VERIFIED** |
| **Point-in-Time Intervals** | Half-open intervals $[t_{\text{from}}, t_{\text{to}})$, open-ended intervals, point-in-time cutoff | `tests/phase7/test_point_in_time_integrity.py` | `test_stock_added_in_2022_not_eligible_in_2021`, `test_stock_eligible_on_or_after_addition`, `test_stock_removed_in_2023_not_eligible_after_removal`, `test_open_ended_interval_works`, `test_invalid_interval_bounds_fail`, `test_sector_classification_pit_checks` | **VERIFIED** |
| **Gated Interface Timestamps** | Segregation of announcement/filing timestamps from disclosure effective dates | `tests/phase7/test_point_in_time_integrity.py`, `tests/phase7/test_no_future_features.py` | `test_gated_interface_contracts_timestamp_distinction`, `test_period_end_date_not_treated_as_availability` | **VERIFIED** |
| **Temporal Cutoff Enforcement** | Exclusion of future prices, sectors, and future source timestamps | `tests/phase7/test_no_future_features.py` | `test_future_price_does_not_enter_history`, `test_future_sector_cannot_backfill_earlier_date`, `test_future_source_timestamp_disqualifies_record` | **VERIFIED** |
| **Corporate Actions Adjustment** | Split/bonus multipliers, cash dividend total-return factor, reference price validation | `tests/phase7/test_corporate_action_adjustments.py` | `test_stock_split_1_to_2_produces_factor_2`, `test_bonus_ratios`, `test_cash_dividend_total_return_factor` | **VERIFIED** |
| **Corporate Action Aliases & Routing** | Canonical aliases (`RIGHTS_ISSUE`, `AMALGAMATION`, etc.), routing restructuring and delisting to `MANUAL_REVIEW` | `tests/phase7/test_corporate_action_adjustments.py` | `test_corporate_action_canonical_aliases_mapping`, `test_ambiguous_or_unknown_action_type_returns_manual_review`, `test_symbol_change_and_delisting_return_manual_review`, `test_unsupported_complex_actions_return_manual_review` | **VERIFIED** |
| **Double-Adjustment Prevention** | Reject adjusting already adjusted series (`TOTAL_RETURN_ADJUSTED`), reject unknown adjustment state | `tests/phase7/test_corporate_action_adjustments.py` | `test_prevent_double_adjustment_and_unknown_state` | **VERIFIED** |
| **Fail-Closed Loaders** | 1-based CSV/JSONL row tracking, error message capture, no silent zero coercion | `tests/phase7/test_data_loaders.py` | `test_csv_loader_returns_accepted_and_rejected_with_row_numbers`, `test_invalid_values_not_silently_coerced_to_zero` | **VERIFIED** |
| **Audit Utility Integrity & Future Tracking** | Structural report generation, zero investment performance reporting, future records counter, turnover status separation | `tests/phase7/test_data_loaders.py` | `test_audit_report_contains_zero_investment_performance_metrics`, `test_audit_report_tracks_future_records_and_traded_value_statuses` | **VERIFIED** |
| **Static Boundary & Vault Defense** | Zero Phase 6 script imports, zero Phase 6 vault references, static universe provider prohibition | `tests/phase7/test_data_loaders.py`, `tests/phase7/test_phase6_boundary.py` | `test_active_phase7_modules_have_no_forbidden_imports`, `test_no_import_of_phase6_training_scripts_in_phase7`, `test_no_phase6_vault_archives_in_phase7_active_config`, `test_no_phase6_vault_paths_in_phase7_code`, `test_static_current_universe_cannot_be_provider` | **VERIFIED** |
| **Universe Liquidity & History** | Minimum 252 valid observations, 60d MDTV $\ge$ INR 10 crore, minimum price $\ge$ INR 20.00 | `tests/phase7/test_universe_survivorship.py` | `test_duplicate_dates_do_not_increase_history_count`, `test_liquidity_threshold_evaluation` | **VERIFIED** |
| **Turnover Derivation Safeguards** | Prohibit Close-alone derivation (`CLOSE_X_VOLUME`), prohibit method on exchange reported, require method on derived | `tests/phase7/test_universe_survivorship.py` | `test_traded_value_derivation_contract_safeguards` | **VERIFIED** |
| **Turnover Status Differentiation** | Distinguish `EXCHANGE_REPORTED`, `MISSING`, `INVALID`; zero turnover with MISSING vs INVALID exclusion reasons | `tests/phase7/test_universe_survivorship.py` | `test_missing_and_invalid_turnover_handling` | **VERIFIED** |
| **Granular Exclusion Reasons** | Preserve and report distinct reasons (`NOT_IN_PIT_UNIVERSE`, `MISSING_MEMBERSHIP_HISTORY`, `MISSING_PRICE_HISTORY`, `INSUFFICIENT_HISTORY`, etc.) | `tests/phase7/test_universe_survivorship.py` | `test_missing_membership_history_causes_exclusion`, `test_suspension_causes_exclusion`, `test_multiple_exclusion_reasons_preserved`, `test_distinction_not_in_pit_universe_vs_missing_membership_history`, `test_distinction_missing_price_history_vs_insufficient_history`, `test_distinction_missing_sector_vs_conflicting_sector`, `test_duplicate_security_record_exclusion`, `test_future_data_detected_exclusion` | **VERIFIED** |
| **Security vs. Build Validation Status** | `ExclusionReason.DATA_VALIDATION_FAILURE` (security level) distinct from `UniverseBuildStatus.DATA_VALIDATION_FAILURE` (build level); neither aliased to unknown | `tests/phase7/test_universe_survivorship.py` | `test_data_validation_failure_security_vs_build_status` | **VERIFIED** |
| **Future Data Handling in Universe** | Never qualifies earlier predictions, increments audit counter, tracks reason and evidence | `tests/phase7/test_universe_survivorship.py` | `test_future_data_handling_and_audit_counter`, `test_future_data_detected_exclusion` | **VERIFIED** |
| **Universe Build Lifecycle** | Granular statuses (`SUCCESS`, `BLOCKED_MISSING_*`, `VALID_EMPTY_UNIVERSE`, `DATA_VALIDATION_FAILURE`), `is_real_data_blocked` property | `tests/phase7/test_universe_survivorship.py` | `test_missing_blk01_or_blk02_produces_explicit_blocked_status`, `test_universe_build_status_full_lifecycle_and_empty_valid` | **VERIFIED** |
| **Deterministic Sorting & Hash** | Output symbols sorted, reproducible SHA-256 universe snapshot hash | `tests/phase7/test_universe_survivorship.py` | `test_deterministic_ordering_and_hash_reproducibility` | **VERIFIED** |
| **Configuration Schema Validation** | Enforce schema types, basis points integer format, negative cost rejection, execution delay | `tests/phase7/test_config_schema.py` | `test_canonical_config_passes_validation`, `test_forbidden_universe_provider_fails`, `test_forbidden_vault_reference_fails`, `test_missing_required_section_raises_error`, `test_negative_or_zero_cost_scenarios_fail`, `test_non_integer_basis_points_fail`, `test_same_day_execution_rejected` | **VERIFIED** |

### Verification Summary:
- Phase 7 unit tests: **70 passing** (`pytest tests/phase7/ -v`).
- Phase 6 safeguard tests: **4 passing** (`pytest test_phase6_safeguards.py -v`).
- Total passing tests: **74 of 74** (100% pass rate).
- Real Data Readiness: **`CONTRACT_READY_REAL_DATA_BLOCKED`** (Gate 1 real-data evaluation blocked pending BLK-01 and BLK-02).

---

## 9. Phase 7 Research Environment Specification (`.venv-phase7`)

- **Standard Runtime:** Python 3.12.10 (MSC v.1943 64 bit AMD64 on Windows).
- **Environment Interpreter:** `.venv-phase7\Scripts\python.exe`
- **Dependency Baseline:** Installed exclusively from `requirements-phase7.txt` (SHA-256: `5484bd0b91edbc22542476aa40f5294ea759a27e93a5ce31eae3b3b3efc2c88d`).
- **Compatibility Status:** Verified via `pip check` (zero broken requirements).
- **Test Verification:** 74 of 74 automated tests passing under Python 3.12.10 (`.venv-phase7\Scripts\python.exe -m pytest tests/phase7/ test_phase6_safeguards.py -v`).
- **Runtime Stability:** Narrow pandas datetime operations (`pd.date_range`) verified stable; C-level access violation crash observed under development Python 3.14.4 is completely eliminated.
- **Mandatory Invocation Rule:** All subsequent Phase 7 Python commands, CI scripts, test runners, and tools MUST explicitly use `.venv-phase7\Scripts\python.exe`.
- **Milestone 3 Runtime Readiness:** The environment is runtime-ready for Milestone 3 implementation.
- **Remaining Blockers:** Real-data blockers BLK-01 (historical Nifty 500 membership) and BLK-02 (complete OHLCV and daily traded value) remain `CONTRACT_READY_REAL_DATA_BLOCKED`. BLK-06 is `ENVIRONMENT STABLE; LEGACY TEST FAILURES REQUIRE REVIEW`. Gate 1 real-data evaluation remains blocked until genuine historical datasets are ingested.
