"""Governed Source Provenance Contract [Milestone 4.14].

Provides cryptographic provenance contracts for synthetic and governed recorded
fixtures, guaranteeing lineage, source mode integrity, and hash conservation.
"""

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Dict, Optional, Tuple

from phase7.paper_policy.constants import SourceMode
from phase7.paper_policy.reason_codes import PolicyReasonCode
from phase7.paper_policy.source_mode import validate_source_mode


@dataclass(frozen=True)
class SourceProvenanceContract:
    """Cryptographic provenance record for offline evaluation fixtures."""
    source_identifier: str
    source_mode: str
    record_hash: str
    generation_timestamp_utc: str
    dataset_label: str
    governance_lock: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


def compute_payload_sha256(payload: Dict[str, Any]) -> str:
    """Compute canonical SHA-256 hash of a payload dictionary excluding provenance metadata."""
    filtered = {k: v for k, v in payload.items() if k not in ("provenance", "record_hash")}
    canonical_json = json.dumps(filtered, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def create_provenance_contract(
    source_identifier: str,
    source_mode: str,
    payload: Dict[str, Any],
    generation_timestamp_utc: str,
    dataset_label: str,
) -> SourceProvenanceContract:
    """Construct an immutable provenance contract for an offline evaluation payload."""
    valid_mode, reason, _ = validate_source_mode(source_mode)
    if not valid_mode:
        raise ValueError(f"Cannot create provenance contract for invalid/blocked source mode: {reason}")

    record_hash = compute_payload_sha256(payload)
    return SourceProvenanceContract(
        source_identifier=source_identifier,
        source_mode=source_mode,
        record_hash=record_hash,
        generation_timestamp_utc=generation_timestamp_utc,
        dataset_label=dataset_label,
        governance_lock=True,
    )


def verify_provenance_contract(
    contract: SourceProvenanceContract,
    payload: Dict[str, Any],
) -> Tuple[bool, Optional[str]]:
    """Verify cryptographic provenance and hash integrity of an evaluation payload.

    Returns:
        (is_valid, reason_code)
    """
    if not contract.source_identifier or not contract.dataset_label:
        return False, PolicyReasonCode.PROVENANCE_INVALID_NO_DECISION.value

    # Source mode check
    valid_mode, reason, _ = validate_source_mode(contract.source_mode)
    if not valid_mode:
        return False, reason

    # Hash conservation check
    expected_hash = compute_payload_sha256(payload)
    if contract.record_hash != expected_hash:
        return False, PolicyReasonCode.PROVENANCE_INVALID_NO_DECISION.value

    return True, None
