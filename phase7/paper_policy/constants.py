"""Governed Paper Policy Constants and Enums [Milestone 4.14].

Provides versioned parameter identifiers, source modes, state enumerations,
gate definitions, and mandatory banners. All policy evaluation is pure, offline,
and quarantined from live data, broker interfaces, and downstream model execution.
"""

from enum import Enum
from typing import Dict, FrozenSet, List, Set

# Parameter Set Identification
PARAMETER_SET_ID: str = "GOVERNED_PAPER_OBSERVATION_POLICY_V1"
PARAMETER_SET_VERSION: str = "1.0.0"

# Source Modes
class SourceMode(str, Enum):
    """Governed source mode classifications."""
    SYNTHETIC_TEST = "SYNTHETIC_TEST"
    GOVERNED_RECORDED_FIXTURE = "GOVERNED_RECORDED_FIXTURE"
    LIVE_SOURCE = "LIVE_SOURCE"


PERMITTED_SOURCE_MODES: FrozenSet[str] = frozenset({
    SourceMode.SYNTHETIC_TEST.value,
    SourceMode.GOVERNED_RECORDED_FIXTURE.value,
})

# Status Enforcements
LIVE_SOURCE_STATUS: str = "LIVE_SOURCE_BLOCKED_BY_OWNER"
ANALYTICAL_STATUS: str = "ANALYTICAL_EXECUTION_BLOCKED_BY_GATE1"
MODEL_STATUS: str = "MODEL_EXECUTION_BLOCKED_BY_MILESTONE5"
ORDER_STATUS: str = "ORDER_EXECUTION_DISABLED"
POLICY_SIMULATION_OUTCOME: str = "POLICY_SIMULATION_COMPLETE"

# Price/OI State Classification
class PriceOIState(str, Enum):
    """Governed Price/Open-Interest state classifications."""
    LONG_BUILDUP = "LONG_BUILDUP"
    SHORT_COVERING = "SHORT_COVERING"
    SHORT_BUILDUP = "SHORT_BUILDUP"
    LONG_UNWINDING = "LONG_UNWINDING"
    NEUTRAL_PRICE = "NEUTRAL_PRICE"
    NEUTRAL_OI = "NEUTRAL_OI"
    INDETERMINATE = "INDETERMINATE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


GOVERNED_PRICE_OI_LABEL: str = "PRICE_OI_STATE"
PROHIBITED_PRICE_OI_LABEL: str = "INSTITUTIONAL_POSITIONING"

# VWAP Formula Types
class VWAPFormulaType(str, Enum):
    """Governed VWAP formula types."""
    SOURCE_REPORTED_VWAP = "SOURCE_REPORTED_VWAP"
    TRADE_RECONSTRUCTED_VWAP = "TRADE_RECONSTRUCTED_VWAP"
    GOVERNED_CANDLE_APPROXIMATION = "GOVERNED_CANDLE_APPROXIMATION"


CANDLE_APPROXIMATION_STATUS: str = "DISPLAY_ONLY"

# Opening-Range Outcomes
class OpeningRangeOutcome(str, Enum):
    """Governed opening-range policy outcomes."""
    OPENING_RANGE_READY = "OPENING_RANGE_READY"
    OPENING_RANGE_INCOMPLETE_NO_DECISION = "OPENING_RANGE_INCOMPLETE_NO_DECISION"
    OPENING_RANGE_STALE_NO_DECISION = "OPENING_RANGE_STALE_NO_DECISION"
    OPENING_RANGE_INVALID_NO_DECISION = "OPENING_RANGE_INVALID_NO_DECISION"


# Options Wall Confidence States
class OptionsWallConfidence(str, Enum):
    """Governed options-wall confidence levels."""
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    MEDIUM_CONFIDENCE = "MEDIUM_CONFIDENCE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    INSUFFICIENT_LIQUIDITY = "INSUFFICIENT_LIQUIDITY"
    INDETERMINATE = "INDETERMINATE"


# Paper Risk Outputs and Safeguards
GOVERNED_RISK_OUTPUT_LABEL: str = "PAPER_POSITION_ESTIMATE"

PROHIBITED_RISK_OUTPUT_LABELS: FrozenSet[str] = frozenset({
    "ORDER_QUANTITY",
    "EXECUTABLE_POSITION",
    "BROKER_ORDER",
})

# Mandatory Screen 11 Operator Banners
SCREEN_11_MANDATORY_BANNERS: List[str] = [
    "SYNTHETIC / GOVERNED FIXTURE MODE ONLY",
    "NO LIVE DATA ACQUISITION",
    "NO AUTOMATIC ORDER EXECUTION",
    "GATE 1 NOT PASSED",
    "MILESTONE 5 BLOCKED",
]

# Centralized Eligibility Gate Identifiers (G01 - G24)
GATE_DESCRIPTIONS: Dict[str, str] = {
    "G01": "Source Mode Isolation (SYNTHETIC_TEST or GOVERNED_RECORDED_FIXTURE required)",
    "G02": "Source Provenance Contract (valid checksum, non-empty source identity, uncompromised label)",
    "G03": "Business Date Sequence (evaluation date matches data business date)",
    "G04": "Underlying Symbol Identity (alphanumeric, approved symbol contract)",
    "G05": "Series Contract Verification (cash EQ series or approved derivative contract)",
    "G06": "Listing Status Validation (actively traded, not suspended or delisted)",
    "G07": "Quote Freshness Contract (quote age <= maximum_quote_age_seconds)",
    "G08": "Timestamp Monotonicity & Boundary (exchange timestamp present, non-future, non-decreasing)",
    "G09": "VWAP Freshness and Formula Governance (source/trade reported, not stale, display-only blocked for decision)",
    "G10": "Opening Range Finalization (finalized 09:15-09:30 interval + 30s buffer, positive volume)",
    "G11": "Volume Positivity (strictly positive cumulative traded volume)",
    "G12": "Cash Underlying Identity Verification (cash asset mapped and verified)",
    "G13": "Derivative Contract Mapping (consistent mapping between underlying and derivative contracts)",
    "G14": "Expiry Date Governance (valid future/current trading day expiry, nearest liquid valid expiry)",
    "G15": "Price/OI State Validity (prior OI > 0, same contract, rollover resolved)",
    "G16": "Options Wall Liquidity Quality (min OI, min volume, min trades, max bid-ask spread)",
    "G17": "Corporate Action Adjustment Resolution (no unadjusted splits, bonuses, or rights)",
    "G18": "Price Basis Reconciliation (no discrepancy between cash settlement and futures basis)",
    "G19": "Observation Deduplication (unique observation ID, non-redundant timestamp)",
    "G20": "Paper Risk Limit Checks (position cap, sector cap, max open observations, stop-loss bounds)",
    "G21": "External Acquisition Policy Guard (EXTERNAL_EVIDENCE_ACQUISITION_DEFERRED_BY_OWNER)",
    "G22": "Gate 1 Analytical Guard (ANALYTICAL_EXECUTION_BLOCKED_BY_GATE1)",
    "G23": "Milestone 5 Model Execution Guard (MODEL_EXECUTION_BLOCKED_BY_MILESTONE5)",
    "G24": "Order Execution Isolation Guard (ORDER_EXECUTION_DISABLED)",
}
