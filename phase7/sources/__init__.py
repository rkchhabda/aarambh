"""Phase 7 isolated data sources package.

Exposes contracts, protocols, fail-closed adapters, manifests, and pilot guards.
Zero top-level imports of third-party NSE packages.
"""

from phase7.sources.audit import StructuralQualityAudit
from phase7.sources.client_factory import create_real_nse_client
from phase7.sources.client_protocol import NSEClientProtocol
from phase7.sources.contracts import (
    AdjustmentState,
    CapabilityStatus,
    ConstituentClassification,
    ConstituentRecord,
    CorporateActionRecord,
    FieldStatus,
    HistoricalEODRecord,
    NSEDataFetcherProtocol,
    RejectedRowRecord,
    RejectedSymbolRecord,
    RequestManifest,
    RequestStatus,
)
from phase7.sources.http_client import (
    HTTPSafetyError,
    HTTPSafetyViolationType,
    inspect_payload_safety,
)
from phase7.sources.manifest import build_manifest, write_manifest
from phase7.sources.normalization import normalize_historical_row
from phase7.sources.nse_adapter import HistoricalFetchResult, NSEDataSourceAdapter
from phase7.sources.nse_constituents import get_nifty500_constituents
from phase7.sources.nse_corporate_actions import get_corporate_actions
from phase7.sources.nse_data_fetcher_adapter import NSEDataFetcherAdapter
from phase7.sources.nse_eod import fetch_symbol_eod_history
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
    "CapabilityStatus",
    "ConstituentClassification",
    "ConstituentRecord",
    "CorporateActionRecord",
    "FieldStatus",
    "HistoricalEODRecord",
    "HistoricalFetchResult",
    "HTTPSafetyError",
    "HTTPSafetyViolationType",
    "NSEClientProtocol",
    "NSEDataFetcherAdapter",
    "NSEDataFetcherProtocol",
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
    "fetch_symbol_eod_history",
    "get_corporate_actions",
    "get_nifty500_constituents",
    "inspect_payload_safety",
    "normalize_historical_row",
    "validate_date_range",
    "validate_staging_path",
    "validate_symbol",
    "write_manifest",
]
