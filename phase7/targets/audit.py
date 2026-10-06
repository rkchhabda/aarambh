"""Target dataset auditing and quality reporting for Phase 7.

Computes deterministic TargetAuditRecord capturing:
1. Input and accepted/rejected/blocked target counts.
2. Specific failure reason aggregations.
3. Overlapping forward label detection.
4. Strict prohibition of investment performance / alpha metrics in audit reports.
"""

from collections import defaultdict
from typing import Sequence

from phase7.targets.contracts import (
    TargetAuditRecord,
    TargetReasonCode,
    TargetResultRecord,
    TargetSpecificationRecord,
    TargetStatus,
)


def audit_target_results(
    specification: TargetSpecificationRecord,
    results: Sequence[TargetResultRecord],
    input_record_count: int,
    dataset_version: str = "1.0.0",
) -> TargetAuditRecord:
    """Generate deterministic quality audit report for computed target results.

    Args:
        specification: TargetSpecificationRecord defining target parameters.
        results: Sequence of TargetResultRecord instances to audit.
        input_record_count: Total count of candidate prediction events evaluated.
        dataset_version: Version identifier of underlying dataset.

    Returns:
        TargetAuditRecord containing counts and provenance metadata.
    """
    accepted = 0
    rejected = 0
    blocked = 0

    future_data = 0
    missing_entry = 0
    missing_exit = 0
    adjustment_failures = 0
    suspensions = 0
    delistings = 0
    invalid_betas = 0

    # Overlapping forward window tracking per symbol
    intervals_by_sym = defaultdict(list)

    for r in results:
        if r.target_status == TargetStatus.VALID:
            accepted += 1
            if r.entry_date and r.exit_date:
                intervals_by_sym[r.symbol].append((r.entry_date, r.exit_date))
        elif r.target_status == TargetStatus.BLOCKED:
            blocked += 1
        else:
            rejected += 1

        for code in r.invalid_reason_codes:
            if code in (TargetReasonCode.FUTURE_DATA_DETECTED, TargetReasonCode.FUTURE_BETA_DETECTED, TargetReasonCode.FUTURE_SECTOR_DETECTED):
                future_data += 1
            elif code == TargetReasonCode.MISSING_ENTRY_PRICE:
                missing_entry += 1
            elif code in (TargetReasonCode.MISSING_EXIT_PRICE, TargetReasonCode.INSUFFICIENT_FORWARD_OBSERVATIONS):
                missing_exit += 1
            elif code == TargetReasonCode.INVALID_ADJUSTMENT_STATE:
                adjustment_failures += 1
            elif code == TargetReasonCode.SUSPENDED_DURING_HORIZON:
                suspensions += 1
            elif code == TargetReasonCode.DELISTED_DURING_HORIZON:
                delistings += 1
            elif code in (TargetReasonCode.INVALID_BETA, TargetReasonCode.FUTURE_BETA_DETECTED):
                invalid_betas += 1

    # Count overlapping intervals per symbol
    overlapping_count = 0
    for sym, intervals in intervals_by_sym.items():
        sorted_intervals = sorted(intervals, key=lambda x: x[0])
        for i in range(len(sorted_intervals) - 1):
            curr_entry, curr_exit = sorted_intervals[i]
            next_entry, next_exit = sorted_intervals[i + 1]
            if next_entry <= curr_exit:
                overlapping_count += 1

    return TargetAuditRecord(
        input_record_count=input_record_count,
        accepted_target_count=accepted,
        rejected_target_count=rejected,
        blocked_target_count=blocked,
        future_data_count=future_data,
        missing_entry_count=missing_entry,
        missing_exit_count=missing_exit,
        adjustment_state_failure_count=adjustment_failures,
        suspension_count=suspensions,
        delisting_count=delistings,
        invalid_beta_count=invalid_betas,
        overlapping_label_count=overlapping_count,
        target_specification_hash=specification.specification_hash,
        dataset_version=dataset_version,
    )
