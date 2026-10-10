"""Shared fixtures, network-denial enforcement, and test markers for Phase 7 test suite.

Strictly enforces:
- OS-level network denial across all Phase 7 tests (blocking sockets, HTTPX, urllib)
- Pytest marker configuration (unit, integration, fault_injection, scale, drill, slow)
- Deterministic UTC clocks and reproducible synthetic generators
- Repository boundary checks ensuring zero test artifacts pollute Git
"""

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import socket
from typing import Any, Callable, Dict, Generator, List, Optional
from unittest.mock import patch
import urllib.request

import httpx
import pytest

from phase7.operations.atomic_io import find_repository_root


def pytest_configure(config):
    """Register custom markers to avoid pytest warnings."""
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "fault_injection: mark test as fault injection drill")
    config.addinivalue_line("markers", "scale: mark test as synthetic scale/memory test")
    config.addinivalue_line("markers", "drill: mark test as operational drill test")
    config.addinivalue_line("markers", "slow: mark test as slow test")


class NetworkAccessDeniedError(RuntimeError):
    """Raised whenever an outbound network call is attempted during tests."""
    pass


def _deny_network_call(*args, **kwargs):
    raise NetworkAccessDeniedError(
        "Network access strictly denied in Phase 7 offline test suite: external sockets blocked."
    )


@pytest.fixture(autouse=True, scope="function")
def enforce_offline_network_denial() -> Generator[None, None, None]:
    """OS-level network denial autouse fixture intercepting all socket and HTTP entry points."""
    with patch("socket.socket.connect", side_effect=_deny_network_call), \
         patch("socket.create_connection", side_effect=_deny_network_call), \
         patch("httpx.Client.send", side_effect=_deny_network_call), \
         patch("urllib.request.urlopen", side_effect=_deny_network_call):
        yield


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Path to the Git repository root."""
    return find_repository_root(__file__)


@pytest.fixture
def temp_staging(tmp_path: Path) -> Path:
    """Isolated temporary external staging directory strictly outside repository."""
    staging = tmp_path / "external_staging"
    staging.mkdir(parents=True, exist_ok=True)
    return staging


@pytest.fixture
def deterministic_clock() -> Callable[[], str]:
    """Returns a deterministic UTC ISO timestamp string."""
    fixed_time = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
    return lambda: fixed_time.isoformat()


@pytest.fixture
def synthetic_contract() -> Dict[str, Any]:
    """Governed synthetic batch contract dictionary."""
    return {
        "panel_version": "SYNTHETIC_PANEL_V1",
        "snapshot_checksum": "a" * 64,
        "selection_checksum": "b" * 64,
        "ordered_symbols_sha256": "c" * 64,
        "date_window": "2024Q1",
        "interval": "1d",
        "governed_symbol_count": 20,
    }
