"""Data audit and provenance verification utility for Phase 7 datasets.

Audits file integrity, timing bounds, field completeness, duplicate counts,
and turnover derivation provenance.

STRICT GOVERNANCE PROHIBITION:
This module produces metadata and data quality metrics ONLY.
It must never calculate or report returns, stock ranks, picks, backtest statistics,
Rank IC, Sharpe, Drawdown, Alpha, or portfolio performance.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from phase7.data.loaders import BaseDataLoader, LoadResult


@dataclass(frozen=True)
class DatasetAuditReport:
    """Provenance and data-quality audit report for a research dataset file."""
    source_identifier: str
    local_input_path: str
    file_checksum_sha256: str
    file_size_bytes: int
    total_row_count: int
    accepted_row_count: int
    rejected_row_count: int
    first_data_date: Optional[str]
    last_data_date: Optional[str]
    symbol_count: int
    isin_count: int
    duplicate_count: int
    missing_field_counts: Dict[str, int]
    traded_value_status_counts: Dict[str, int]
    unknown_adjustment_state_count: int
    validation_status: str
    blockers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize audit report to plain dictionary."""
        return {
            "source_identifier": self.source_identifier,
            "local_input_path": self.local_input_path,
            "file_checksum_sha256": self.file_checksum_sha256,
            "file_size_bytes": self.file_size_bytes,
            "total_row_count": self.total_row_count,
            "accepted_row_count": self.accepted_row_count,
            "rejected_row_count": self.rejected_row_count,
            "first_data_date": self.first_data_date,
            "last_data_date": self.last_data_date,
            "symbol_count": self.symbol_count,
            "isin_count": self.isin_count,
            "duplicate_count": self.duplicate_count,
            "missing_field_counts": self.missing_field_counts,
            "traded_value_status_counts": self.traded_value_status_counts,
            "unknown_adjustment_state_count": self.unknown_adjustment_state_count,
            "validation_status": self.validation_status,
            "blockers": self.blockers,
            "warnings": self.warnings,
        }


def audit_dataset_file(file_path: Path, loader: BaseDataLoader) -> DatasetAuditReport:
    """Audit a local dataset file using a fail-closed loader.

    Args:
        file_path: Local path to the tabular data file.
        loader: Configured fail-closed data loader instance.

    Returns:
        DatasetAuditReport containing provenance checksums and quality counts.
    """
    if not file_path.is_file():
        raise FileNotFoundError(f"File to audit not found: {file_path}")

    raw_bytes = file_path.read_bytes()
    checksum = hashlib.sha256(raw_bytes).hexdigest()
    file_size = len(raw_bytes)

    load_res: LoadResult = loader.load(file_path)

    # Missing field counts across rejected records
    missing_fields: Dict[str, int] = {}
    for rej in load_res.rejected_records:
        for r in rej.reasons:
            if "missing" in r.lower():
                missing_fields[r] = missing_fields.get(r, 0) + 1

    # Count traded value status and adjustment states in accepted price records
    tv_counts: Dict[str, int] = {}
    unknown_adj_count = 0
    for rec in load_res.accepted_records:
        if hasattr(rec, "traded_value_status"):
            st = rec.traded_value_status.value
            tv_counts[st] = tv_counts.get(st, 0) + 1
        if hasattr(rec, "price_adjustment_state"):
            if rec.price_adjustment_state.value == "UNKNOWN":
                unknown_adj_count += 1

    first_date_str = load_res.date_range[0].isoformat() if load_res.date_range else None
    last_date_str = load_res.date_range[1].isoformat() if load_res.date_range else None

    val_status = "VALID"
    blockers = list(load_res.blockers)
    warnings = list(load_res.warnings)

    if load_res.rejected_count > 0:
        val_status = "PARTIAL" if load_res.accepted_count > 0 else "INVALID"
        warnings.append(f"{load_res.rejected_count} rows failed contract validation.")

    return DatasetAuditReport(
        source_identifier=file_path.name,
        local_input_path=str(file_path),
        file_checksum_sha256=checksum,
        file_size_bytes=file_size,
        total_row_count=load_res.total_rows,
        accepted_row_count=load_res.accepted_count,
        rejected_row_count=load_res.rejected_count,
        first_data_date=first_date_str,
        last_data_date=last_date_str,
        symbol_count=load_res.symbol_count,
        isin_count=load_res.isin_count,
        duplicate_count=load_res.duplicate_count,
        missing_field_counts=missing_fields,
        traded_value_status_counts=tv_counts,
        unknown_adjustment_state_count=unknown_adj_count,
        validation_status=val_status,
        blockers=blockers,
        warnings=warnings,
    )
