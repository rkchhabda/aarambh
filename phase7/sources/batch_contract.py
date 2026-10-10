"""Phase 7 governed batch contract and exit-code specifications.

Governs parameters, invariants, and exit codes for multi-symbol historical batches.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional


class BatchExitCode(int, Enum):
    SUCCESS = 0
    ARGUMENT_ERROR = 2
    AUTHORIZATION_ERROR = 3
    CLIENT_CONSTRUCTION_ERROR = 4
    RETRIEVAL_ERROR = 5
    SCHEMA_NORMALIZATION_ERROR = 6
    PERSISTENCE_MANIFEST_ERROR = 7
    INCOMPLETE_BATCH = 8
    CLIENT_CLOSE_ERROR = 9
    UNEXPECTED_INTERNAL_ERROR = 10
    INVALID_RESUME_CHECKPOINT = 11
    SOURCE_PANEL_OR_SELECTION_MISMATCH = 12


class BatchSymbolStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    EMPTY = "EMPTY"
    PARTIAL = "PARTIAL"
    HALTED = "HALTED"


class BatchStatus(str, Enum):
    INITIALIZED = "INITIALIZED"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    HALTED = "HALTED"


@dataclass(frozen=True)
class BatchContract:
    batch_id: str
    source_panel_version: str
    source_snapshot_checksum: str
    selection_checksum: str
    symbol_count: int
    ordered_symbols_hash: str
    start_date: str
    end_date: str
    interval: str
    staging_root_hash: str
    schema_mapping_version: str
    maximum_concurrency: int
    minimum_request_spacing_seconds: float
    maximum_retries: int
    failure_threshold: int
    authorization_scope: str
    classification: str
    batch_status: str
    created_timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def compute_contract_hash(self) -> str:
        d = self.to_dict()
        # Exclude batch_status from immutable contract identity
        identity_dict = {k: v for k, v in d.items() if k != "batch_status"}
        serialized = json.dumps(identity_dict, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


REQUIRED_PANEL_VERSION = "CURRENT_NIFTY500_09Oct2026_8F4C439F"
REQUIRED_SNAPSHOT_CHECKSUM = "8f4c439f35fffc8ec87f107ebc9e03aef00ad26301d0912711d808ac592d117d"
REQUIRED_START_DATE = "2024-01-01"
REQUIRED_END_DATE = "2024-03-31"
REQUIRED_INTERVAL = "1d"
REQUIRED_SYMBOL_COUNT = 20
REQUIRED_SCHEMA_MAPPING_VERSION = "NSE_4_0_1_HISTORICAL_CAMELCASE_V1"
REQUIRED_AUTHORIZATION_SCOPE = "TWENTY_STOCK_THREE_MONTH_NSE_BATCH_PILOT"
REQUIRED_CLASSIFICATION = "DETERMINISTIC_CURRENT_PANEL_OPERATIONAL_SAMPLE"


def validate_batch_contract(contract: BatchContract) -> None:
    """Validate a batch contract against immutable governance invariants."""
    if contract.source_panel_version != REQUIRED_PANEL_VERSION:
        raise ValueError(
            f"Invalid source_panel_version: {contract.source_panel_version} != {REQUIRED_PANEL_VERSION}"
        )
    if contract.source_snapshot_checksum != REQUIRED_SNAPSHOT_CHECKSUM:
        raise ValueError(
            f"Invalid source_snapshot_checksum: {contract.source_snapshot_checksum} != {REQUIRED_SNAPSHOT_CHECKSUM}"
        )
    if contract.symbol_count != REQUIRED_SYMBOL_COUNT:
        raise ValueError(
            f"Invalid symbol_count: {contract.symbol_count} != {REQUIRED_SYMBOL_COUNT}"
        )
    if contract.start_date != REQUIRED_START_DATE:
        raise ValueError(
            f"Invalid start_date: {contract.start_date} != {REQUIRED_START_DATE}"
        )
    if contract.end_date != REQUIRED_END_DATE:
        raise ValueError(
            f"Invalid end_date: {contract.end_date} != {REQUIRED_END_DATE}"
        )
    if contract.interval != REQUIRED_INTERVAL:
        raise ValueError(
            f"Invalid interval: {contract.interval} != {REQUIRED_INTERVAL}"
        )
    if contract.maximum_concurrency != 1:
        raise ValueError(
            f"Invalid maximum_concurrency: {contract.maximum_concurrency} != 1"
        )
    if contract.minimum_request_spacing_seconds < 2.0:
        raise ValueError(
            f"Invalid minimum_request_spacing_seconds: {contract.minimum_request_spacing_seconds} < 2.0"
        )
    if contract.maximum_retries != 0:
        raise ValueError(
            f"Invalid maximum_retries: {contract.maximum_retries} != 0"
        )
    if contract.failure_threshold != 1:
        raise ValueError(
            f"Invalid failure_threshold: {contract.failure_threshold} != 1"
        )
    if contract.schema_mapping_version != REQUIRED_SCHEMA_MAPPING_VERSION:
        raise ValueError(
            f"Invalid schema_mapping_version: {contract.schema_mapping_version} != {REQUIRED_SCHEMA_MAPPING_VERSION}"
        )
    if contract.authorization_scope != REQUIRED_AUTHORIZATION_SCOPE:
        raise ValueError(
            f"Invalid authorization_scope: {contract.authorization_scope} != {REQUIRED_AUTHORIZATION_SCOPE}"
        )
    if contract.classification != REQUIRED_CLASSIFICATION:
        raise ValueError(
            f"Invalid classification: {contract.classification} != {REQUIRED_CLASSIFICATION}"
        )
