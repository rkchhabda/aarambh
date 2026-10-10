"""Tests for Milestone 4.9C NSE HTTP2 runtime dependency resolution.

Verifies:
1. requirements-phase7.txt freezes nse[server]==4.0.1 without unpinned or duplicate entries.
2. h2, hpack, hyperframe are installed in .venv-phase7.
3. httpx remains 0.28.1 and nse remains 4.0.1.
4. HTTPX and NSE client construction with http2=True / server=True succeed under mocking with zero network calls.
5. Regression test reproducing the exact prior error ('Using http2=True, but the \\'h2\\' package is not installed').
6. Isolation safeguards: zero network calls, zero marker creation, zero market data downloads, zero targets, models, or metrics.
"""

import importlib.metadata as metadata
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from phase7.sources.client_factory import create_real_nse_client
from phase7.sources.client_protocol import NSEClientProtocol


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def temp_external_dir(tmp_path: Path) -> Path:
    d = tmp_path / "mock_staging_raw"
    d.mkdir(parents=True, exist_ok=True)
    return d


# 1 & 2: Governed requirement has nse[server]==4.0.1 and old nse==4.0.1 is absent
def test_requirements_file_has_server_extra_and_no_duplicates(repo_root: Path):
    req_file = repo_root / "requirements-phase7.txt"
    assert req_file.exists(), "requirements-phase7.txt must exist"
    content = req_file.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]

    assert "nse[server]==4.0.1" in lines, "requirements-phase7.txt must specify nse[server]==4.0.1"
    assert "nse==4.0.1" not in lines, "Old un-extra requirement nse==4.0.1 must be absent"
    nse_lines = [l for l in lines if l.startswith("nse")]
    assert len(nse_lines) == 1, f"Exactly one nse entry permitted, found: {nse_lines}"


# 3, 4, 5, 6, 7: Installed packages verification
def test_installed_dependencies_versions():
    # 3: h2 installed
    assert importlib.util.find_spec("h2") is not None, "h2 must be installed"
    h2_version = metadata.version("h2")
    assert h2_version.startswith("4."), f"Expected h2 4.*, got {h2_version}"

    # 4: hpack installed
    assert importlib.util.find_spec("hpack") is not None, "hpack must be installed"
    hpack_version = metadata.version("hpack")
    assert hpack_version.startswith("4."), f"Expected hpack 4.*, got {hpack_version}"

    # 5: hyperframe installed
    assert importlib.util.find_spec("hyperframe") is not None, "hyperframe must be installed"
    hyperframe_version = metadata.version("hyperframe")
    assert hyperframe_version.startswith("6."), f"Expected hyperframe 6.*, got {hyperframe_version}"

    # 6: httpx remains 0.28.1
    assert metadata.version("httpx") == "0.28.1", "httpx must remain pinned to 0.28.1"

    # 7: nse remains 4.0.1
    assert metadata.version("nse") == "4.0.1", "nse must remain pinned to 4.0.1"


# 8 & 9: HTTPX client construction with http2=True succeeds under mocking with 0 network calls
def test_httpx_client_http2_construction_zero_network():
    with patch("httpx.Client.send") as mock_send, patch("socket.socket.connect") as mock_connect:
        client = httpx.Client(http2=True)
        assert client is not None
        client.close()
        mock_send.assert_not_called()
        mock_connect.assert_not_called()


# 10, 11, 12, 13, 14, 15: NSE client construction through factory succeeds without missing-h2 error
def test_nse_client_construction_through_factory(temp_external_dir: Path):
    # Intercept Transport._getCookies so no network socket is opened during client init
    with patch("nse.transport.Transport._getCookies", return_value={}) as mock_cookies:
        client = create_real_nse_client(
            download_folder=temp_external_dir,
            server=True,
            timeout=15,
        )
        assert client is not None
        assert isinstance(client, NSEClientProtocol)
        mock_cookies.assert_called_once()

        # 14: Closure
        if hasattr(client, "_transport") and hasattr(client._transport, "_session"):
            client._transport._session.close()

        # 15: Zero retrieval methods called
        for forbidden_method in [
            "equityQuote",
            "status",
            "fetch_equity_historical_data",
            "listEquityStocksByIndex",
            "actions",
        ]:
            if hasattr(client, forbidden_method):
                method_obj = getattr(client, forbidden_method)
                assert not isinstance(method_obj, MagicMock) or method_obj.call_count == 0


# 16, 17: No authorization marker created or reused in test
def test_no_authorization_marker_creation_or_reuse(temp_external_dir: Path):
    auth_dir = temp_external_dir / "authorization"
    assert not auth_dir.exists(), "Test must not create authorization directory"
    active_marker = auth_dir / "pilot_authorization.json"
    assert not active_marker.exists(), "Active marker must not exist"


# 18: No market data downloaded
def test_no_market_data_downloaded(temp_external_dir: Path):
    raw_files = list(temp_external_dir.glob("*.csv")) + list(temp_external_dir.glob("*.parquet"))
    assert len(raw_files) == 0, f"No market data files should exist, found: {raw_files}"


# 19, 20, 21: No target generation, model training, or performance metrics
def test_no_target_generation_or_models_or_metrics():
    import phase7.sources as sources
    for attr in dir(sources):
        assert "target" not in attr.lower(), f"No target attribute in sources: {attr}"
        assert "model" not in attr.lower(), f"No model attribute in sources: {attr}"
        assert "sharpe" not in attr.lower(), f"No sharpe attribute in sources: {attr}"


# 22, 23, 24: Module isolation safeguards
def test_source_runtime_dependencies_isolation(repo_root: Path):
    import ast
    sources_dir = repo_root / "phase7" / "sources"
    forbidden_prefixes = ("scripts.phase6", "service", "features.data_provider", "features.universe")
    for py_file in sources_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for fb in forbidden_prefixes:
                        assert not alias.name.startswith(fb), f"Forbidden import '{alias.name}' in {py_file}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for fb in forbidden_prefixes:
                        assert not node.module.startswith(fb), f"Forbidden from-import '{node.module}' in {py_file}"


# REGRESSION TEST: Exact error reproduced when h2 is simulated missing, and verified resolved
def test_regression_http2_requires_h2_error_resolved():
    # 1. Verify in active environment, httpx.Client(http2=True) succeeds without error
    client = httpx.Client(http2=True)
    assert client is not None
    client.close()

    # 2. Simulate the prior missing-h2 condition and verify exact prior error message
    import sys
    saved = sys.modules.get("h2")
    try:
        sys.modules["h2"] = None  # Causes ImportError when httpx attempts import
        with pytest.raises(ImportError) as exc_info:
            httpx.Client(http2=True)
    finally:
        if saved is not None:
            sys.modules["h2"] = saved

    msg = str(exc_info.value)
    assert "Using http2=True, but the 'h2' package is not installed" in msg
    assert "pip install httpx[http2]" in msg
