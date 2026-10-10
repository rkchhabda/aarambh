"""Fault injection and simulated failure hooks for Phase 7 production drills.

Supports deterministic testing of:
- Crashes at exact lifecycle points
- Disk-full (ENOSPC / Error 28) simulation
- Short-write simulation
- Permission denied (EACCES / Error 13) simulation
- Checksum corruption
- Manifest deletion / tampering
"""

from contextlib import contextmanager
import os
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Union


class InjectedFaultError(RuntimeError):
    """Raised when an injected fault or controlled crash triggers."""
    pass


class InjectedDiskFullError(OSError):
    """Simulates ENOSPC (disk full)."""
    def __init__(self, message: str = "No space left on device"):
        super().__init__(28, message)


class InjectedPermissionDeniedError(PermissionError):
    """Simulates EACCES (permission denied)."""
    def __init__(self, message: str = "Permission denied"):
        super().__init__(13, message)


class InjectedClientCloseError(RuntimeError):
    """Simulates failure during client cleanup."""
    pass


class FaultController:
    """Controls simulated lifecycle crashes and faults."""

    def __init__(self) -> None:
        self.active_crash_points: set = set()
        self.triggered_points: List[str] = []
        self.fault_actions: Dict[str, Callable[[], None]] = {}

    def arm_crash(self, point_name: str) -> None:
        self.active_crash_points.add(point_name)

    def register_fault_action(self, point_name: str, action: Callable[[], None]) -> None:
        self.fault_actions[point_name] = action

    def trigger_point(self, point_name: str) -> None:
        if point_name in self.fault_actions:
            self.triggered_points.append(point_name)
            self.fault_actions[point_name]()

        if point_name in self.active_crash_points:
            self.triggered_points.append(point_name)
            raise InjectedFaultError(f"Injected controlled crash at lifecycle point: '{point_name}'")

    def reset(self) -> None:
        self.active_crash_points.clear()
        self.triggered_points.clear()
        self.fault_actions.clear()


_GLOBAL_FAULT_CONTROLLER = FaultController()


def get_fault_controller() -> FaultController:
    return _GLOBAL_FAULT_CONTROLLER


@contextmanager
def armed_fault(point_name: str, action: Optional[Callable[[], None]] = None) -> Iterator[FaultController]:
    ctrl = get_fault_controller()
    if action:
        ctrl.register_fault_action(point_name, action)
    else:
        ctrl.arm_crash(point_name)
    try:
        yield ctrl
    finally:
        ctrl.reset()


def corrupt_file_checksum(file_path: Union[Path, str], byte_offset: int = 0) -> None:
    """Mutate a single byte in a file to deterministically corrupt its checksum."""
    p = Path(file_path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"File not found to corrupt: {p}")
    data = bytearray(p.read_bytes())
    if not data:
        data = bytearray(b"corrupted")
    else:
        idx = byte_offset % len(data)
        data[idx] = (data[idx] + 1) % 256
    p.write_bytes(bytes(data))
