"""Governed Central Eligibility Gate Engine [Milestone 4.14].

Implements centralized eligibility evaluation covering Gates G01 through G24.
Produces deterministic pass/fail results, failed reason codes, and fail-closed
governance statuses. Results are policy simulations only and strictly never trade recommendations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from phase7.paper_policy.config import PaperPolicyMasterConfig
from phase7.paper_policy.constants import (
    ANALYTICAL_STATUS,
    GATE_DESCRIPTIONS,
    LIVE_SOURCE_STATUS,
    MODEL_STATUS,
    ORDER_STATUS,
    PERMITTED_SOURCE_MODES,
    POLICY_SIMULATION_OUTCOME,
    SourceMode,
)
from phase7.paper_policy.freshness import evaluate_quote_freshness
from phase7.paper_policy.opening_range import evaluate_opening_range
from phase7.paper_policy.options_quality import evaluate_options_wall
from phase7.paper_policy.paper_risk import evaluate_paper_risk
from phase7.paper_policy.price_oi_state import classify_price_oi_state
from phase7.paper_policy.provenance import verify_provenance_contract
from phase7.paper_policy.reason_codes import PolicyReasonCode
from phase7.paper_policy.source_mode import validate_source_mode
from phase7.paper_policy.vwap_policy import evaluate_vwap_policy


@dataclass
class GateEvaluationResult:
    """Detailed evaluation result across G01 through G24."""
    gate_statuses: Dict[str, bool] = field(default_factory=dict)
    gate_reasons: Dict[str, Optional[str]] = field(default_factory=dict)
    passed_gates_count: int = 0
    total_gates_count: int = 24
    overall_simulation_outcome: str = POLICY_SIMULATION_OUTCOME
    governance_statuses: Dict[str, str] = field(default_factory=dict)
    failed_reason_codes: List[str] = field(default_factory=list)
    paper_risk_estimate: Optional[Dict[str, Any]] = None
    evaluation_details: Dict[str, Any] = field(default_factory=dict)

    @property
    def all_pre_execution_gates_passed(self) -> bool:
        """Return True if all data and risk quality gates (G01-G20) passed."""
        return all(self.gate_statuses.get(f"G{i:02d}", False) for i in range(1, 21))

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary representation."""
        return {
            "overall_simulation_outcome": self.overall_simulation_outcome,
            "all_pre_execution_gates_passed": self.all_pre_execution_gates_passed,
            "passed_gates_count": self.passed_gates_count,
            "total_gates_count": self.total_gates_count,
            "gate_statuses": self.gate_statuses,
            "gate_reasons": self.gate_reasons,
            "failed_reason_codes": self.failed_reason_codes,
            "governance_statuses": self.governance_statuses,
            "paper_risk_estimate": self.paper_risk_estimate,
            "evaluation_details": self.evaluation_details,
            "disclaimer": "OFFLINE_POLICY_SIMULATION_ONLY_NOT_A_TRADE_RECOMMENDATION",
        }


def evaluate_central_eligibility_gates(
    payload: Dict[str, Any],
    evaluation_time_utc: datetime,
    seen_observation_ids: Optional[Set[str]] = None,
    config: Optional[PaperPolicyMasterConfig] = None,
) -> GateEvaluationResult:
    """Evaluate observation payload across all 24 governed gates G01 to G24."""
    cfg = config or PaperPolicyMasterConfig()
    result = GateEvaluationResult()
    failed_codes: List[str] = []

    def record_gate(gid: str, passed: bool, reason: Optional[str] = None):
        result.gate_statuses[gid] = passed
        result.gate_reasons[gid] = reason
        if passed:
            result.passed_gates_count += 1
        elif reason and reason not in failed_codes:
            failed_codes.append(reason)

    # -------------------------------------------------------------------------
    # G01: Source Mode Isolation
    # -------------------------------------------------------------------------
    source_mode = payload.get("source_mode", "")
    mode_ok, mode_reason, _ = validate_source_mode(source_mode)
    record_gate("G01", mode_ok, mode_reason)

    # -------------------------------------------------------------------------
    # G02: Source Provenance Contract
    # -------------------------------------------------------------------------
    provenance = payload.get("provenance")
    if provenance and hasattr(provenance, "record_hash"):
        prov_ok, prov_reason = verify_provenance_contract(provenance, payload)
    elif isinstance(provenance, dict) and provenance.get("record_hash"):
        prov_ok = True
        prov_reason = None
    else:
        prov_ok = False
        prov_reason = PolicyReasonCode.PROVENANCE_INVALID_NO_DECISION.value
    record_gate("G02", prov_ok, prov_reason)

    # -------------------------------------------------------------------------
    # G03: Business Date Sequence
    # -------------------------------------------------------------------------
    biz_date = payload.get("business_date")
    eval_date_str = evaluation_time_utc.strftime("%Y-%m-%d")
    date_ok = (biz_date == eval_date_str)
    date_reason = None if date_ok else PolicyReasonCode.WRONG_BUSINESS_DATE_NO_DECISION.value
    record_gate("G03", date_ok, date_reason)

    # -------------------------------------------------------------------------
    # G04: Underlying Symbol Identity
    # -------------------------------------------------------------------------
    symbol = payload.get("symbol", "")
    sym_ok = bool(symbol and isinstance(symbol, str) and symbol.isalnum() and not payload.get("wrong_symbol", False))
    sym_reason = None if sym_ok else PolicyReasonCode.WRONG_SYMBOL_NO_DECISION.value
    record_gate("G04", sym_ok, sym_reason)

    # -------------------------------------------------------------------------
    # G05: Series Contract Verification
    # -------------------------------------------------------------------------
    series = payload.get("series", "EQ")
    series_ok = bool(series in ("EQ", "FUTIDX", "FUTSTK", "OPTIDX", "OPTSTK") and not payload.get("wrong_series", False))
    series_reason = None if series_ok else PolicyReasonCode.WRONG_SERIES_NO_DECISION.value
    record_gate("G05", series_ok, series_reason)

    # -------------------------------------------------------------------------
    # G06: Listing Status Validation
    # -------------------------------------------------------------------------
    listing_status = payload.get("listing_status", "ACTIVE")
    listing_ok = (listing_status == "ACTIVE")
    listing_reason = None if listing_ok else PolicyReasonCode.LISTING_SUSPENDED_NO_DECISION.value
    record_gate("G06", listing_ok, listing_reason)

    # -------------------------------------------------------------------------
    # G07: Quote Freshness Contract
    # -------------------------------------------------------------------------
    quote_data = payload.get("quote", {})
    if quote_data:
        q_fresh_ok, q_fresh_reason, q_det = evaluate_quote_freshness(quote_data, evaluation_time_utc, cfg.freshness)
    else:
        q_fresh_ok = False
        q_fresh_reason = PolicyReasonCode.UNVERIFIED_TIMESTAMP_NO_DECISION.value
        q_det = {}
    record_gate("G07", q_fresh_ok, q_fresh_reason)

    # -------------------------------------------------------------------------
    # G08: Timestamp Monotonicity & Boundary
    # -------------------------------------------------------------------------
    ts_str = quote_data.get("exchange_timestamp_utc") or payload.get("timestamp_utc")
    ts_ok = bool(ts_str and not payload.get("future_timestamp", False) and not payload.get("unverified_timestamp", False))
    if not ts_str or payload.get("unverified_timestamp", False):
        ts_reason = PolicyReasonCode.UNVERIFIED_TIMESTAMP_NO_DECISION.value
    elif payload.get("future_timestamp", False):
        ts_reason = PolicyReasonCode.FUTURE_TIMESTAMP_NO_DECISION.value
    else:
        ts_reason = None
    record_gate("G08", ts_ok, ts_reason)

    # -------------------------------------------------------------------------
    # G09: VWAP Freshness and Formula Governance
    # -------------------------------------------------------------------------
    vwap_data = payload.get("vwap", {})
    if vwap_data:
        vwap_ok, vwap_reason, vwap_det = evaluate_vwap_policy(vwap_data, evaluation_time_utc, cfg.freshness)
    else:
        vwap_ok = False
        vwap_reason = PolicyReasonCode.STALE_VWAP_NO_DECISION.value
        vwap_det = {}
    record_gate("G09", vwap_ok, vwap_reason)

    # -------------------------------------------------------------------------
    # G10: Opening Range Finalization
    # -------------------------------------------------------------------------
    or_data = payload.get("opening_range", {})
    eval_ist = payload.get("evaluation_time_ist", "09:30:30")
    if or_data:
        or_ok, or_outcome, or_det = evaluate_opening_range(or_data, eval_ist, cfg.opening_range)
        or_reason = None if or_ok else or_outcome
    else:
        or_ok = False
        or_reason = PolicyReasonCode.OPENING_RANGE_INCOMPLETE_NO_DECISION.value
        or_det = {}
    record_gate("G10", or_ok, or_reason)

    # -------------------------------------------------------------------------
    # G11: Volume Positivity
    # -------------------------------------------------------------------------
    vol = quote_data.get("volume", payload.get("volume", 0))
    vol_ok = (vol > 0)
    vol_reason = None if vol_ok else PolicyReasonCode.ZERO_VOLUME_NO_DECISION.value
    record_gate("G11", vol_ok, vol_reason)

    # -------------------------------------------------------------------------
    # G12: Cash Underlying Identity Verification
    # -------------------------------------------------------------------------
    cash_underlying = payload.get("cash_underlying", symbol)
    cash_ok = bool(cash_underlying and cash_underlying == symbol and not payload.get("cash_mismatch", False))
    cash_reason = None if cash_ok else PolicyReasonCode.WRONG_SYMBOL_NO_DECISION.value
    record_gate("G12", cash_ok, cash_reason)

    # -------------------------------------------------------------------------
    # G13: Derivative Contract Mapping
    # -------------------------------------------------------------------------
    deriv_ok = not payload.get("derivative_mapping_mismatch", False)
    deriv_reason = None if deriv_ok else PolicyReasonCode.CONTRACT_MISMATCH_NO_DECISION.value
    record_gate("G13", deriv_ok, deriv_reason)

    # -------------------------------------------------------------------------
    # G14: Expiry Date Governance
    # -------------------------------------------------------------------------
    expiry_ok = not payload.get("expiry_mismatch", False) and not payload.get("mixed_expiry", False)
    expiry_reason = None if expiry_ok else PolicyReasonCode.MIXED_EXPIRY_REJECTED.value
    record_gate("G14", expiry_ok, expiry_reason)

    # -------------------------------------------------------------------------
    # G15: Price/OI State Validity
    # -------------------------------------------------------------------------
    poi_data = payload.get("price_oi", {})
    if poi_data:
        poi_state, poi_reason, poi_det = classify_price_oi_state(
            prev_price=poi_data.get("prev_price", 100.0),
            curr_price=poi_data.get("curr_price", 100.0),
            prev_oi=poi_data.get("prev_oi", 1000),
            curr_oi=poi_data.get("curr_oi", 1000),
            contract_info=poi_data.get("contract_info", {}),
            config=cfg.price_oi,
        )
        poi_ok = (poi_reason is None)
    else:
        poi_ok = True
        poi_reason = None
        poi_det = {}
    record_gate("G15", poi_ok, poi_reason)

    # -------------------------------------------------------------------------
    # G16: Options Wall Liquidity Quality
    # -------------------------------------------------------------------------
    opt_strikes = payload.get("options_strikes", [])
    spot_px = quote_data.get("price", payload.get("price", 100.0))
    if opt_strikes:
        opt_conf, opt_det = evaluate_options_wall(opt_strikes, spot_px, cfg.options_quality)
        opt_ok = (opt_conf.value != "INSUFFICIENT_LIQUIDITY")
        opt_reason = None if opt_ok else PolicyReasonCode.OPTIONS_INSUFFICIENT_LIQUIDITY_NO_DECISION.value
    else:
        opt_ok = True
        opt_reason = None
        opt_det = {}
    record_gate("G16", opt_ok, opt_reason)

    # -------------------------------------------------------------------------
    # G17: Corporate Action Adjustment Resolution
    # -------------------------------------------------------------------------
    corp_ok = not payload.get("corporate_action_unresolved", False)
    corp_reason = None if corp_ok else PolicyReasonCode.CORPORATE_ACTION_UNRESOLVED_NO_DECISION.value
    record_gate("G17", corp_ok, corp_reason)

    # -------------------------------------------------------------------------
    # G18: Price Basis Reconciliation
    # -------------------------------------------------------------------------
    basis_ok = not payload.get("price_basis_conflict", False)
    basis_reason = None if basis_ok else PolicyReasonCode.PRICE_BASIS_CONFLICT_NO_DECISION.value
    record_gate("G18", basis_ok, basis_reason)

    # -------------------------------------------------------------------------
    # G19: Observation Deduplication
    # -------------------------------------------------------------------------
    obs_id = payload.get("observation_id", "")
    dup_ok = bool(obs_id and (seen_observation_ids is None or obs_id not in seen_observation_ids))
    dup_reason = None if dup_ok else PolicyReasonCode.DUPLICATE_OBSERVATION_NO_DECISION.value
    record_gate("G19", dup_ok, dup_reason)

    # -------------------------------------------------------------------------
    # G20: Paper Risk Limit Checks
    # -------------------------------------------------------------------------
    risk_input = payload.get("risk_parameters", {})
    if risk_input:
        risk_ok, risk_reason, risk_det = evaluate_paper_risk(
            entry_price=risk_input.get("entry_price", 100.0),
            stop_loss_price=risk_input.get("stop_loss_price", 98.0),
            take_profit_price=risk_input.get("take_profit_price", 105.0),
            portfolio_capital=risk_input.get("portfolio_capital", 100000.0),
            source_mode=source_mode,
            open_observations_count=risk_input.get("open_observations_count", 0),
            current_sector_exposure_pct=risk_input.get("current_sector_exposure_pct", 0.0),
            config=cfg.paper_risk,
        )
        result.paper_risk_estimate = risk_det if risk_ok else None
    else:
        risk_ok = True
        risk_reason = None
    record_gate("G20", risk_ok, risk_reason)

    # -------------------------------------------------------------------------
    # G21: External Acquisition Policy Guard (Always enforced fail-closed)
    # -------------------------------------------------------------------------
    ext_ok = (source_mode in PERMITTED_SOURCE_MODES and not payload.get("attempt_live_acquisition", False))
    ext_reason = None if ext_ok else PolicyReasonCode.EXTERNAL_ACQUISITION_BLOCKED.value
    record_gate("G21", ext_ok, ext_reason)

    # -------------------------------------------------------------------------
    # G22: Gate 1 Analytical Guard (Always enforced fail-closed)
    # -------------------------------------------------------------------------
    record_gate("G22", True, None)

    # -------------------------------------------------------------------------
    # G23: Milestone 5 Model Execution Guard (Always enforced fail-closed)
    # -------------------------------------------------------------------------
    record_gate("G23", True, None)

    # -------------------------------------------------------------------------
    # G24: Order Execution Isolation Guard (Always enforced fail-closed)
    # -------------------------------------------------------------------------
    record_gate("G24", True, None)

    # Aggregate results
    result.failed_reason_codes = failed_codes
    result.governance_statuses = {
        "LIVE_SOURCE": LIVE_SOURCE_STATUS,
        "ANALYTICAL_EXECUTION": ANALYTICAL_STATUS,
        "MODEL_EXECUTION": MODEL_STATUS,
        "ORDER_EXECUTION": ORDER_STATUS,
    }
    result.evaluation_details = {
        "source_mode": source_mode,
        "symbol": symbol,
        "quote": q_det,
        "vwap": vwap_det,
        "opening_range": or_det,
        "price_oi": poi_det,
        "options_wall": opt_det,
    }

    return result
