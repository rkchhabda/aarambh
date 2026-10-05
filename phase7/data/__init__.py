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
    PITMembershipEventRecord,
    PITMembershipRecord,
    PITSectorClassificationRecord,
    PITShareholdingRecord,
    PriceAdjustmentState,
    TradedValueStatus,
    canonicalize_corporate_action_type,
    convert_membership_events_to_intervals,
    compute_row_hash,
    CORPORATE_ACTION_SOURCE_ALIASES,
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
    parse_membership_event_row,
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
    "PITMembershipEventRecord",
    "PITMembershipRecord",
    "PITSectorClassificationRecord",
    "PITShareholdingRecord",
    "PriceAdjustmentState",
    "TradedValueStatus",
    "canonicalize_corporate_action_type",
    "convert_membership_events_to_intervals",
    "compute_row_hash",
    "CORPORATE_ACTION_SOURCE_ALIASES",
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
    "parse_membership_event_row",
    "DatasetAuditReport",
    "audit_dataset_file",
]
