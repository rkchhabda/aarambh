"""Phase 7 Data Engine Package.

Provides canonical data contracts, point-in-time universe construction,
deterministic corporate-action adjustments, fail-closed loaders, and data auditing.

Governing Preregistration: docs/PHASE7_RESEARCH_PREREGISTRATION.md
Standard Environment: Python 3.12 (.venv-phase7)
"""

from phase7.data.contracts import (
    CorporateActionRecord,
    CorporateActionResolution,
    CorporateActionType,
    DailyPriceRecord,
    EligibilityStatus,
    EligibilitySuspensionRecord,
    ExclusionReason,
    PITCorporateAnnouncementRecord,
    PITFinancialStatementRecord,
    PITMembershipRecord,
    PITSectorClassificationRecord,
    PITShareholdingRecord,
    PriceAdjustmentState,
    TradedValueStatus,
    compute_row_hash,
)
from phase7.data.corporate_actions import (
    CorporateActionEngine,
    NormalizedCorporateAction,
    adjust_price_series,
)
from phase7.data.universe import (
    PointInTimeUniverseBuilder,
    UniverseBuildResult,
    UniverseBuildStatus,
)
from phase7.data.loaders import (
    BaseDataLoader,
    CSVDataLoader,
    JSONLinesDataLoader,
    LoadResult,
    RejectedRecord,
)
from phase7.data.audit import DatasetAuditReport, audit_dataset_file

__all__ = [
    "CorporateActionRecord",
    "CorporateActionResolution",
    "CorporateActionType",
    "DailyPriceRecord",
    "EligibilityStatus",
    "EligibilitySuspensionRecord",
    "ExclusionReason",
    "PITCorporateAnnouncementRecord",
    "PITFinancialStatementRecord",
    "PITMembershipRecord",
    "PITSectorClassificationRecord",
    "PITShareholdingRecord",
    "PriceAdjustmentState",
    "TradedValueStatus",
    "compute_row_hash",
    "CorporateActionEngine",
    "NormalizedCorporateAction",
    "adjust_price_series",
    "PointInTimeUniverseBuilder",
    "UniverseBuildResult",
    "UniverseBuildStatus",
    "BaseDataLoader",
    "CSVDataLoader",
    "JSONLinesDataLoader",
    "LoadResult",
    "RejectedRecord",
    "DatasetAuditReport",
    "audit_dataset_file",
]
