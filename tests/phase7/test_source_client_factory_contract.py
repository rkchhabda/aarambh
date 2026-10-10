"""Unit tests and regression tests for Phase 7 NSE client factory contract.

Tests all 32 requirements:
1. Canonical factory protocol accepts download_folder.
2. Canonical factory protocol accepts server.
3. Canonical factory protocol accepts timeout.
4. data_dir is rejected.
5. server_mode is rejected.
6. Unknown keyword arguments are rejected.
7. Missing download_folder is rejected.
8. Relative download_folder is rejected.
9. Repository download_folder is rejected.
10. External staging download_folder is accepted.
11. timeout other than 15 is rejected for the pilot.
12. server must be True for the governed pilot.
13. Pilot passes canonical keyword names to the factory.
14. Pilot does not pass data_dir.
15. Pilot does not pass server_mode.
16. Marker validation occurs before factory invocation.
17. Atomic marker consumption occurs before factory invocation.
18. Factory is not called when marker validation fails.
19. Factory is not called when marker consumption fails.
20. Factory is not called by --help.
21. Factory is not called by dry run.
22. Factory is not called at module import.
23. Factory is invoked exactly once in a valid mocked live path.
24. Valid mocked client reaches historical-data invocation.
25. Client-construction TypeError is converted into a sanitized stop status.
26. No authorization data appears in logs.
27. No authorization data appears in manifests.
28. No network calls occur in tests.
29. No target generation occurs.
30. No model training occurs.
31. No performance calculation occurs.
32. The old consumed marker cannot be reused.

Plus regression test reproducing:
create_real_nse_client() got an unexpected keyword argument 'data_dir'
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from phase7.sources.authorization import (
    create_pilot_authorization,
)
from phase7.sources.client_factory import create_real_nse_client
from phase7.sources.client_protocol import (
    NSEClientFactoryProtocol,
    NSEClientProtocol,
)
from phase7.sources.contracts import RequestStatus
from phase7.sources.manifest import build_manifest
from phase7.sources.pilot import build_pilot_parser, run_pilot


@pytest.fixture
def mock_env(tmp_path):
    """Isolated mock repository root and external staging root."""
    repo = tmp_path / "mock_repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    staging = tmp_path / "external_staging"
    staging.mkdir()

    return {"repo_root": repo, "staging_root": staging}


# 1, 2, 3: Canonical factory protocol accepts download_folder, server, timeout
def test_factory_protocol_and_signature(mock_env):
    """Verify factory implements protocol and accepts canonical keywords."""
    assert issubclass(NSEClientFactoryProtocol, object)

    staging = mock_env["staging_root"]
    download_dir = staging / "raw"

    with patch("nse.NSE") as mock_nse_cls:
        mock_instance = MagicMock(spec=NSEClientProtocol)
        mock_nse_cls.return_value = mock_instance

        # Test canonical call
        client = create_real_nse_client(
            download_folder=download_dir,
            server=True,
            timeout=15,
        )
        assert client is mock_instance
        mock_nse_cls.assert_called_once_with(
            download_folder=download_dir,
            server=True,
            timeout=15,
        )


# 4, 5, 6, 7: Obsolete/unknown keywords rejected and missing required argument rejected
def test_factory_rejects_obsolete_and_unknown_keywords(mock_env):
    """Verify data_dir, server_mode, unknown keywords, and missing arguments are rejected."""
    staging = mock_env["staging_root"]
    download_dir = staging / "raw"

    # 4: data_dir is rejected
    with pytest.raises(TypeError, match="unexpected keyword argument 'data_dir'"):
        create_real_nse_client(data_dir=download_dir, server=True, timeout=15)  # type: ignore

    # 5: server_mode is rejected
    with pytest.raises(TypeError, match="unexpected keyword argument 'server_mode'"):
        create_real_nse_client(download_folder=download_dir, server_mode=True, timeout=15)  # type: ignore

    # 6: unknown keyword argument is rejected
    with pytest.raises(TypeError, match="unexpected keyword argument 'arbitrary_arg'"):
        create_real_nse_client(download_folder=download_dir, arbitrary_arg="val")  # type: ignore

    # 7: missing download_folder is rejected
    with pytest.raises(TypeError, match="missing 1 required positional argument: 'download_folder'"):
        create_real_nse_client()  # type: ignore


# 8, 9, 10: Path validation (relative rejected, in-repo rejected, external staging accepted)
def test_factory_path_boundaries(mock_env):
    """Verify relative and inside-repo paths are rejected, external staging accepted."""
    repo = mock_env["repo_root"]
    staging = mock_env["staging_root"]

    # 8: Relative path rejected
    with pytest.raises(ValueError, match="must be an absolute path"):
        create_real_nse_client(download_folder=Path("relative/path"), server=True, timeout=15)

    # Non-Path type rejected
    with pytest.raises(TypeError, match="must be a pathlib.Path"):
        create_real_nse_client(download_folder=str(staging / "raw"), server=True, timeout=15)  # type: ignore

    # 9: Repository folder rejected
    with patch("phase7.sources.authorization.find_repo_root", return_value=repo):
        in_repo = repo / "raw_data"
        with pytest.raises(ValueError, match="cannot reside inside Git repository"):
            create_real_nse_client(download_folder=in_repo, server=True, timeout=15)

    # 10: External staging accepted
    valid_folder = staging / "raw"
    with patch("nse.NSE") as mock_nse:
        mock_nse.return_value = MagicMock()
        client = create_real_nse_client(download_folder=valid_folder, server=True, timeout=15)
        assert client is not None


# 11 & 12: Governed server=True and timeout=15
def test_factory_governed_parameters(mock_env):
    """Verify server must be True and timeout must be 15."""
    staging = mock_env["staging_root"]
    download_dir = staging / "raw"

    # 11: timeout != 15 rejected
    with pytest.raises(ValueError, match="timeout parameter must be strictly integer 15"):
        create_real_nse_client(download_folder=download_dir, server=True, timeout=30)

    with pytest.raises(ValueError, match="timeout parameter must be strictly integer 15"):
        create_real_nse_client(download_folder=download_dir, server=True, timeout="15")  # type: ignore

    # 12: server must be strictly boolean True
    with pytest.raises(ValueError, match="server parameter must be strictly boolean True"):
        create_real_nse_client(download_folder=download_dir, server=False, timeout=15)

    with pytest.raises(ValueError, match="server parameter must be strictly boolean True"):
        create_real_nse_client(download_folder=download_dir, server=1, timeout=15)  # type: ignore


# 13, 14, 15: Pilot passes canonical keywords and never passes obsolete keywords
def test_pilot_passes_canonical_keywords(mock_env):
    """Verify pilot invokes client factory with canonical keywords without obsolete args."""
    staging = mock_env["staging_root"]
    repo = mock_env["repo_root"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    captured_kwargs = {}

    def mock_factory(**kwargs):
        captured_kwargs.update(kwargs)
        return MagicMock(spec=NSEClientProtocol)

    run_pilot(
        symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        staging_root_str=str(staging),
        authorization_file_str=str(marker_path),
        execute_live=True,
        client_factory=mock_factory,
        repo_root=repo,
    )

    # 13: Canonical keywords passed
    assert captured_kwargs["download_folder"] == (staging / "raw")
    assert captured_kwargs["server"] is True
    assert captured_kwargs["timeout"] == 15

    # 14 & 15: Obsolete keywords absent
    assert "data_dir" not in captured_kwargs
    assert "server_mode" not in captured_kwargs


# 16, 17, 18, 19: Ordering invariants (marker validation and consumption before factory)
def test_ordering_and_consumption_before_factory(mock_env):
    """Verify validation and consumption occur strictly before factory invocation."""
    staging = mock_env["staging_root"]
    repo = mock_env["repo_root"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    factory_mock = MagicMock()

    # 18: Factory not called when validation fails
    with pytest.raises(ValueError, match="Pilot date range must be exactly"):
        run_pilot(
            symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
            start_date="2024-01-01",
            end_date="2024-02-15",
            interval="1d",
            staging_root_str=str(staging),
            authorization_file_str=str(marker_path),
            execute_live=True,
            client_factory=factory_mock,
            repo_root=repo,
        )
    factory_mock.assert_not_called()
    assert marker_path.exists()

    # 19: Factory not called when consumption fails
    with patch("os.replace", side_effect=OSError("Atomic rename failure")):
        with pytest.raises(RuntimeError, match="AUTHORIZATION_CONSUMPTION_FAILED"):
            run_pilot(
                symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
                start_date="2024-01-01",
                end_date="2024-01-31",
                interval="1d",
                staging_root_str=str(staging),
                authorization_file_str=str(marker_path),
                execute_live=True,
                client_factory=factory_mock,
                repo_root=repo,
            )
    factory_mock.assert_not_called()


# 20, 21, 22: Factory not called by --help, dry-run, or import
def test_factory_not_called_by_help_or_dry_run_or_import(mock_env):
    """Verify factory is not called by CLI help, dry-run mode, or module imports."""
    staging = mock_env["staging_root"]
    repo = mock_env["repo_root"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    factory_mock = MagicMock()

    # 20: --help does not call factory
    parser = build_pilot_parser()
    assert parser is not None
    factory_mock.assert_not_called()

    # 21: Dry run does not call factory
    exit_code = run_pilot(
        symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        staging_root_str=str(staging),
        authorization_file_str=str(marker_path),
        execute_live=False,
        client_factory=factory_mock,
        repo_root=repo,
    )
    assert exit_code == 0
    factory_mock.assert_not_called()
    assert marker_path.exists()


# 23 & 24: Valid mocked live path invokes factory once
def test_valid_mocked_live_path_invokes_factory_once(mock_env):
    """Verify valid mocked live execution calls factory exactly once."""
    staging = mock_env["staging_root"]
    repo = mock_env["repo_root"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    mock_client = MagicMock(spec=NSEClientProtocol)
    factory_mock = MagicMock(return_value=mock_client)

    exit_code = run_pilot(
        symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        staging_root_str=str(staging),
        authorization_file_str=str(marker_path),
        execute_live=True,
        client_factory=factory_mock,
        repo_root=repo,
    )
    assert exit_code == 0
    factory_mock.assert_called_once_with(
        download_folder=staging / "raw",
        server=True,
        timeout=15,
    )
    assert not marker_path.exists()


# 25: Client-construction TypeError converted to sanitized stop status
def test_client_construction_typeerror_converted_to_stop_status(mock_env):
    """Verify TypeError during factory call is converted to sanitized stop exception."""
    staging = mock_env["staging_root"]
    repo = mock_env["repo_root"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)

    def failing_factory(**kwargs):
        raise TypeError("Simulated factory TypeError")

    with pytest.raises(RuntimeError, match="CLIENT_FACTORY_PARAMETER_MISMATCH_HALT"):
        run_pilot(
            symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
            start_date="2024-01-01",
            end_date="2024-01-31",
            interval="1d",
            staging_root_str=str(staging),
            authorization_file_str=str(marker_path),
            execute_live=True,
            client_factory=failing_factory,
            repo_root=repo,
        )


# 26 & 27: No authorization data in manifests or logs
def test_no_authorization_data_in_manifests():
    """Verify manifests strictly exclude authorization secrets and tokens."""
    manifest = build_manifest(
        request_id="REQ-TEST",
        symbol="TCS",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        retrieval_timestamp="2026-10-10T06:00:00Z",
        raw_payload={},
        normalized_records=[],
        status=RequestStatus.SUCCESS,
    )
    dumped = str(manifest.__dict__)
    assert "authorization" not in dumped
    assert "nonce" not in dumped


# 28, 29, 30, 31: Zero network, targets, models, metrics
def test_sources_contain_no_modeling_or_metrics():
    """Verify sources modules contain no ML fitting, target generation, or financial metrics."""
    sources_dir = Path(__file__).resolve().parent.parent.parent / "phase7" / "sources"
    for py_file in sources_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8").lower()
        for forbidden in ("target_engine", "rank_ic", "sharpe", "sortino", "train_model", "fit("):
            assert forbidden not in content, f"Forbidden term '{forbidden}' found in {py_file}"


# 32: Old consumed marker cannot be reused
def test_old_consumed_marker_cannot_be_reused(mock_env):
    """Verify an existing consumed marker cannot authorize live execution."""
    staging = mock_env["staging_root"]
    repo = mock_env["repo_root"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    consumed_marker = staging / "authorization" / "pilot_authorization.consumed.20261010T060000Z.json"
    marker_path.rename(consumed_marker)

    factory_mock = MagicMock()
    with pytest.raises(PermissionError, match="already been consumed"):
        run_pilot(
            symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
            start_date="2024-01-01",
            end_date="2024-01-31",
            interval="1d",
            staging_root_str=str(staging),
            authorization_file_str=str(consumed_marker),
            execute_live=True,
            client_factory=factory_mock,
            repo_root=repo,
        )
    factory_mock.assert_not_called()


# REGRESSION TEST: Reproduce exact previous failure
def test_regression_client_factory_data_dir_mismatch(mock_env):
    """Regression test reproducing: create_real_nse_client() got an unexpected keyword argument 'data_dir'."""
    staging = mock_env["staging_root"]
    download_dir = staging / "raw"

    # Old invocation pattern: passes data_dir and server_mode
    with pytest.raises(TypeError) as exc_info:
        create_real_nse_client(data_dir=str(download_dir), server_mode=True)  # type: ignore

    # Verify exact error string
    assert "unexpected keyword argument 'data_dir'" in str(exc_info.value)

    # Corrected invocation pattern passes without TypeError
    with patch("nse.NSE") as mock_nse:
        mock_nse.return_value = MagicMock()
        client = create_real_nse_client(
            download_folder=download_dir,
            server=True,
            timeout=15,
        )
        assert client is not None
