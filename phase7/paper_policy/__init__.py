"""Phase 7 Governed Paper-Observation Policy Package [Milestone 4.14].

Provides pure, deterministic, offline policy evaluation, parameter contracts,
centralized eligibility gates G01 to G24, and operator view models.
"""

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
    PERMITTED_SOURCE_MODES,
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
    SourceProvenanceContract,
    compute_payload_sha256,
    create_provenance_contract,
    verify_provenance_contract,
)
from phase7.paper_policy.reason_codes import PolicyReasonCode
from phase7.paper_policy.source_mode import (
    is_source_mode_permitted,
    validate_source_mode,
    verify_immutable_source_label,
)
from phase7.paper_policy.view_models import format_screen_11_cli

__all__ = [
    "PARAMETER_SET_ID",
    "PARAMETER_SET_VERSION",
    "SourceMode",
    "PERMITTED_SOURCE_MODES",
    "LIVE_SOURCE_STATUS",
    "ANALYTICAL_STATUS",
    "MODEL_STATUS",
    "ORDER_STATUS",
    "POLICY_SIMULATION_OUTCOME",
    "PriceOIState",
    "GOVERNED_PRICE_OI_LABEL",
    "PROHIBITED_PRICE_OI_LABEL",
    "VWAPFormulaType",
    "CANDLE_APPROXIMATION_STATUS",
    "OpeningRangeOutcome",
    "OptionsWallConfidence",
    "GOVERNED_RISK_OUTPUT_LABEL",
    "PROHIBITED_RISK_OUTPUT_LABELS",
    "SCREEN_11_MANDATORY_BANNERS",
    "GATE_DESCRIPTIONS",
    "PolicyReasonCode",
    "IndicatorConfig",
    "PriceOIConfig",
    "FreshnessConfig",
    "OpeningRangeConfig",
    "OptionsQualityConfig",
    "PaperRiskConfig",
    "PaperPolicyMasterConfig",
    "validate_source_mode",
    "is_source_mode_permitted",
    "verify_immutable_source_label",
    "SourceProvenanceContract",
    "create_provenance_contract",
    "verify_provenance_contract",
    "compute_payload_sha256",
    "evaluate_quote_freshness",
    "evaluate_vwap_freshness",
    "evaluate_vwap_policy",
    "evaluate_opening_range",
    "classify_price_oi_state",
    "evaluate_strike_liquidity",
    "evaluate_options_wall",
    "calculate_pcr",
    "evaluate_paper_risk",
    "GateEvaluationResult",
    "evaluate_central_eligibility_gates",
    "format_screen_11_cli",
]
