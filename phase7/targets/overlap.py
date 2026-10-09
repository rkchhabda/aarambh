"""Overlap detection and connected group tracking for Phase 7 target windows.

Rules and Invariants:
1. Retains all target records; never purges or embargos here (deferred to walk-forward validation in Milestone 4).
2. Never groups different securities together (isolation strictly per symbol + ISIN).
3. Evaluates closed holding intervals [outcome_start, outcome_end].
   Boundary-touching convention: If window B begins on the exact date window A ends (entry_B == exit_A),
   the windows share that market session and are classified as overlapping. If entry_B > exit_A,
   the windows are non-overlapping.
4. Chained overlaps belong to a deterministic connected group identifier computed via connected components.
5. Identical windows are classified as overlapping.
6. Zero statistical or investment-performance metrics computed.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
import hashlib
from typing import Dict, List, Optional, Sequence, Set, Tuple

from phase7.data.contracts import compute_row_hash
from phase7.targets.contracts import (
    TargetResultRecord,
    TargetStatus,
)


@dataclass(frozen=True)
class TargetOverlapMetadata:
    """Immutable record tracking forward window overlaps and connected groups."""
    symbol: str
    isin: str
    target_name: str
    target_specification_hash: str
    prediction_timestamp: datetime
    outcome_start: Optional[date]
    outcome_end: Optional[date]
    overlap_count: int
    overlap_group_id: str
    overlapping_target_identifiers: Tuple[str, ...]
    target_identifier: str = ""

    def __post_init__(self) -> None:
        if not self.target_identifier and hasattr(self, "target_identifier"):
            clean_dict = {k: v for k, v in self.__dict__.items() if k != "target_identifier"}
            computed = compute_row_hash(clean_dict)
            object.__setattr__(self, "target_identifier", computed)


def windows_overlap(
    start_a: date,
    end_a: date,
    start_b: date,
    end_b: date,
) -> bool:
    """Evaluate whether two forward holding windows overlap under closed interval convention.

    Convention:
        If start_b <= end_a and start_a <= end_b, the windows share at least one market session
        (including boundary touch when start_b == end_a).
    """
    return max(start_a, start_b) <= min(end_a, end_b)


def detect_target_overlaps(
    targets: Sequence[TargetResultRecord],
    target_specification_hash: str = "",
) -> List[TargetOverlapMetadata]:
    """Detect pairwise and chained window overlaps per security and assign deterministic groups.

    Args:
        targets: Sequence of TargetResultRecord instances to evaluate.
        target_specification_hash: Preregistered target specification hash.

    Returns:
        List of TargetOverlapMetadata records preserving all input targets in order.
    """
    if not targets:
        return []

    # 1. Group targets strictly per security (symbol, isin)
    # Track original index to maintain order preservation
    by_security: Dict[Tuple[str, str], List[Tuple[int, TargetResultRecord]]] = defaultdict(list)
    for idx, t in enumerate(targets):
        by_security[(t.symbol, t.isin)].append((idx, t))

    results: List[Optional[TargetOverlapMetadata]] = [None] * len(targets)

    for (symbol, isin), sec_targets in by_security.items():
        # Valid targets with non-None outcome start and end
        valid_items = [
            (idx, t) for idx, t in sec_targets
            if t.target_status == TargetStatus.VALID and t.entry_date is not None and t.exit_date is not None
        ]

        # Targets with no outcome dates (invalid/blocked) get zero overlaps
        invalid_items = [
            (idx, t) for idx, t in sec_targets
            if not (t.target_status == TargetStatus.VALID and t.entry_date is not None and t.exit_date is not None)
        ]

        for idx, t in invalid_items:
            spec_hash = target_specification_hash or (t.source_dataset_versions.get("target_specification_hash", ""))
            tid = t.target_hash or f"rec_{idx}"
            results[idx] = TargetOverlapMetadata(
                symbol=symbol,
                isin=isin,
                target_name=t.target_name,
                target_specification_hash=spec_hash,
                prediction_timestamp=t.prediction_timestamp,
                outcome_start=t.entry_date,
                outcome_end=t.exit_date,
                overlap_count=0,
                overlap_group_id=f"invalid_{tid[:16]}",
                overlapping_target_identifiers=(),
                target_identifier=tid,
            )

        if not valid_items:
            continue

        # Build adjacency graph for connected component analysis
        # Vertices identified by index in valid_items
        adj: Dict[int, Set[int]] = defaultdict(set)
        for i in range(len(valid_items)):
            _, t_i = valid_items[i]
            for j in range(i + 1, len(valid_items)):
                _, t_j = valid_items[j]
                assert t_i.entry_date is not None and t_i.exit_date is not None
                assert t_j.entry_date is not None and t_j.exit_date is not None
                if windows_overlap(t_i.entry_date, t_i.exit_date, t_j.entry_date, t_j.exit_date):
                    adj[i].add(j)
                    adj[j].add(i)

        # Find connected components deterministically
        visited: Set[int] = set()
        components: List[List[int]] = []
        for i in range(len(valid_items)):
            if i not in visited:
                comp: List[int] = []
                queue = [i]
                visited.add(i)
                while queue:
                    node = queue.pop(0)
                    comp.append(node)
                    for neighbor in sorted(adj[node]):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
                components.append(comp)

        # Assign deterministic group ID per component
        for comp in components:
            # Component target identifiers deterministically sorted
            comp_target_ids = sorted(
                valid_items[node][1].target_hash or f"target_{valid_items[node][0]}"
                for node in comp
            )
            hasher = hashlib.sha256()
            hasher.update((f"{symbol}:{isin}:" + ":".join(comp_target_ids)).encode("utf-8"))
            group_hash = hasher.hexdigest()[:16]

            if len(comp) == 1:
                group_id = f"solo_{group_hash}"
            else:
                group_id = f"grp_{group_hash}"

            for node in comp:
                orig_idx, target_rec = valid_items[node]
                # Direct overlapping neighbors for this specific target
                neighbors = sorted(
                    valid_items[n][1].target_hash or f"target_{valid_items[n][0]}"
                    for n in adj[node]
                )
                spec_hash = target_specification_hash or (target_rec.source_dataset_versions.get("target_specification_hash", ""))
                tid = target_rec.target_hash or f"target_{orig_idx}"

                results[orig_idx] = TargetOverlapMetadata(
                    symbol=symbol,
                    isin=isin,
                    target_name=target_rec.target_name,
                    target_specification_hash=spec_hash,
                    prediction_timestamp=target_rec.prediction_timestamp,
                    outcome_start=target_rec.entry_date,
                    outcome_end=target_rec.exit_date,
                    overlap_count=len(neighbors),
                    overlap_group_id=group_id,
                    overlapping_target_identifiers=tuple(neighbors),
                    target_identifier=tid,
                )

    return [r for r in results if r is not None]
