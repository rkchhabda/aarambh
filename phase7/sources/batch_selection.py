"""Phase 7 deterministic 20-symbol selection and freeze engine.

Selects 20 operational symbols deterministically from the frozen NIFTY 500 snapshot.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

EXCLUDED_FIVE_PILOT_SYMBOLS: Tuple[str, ...] = (
    "RELIANCE",
    "TCS",
    "HDFCBANK",
    "INFY",
    "ICICIBANK",
)

SELECTION_SEED_STRING = "MILESTONE_4_10B"
SELECTION_ALGORITHM = "SHA256(panel_version|symbol|seed_string)_ASC_EXCLUDE_5"
SELECTION_CLASSIFICATION = "DETERMINISTIC_CURRENT_PANEL_OPERATIONAL_SAMPLE"


@dataclass(frozen=True)
class SelectionResult:
    source_panel_version: str
    source_snapshot_checksum: str
    source_constituent_count: int
    exclusion_list: List[str]
    selection_algorithm: str
    selection_seed_string: str
    selected_symbol_count: int
    ordered_selected_symbols: List[str]
    ordered_symbols_hash: str
    selection_checksum: str
    creation_timestamp: str
    classification: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def calculate_ordered_symbols_hash(symbols: List[str]) -> str:
    """Calculate hash of ordered symbol sequence."""
    payload = "\n".join(symbols).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def perform_deterministic_selection(
    snapshot_path: Path,
    expected_checksum: str = "8f4c439f35fffc8ec87f107ebc9e03aef00ad26301d0912711d808ac592d117d",
    panel_version: str = "CURRENT_NIFTY500_09Oct2026_8F4C439F",
    target_count: int = 20,
    excluded_symbols: Tuple[str, ...] = EXCLUDED_FIVE_PILOT_SYMBOLS,
    seed_suffix: str = SELECTION_SEED_STRING,
) -> SelectionResult:
    """Perform deterministic 20-symbol selection from frozen snapshot."""
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Snapshot file not found: {snapshot_path}")

    raw_bytes = snapshot_path.read_bytes()
    computed_hash = hashlib.sha256(raw_bytes).hexdigest()
    if computed_hash != expected_checksum:
        raise ValueError(
            f"Snapshot checksum mismatch: {computed_hash} != {expected_checksum}"
        )

    lines = [line.strip() for line in raw_bytes.decode("utf-8").splitlines() if line.strip()]
    if not lines:
        raise ValueError("Snapshot file is empty")

    rows = [json.loads(line) for line in lines]
    symbols = sorted(list(set(r["symbol"] for r in rows if "symbol" in r and r["symbol"])))
    if len(symbols) != 500:
        raise ValueError(f"Expected exactly 500 unique symbols, found {len(symbols)}")

    # Deterministic scoring: SHA256(panel_version|symbol|seed_suffix)
    scored: List[Tuple[str, str]] = []
    for sym in symbols:
        seed = f"{panel_version}|{sym}|{seed_suffix}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        scored.append((digest, sym))

    # Sort ascending by SHA-256 digest, breaking ties by ASCII symbol
    scored.sort(key=lambda x: (x[0], x[1]))

    excluded_set: Set[str] = set(excluded_symbols)
    filtered = [sym for digest, sym in scored if sym not in excluded_set]

    if len(filtered) < target_count:
        raise ValueError(
            f"Insufficient candidate symbols remaining after exclusion: {len(filtered)} < {target_count}"
        )

    selected = filtered[:target_count]
    selection_checksum = calculate_ordered_symbols_hash(selected)
    ordered_symbols_hash = hashlib.sha256(",".join(selected).encode("utf-8")).hexdigest()
    creation_ts = datetime.now(timezone.utc).isoformat()

    return SelectionResult(
        source_panel_version=panel_version,
        source_snapshot_checksum=computed_hash,
        source_constituent_count=len(symbols),
        exclusion_list=list(excluded_symbols),
        selection_algorithm=SELECTION_ALGORITHM,
        selection_seed_string=seed_suffix,
        selected_symbol_count=len(selected),
        ordered_selected_symbols=selected,
        ordered_symbols_hash=ordered_symbols_hash,
        selection_checksum=selection_checksum,
        creation_timestamp=creation_ts,
        classification=SELECTION_CLASSIFICATION,
    )


def save_selection_evidence(
    result: SelectionResult,
    selection_dir: Path,
) -> Dict[str, Path]:
    """Persist selection evidence files outside Git in external staging root."""
    selection_dir.mkdir(parents=True, exist_ok=True)

    selected_symbols_file = selection_dir / "selected_symbols.json"
    manifest_file = selection_dir / "selection_manifest.json"
    audit_file = selection_dir / "selection_audit.json"

    # 1. selected_symbols.json
    symbols_payload = {
        "classification": result.classification,
        "panel_version": result.source_panel_version,
        "selection_checksum": result.selection_checksum,
        "count": result.selected_symbol_count,
        "symbols": result.ordered_selected_symbols,
    }
    selected_symbols_file.write_text(json.dumps(symbols_payload, indent=2), encoding="utf-8")

    # 2. selection_manifest.json
    manifest_payload = result.to_dict()
    manifest_file.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")

    # 3. selection_audit.json
    audit_payload = {
        "audit_version": "1.0",
        "timestamp": result.creation_timestamp,
        "classification": result.classification,
        "source_panel_version": result.source_panel_version,
        "source_snapshot_checksum": result.source_snapshot_checksum,
        "source_symbols_count": result.source_constituent_count,
        "excluded_symbols": result.exclusion_list,
        "excluded_count": len(result.exclusion_list),
        "selected_count": result.selected_symbol_count,
        "selection_checksum": result.selection_checksum,
        "ordered_symbols_hash": result.ordered_symbols_hash,
        "algorithm": result.selection_algorithm,
        "seed_string": result.selection_seed_string,
        "file_paths": {
            "selected_symbols": str(selected_symbols_file.resolve()),
            "selection_manifest": str(manifest_file.resolve()),
            "selection_audit": str(audit_file.resolve()),
        },
    }
    audit_file.write_text(json.dumps(audit_payload, indent=2), encoding="utf-8")

    return {
        "selected_symbols": selected_symbols_file,
        "manifest": manifest_file,
        "audit": audit_file,
    }


def load_selection_manifest(selection_dir: Path) -> SelectionResult:
    """Load and parse selection manifest from external directory."""
    manifest_file = selection_dir / "selection_manifest.json"
    if not manifest_file.exists():
        raise FileNotFoundError(f"Selection manifest not found: {manifest_file}")

    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    return SelectionResult(
        source_panel_version=data["source_panel_version"],
        source_snapshot_checksum=data["source_snapshot_checksum"],
        source_constituent_count=data["source_constituent_count"],
        exclusion_list=data["exclusion_list"],
        selection_algorithm=data["selection_algorithm"],
        selection_seed_string=data["selection_seed_string"],
        selected_symbol_count=data["selected_symbol_count"],
        ordered_selected_symbols=data["ordered_selected_symbols"],
        ordered_symbols_hash=data["ordered_symbols_hash"],
        selection_checksum=data["selection_checksum"],
        creation_timestamp=data["creation_timestamp"],
        classification=data["classification"],
    )
