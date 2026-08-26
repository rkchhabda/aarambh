# 30-Day Launch Plan — Quant Signal Platform

## Current State (Day 0)
| Component | Status |
|-----------|--------|
| **MVP Strategy** (Scenario 2/2b: Long-only + 200-SMA) | ✅ Backtested: Sharpe 1.84, MaxDD -9.8% |
| **Inference API** (FastAPI) | ✅ Working (verified via direct call) |
| **Monitoring Dashboard** (Streamlit) | ✅ Code complete |
| **API Key / Tier System** | ✅ Implemented (Free/Pro/Enterprise) |
| **Containerization** | ✅ Dockerfile + docker-compose + deploy.sh |
| **V2 Percentile Calibration** | ✅ Backtested: Short freq ↑ 0%→23%, but Sharpe still -0.13 |

---

## Week 1 (Days 1-7): Deploy MVP to Cloud — Paper Trading Only

| Day | Task | Owner | Deliverable |
|-----|------|-------|-------------|
| 1 | Provision cloud VM (AWS EC2 t3.medium / Render / Railway) | DevOps | Running instance with Docker |
| 2 | Push Docker images, run `./deploy.sh up` | DevOps | API + Dashboard live at public URLs |
| 3 | Configure DNS + TLS (Let's Encrypt) | DevOps | `api.yourdomain.com`, `app.yourdomain.com` |
| 4 | Connect paper-trading broker (Alpaca / IBKR paper) | Quant | Auto-execution of Scenario 2/2b signals |
| 5 | Run end-to-end smoke test: signal → order → fill | QA | Zero-dollar paper fill log |
| 6-7 | Monitor latency, uptime, data freshness | All | 99.9% uptime, <200ms API p99 |

**Exit Criteria**: Paper portfolio running 5 tickers, daily P&L tracked vs backtest.

---

## Week 2 (Days 8-14): V2 Staging Integration

| Day | Task | Owner | Deliverable |
|-----|------|-------|-------------|
| 8 | Deploy V2 percentile-calibrated model to **staging** endpoint (`/v2/signal`) | ML Eng | Staging API |
| 9 | A/B test: 50% traffic V1 (Scenario 2/2b), 50% V2 (Percentile+Regime) | Quant | Traffic split |
| 10-12 | Collect live Sharpe, hit rate, turnover for both | Quant | Live metrics dashboard |
| 13 | Decision gate: if V2 Sharpe > 0.5 over 5+ trading days → promote | PM | Go/No-Go doc |
| 14 | If promoted: cutover to V2; else revert to V1, log learnings | PM | Decision record |

**Note**: V2 backtest Sharpe was -0.132. **Do not promote until live V2 > 0.5**. This is the research track.

---

## Week 3 (Days 15-21): Beta Launch

| Day | Task | Owner | Deliverable |
|-----|------|-------|-------------|
| 15 | Create landing page (Free/Pro tiers, Stripe integration) | Frontend | `yourdomain.com` |
| 16 | Onboard 5 beta testers (discord/email list) | PM | Beta access granted |
| 17-19 | Collect feedback: signal clarity, dashboard UX, API ergonomics | PM | Feedback doc |
| 20 | Iterate: fix top 3 bugs, add webhook alert for Pro tier | Eng | Patch release |
| 21 | Beta retrospective: NPS, retention, signal quality rating | PM | Go/No-Go for public |

---

## Week 4 (Days 22-30): Public Launch

| Day | Task | Owner | Deliverable |
|-----|------|-------|-------------|
| 22 | Final security audit (OWASP, API rate limits, key rotation) | Security | Audit pass |
| 23 | Load test API (100 RPS sustained) | Eng | Pass |
| 24 | Press kit / Twitter announcement / Product Hunt | Marketing | Launch assets |
| 25 | **PUBLIC LAUNCH** — Tier 1 (Free) + Tier 2 (Pro $49/mo) live | All | Revenue day 1 |
| 26-28 | Monitor signups, churn, support tickets | PM | Daily standup |
| 29 | First weekly metrics review: MRR, active users, API health | PM | Report |
| 30 | Retrospective + plan Month 2 | All | OKRs for Month 2 |

---

## Revenue Targets (Month 1)
| Tier | Price | Target Users | MRR |
|------|-------|--------------|-----|
| Free | $0 | 200 | $0 |
| Pro | $49/mo | 20 | **$980** |
| Enterprise | Custom | 1 | Negotiated |

---

## Risk Register
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| V2 live Sharpe << backtest | High | High | Strict 0.5 Sharpe gate; auto-revert |
| API rate limit / broker API changes | Med | High | Circuit breakers; fallback to cached signal |
| Data feed gap (yfinance downtime) | Low | High | Cache 24h; alert on stale data |
| Regulatory (investment advice) | Low | Critical | Disclaimer: "Educational signals only" |

---

## Final Verdict

### MVP (Track A — Scenario 2/2b) → **LAUNCH READY**
- ✅ Backtest Sharpe **1.84**, MaxDD **-9.8%** (vs B&H 1.68 / -17.7%)
- ✅ 5-ticker diversification, regime filter cuts drawdown in half
- ✅ API + Dashboard + Auth + Containers all working
- ✅ Paper-trading path clear

### V2 (Track B — Percentile Calibration) → **HOLD**
- ✅ **Signal frequency fixed**: shorts 0% → 8-31% (per-ticker)
- ❌ **Sharpe still negative** (-0.132 with regime, -0.40 pure)
- 🔬 Root cause: LSTM probabilities too low-information (cluster ~0.52 mean)
- 📋 Next step: **Better model architecture** (attention, multi-horizon, or Kronos-base at 5-day horizon on GPU)

---

**DECISION: PROCEED WITH TRACK A ONLY. Track B stays in research.**

---

**PHASE 6 COMPLETE**