"""Phase 7 isolated data sources package.

Exposes contracts, protocols, fail-closed adapters, manifests, and pilot guards.
Zero top-level imports of third-party NSE packages.
"""

from phase7.sources.audit import StructuralQualityAudit
from phase7.sources.client_factory import create_real_nse_client
from phase7.sources.client_protocol import NSEClientProtocol
from phase7.sources.contracts import (
    AdjustmentState,
    ConstituentClassification,
    ConstituentRecord,
    CorporateActionRecord,
    FieldStatus,
    HistoricalEODRecord,
    RejectedRowRecord,
    RejectedSymbolRecord,
    RequestManifest,
    RequestStatus,
)
from phase7.sources.manifest import build_manifest, write_manifest
from phase7.sources.normalization import normalize_historical_row
from phase7.sources.nse_adapter import HistoricalFetchResult, NSEDataSourceAdapter
from phase7.sources.pilot_guard import (
    DEVELOPMENT_CUTOFF_DATE,
    PILOT_ALLOWED_SYMBOLS,
    PILOT_END_DATE,
    PILOT_START_DATE,
    PilotGuard,
    validate_date_range,
    validate_staging_path,
    validate_symbol,
)
from phase7.sources.rejections import RejectionLedger

__all__ = [
    "AdjustmentState",
    "ConstituentClassification",
    "ConstituentRecord",
    "CorporateActionRecord",
    "FieldStatus",
    "HistoricalEODRecord",
    "HistoricalFetchResult",
    "NSEClientProtocol",
    "NSEDataSourceAdapter",
    "PilotGuard",
    "PILOT_ALLOWED_SYMBOLS",
    "PILOT_START_DATE",
    "PILOT_END_DATE",
    "DEVELOPMENT_CUTOFF_DATE",
    "RejectionLedger",
    "RejectedRowRecord",
    "RejectedSymbolRecord",
    "RequestManifest",
    "RequestStatus",
    "StructuralQualityAudit",
    "build_manifest",
    "create_real_nse_client",
    "normalize_historical_row",
    "validate_date_range",
    "validate_staging_path",
    "validate_symbol",
    "write_manifest",
]
