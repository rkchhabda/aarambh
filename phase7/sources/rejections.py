"""Rejection ledgers for auditing malformed symbols and invalid row payloads."""

import json
from pathlib import Path
from typing import Any, Dict, List

from phase7.sources.contracts import RejectedRowRecord, RejectedSymbolRecord


class RejectionLedger:
    """Manages immutable logs of rejected requests and invalid rows."""

    def __init__(self, ledger_dir: Path):
        self.ledger_dir = Path(ledger_dir)
        self.rejected_symbols: List[RejectedSymbolRecord] = []
        self.rejected_rows: List[RejectedRowRecord] = []

    def record_rejected_symbol(
        self,
        symbol: str,
        reason: str,
        timestamp: str,
        requested_range: str = "",
    ) -> RejectedSymbolRecord:
        record = RejectedSymbolRecord(
            symbol=symbol,
            reason=reason,
            timestamp=timestamp,
            requested_range=requested_range,
        )
        self.rejected_symbols.append(record)
        return record

    def record_symbol_rejection(self, record: RejectedSymbolRecord) -> None:
        self.rejected_symbols.append(record)

    def record_rejected_row(
        self,
        symbol: str,
        raw_payload: Dict[str, Any],
        reason: str,
        timestamp: str,
    ) -> RejectedRowRecord:
        record = RejectedRowRecord(
            symbol=symbol,
            raw_payload=raw_payload,
            reason=reason,
            timestamp=timestamp,
        )
        self.rejected_rows.append(record)
        return record

    def record_row_rejection(self, record: RejectedRowRecord) -> None:
        self.rejected_rows.append(record)

    def persist(self) -> Dict[str, Path]:
        """Write rejected symbol and row ledgers to disk."""
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        paths = {}

        if self.rejected_symbols:
            sym_path = self.ledger_dir / "rejected_symbols.json"
            data = [
                {
                    "symbol": r.symbol,
                    "reason": r.reason,
                    "timestamp": r.timestamp,
                    "requested_range": r.requested_range,
                }
                for r in self.rejected_symbols
            ]
            with sym_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            paths["symbols"] = sym_path

        if self.rejected_rows:
            row_path = self.ledger_dir / "rejected_rows.json"
            data = [
                {
                    "symbol": r.symbol,
                    "raw_payload": r.raw_payload,
                    "reason": r.reason,
                    "timestamp": r.timestamp,
                }
                for r in self.rejected_rows
            ]
            with row_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            paths["rows"] = row_path

        return paths
