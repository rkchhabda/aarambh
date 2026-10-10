"""Structural quality audit calculations for acquired source records.

Computes coverage, schema validity, and gap metrics without calculating returns or performance.
"""

from typing import Any, Dict, List, Set
from phase7.sources.contracts import HistoricalEODRecord


class StructuralQualityAudit:
    """Calculates structural metrics on normalized historical panels."""

    def __init__(self, records: List[HistoricalEODRecord]):
        self.records = records

    def run_audit(self) -> Dict[str, Any]:
        total_rows = len(self.records)
        symbols: Set[str] = set()
        dates: Set[str] = set()
        natural_keys: Set[tuple] = set()
        duplicate_keys = 0
        missing_turnover = 0
        missing_isin = 0
        invalid_ohlc = 0
        negative_vol = 0

        for r in self.records:
            symbols.add(r.symbol)
            dates.add(r.trading_date)
            key = (r.symbol, r.trading_date)
            if key in natural_keys:
                duplicate_keys += 1
            natural_keys.add(key)

            if r.total_traded_value_inr is None:
                missing_turnover += 1
            if r.isin is None:
                missing_isin += 1
            if r.low > r.high or r.open < r.low or r.open > r.high or r.close < r.low or r.close > r.high:
                invalid_ohlc += 1
            if r.total_traded_quantity < 0:
                negative_vol += 1

        earliest = min(dates) if dates else "N/A"
        latest = max(dates) if dates else "N/A"

        return {
            "total_rows": total_rows,
            "unique_symbols": len(symbols),
            "unique_dates": len(dates),
            "earliest_date": earliest,
            "latest_date": latest,
            "duplicate_natural_keys": duplicate_keys,
            "missing_turnover_rows": missing_turnover,
            "missing_isin_rows": missing_isin,
            "invalid_ohlc_rows": invalid_ohlc,
            "negative_volume_rows": negative_vol,
        }
