"""Governed Paper Policy View Models [Milestone 4.14].

Provides structured view models and text formatters for Screen 11 (Paper Policy Lab)
within the offline operator CLI and GUI interfaces.
"""

from typing import Any, Dict, List, Optional

from phase7.paper_policy.constants import (
    GATE_DESCRIPTIONS,
    PARAMETER_SET_ID,
    PARAMETER_SET_VERSION,
    SCREEN_11_MANDATORY_BANNERS,
)
from phase7.paper_policy.eligibility_gate import GateEvaluationResult


def format_screen_11_cli(
    result: GateEvaluationResult,
    custom_banners: Optional[List[str]] = None,
) -> List[str]:
    """Format Paper Policy Lab (Screen 11) for CLI display."""
    lines: List[str] = []
    lines.append("=" * 80)
    banners = custom_banners or SCREEN_11_MANDATORY_BANNERS
    for b in banners:
        lines.append(f" [BANNER] {b}")
    lines.append("=" * 80)
    lines.append("SCREEN 11: PAPER POLICY LAB [Milestone 4.14]")
    lines.append("-" * 80)

    # Parameter Set Metadata
    lines.append(f"Parameter Set ID:      {PARAMETER_SET_ID}")
    lines.append(f"Parameter Version:     {PARAMETER_SET_VERSION}")
    details = result.evaluation_details
    lines.append(f"Source Mode:           {details.get('source_mode', 'SYNTHETIC_TEST')}")
    lines.append(f"Target Symbol:         {details.get('symbol', 'NIFTY50_SYNTHETIC')}")
    lines.append("-" * 80)

    # Core Policy Evaluation Subsystems
    q_det = details.get("quote", {})
    lines.append(f"Quote Freshness:       Age: {q_det.get('age_seconds', 0.0):.1f}s | TS: {q_det.get('quote_ts', 'VALID_SYNTHETIC')}")

    v_det = details.get("vwap", {})
    lines.append(f"VWAP Evaluation:       Formula: {v_det.get('formula_type', 'SOURCE_REPORTED_VWAP')} | Status: {v_det.get('display_status', 'DECISION_ELIGIBLE_FORMULA')}")

    or_det = details.get("opening_range", {})
    lines.append(f"Opening Range:         Outcome: {or_det.get('outcome', 'OPENING_RANGE_READY')} | Spread: {or_det.get('range_spread_pct', 0.0)}%")

    poi_det = details.get("price_oi", {})
    lines.append(f"Price/OI State:        {poi_det.get('state', 'LONG_BUILDUP')} (Price: {poi_det.get('price_change_pct', 0.0):+.2f}%, OI: {poi_det.get('oi_change_pct', 0.0):+.2f}%)")

    opt_det = details.get("options_wall", {})
    lines.append(f"Options Wall Quality:  Confidence: {opt_det.get('confidence', 'HIGH_CONFIDENCE')} | Call Wall: {opt_det.get('call_wall_strike')} | Put Wall: {opt_det.get('put_wall_strike')}")
    lines.append("-" * 80)

    # Eligibility Gates G01 - G24
    lines.append(f"Central Gates:         {result.passed_gates_count} / {result.total_gates_count} Passed")
    for gid in sorted(result.gate_statuses.keys()):
        passed = result.gate_statuses[gid]
        mark = "[PASS]" if passed else "[FAIL]"
        desc = GATE_DESCRIPTIONS.get(gid, "Governed Gate")
        reason = f" ({result.gate_reasons[gid]})" if not passed and result.gate_reasons.get(gid) else ""
        lines.append(f"  {gid} {mark:<6} {desc[:50]:<50}{reason}")

    if result.failed_reason_codes:
        lines.append(f"Failed Reason Codes:   {', '.join(result.failed_reason_codes)}")
    else:
        lines.append("Failed Reason Codes:   NONE (All evaluation gates passed)")
    lines.append("-" * 80)

    # Paper Risk Sizing
    risk = result.paper_risk_estimate
    if risk:
        lines.append(f"Paper Risk Output:     {risk.get('output_type')} (Value: INR {risk.get('paper_position_value', 0.0):,.2f} | {risk.get('paper_position_pct', 0.0)}% of capital)")
        lines.append(f"  Risk Parameters:     Risk/Obs: {risk.get('capital_at_risk')} | Stop: {risk.get('stop_distance_pct')}% | R:R: {risk.get('reward_risk_ratio')}")
    else:
        lines.append("Paper Risk Output:     BLOCKED (Gate rejections or live source exclusion)")
    lines.append("-" * 80)

    # Final Simulation and Governance Statuses
    lines.append(f"Policy Outcome:        {result.overall_simulation_outcome}")
    for k, v in result.governance_statuses.items():
        lines.append(f"  - {k:<22}: {v}")
    lines.append("-" * 80)
    lines.append("DISCLAIMER: OFFLINE SYNTHETIC SIMULATION ONLY. NEVER A TRADE RECOMMENDATION.")
    lines.append("=" * 80)

    return lines
