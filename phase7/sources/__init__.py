"""Phase 7 isolated data sources package.

Exposes contracts, protocols, fail-closed adapters, manifests, and pilot guards.
Zero top-level imports of third-party NSE packages.
"""

from phase7.sources.audit import StructuralQualityAudit
from phase7.sources.batch_audit import (
    BatchAuditSummary,
    generate_batch_audit_payload,
    save_batch_audit,
    verify_batch_conservation,
)
from phase7.sources.batch_authorization import (
    BatchAuthorizationRecord,
    consume_batch_authorization_marker,
    create_batch_authorization_marker,
    validate_batch_authorization,
)
from phase7.sources.batch_checkpoint import (
    BatchCheckpoint,
    BatchSymbolStatus,
    InvalidResumeCheckpointError,
    SymbolCheckpoint,
    create_initial_batch_checkpoint,
    load_checkpoint,
    save_checkpoint,
    validate_resume_checkpoint,
)
from phase7.sources.batch_contract import (
    BatchContract,
    BatchExitCode,
    BatchStatus,
    validate_batch_contract,
)
from phase7.sources.batch_pilot import run_batch_pilot
from phase7.sources.batch_selection import (
    SelectionResult,
    load_selection_manifest,
    perform_deterministic_selection,
    save_selection_evidence,
)
from phase7.sources.client_factory import create_real_nse_client
from phase7.sources.client_protocol import NSEClientFactoryProtocol, NSEClientProtocol
from phase7.sources.contracts import (
    AdjustmentState,
    CapabilityStatus,
    ConstituentClassification,
    ConstituentRecord,
    ConstituentSnapshotManifest,
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
    SnapshotAuthorizationRecord,
    SnapshotPilotExitCode,
    SnapshotPilotOutcome,
)
from phase7.sources.constituent_authorization import (
    consume_snapshot_authorization,
    create_snapshot_authorization,
    load_and_validate_snapshot_authorization,
)
from phase7.sources.constituent_persistence import (
    save_normalized_snapshot,
    save_raw_snapshot,
    save_snapshot_manifest,
)
from phase7.sources.constituent_pilot import run_snapshot_pilot
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
from phase7.sources.nse_constituents import (
    fetch_current_index_constituents,
    get_nifty500_constituents,
    validate_index_name,
)
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
from phase7.sources.schema_mappings import (
    NSE_4_0_1_SCHEMA_VERSION,
    detect_payload_schema_version,
    parse_nse_d_b_y,
)

__all__ = [
    "AdjustmentState",
    "CapabilityStatus",
    "ConstituentClassification",
    "ConstituentRecord",
    "ConstituentSnapshotManifest",
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
    "NSE_4_0_1_SCHEMA_VERSION",
    "detect_payload_schema_version",
    "parse_nse_d_b_y",
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
    "SnapshotAuthorizationRecord",
    "SnapshotPilotExitCode",
    "SnapshotPilotOutcome",
    "consume_snapshot_authorization",
    "create_snapshot_authorization",
    "load_and_validate_snapshot_authorization",
    "save_normalized_snapshot",
    "save_raw_snapshot",
    "save_snapshot_manifest",
    "run_snapshot_pilot",
    "fetch_current_index_constituents",
    "validate_index_name",
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
    "BatchContract",
    "BatchExitCode",
    "BatchStatus",
    "BatchSymbolStatus",
    "validate_batch_contract",
    "SelectionResult",
    "perform_deterministic_selection",
    "save_selection_evidence",
    "load_selection_manifest",
    "BatchAuthorizationRecord",
    "create_batch_authorization_marker",
    "validate_batch_authorization",
    "consume_batch_authorization_marker",
    "BatchCheckpoint",
    "SymbolCheckpoint",
    "create_initial_batch_checkpoint",
    "save_checkpoint",
    "load_checkpoint",
    "validate_resume_checkpoint",
    "InvalidResumeCheckpointError",
    "BatchAuditSummary",
    "verify_batch_conservation",
    "generate_batch_audit_payload",
    "save_batch_audit",
    "run_batch_pilot",
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
