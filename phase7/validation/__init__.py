"""Phase 7 Walk-Forward Validation Framework.

Provides expanding walk-forward partitioning, purge and embargo interval enforcement,
fold-local preprocessing transformations, and deterministic validation auditing.
"""

from phase7.validation.contracts import (
    InsufficientDataForWalkForwardError,
    InvalidPurgeEmbargoConfigError,
    PreprocessingLeakageError,
    PreprocessingNotFittedError,
    PreprocessingParameterRecord,
    PurgeEmbargoInterval,
    ValidationAuditRecord,
    ValidationLeakageError,
    ValidationStatus,
    WalkForwardConfig,
    WalkForwardFold,
)
from phase7.validation.preprocessing import (
    BaseFoldLocalTransformer,
    CrossSectionalRanker,
    FoldLocalImputer,
    FoldLocalPipeline,
    FoldLocalRobustScaler,
    FoldLocalStandardScaler,
    FoldLocalWinsorizer,
)
from phase7.validation.purge_embargo import (
    build_purge_embargo_interval,
    compute_embargo_interval,
    compute_purge_interval,
    validate_purge_embargo_days,
    verify_zero_label_leakage,
)
from phase7.validation.walk_forward import (
    ExpandingWalkForwardSplitter,
)

__all__ = [
    "BaseFoldLocalTransformer",
    "CrossSectionalRanker",
    "ExpandingWalkForwardSplitter",
    "FoldLocalImputer",
    "FoldLocalPipeline",
    "FoldLocalRobustScaler",
    "FoldLocalStandardScaler",
    "FoldLocalWinsorizer",
    "InsufficientDataForWalkForwardError",
    "InvalidPurgeEmbargoConfigError",
    "PreprocessingLeakageError",
    "PreprocessingNotFittedError",
    "PreprocessingParameterRecord",
    "PurgeEmbargoInterval",
    "ValidationAuditRecord",
    "ValidationLeakageError",
    "ValidationStatus",
    "WalkForwardConfig",
    "WalkForwardFold",
    "build_purge_embargo_interval",
    "compute_embargo_interval",
    "compute_purge_interval",
    "validate_purge_embargo_days",
    "verify_zero_label_leakage",
]
