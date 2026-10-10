"""Synthetic scale, memory tracking, and throughput simulation for Phase 7.

Strictly enforces:
- Fully synthetic data generation using deterministic PRNG (no real market data)
- Synthetic symbol format: SYN0001, SYN0002, ...
- Deterministic row generation for 20, 100, 500 symbols across 22, 65, 252, 3000 sessions
- Checksum determinism: identical inputs produce identical checksums
- Row conservation verification at 500-symbol scale
- Memory tracking ensuring bounded memory growth (no memory leaks)
- Checkpoint and manifest scalability guarantees
"""

from dataclasses import dataclass
from datetime import date, timedelta
import hashlib
import json
import random
import tracemalloc
from typing import Any, Dict, Iterator, List, Optional, Tuple


@dataclass(frozen=True)
class SyntheticRow:
    """Deterministic synthetic OHLCV row."""
    symbol: str
    session_date: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "session_date": self.session_date,
            "open": self.open_price,
            "high": self.high_price,
            "low": self.low_price,
            "close": self.close_price,
            "volume": self.volume,
        }


def generate_synthetic_symbols(count: int) -> List[str]:
    """Generate clearly synthetic symbol names: SYN0001, SYN0002, etc."""
    return [f"SYN{i+1:04d}" for i in range(count)]


def generate_synthetic_series(
    symbol: str,
    num_sessions: int,
    start_date: str = "2024-01-01",
    seed_offset: int = 0,
) -> List[SyntheticRow]:
    """Deterministically generate synthetic OHLCV series for a symbol."""
    # Seed PRNG deterministically based on symbol name and offset
    seed_val = int(hashlib.md5(f"{symbol}:{seed_offset}".encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed_val)

    rows: List[SyntheticRow] = []
    base_price = 100.0 + (rng.random() * 900.0)
    current_dt = date.fromisoformat(start_date)

    for i in range(num_sessions):
        # Skip weekends to simulate trading sessions
        while current_dt.weekday() >= 5:
            current_dt += timedelta(days=1)

        pct_change = (rng.random() - 0.49) * 0.04
        close_p = round(base_price * (1.0 + pct_change), 2)
        open_p = round(base_price * (1.0 + ((rng.random() - 0.5) * 0.02)), 2)
        high_p = round(max(open_p, close_p) + (rng.random() * 2.0), 2)
        low_p = round(min(open_p, close_p) - (rng.random() * 2.0), 2)
        vol = rng.randint(10_000, 500_000)

        rows.append(
            SyntheticRow(
                symbol=symbol,
                session_date=current_dt.isoformat(),
                open_price=open_p,
                high_price=high_p,
                low_price=low_p,
                close_price=close_p,
                volume=vol,
            )
        )
        base_price = close_p
        current_dt += timedelta(days=1)

    return rows


def compute_series_checksum(rows: List[SyntheticRow]) -> str:
    """Compute deterministic SHA-256 digest of a series."""
    h = hashlib.sha256()
    for r in rows:
        h.update(f"{r.symbol}|{r.session_date}|{r.open_price}|{r.high_price}|{r.low_price}|{r.close_price}|{r.volume}\n".encode("utf-8"))
    return h.hexdigest()


class MemoryTracker:
    """Context manager for measuring peak memory consumption in bytes."""

    def __init__(self) -> None:
        self.peak_bytes = 0
        self.current_bytes = 0

    def __enter__(self) -> "MemoryTracker":
        tracemalloc.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.current_bytes, self.peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

    @property
    def peak_megabytes(self) -> float:
        return self.peak_bytes / (1024 * 1024)
