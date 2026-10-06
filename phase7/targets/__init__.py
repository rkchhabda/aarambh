"""Phase 7 Target Engine Package.

Provides canonical target contracts, T+1 alignment, discrete return calculations,
20-day sector-relative targets, 60-day beta-adjusted residual targets, and quality audits.
"""

from phase7.targets.alignment import (
    TargetAlignmentResult,
    align_forward_observations,
)
from phase7.targets.audit import (
    audit_target_results,
)
from phase7.targets.contracts import (
    BetaInputRecord,
    ForwardPriceObservationRecord,
    PredictionEventRecord,
    SectorBenchmarkObservationRecord,
    TargetAuditRecord,
    TargetReasonCode,
    TargetResultRecord,
    TargetSpecificationRecord,
    TargetStatus,
)
from phase7.targets.residual import (
    calculate_60d_residual_target,
    validate_beta_record,
)
from phase7.targets.returns import (
    calculate_discrete_return,
    validate_adjustment_compatibility,
)
from phase7.targets.sector_relative import (
    calculate_20d_sector_relative_target,
    resolve_pit_sector_classification,
)

__all__ = [
    "BetaInputRecord",
    "ForwardPriceObservationRecord",
    "PredictionEventRecord",
    "SectorBenchmarkObservationRecord",
    "TargetAlignmentResult",
    "TargetAuditRecord",
    "TargetReasonCode",
    "TargetResultRecord",
    "TargetSpecificationRecord",
    "TargetStatus",
    "align_forward_observations",
    "audit_target_results",
    "calculate_20d_sector_relative_target",
    "calculate_60d_residual_target",
    "calculate_discrete_return",
    "resolve_pit_sector_classification",
    "validate_adjustment_compatibility",
    "validate_beta_record",
]
