# Phase 7 — Live Shadow Portfolio Protocol

**Repository:** GaurviDEEP
**Working Branch:** `phase7-research`
**Governing Document:** [`docs/PHASE7_RESEARCH_PREREGISTRATION.md`](PHASE7_RESEARCH_PREREGISTRATION.md)
**Standard Environment:** Python 3.12 (`.venv-phase7`)
**Status:** PROTOCOL PRE-REGISTERED
**Effective Date:** 2026-10-05

---

## 1. General Principles & Safety Mandates

1. **Zero Real-Money Execution:**
   - The Phase 7 live shadow portfolio is an **exclusively forward-testing, simulated paper-portfolio protocol**.
   - No capital allocation, order execution, broker routing, or real-money trading is authorized during Phase 7.
2. **Public Endpoint Quarantine:**
   - No stock-picking API routes (e.g. `/v1/signal` or public recommendations) may be deployed or updated in production during this research programme.
   - All shadow portfolio outputs are recorded strictly into internal research ledgers.
3. **Execution Delay & Signal Pre-Commitment:**
   - Predictions are computed and timestamped after Friday market close (or weekend).
   - Execution is strictly modeled at the next session's executable price ($t+1$, Monday market open or session VWAP).
   - The prediction ledger is append-only and cryptographically committed before Monday market open (09:15 IST).

---

## 2. Duration & Operational Schedule

- **Validation Period:** **12 contiguous months**.
- **Scheduled Rebalance Cycles:** At least **50 scheduled weekly rebalance events**.
- **Multi-Regime Extension Rule:** If the 12-month period traverses only a single persistent market regime (e.g. uninterrupted bull run without a $\ge 5\%$ market correction), the evaluation period must be extended until at least two material market regimes are observed.
- **System Availability SLA:** $\ge \mathbf{90.0\%}$ uptime on scheduled weekly prediction runs. Any missed or delayed run must be logged with root-cause analysis in the incident register.

---

## 3. Signal States & Abstention Framework

To prevent forced trading during ambiguous or adverse market conditions, the ranking engine supports three discrete qualification states:

```
[Cross-Sectional Rank Engine]
         │
         ├── Top 10% & Multi-Family Consensus & Liquidity Pass ──► [SELECT]
         ├── Top 20% or Distributional Outlier Warning           ──► [WATCH]
         └── System-Wide Adverse Risk / High Cost Drag          ──► [NO_QUALIFYING_OPPORTUNITY]
```

### 3.1 `SELECT` Qualification Rules
A security qualifies for `SELECT` status on date $t$ if and only if all of the following criteria are met:
1. **Top Decile Rank:** Its cross-sectional rank percentile is within the top $10\%$ of the active eligible universe.
2. **Multi-Model Consensus:** At least two independent model families rank the security within the top $20\%$ of the universe.
3. **Liquidity & Capacity Check:** The required trade size $\le 5.00\%$ of trailing 60-day MDTV.
4. **Risk & Concentration Check:** Adding the stock does not breach the $5.00\%$ stock weight limit or $25.00\%$ sector exposure limit.
5. **Distributional Inlier:** Security features are within 3 standard deviations of the model's training distribution (Mahalanobis distance check).
6. **Cost-Adjusted Edge:** Expected sector-relative return exceeds round-trip transaction cost hurdle ($25\text{ bps}$).
7. **Zero Active Flags:** No unresolved corporate governance, audit qualification, or regulatory surveillance flags.

### 3.2 `WATCH` Qualification
Securities ranking in the top $20\%$ that fail multi-model consensus, exhibit mild distributional drift, or face sector capacity constraints are assigned `WATCH` status (monitored without portfolio inclusion).

### 3.3 `NO_QUALIFYING_OPPORTUNITY` (Systemic Abstention)
The portfolio engine must issue `NO_QUALIFYING_OPPORTUNITY` for an entire rebalance cycle if:
- Market regime indicates extreme crisis/illiquidity (e.g. VIX $> 35$ or $> 80\%$ universe below 50-SMA).
- Fewer than 10 securities achieve `SELECT` qualification.
- Data feeds fail validation checksums or timing audits.
- In this state, portfolio capital transitions to risk-free cash (overnight collateral yield).

---

## 4. Immutable Shadow Prediction Ledger Schema

All live predictions must be appended to `artifacts/phase7/live_shadow_ledger.jsonl`. Each record must contain:

| Field Name | Type | Description |
|---|---|---|
| `prediction_id` | `UUID` | Unique identifier for prediction record |
| `prediction_timestamp` | `TIMESTAMP` | UTC timestamp when prediction was generated |
| `effective_date` | `DATE` | Intended $t+1$ execution trading date |
| `model_id` | `STRING` | Frozen candidate model identifier |
| `code_commit` | `STRING` | Git commit hash producing the prediction |
| `symbol` | `STRING` | NSE equity symbol |
| `rank_score` | `FLOAT` | Ordinal rank percentile score ($0.0 \to 1.0$) |
| `decision_state` | `STRING` | `SELECT` / `WATCH` / `NO_QUALIFYING_OPPORTUNITY` |
| `target_weight_bps` | `INT` | Allocated portfolio weight in basis points |
| `t_plus_1_exec_price` | `FLOAT` | Realized execution price at $t+1$ (filled post-session) |
| `realized_gross_ret_20d` | `FLOAT` | Realized gross 20d return (filled at $t+20$) |
| `realized_net_ret_20d` | `FLOAT` | Realized net return after modeled transaction costs |
| `max_adverse_excursion` | `FLOAT` | Deepest intra-holding drawdown percentage (MAE) |
| `max_favourable_excursion`| `FLOAT` | Highest intra-holding gain percentage (MFE) |

---

## 5. Gate 5 Live Shadow Success Thresholds

At the conclusion of the 12-month forward validation period, the shadow portfolio must satisfy:

| Metric | Minimum Required Gate 5 Threshold |
|---|---|
| **Cumulative Net Return** | Positive after all transaction costs |
| **Benchmark-Relative Alpha** | Positive excess return over Nifty 500 TRI |
| **12-Month Net Sharpe Ratio** | $\ge \mathbf{0.70}$ |
| **Maximum Drawdown Limit** | $\le \mathbf{20.0\%}$ |
| **Sector-Relative Hit Rate** | $\ge \mathbf{53.0\%}$ (realized positive sector excess returns) |
| **System Availability** | $\ge \mathbf{90.0\%}$ scheduled prediction cycles |
| **Integrity Incidents** | Zero critical data, liquidity, or leakage incidents |

Failure to meet these thresholds requires concluding the programme with a null finding and prevents any production deployment consideration.
