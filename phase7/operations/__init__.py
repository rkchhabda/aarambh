"""Phase 7 Operations and Production-Readiness Framework.

Internal non-distributed offline hardening modules:
- atomic_io: Durability and atomic filesystem writes
- file_lock: Inter-process file locking and concurrency
- integrity: Checkpoint, manifest, and conservation auditing
- recovery: Fail-closed crash recovery and resume validation
- backup_restore: Offline backup, restore, and bit-level verification
- fault_injection: Controlled lifecycle crash and failure simulation
- security_validation: Hostile input sanitization and boundary defense
- scale_simulation: Synthetic universe and bounded memory tracking
- audit_reconciliation: Structured logging and audit reconciliation
- drill_runner: Governed operational drills (DRILL-01 to DRILL-16)
- readiness_report: 15-domain internal production readiness scorecard
"""

from phase7.operations.atomic_io import (
    AtomicIOError,
    FileOverwriteRefusedError,
    FilenameValidationError,
    StagingPathViolation,
    atomic_write_bytes,
    atomic_write_text,
    cleanup_stale_temporary_files,
    find_repository_root,
    validate_filename,
    validate_safe_staging_path,
)
from phase7.operations.file_lock import (
    DirectoryProcessLock,
    LockAcquisitionError,
    LockError,
    LockTamperingError,
    SingleRequestGate,
    SingleRequestViolationError,
    StaleLockDetectedError,
)
from phase7.operations.integrity import (
    CheckpointIntegrityError,
    ConservationIntegrityError,
    ContractMismatchError,
    IntegrityError,
    IntegrityReport,
    ManifestIntegrityError,
    validate_batch_contract_match,
    validate_checkpoint_integrity,
    validate_manifest_integrity,
    verify_sha256,
)
from phase7.operations.recovery import (
    CorruptedPriorEvidenceError,
    RecoveryError,
    ResumeAuthorizationError,
    ResumeContractMismatchError,
    ResumePlan,
    inspect_run_state,
    validate_resume_prerequisites,
)
from phase7.operations.backup_restore import (
    BackupInventoryError,
    BackupRestoreError,
    RestorationIntegrityError,
    create_offline_backup,
    restore_and_verify_backup,
)
from phase7.operations.fault_injection import (
    FaultController,
    InjectedClientCloseError,
    InjectedDiskFullError,
    InjectedFaultError,
    InjectedPermissionDeniedError,
    armed_fault,
    corrupt_file_checksum,
    get_fault_controller,
)
from phase7.operations.security_validation import (
    HostileInputError,
    MaliciousPayloadError,
    SecurityBoundaryError,
    detect_html_or_captcha_masquerade,
    redact_sensitive_data,
    sanitize_numeric_values,
    validate_json_payload_depth,
    validate_symbol_security,
    validate_url_security,
)
from phase7.operations.scale_simulation import (
    MemoryTracker,
    SyntheticRow,
    compute_series_checksum,
    generate_synthetic_series,
    generate_synthetic_symbols,
)
from phase7.operations.audit_reconciliation import (
    AuditEntry,
    AuditError,
    AuditReconciliationError,
    LogInjectionError,
    StructuredAuditLogger,
    reconcile_audit_trail,
    sanitize_log_message,
)
from phase7.operations.drill_runner import (
    DrillRecord,
    OperationalDrillRunner,
)
from phase7.operations.readiness_report import (
    DomainScore,
    ReadinessScorecard,
)

__all__ = [
    "AtomicIOError",
    "FileOverwriteRefusedError",
    "FilenameValidationError",
    "StagingPathViolation",
    "atomic_write_bytes",
    "atomic_write_text",
    "cleanup_stale_temporary_files",
    "find_repository_root",
    "validate_filename",
    "validate_safe_staging_path",
    "DirectoryProcessLock",
    "LockAcquisitionError",
    "LockError",
    "LockTamperingError",
    "SingleRequestGate",
    "SingleRequestViolationError",
    "StaleLockDetectedError",
    "CheckpointIntegrityError",
    "ConservationIntegrityError",
    "ContractMismatchError",
    "IntegrityError",
    "IntegrityReport",
    "ManifestIntegrityError",
    "validate_batch_contract_match",
    "validate_checkpoint_integrity",
    "validate_manifest_integrity",
    "verify_sha256",
    "CorruptedPriorEvidenceError",
    "RecoveryError",
    "ResumeAuthorizationError",
    "ResumeContractMismatchError",
    "ResumePlan",
    "inspect_run_state",
    "validate_resume_prerequisites",
    "BackupInventoryError",
    "BackupRestoreError",
    "RestorationIntegrityError",
    "create_offline_backup",
    "restore_and_verify_backup",
    "FaultController",
    "InjectedClientCloseError",
    "InjectedDiskFullError",
    "InjectedFaultError",
    "InjectedPermissionDeniedError",
    "armed_fault",
    "corrupt_file_checksum",
    "get_fault_controller",
    "HostileInputError",
    "MaliciousPayloadError",
    "SecurityBoundaryError",
    "detect_html_or_captcha_masquerade",
    "redact_sensitive_data",
    "sanitize_numeric_values",
    "validate_json_payload_depth",
    "validate_symbol_security",
    "validate_url_security",
    "MemoryTracker",
    "SyntheticRow",
    "compute_series_checksum",
    "generate_synthetic_series",
    "generate_synthetic_symbols",
    "AuditEntry",
    "AuditError",
    "AuditReconciliationError",
    "LogInjectionError",
    "StructuredAuditLogger",
    "reconcile_audit_trail",
    "sanitize_log_message",
    "DrillRecord",
    "OperationalDrillRunner",
    "DomainScore",
    "ReadinessScorecard",
]
