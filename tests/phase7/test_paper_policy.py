"""Focused Verification Test Suite for Governed Paper Policy [Milestone 4.14].

Validates:
1. Parameter contracts, indicator definitions, and threshold bounds.
2. Source mode isolation and anti-masquerade guards.
3. Cryptographic provenance and hash conservation.
4. Quote and VWAP freshness contracts and timestamp boundaries.
5. VWAP formula governance and display-only restrictions.
6. Opening range interval finalization and deterministic timing.
7. Price/OI state classification, neutral bands, and contract continuity.
8. Options wall quality, liquidity thresholds, and wall confidence.
9. Put-Call Ratio (PCR) single-expiry filtering and zero-denominator rejection.
10. Paper-only risk estimation, portfolio caps, and prohibited order term safeguards.
11. Centralized eligibility gates G01 through G24.
12. Offline operator Screen 11 integration (CLI and GUI).
13. Network quarantine and Phase 6 isolation integrity.
"""

from datetime import datetime, time, timezone
import json
from pathlib import Path
import tkinter as tk
import pytest

from phase7.operator.cli import OperatorCLI
from phase7.operator.core import OperatorCore
from phase7.operator.gui import OperatorGUI
from phase7.paper_policy.config import (
    FreshnessConfig,
    IndicatorConfig,
    OpeningRangeConfig,
    OptionsQualityConfig,
    PaperPolicyMasterConfig,
    PaperRiskConfig,
    PriceOIConfig,
)
from phase7.paper_policy.constants import (
    ANALYTICAL_STATUS,
    CANDLE_APPROXIMATION_STATUS,
    GATE_DESCRIPTIONS,
    GOVERNED_PRICE_OI_LABEL,
    GOVERNED_RISK_OUTPUT_LABEL,
    LIVE_SOURCE_STATUS,
    MODEL_STATUS,
    ORDER_STATUS,
    PARAMETER_SET_ID,
    PARAMETER_SET_VERSION,
    POLICY_SIMULATION_OUTCOME,
    PROHIBITED_PRICE_OI_LABEL,
    PROHIBITED_RISK_OUTPUT_LABELS,
    SCREEN_11_MANDATORY_BANNERS,
    OpeningRangeOutcome,
    OptionsWallConfidence,
    PriceOIState,
    SourceMode,
    VWAPFormulaType,
)
from phase7.paper_policy.eligibility_gate import (
    GateEvaluationResult,
    evaluate_central_eligibility_gates,
)
from phase7.paper_policy.freshness import (
    evaluate_quote_freshness,
    evaluate_vwap_freshness,
)
from phase7.paper_policy.opening_range import evaluate_opening_range
from phase7.paper_policy.options_quality import (
    evaluate_options_wall,
    evaluate_strike_liquidity,
)
from phase7.paper_policy.paper_risk import evaluate_paper_risk
from phase7.paper_policy.pcr_policy import calculate_pcr
from phase7.paper_policy.price_oi_state import classify_price_oi_state
from phase7.paper_policy.provenance import (
    create_provenance_contract,
    verify_provenance_contract,
)
from phase7.paper_policy.reason_codes import PolicyReasonCode
from phase7.paper_policy.source_mode import (
    SourceModeError,
    is_source_mode_permitted,
    validate_source_mode,
    verify_immutable_source_label,
)
from phase7.paper_policy.view_models import format_screen_11_cli
from phase7.paper_policy.vwap_policy import evaluate_vwap_policy


# =============================================================================
# 1. Parameter Validation and Configuration Bounds Tests
# =============================================================================

def test_paper_policy_master_config_defaults():
    """Verify default master configuration parameter IDs and versioning."""
    cfg = PaperPolicyMasterConfig()
    cfg.validate()
    assert cfg.parameter_set_id == "GOVERNED_PAPER_OBSERVATION_POLICY_V1"
    assert cfg.parameter_set_version == "1.0.0"
    as_dict = cfg.to_dict()
    assert as_dict["indicators"]["sma_periods"] == [20, 50, 200]
    assert as_dict["indicators"]["ema_periods"] == [9, 21]
    assert as_dict["indicators"]["rsi_period"] == 14
    assert as_dict["indicators"]["atr_period"] == 14
    assert as_dict["indicators"]["macd"] == [12, 26, 9]
    assert as_dict["indicators"]["execution_status"] == "BLOCKED_UNTIL_GATE1"


def test_indicator_config_invalid_periods():
    """Verify indicator configuration rejects non-positive or inverted periods."""
    with pytest.raises(ValueError, match="strictly positive"):
        IndicatorConfig(sma_periods=(20, -50, 200)).validate()

    with pytest.raises(ValueError, match="strictly less"):
        IndicatorConfig(macd_fast=26, macd_slow=12).validate()


def test_price_oi_config_bounds():
    """Verify Price/OI configuration rejects invalid threshold relationships."""
    cfg = PriceOIConfig()
    cfg.validate()
    assert cfg.price_state_threshold_pct == 0.25
    assert cfg.oi_state_threshold_pct == 2.00
    assert cfg.price_neutral_band_pct == 0.10
    assert cfg.oi_neutral_band_pct == 1.00

    # Neutral band must be strictly less than state threshold
    with pytest.raises(ValueError, match="price_neutral_band_pct"):
        PriceOIConfig(price_state_threshold_pct=0.25, price_neutral_band_pct=0.30).validate()

    with pytest.raises(ValueError, match="oi_neutral_band_pct"):
        PriceOIConfig(oi_state_threshold_pct=2.0, oi_neutral_band_pct=2.5).validate()


def test_paper_risk_config_bounds():
    """Verify paper risk configuration bounds and safety ranges."""
    cfg = PaperRiskConfig()
    cfg.validate()

    with pytest.raises(ValueError, match="minimum_stop_distance_pct"):
        PaperRiskConfig(minimum_stop_distance_pct=4.0, maximum_stop_distance_pct=3.0).validate()

    with pytest.raises(ValueError, match="minimum_reward_risk_ratio"):
        PaperRiskConfig(minimum_reward_risk_ratio=0.0).validate()


# =============================================================================
# 2. Source Mode Isolation and Anti-Masquerade Guards Tests
# =============================================================================

def test_source_mode_permitted_isolation():
    """Verify only synthetic and governed fixture source modes are permitted."""
    assert is_source_mode_permitted(SourceMode.SYNTHETIC_TEST.value) is True
    assert is_source_mode_permitted(SourceMode.GOVERNED_RECORDED_FIXTURE.value) is True
    assert is_source_mode_permitted(SourceMode.LIVE_SOURCE.value) is False
    assert is_source_mode_permitted("UNKNOWN_MODE") is False


def test_live_source_mode_blocked_fail_closed():
    """Verify LIVE_SOURCE is blocked by owner external acquisition policy."""
    ok, reason, status = validate_source_mode(SourceMode.LIVE_SOURCE.value)
    assert ok is False
    assert reason == PolicyReasonCode.EXTERNAL_ACQUISITION_BLOCKED.value
    assert status == LIVE_SOURCE_STATUS


def test_unknown_source_mode_rejection():
    """Verify unknown or improvised source modes are rejected."""
    ok, reason, _ = validate_source_mode("UNAUTHORIZED_SCRAPED_SOURCE")
    assert ok is False
    assert reason == PolicyReasonCode.SOURCE_MODE_BLOCKED_NO_DECISION.value


def test_anti_masquerade_guard_synthetic_relabeling():
    """Verify runtime attempts to relabel synthetic data as live are rejected."""
    tampered_record = {"source_mode": "LIVE_SOURCE", "is_synthetic": True}
    with pytest.raises(SourceModeError, match="PROHIBITED_RELABELING"):
        verify_immutable_source_label(tampered_record)


def test_source_label_missing_rejection():
    """Verify missing source mode label raises SourceModeError."""
    with pytest.raises(SourceModeError, match="Missing mandatory 'source_mode'"):
        verify_immutable_source_label({"data": 123})


# =============================================================================
# 3. Cryptographic Provenance and Hash Conservation Tests
# =============================================================================

def test_provenance_contract_creation_and_verification():
    """Verify valid provenance contract creation and verification pass."""
    payload = {"symbol": "TCS", "price": 3500.0, "volume": 1000}
    contract = create_provenance_contract(
        source_identifier="LAB_SYNTHETIC_GENERATOR",
        source_mode=SourceMode.SYNTHETIC_TEST.value,
        payload=payload,
        generation_timestamp_utc="2026-11-02T04:00:00+00:00",
        dataset_label="SYNTHETIC_TEST_V1",
    )
    ok, reason = verify_provenance_contract(contract, payload)
    assert ok is True
    assert reason is None
    assert contract.governance_lock is True


def test_provenance_tampered_payload_detection():
    """Verify tampering with evaluation payload invalidates cryptographic provenance."""
    payload = {"symbol": "TCS", "price": 3500.0, "volume": 1000}
    contract = create_provenance_contract(
        source_identifier="LAB_SYNTHETIC_GENERATOR",
        source_mode=SourceMode.SYNTHETIC_TEST.value,
        payload=payload,
        generation_timestamp_utc="2026-11-02T04:00:00+00:00",
        dataset_label="SYNTHETIC_TEST_V1",
    )
    tampered = {"symbol": "TCS", "price": 3500.5, "volume": 1000}
    ok, reason = verify_provenance_contract(contract, tampered)
    assert ok is False
    assert reason == PolicyReasonCode.PROVENANCE_INVALID_NO_DECISION.value


def test_provenance_creation_rejected_for_live_source():
    """Verify provenance contracts cannot be created for blocked LIVE_SOURCE."""
    payload = {"symbol": "INFY", "price": 1800.0}
    with pytest.raises(ValueError, match="Cannot create provenance contract"):
        create_provenance_contract(
            source_identifier="LIVE_PROBE",
            source_mode=SourceMode.LIVE_SOURCE.value,
            payload=payload,
            generation_timestamp_utc="2026-11-02T04:00:00+00:00",
            dataset_label="LIVE_ATTEMPT",
        )


# =============================================================================
# 4. Freshness and Timestamp Verification Tests
# =============================================================================

def test_quote_freshness_valid():
    """Verify quote within 20 seconds is classified fresh."""
    eval_time = datetime(2026, 11, 2, 9, 31, 10, tzinfo=timezone.utc)
    quote = {
        "price": 24500.0,
        "volume": 5000,
        "exchange_timestamp_utc": "2026-11-02T09:31:00+00:00",  # 10s old
        "business_date": "2026-11-02",
    }
    ok, reason, details = evaluate_quote_freshness(quote, eval_time)
    assert ok is True
    assert reason is None
    assert details["age_seconds"] == 10.0


def test_quote_freshness_stale_rejection():
    """Verify quote exceeding maximum 20 seconds age returns STALE_QUOTE_NO_DECISION."""
    eval_time = datetime(2026, 11, 2, 9, 31, 30, tzinfo=timezone.utc)
    quote = {
        "price": 24500.0,
        "volume": 5000,
        "exchange_timestamp_utc": "2026-11-02T09:31:00+00:00",  # 30s old > 20s max
        "business_date": "2026-11-02",
    }
    ok, reason, _ = evaluate_quote_freshness(quote, eval_time)
    assert ok is False
    assert reason == PolicyReasonCode.STALE_QUOTE_NO_DECISION.value


def test_quote_future_timestamp_rejection():
    """Verify future quote timestamp returns FUTURE_TIMESTAMP_NO_DECISION."""
    eval_time = datetime(2026, 11, 2, 9, 30, 0, tzinfo=timezone.utc)
    quote = {
        "price": 24500.0,
        "volume": 5000,
        "exchange_timestamp_utc": "2026-11-02T09:30:15+00:00",  # 15s in future
        "business_date": "2026-11-02",
    }
    ok, reason, _ = evaluate_quote_freshness(quote, eval_time)
    assert ok is False
    assert reason == PolicyReasonCode.FUTURE_TIMESTAMP_NO_DECISION.value


def test_quote_wrong_business_date_rejection():
    """Verify quote from previous business date returns WRONG_BUSINESS_DATE_NO_DECISION."""
    eval_time = datetime(2026, 11, 2, 9, 30, 10, tzinfo=timezone.utc)
    quote = {
        "price": 24500.0,
        "volume": 5000,
        "exchange_timestamp_utc": "2026-11-01T09:30:00+00:00",
        "business_date": "2026-11-01",  # Yesterday
    }
    ok, reason, _ = evaluate_quote_freshness(quote, eval_time)
    assert ok is False
    assert reason == PolicyReasonCode.WRONG_BUSINESS_DATE_NO_DECISION.value


def test_quote_zero_volume_rejection():
    """Verify zero traded volume quote returns ZERO_VOLUME_NO_DECISION."""
    eval_time = datetime(2026, 11, 2, 9, 30, 10, tzinfo=timezone.utc)
    quote = {
        "price": 24500.0,
        "volume": 0,
        "exchange_timestamp_utc": "2026-11-02T09:30:05+00:00",
        "business_date": "2026-11-02",
    }
    ok, reason, _ = evaluate_quote_freshness(quote, eval_time)
    assert ok is False
    assert reason == PolicyReasonCode.ZERO_VOLUME_NO_DECISION.value


def test_quote_missing_timestamp_unverified():
    """Verify quote with missing timestamp returns UNVERIFIED_TIMESTAMP_NO_DECISION."""
    eval_time = datetime(2026, 11, 2, 9, 30, 10, tzinfo=timezone.utc)
    quote = {"price": 24500.0, "volume": 100}
    ok, reason, _ = evaluate_quote_freshness(quote, eval_time)
    assert ok is False
    assert reason == PolicyReasonCode.UNVERIFIED_TIMESTAMP_NO_DECISION.value


def test_vwap_freshness_evaluation():
    """Verify VWAP freshness boundaries (<= 30s) and stale rejections."""
    eval_time = datetime(2026, 11, 2, 9, 30, 30, tzinfo=timezone.utc)
    fresh_vwap = {"vwap_value": 24450.0, "timestamp_utc": "2026-11-02T09:30:10+00:00"}
    ok, reason, _ = evaluate_vwap_freshness(fresh_vwap, eval_time)
    assert ok is True

    stale_vwap = {"vwap_value": 24450.0, "timestamp_utc": "2026-11-02T09:29:50+00:00"}  # 40s old
    ok, reason, _ = evaluate_vwap_freshness(stale_vwap, eval_time)
    assert ok is False
    assert reason == PolicyReasonCode.STALE_VWAP_NO_DECISION.value


# =============================================================================
# 5. VWAP Policy and Formula Governance Tests
# =============================================================================

def test_vwap_formula_decision_eligibility():
    """Verify SOURCE_REPORTED and TRADE_RECONSTRUCTED VWAP are decision eligible."""
    eval_time = datetime(2026, 11, 2, 9, 30, 10, tzinfo=timezone.utc)
    data_source = {
        "formula_type": VWAPFormulaType.SOURCE_REPORTED_VWAP.value,
        "vwap_value": 24400.0,
        "cumulative_volume": 100000,
        "timestamp_utc": "2026-11-02T09:30:00+00:00",
    }
    ok, _, det = evaluate_vwap_policy(data_source, eval_time)
    assert ok is True
    assert det["is_decision_eligible"] is True
    assert det["is_display_only"] is False


def test_vwap_candle_approximation_display_only_restriction():
    """Verify GOVERNED_CANDLE_APPROXIMATION is restricted to DISPLAY_ONLY."""
    eval_time = datetime(2026, 11, 2, 9, 30, 10, tzinfo=timezone.utc)
    data_candle = {
        "formula_type": VWAPFormulaType.GOVERNED_CANDLE_APPROXIMATION.value,
        "vwap_value": 24405.0,
        "cumulative_volume": 100000,
        "timestamp_utc": "2026-11-02T09:30:00+00:00",
    }
    ok, _, det = evaluate_vwap_policy(data_candle, eval_time)
    assert ok is True
    assert det["is_decision_eligible"] is False
    assert det["is_display_only"] is True
    assert det["display_status"] == CANDLE_APPROXIMATION_STATUS


def test_vwap_zero_cumulative_volume_rejection():
    """Verify VWAP with non-positive cumulative volume is rejected."""
    eval_time = datetime(2026, 11, 2, 9, 30, 10, tzinfo=timezone.utc)
    data = {
        "formula_type": VWAPFormulaType.SOURCE_REPORTED_VWAP.value,
        "vwap_value": 24400.0,
        "cumulative_volume": 0,
        "timestamp_utc": "2026-11-02T09:30:00+00:00",
    }
    ok, reason, _ = evaluate_vwap_policy(data, eval_time)
    assert ok is False
    assert reason == PolicyReasonCode.ZERO_VOLUME_NO_DECISION.value


def test_vwap_invalid_formula_rejection():
    """Verify unregistered VWAP formula type is rejected."""
    eval_time = datetime(2026, 11, 2, 9, 30, 10, tzinfo=timezone.utc)
    data = {
        "formula_type": "IMPROVISED_ESTIMATE",
        "vwap_value": 24400.0,
        "cumulative_volume": 100000,
        "timestamp_utc": "2026-11-02T09:30:00+00:00",
    }
    ok, reason, _ = evaluate_vwap_policy(data, eval_time)
    assert ok is False
    assert reason == PolicyReasonCode.PROVENANCE_INVALID_NO_DECISION.value


# =============================================================================
# 6. Opening Range Policy Tests
# =============================================================================

def test_opening_range_ready_after_buffer():
    """Verify opening range evaluated at or after 09:30:30 IST is READY."""
    data = {"high": 24550.0, "low": 24420.0, "volume": 150000, "finalized": True}
    ok, outcome, det = evaluate_opening_range(data, "09:30:35")
    assert ok is True
    assert outcome == OpeningRangeOutcome.OPENING_RANGE_READY.value
    assert det["range_spread"] == 130.0


def test_opening_range_incomplete_before_buffer():
    """Verify evaluation before 09:30:30 IST returns OPENING_RANGE_INCOMPLETE_NO_DECISION."""
    data = {"high": 24550.0, "low": 24420.0, "volume": 150000, "finalized": True}
    ok, outcome, _ = evaluate_opening_range(data, "09:28:00")
    assert ok is False
    assert outcome == OpeningRangeOutcome.OPENING_RANGE_INCOMPLETE_NO_DECISION.value

    # Exactly at 09:30:00 (before 30s buffer)
    ok2, outcome2, _ = evaluate_opening_range(data, "09:30:00")
    assert ok2 is False
    assert outcome2 == OpeningRangeOutcome.OPENING_RANGE_INCOMPLETE_NO_DECISION.value


def test_opening_range_unfinalized_interval_rejection():
    """Verify unfinalized opening range interval is rejected."""
    data = {"high": 24550.0, "low": 24420.0, "volume": 150000, "finalized": False}
    ok, outcome, _ = evaluate_opening_range(data, "09:31:00")
    assert ok is False
    assert outcome == OpeningRangeOutcome.OPENING_RANGE_INCOMPLETE_NO_DECISION.value


def test_opening_range_invalid_bounds_rejection():
    """Verify invalid high/low prices return OPENING_RANGE_INVALID_NO_DECISION."""
    data_inverted = {"high": 24400.0, "low": 24500.0, "volume": 1000, "finalized": True}
    ok, outcome, _ = evaluate_opening_range(data_inverted, "09:31:00")
    assert ok is False
    assert outcome == OpeningRangeOutcome.OPENING_RANGE_INVALID_NO_DECISION.value


def test_opening_range_stale_after_close():
    """Verify opening range evaluated past market close is marked stale."""
    data = {"high": 24550.0, "low": 24420.0, "volume": 150000, "finalized": True}
    ok, outcome, _ = evaluate_opening_range(data, "16:00:00")
    assert ok is False
    assert outcome == OpeningRangeOutcome.OPENING_RANGE_STALE_NO_DECISION.value


# =============================================================================
# 7. Price/OI State Classification and Neutral Bands Tests
# =============================================================================

def test_price_oi_four_quadrant_states():
    """Verify Price/OI four standard quadrant states: Long Buildup, Short Covering, Short Buildup, Long Unwinding."""
    # 1. Long Buildup: Price +0.41%, OI +5.0%
    s1, r1, det1 = classify_price_oi_state(prev_price=24400.0, curr_price=24500.0, prev_oi=100000, curr_oi=105000)
    assert s1 == PriceOIState.LONG_BUILDUP
    assert r1 is None
    assert det1["label"] == GOVERNED_PRICE_OI_LABEL

    # 2. Short Covering: Price +0.41%, OI -5.0%
    s2, _, _ = classify_price_oi_state(prev_price=24400.0, curr_price=24500.0, prev_oi=100000, curr_oi=95000)
    assert s2 == PriceOIState.SHORT_COVERING

    # 3. Short Buildup: Price -0.41%, OI +5.0%
    s3, _, _ = classify_price_oi_state(prev_price=24500.0, curr_price=24400.0, prev_oi=100000, curr_oi=105000)
    assert s3 == PriceOIState.SHORT_BUILDUP

    # 4. Long Unwinding: Price -0.41%, OI -5.0%
    s4, _, _ = classify_price_oi_state(prev_price=24500.0, curr_price=24400.0, prev_oi=100000, curr_oi=95000)
    assert s4 == PriceOIState.LONG_UNWINDING


def test_price_oi_neutral_bands_and_indeterminate():
    """Verify neutral band dampening results in NEUTRAL_PRICE, NEUTRAL_OI, or INDETERMINATE."""
    # Price neutral (change <= 0.10%), OI active (+5.0%)
    s_np, _, _ = classify_price_oi_state(prev_price=24500.0, curr_price=24510.0, prev_oi=100000, curr_oi=105000)
    assert s_np == PriceOIState.NEUTRAL_PRICE

    # OI neutral (change <= 1.0%), Price active (+0.41%)
    s_noi, _, _ = classify_price_oi_state(prev_price=24400.0, curr_price=24500.0, prev_oi=100000, curr_oi=100500)
    assert s_noi == PriceOIState.NEUTRAL_OI

    # Both neutral
    s_both, _, _ = classify_price_oi_state(prev_price=24500.0, curr_price=24505.0, prev_oi=100000, curr_oi=100200)
    assert s_both == PriceOIState.INDETERMINATE


def test_price_oi_continuity_validations():
    """Verify zero prior OI, contract mismatch, and corporate action checks."""
    # Zero prior OI
    s_oi, r_oi, _ = classify_price_oi_state(prev_price=100.0, curr_price=101.0, prev_oi=0, curr_oi=500)
    assert s_oi == PriceOIState.INSUFFICIENT_DATA
    assert r_oi == PolicyReasonCode.ZERO_PRIOR_OI_NO_DECISION.value

    # Rollover mismatch
    s_ro, r_ro, _ = classify_price_oi_state(
        prev_price=100.0, curr_price=101.0, prev_oi=1000, curr_oi=1100,
        contract_info={"rollover_mismatch": True}
    )
    assert s_ro == PriceOIState.INSUFFICIENT_DATA
    assert r_ro == PolicyReasonCode.ROLLOVER_MISMATCH_NO_DECISION.value

    # Corporate action unresolved
    s_ca, r_ca, _ = classify_price_oi_state(
        prev_price=100.0, curr_price=101.0, prev_oi=1000, curr_oi=1100,
        contract_info={"corporate_action_unresolved": True}
    )
    assert s_ca == PriceOIState.INSUFFICIENT_DATA
    assert r_ca == PolicyReasonCode.CORPORATE_ACTION_UNRESOLVED_NO_DECISION.value


def test_price_oi_strictly_forbids_institutional_positioning_label():
    """Verify that INSTITUTIONAL_POSITIONING is prohibited and PRICE_OI_STATE is enforced."""
    assert GOVERNED_PRICE_OI_LABEL == "PRICE_OI_STATE"
    assert PROHIBITED_PRICE_OI_LABEL == "INSTITUTIONAL_POSITIONING"
    _, _, det = classify_price_oi_state(prev_price=24400.0, curr_price=24500.0, prev_oi=100000, curr_oi=105000)
    assert det["label"] == "PRICE_OI_STATE"
    assert "INSTITUTIONAL_POSITIONING" not in det


# =============================================================================
# 8. Options Quality, Walls, and Liquidity Tests
# =============================================================================

def test_strike_liquidity_within_window():
    """Verify strike liquidity within +/-15% window meeting minimum metrics."""
    strike = {
        "strike_price": 24600.0,
        "open_interest": 25000,
        "volume": 5000,
        "trade_count": 250,
        "bid_price": 100.0,
        "ask_price": 102.0,
    }
    ok, reason, det = evaluate_strike_liquidity(strike, spot_price=24500.0)
    assert ok is True
    assert reason is None
    assert det["distance_pct"] < 15.0


def test_strike_liquidity_outside_window_rejected():
    """Verify strike outside +/-15% window is rejected."""
    strike = {
        "strike_price": 29000.0,  # ~18.3% away
        "open_interest": 25000,
        "volume": 5000,
        "trade_count": 250,
        "bid_price": 5.0,
        "ask_price": 5.5,
    }
    ok, reason, _ = evaluate_strike_liquidity(strike, spot_price=24500.0)
    assert ok is False
    assert reason == PolicyReasonCode.OPTIONS_INSUFFICIENT_LIQUIDITY_NO_DECISION.value


def test_options_wall_confidence_and_conflict_metadata():
    """Verify options wall identification assigns confidence without replacing targets."""
    strikes = [
        {"strike_price": 24600.0, "option_type": "CE", "open_interest": 45000, "volume": 5000, "trade_count": 200, "bid_price": 100.0, "ask_price": 102.0},
        {"strike_price": 24700.0, "option_type": "CE", "open_interest": 25000, "volume": 3000, "trade_count": 150, "bid_price": 60.0, "ask_price": 61.0},
        {"strike_price": 24400.0, "option_type": "PE", "open_interest": 52000, "volume": 6000, "trade_count": 250, "bid_price": 95.0, "ask_price": 97.0},
        {"strike_price": 24300.0, "option_type": "PE", "open_interest": 30000, "volume": 4000, "trade_count": 180, "bid_price": 65.0, "ask_price": 66.0},
    ]
    conf, meta = evaluate_options_wall(strikes, spot_price=24500.0)
    assert conf in (OptionsWallConfidence.HIGH_CONFIDENCE, OptionsWallConfidence.MEDIUM_CONFIDENCE)
    assert meta["call_wall_strike"] == 24600.0
    assert meta["put_wall_strike"] == 24400.0
    assert meta["conflict_metadata_only"] is True


def test_options_wall_empty_strikes_indeterminate():
    """Verify empty options chain returns INDETERMINATE confidence."""
    conf, _ = evaluate_options_wall([], spot_price=24500.0)
    assert conf == OptionsWallConfidence.INDETERMINATE


# =============================================================================
# 9. Put-Call Ratio (PCR) Policy Tests
# =============================================================================

def test_pcr_calculation_valid():
    """Verify Put-Call Ratio computation for single expiry and business date."""
    contracts = [
        {"strike_price": 24600.0, "option_type": "CE", "open_interest": 50000, "volume": 10000, "expiry_date": "2026-11-05", "business_date": "2026-11-02"},
        {"strike_price": 24400.0, "option_type": "PE", "open_interest": 60000, "volume": 12000, "expiry_date": "2026-11-05", "business_date": "2026-11-02"},
    ]
    ok, reason, det = calculate_pcr(contracts, spot_price=24500.0)
    assert ok is True
    assert reason is None
    assert det["oi_pcr"] == 1.2
    assert det["volume_pcr"] == 1.2
    assert det["included_contracts"] == 2


def test_pcr_zero_denominator_rejection():
    """Verify zero call open interest returns PCR_ZERO_DENOMINATOR_NO_DECISION."""
    contracts = [
        {"strike_price": 24400.0, "option_type": "PE", "open_interest": 60000, "volume": 12000, "expiry_date": "2026-11-05", "business_date": "2026-11-02"},
    ]
    ok, reason, _ = calculate_pcr(contracts, spot_price=24500.0)
    assert ok is False
    assert reason == PolicyReasonCode.PCR_ZERO_DENOMINATOR_NO_DECISION.value


def test_pcr_mixed_expiry_rejection():
    """Verify mixed expiry contracts without explicit target are rejected."""
    contracts = [
        {"strike_price": 24600.0, "option_type": "CE", "open_interest": 50000, "volume": 10000, "expiry_date": "2026-11-05", "business_date": "2026-11-02"},
        {"strike_price": 24400.0, "option_type": "PE", "open_interest": 60000, "volume": 12000, "expiry_date": "2026-11-12", "business_date": "2026-11-02"},
    ]
    ok, reason, _ = calculate_pcr(contracts, spot_price=24500.0)
    assert ok is False
    assert reason == PolicyReasonCode.MIXED_EXPIRY_REJECTED.value


def test_pcr_excluded_contracts_outside_strike_window():
    """Verify contracts far outside +/-15% strike window are tallies as excluded."""
    contracts = [
        {"strike_price": 24600.0, "option_type": "CE", "open_interest": 50000, "volume": 10000, "expiry_date": "2026-11-05", "business_date": "2026-11-02"},
        {"strike_price": 24400.0, "option_type": "PE", "open_interest": 60000, "volume": 12000, "expiry_date": "2026-11-05", "business_date": "2026-11-02"},
        {"strike_price": 35000.0, "option_type": "CE", "open_interest": 10000, "volume": 2000, "expiry_date": "2026-11-05", "business_date": "2026-11-02"},  # Outside
    ]
    ok, _, det = calculate_pcr(contracts, spot_price=24500.0)
    assert ok is True
    assert det["included_contracts"] == 2
    assert det["excluded_contracts"] == 1


# =============================================================================
# 10. Paper Risk Estimation and Safety Cap Tests
# =============================================================================

def test_paper_risk_position_sizing_valid():
    """Verify paper risk sizing calculation within governed bounds."""
    ok, reason, det = evaluate_paper_risk(
        entry_price=100.0,
        stop_loss_price=98.5,  # 1.5% stop distance
        take_profit_price=103.5,  # 3.5% reward, R:R = 2.33
        portfolio_capital=100000.0,
        source_mode=SourceMode.SYNTHETIC_TEST.value,
    )
    assert ok is True
    assert reason is None
    assert det["output_type"] == GOVERNED_RISK_OUTPUT_LABEL
    assert det["stop_distance_pct"] == 1.5
    assert det["reward_risk_ratio"] > 1.5


def test_paper_risk_out_of_bounds_stop_distance_rejection():
    """Verify stop distance below 0.75% or above 3.5% is rejected."""
    # Stop distance 0.5% (< 0.75% min)
    ok_tight, reason_tight, _ = evaluate_paper_risk(
        entry_price=100.0, stop_loss_price=99.5, take_profit_price=103.0,
        portfolio_capital=100000.0, source_mode=SourceMode.SYNTHETIC_TEST.value
    )
    assert ok_tight is False
    assert reason_tight == PolicyReasonCode.RISK_LIMIT_EXCEEDED_NO_DECISION.value

    # Stop distance 5.0% (> 3.5% max)
    ok_wide, reason_wide, _ = evaluate_paper_risk(
        entry_price=100.0, stop_loss_price=95.0, take_profit_price=110.0,
        portfolio_capital=100000.0, source_mode=SourceMode.SYNTHETIC_TEST.value
    )
    assert ok_wide is False
    assert reason_wide == PolicyReasonCode.RISK_LIMIT_EXCEEDED_NO_DECISION.value


def test_paper_risk_insufficient_rr_ratio_rejection():
    """Verify reward-to-risk ratio below 1.50 is rejected."""
    ok, reason, _ = evaluate_paper_risk(
        entry_price=100.0, stop_loss_price=98.0, take_profit_price=101.5,  # R:R = 1.5 / 2.0 = 0.75
        portfolio_capital=100000.0, source_mode=SourceMode.SYNTHETIC_TEST.value
    )
    assert ok is False
    assert reason == PolicyReasonCode.RISK_LIMIT_EXCEEDED_NO_DECISION.value


def test_paper_risk_max_open_observations_cap():
    """Verify risk calculation is blocked when open observations reach cap."""
    ok, reason, _ = evaluate_paper_risk(
        entry_price=100.0, stop_loss_price=98.5, take_profit_price=103.5,
        portfolio_capital=100000.0, source_mode=SourceMode.SYNTHETIC_TEST.value,
        open_observations_count=5,  # Cap reached
    )
    assert ok is False
    assert reason == PolicyReasonCode.RISK_LIMIT_EXCEEDED_NO_DECISION.value


def test_paper_risk_sector_exposure_cap():
    """Verify risk calculation is blocked when sector exposure exceeds cap."""
    ok, reason, _ = evaluate_paper_risk(
        entry_price=100.0, stop_loss_price=98.5, take_profit_price=103.5,
        portfolio_capital=100000.0, source_mode=SourceMode.SYNTHETIC_TEST.value,
        current_sector_exposure_pct=15.0,  # Cap reached
    )
    assert ok is False
    assert reason == PolicyReasonCode.RISK_LIMIT_EXCEEDED_NO_DECISION.value


def test_paper_risk_strictly_prohibits_order_terms():
    """Verify paper risk output strictly forbids broker and order execution terms."""
    ok, _, det = evaluate_paper_risk(
        entry_price=100.0, stop_loss_price=98.5, take_profit_price=103.5,
        portfolio_capital=100000.0, source_mode=SourceMode.SYNTHETIC_TEST.value
    )
    assert ok is True
    for prohibited in PROHIBITED_RISK_OUTPUT_LABELS:
        assert prohibited not in det


# =============================================================================
# 11. Centralized Eligibility Gates G01 through G24 Tests
# =============================================================================

def test_central_gates_full_pass():
    """Verify all 24 gates G01-G24 pass on a clean synthetic evaluation payload."""
    now = datetime(2026, 11, 2, 9, 31, 0, tzinfo=timezone.utc)
    date_str = "2026-11-02"
    payload = {
        "observation_id": "OBS-001",
        "source_mode": SourceMode.SYNTHETIC_TEST.value,
        "symbol": "TCS",
        "series": "EQ",
        "listing_status": "ACTIVE",
        "business_date": date_str,
        "quote": {"price": 3500.0, "volume": 50000, "exchange_timestamp_utc": now.isoformat()},
        "vwap": {"formula_type": VWAPFormulaType.SOURCE_REPORTED_VWAP.value, "vwap_value": 3495.0, "cumulative_volume": 100000, "timestamp_utc": now.isoformat()},
        "opening_range": {"high": 3520.0, "low": 3480.0, "volume": 20000, "finalized": True},
        "evaluation_time_ist": "09:35:00",
        "provenance": {"record_hash": "DUMMY_HASH"},
        "price_oi": {"prev_price": 3480.0, "curr_price": 3500.0, "prev_oi": 10000, "curr_oi": 10500},
        "risk_parameters": {"entry_price": 3500.0, "stop_loss_price": 3450.0, "take_profit_price": 3600.0, "portfolio_capital": 100000.0},
    }
    result = evaluate_central_eligibility_gates(payload, now)
    assert result.passed_gates_count == 24
    assert result.total_gates_count == 24
    assert result.all_pre_execution_gates_passed is True
    assert result.overall_simulation_outcome == POLICY_SIMULATION_OUTCOME
    assert result.governance_statuses["LIVE_SOURCE"] == LIVE_SOURCE_STATUS
    assert result.governance_statuses["ANALYTICAL_EXECUTION"] == ANALYTICAL_STATUS
    assert result.governance_statuses["MODEL_EXECUTION"] == MODEL_STATUS
    assert result.governance_statuses["ORDER_EXECUTION"] == ORDER_STATUS


def test_central_gates_duplicate_observation_rejection():
    """Verify duplicate observation ID fails G19."""
    now = datetime(2026, 11, 2, 9, 31, 0, tzinfo=timezone.utc)
    seen = {"OBS-001"}
    payload = {
        "observation_id": "OBS-001",
        "source_mode": SourceMode.SYNTHETIC_TEST.value,
        "symbol": "TCS",
        "business_date": "2026-11-02",
        "quote": {"price": 3500.0, "volume": 50000, "exchange_timestamp_utc": now.isoformat()},
    }
    result = evaluate_central_eligibility_gates(payload, now, seen_observation_ids=seen)
    assert result.gate_statuses["G19"] is False
    assert result.gate_reasons["G19"] == PolicyReasonCode.DUPLICATE_OBSERVATION_NO_DECISION.value


def test_central_gates_live_source_blocked():
    """Verify LIVE_SOURCE fails G01 and G21 fail-closed."""
    now = datetime(2026, 11, 2, 9, 31, 0, tzinfo=timezone.utc)
    payload = {
        "observation_id": "OBS-002",
        "source_mode": SourceMode.LIVE_SOURCE.value,
        "symbol": "TCS",
        "business_date": "2026-11-02",
        "quote": {"price": 3500.0, "volume": 50000, "exchange_timestamp_utc": now.isoformat()},
    }
    result = evaluate_central_eligibility_gates(payload, now)
    assert result.gate_statuses["G01"] is False
    assert result.gate_statuses["G21"] is False
    assert PolicyReasonCode.EXTERNAL_ACQUISITION_BLOCKED.value in result.failed_reason_codes


# =============================================================================
# 12. Operator Screen 11 Integration Tests
# =============================================================================

def test_screen_11_operator_core_integration():
    """Verify OperatorCore returns Screen 11 dictionary with all required keys."""
    core = OperatorCore()
    lab = core.get_paper_policy_lab()
    assert lab["screen"] == 11
    assert lab["title"] == "PAPER POLICY LAB"
    assert lab["banners"] == SCREEN_11_MANDATORY_BANNERS
    assert "evaluation_result" in lab
    assert lab["evaluation_result"]["passed_gates_count"] == 24


def test_screen_11_cli_rendering():
    """Verify OperatorCLI renders Screen 11 with mandatory banners and gate table."""
    cli = OperatorCLI()
    output = cli.render_screen(11)
    for b in SCREEN_11_MANDATORY_BANNERS:
        assert b in output
    assert "SCREEN 11: PAPER POLICY LAB" in output
    assert "Central Gates:" in output
    assert "DISCLAIMER: OFFLINE SYNTHETIC SIMULATION ONLY" in output


def test_screen_11_view_model_formatter():
    """Verify direct format_screen_11_cli formatter generates clean output."""
    now = datetime(2026, 11, 2, 9, 31, 0, tzinfo=timezone.utc)
    payload = {
        "observation_id": "OBS-VM-01",
        "source_mode": SourceMode.SYNTHETIC_TEST.value,
        "symbol": "INFY",
        "business_date": "2026-11-02",
        "quote": {"price": 1800.0, "volume": 10000, "exchange_timestamp_utc": now.isoformat()},
    }
    result = evaluate_central_eligibility_gates(payload, now)
    lines = format_screen_11_cli(result)
    assert any("SCREEN 11: PAPER POLICY LAB" in line for line in lines)
    assert any("INFY" in line for line in lines)


def test_screen_11_gui_headless_initialization():
    """Verify OperatorGUI with include_lab=True populates 11 notebook tabs."""
    root = tk.Tk()
    root.withdraw()
    try:
        core = OperatorCore()
        gui = OperatorGUI(root, core=core, include_lab=True)
        assert gui.notebook.index("end") == 11
        assert gui.policy_text is not None
        content = gui.policy_text.get("1.0", tk.END)
        assert "SCREEN 11: PAPER POLICY LAB" in content
    finally:
        root.destroy()


# =============================================================================
# 13. Network Quarantine and Safeguards Isolation Tests
# =============================================================================

def test_paper_policy_no_network_imports():
    """Scan phase7.paper_policy for unauthorized network or broker modules."""
    import phase7.paper_policy as pp
    module_path = Path(pp.__file__).parent
    forbidden = ["socket", "urllib.request", "requests", "httpx", "aiohttp", "telegram", "nsepython"]

    for py_file in module_path.glob("*.py"):
        content = py_file.read_text(encoding="utf-8").lower()
        for f in forbidden:
            assert f"import {f}" not in content, f"Forbidden import '{f}' in {py_file.name}"


def test_paper_policy_does_not_mutate_staging():
    """Verify evaluating paper policy leaves preserved staging completely intact."""
    staging_dir = Path(r"C:\Users\r_chh\gaurvideep_phase7_staging\nse500")
    if staging_dir.exists():
        manifest_files = list(staging_dir.rglob("*.final.json"))
        mtimes_before = {p: p.stat().st_mtime_ns for p in manifest_files}

        core = OperatorCore()
        core.get_paper_policy_lab()

        mtimes_after = {p: p.stat().st_mtime_ns for p in manifest_files}
        assert mtimes_before == mtimes_after
