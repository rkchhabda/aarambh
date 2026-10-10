"""Phase 7 isolated data sources package.

Exposes contracts, protocols, fail-closed adapters, manifests, and pilot guards.
Zero top-level imports of third-party NSE packages.
"""

from phase7.sources.audit import StructuralQualityAudit
from phase7.sources.client_factory import create_real_nse_client
from phase7.sources.client_protocol import NSEClientFactoryProtocol, NSEClientProtocol
from phase7.sources.contracts import (
    AdjustmentState,
    CapabilityStatus,
    ConstituentClassification,
    ConstituentRecord,
    CorporateActionRecord,
    FieldStatus,
    HistoricalEODRecord,
    NSEDataFetcherProtocol,
    PilotAuthorizationRecord,
    PilotExitCode,
    PilotOutcome,
    PilotStopReason,
    RejectedRowRecord,
    RejectedSymbolRecord,
    RequestManifest,
    RequestStatus,
    SessionBootstrapAudit,
)
from phase7.sources.http_client import (
    HTTPSafetyError,
    HTTPSafetyViolationType,
    inspect_payload_safety,
)
from phase7.sources.manifest import (
    build_manifest,
    build_pending_manifest,
    check_audit_conservation,
    write_manifest,
)
from phase7.sources.normalization import normalize_historical_row
from phase7.sources.nse_adapter import HistoricalFetchResult, NSEDataSourceAdapter
from phase7.sources.nse_constituents import get_nifty500_constituents
from phase7.sources.nse_corporate_actions import get_corporate_actions
from phase7.sources.nse_data_fetcher_adapter import NSEDataFetcherAdapter
from phase7.sources.nse_eod import fetch_symbol_eod_history
from phase7.sources.persistence import (
    persist_normalized_records,
    persist_raw_payload,
    persist_request_manifest,
)
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
    "NSEClientFactoryProtocol",
    "NSEClientProtocol",
    "NSEDataFetcherAdapter",
    "NSEDataFetcherProtocol",
    "NSEDataSourceAdapter",
    "PilotAuthorizationRecord",
    "PilotExitCode",
    "PilotGuard",
    "PilotOutcome",
    "PilotStopReason",
    "PILOT_ALLOWED_SYMBOLS",
    "PILOT_APPROVED_SYMBOLS",
    "PILOT_START_DATE",
    "PILOT_END_DATE",
    "PILOT_INTERVAL",
    "PILOT_MILESTONE",
    "PILOT_SCOPE",
    "ACTIVE_MARKER_FILENAME",
    "compute_authorization_hash",
    "compute_staging_root_hash",
    "consume_authorization",
    "create_pilot_authorization",
    "load_and_validate_authorization",
    "validate_authorization_marker_path",
    "DEVELOPMENT_CUTOFF_DATE",
    "RejectionLedger",
    "RejectedRowRecord",
    "RejectedSymbolRecord",
    "RequestManifest",
    "RequestStatus",
    "SessionBootstrapAudit",
    "StructuralQualityAudit",
    "build_manifest",
    "build_pending_manifest",
    "check_audit_conservation",
    "create_real_nse_client",
    "fetch_symbol_eod_history",
    "get_corporate_actions",
    "get_nifty500_constituents",
    "inspect_payload_safety",
    "normalize_historical_row",
    "persist_normalized_records",
    "persist_raw_payload",
    "persist_request_manifest",
    "validate_date_range",
    "validate_staging_path",
    "validate_staging_root",
    "validate_symbol",
    "write_manifest",
]


def __getattr__(name: str):
    """Lazy-load authorization functions and constants to prevent CLI runner warnings."""
    _auth_attrs = {
        "ACTIVE_MARKER_FILENAME",
        "PILOT_APPROVED_SYMBOLS",
        "PILOT_INTERVAL",
        "PILOT_MILESTONE",
        "PILOT_SCOPE",
        "compute_authorization_hash",
        "compute_staging_root_hash",
        "consume_authorization",
        "create_pilot_authorization",
        "load_and_validate_authorization",
        "validate_authorization_marker_path",
        "validate_staging_root",
    }
    if name in _auth_attrs:
        import phase7.sources.authorization as auth_mod
        return getattr(auth_mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
