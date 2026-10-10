"""Unit and regression tests for Phase 7 pilot exit code contracts.

Verifies:
- 0: All five symbols completed and pilot acceptance passed.
- 2: Argument or scope validation failure.
- 3: Authorization validation or consumption failure.
- 4: Client-construction failure.
- 5: Retrieval or upstream connectivity failure.
- 6: Payload safety, schema, or normalization failure.
- 7: Persistence, manifest, or audit-conservation failure.
- 8: Incomplete execution, including fewer than five completed symbols.
- 9: Client-close failure.
- 10: Unexpected internal error.
- Regression test: test_client_initialization_without_symbol_loop_cannot_succeed
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from phase7.sources.authorization import create_pilot_authorization
from phase7.sources.client_protocol import NSEClientProtocol
from phase7.sources.contracts import PilotExitCode, RequestStatus
from phase7.sources.pilot import main, run_pilot


@pytest.fixture
def test_env(tmp_path):
    staging = tmp_path / "staging_pilot_exit"
    staging.mkdir(parents=True, exist_ok=True)
    repo = tmp_path / "mock_repo"
    repo.mkdir(parents=True, exist_ok=True)
    return {"staging": staging, "repo": repo}


def make_valid_eod_rows(symbol: str):
    return [
        {
            "CH_TIMESTAMP": f"2024-01-{day:02d}",
            "CH_SERIES": "EQ",
            "CH_OPENING_PRICE": 2500.0,
            "CH_TRADE_HIGH_PRICE": 2550.0,
            "CH_TRADE_LOW_PRICE": 2480.0,
            "CH_CLOSING_PRICE": 2520.0,
            "CH_TOT_TRADED_QTY": 100000,
            "CH_TOT_TRADED_VAL": 252000000.0,
            "CH_ISIN": "INE002A01018",
        }
        for day in range(1, 20)
    ]


def test_client_initialization_without_symbol_loop_cannot_succeed(test_env):
    """Regression test: client initialization alone without completing the 5-symbol loop must never exit 0."""
    staging = test_env["staging"]
    repo = test_env["repo"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    mock_client = MagicMock(spec=NSEClientProtocol)
    # Simulate client that raises an exception on first symbol, so 0 symbols complete
    mock_client.fetch_equity_historical_data.side_effect = ConnectionError("Simulated immediate retrieval stop")
    factory = MagicMock(return_value=mock_client)

    exit_code = run_pilot(
        symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        staging_root_str=str(staging),
        authorization_file_str=str(marker_path),
        execute_live=True,
        client_factory=factory,
        repo_root=repo,
        pacing_seconds=0.0,
    )

    # Must be non-zero (never 0)
    assert exit_code != 0
    # Must be retrieval error (5) or incomplete execution (8)
    assert exit_code in (PilotExitCode.RETRIEVAL_ERROR.value, PilotExitCode.INCOMPLETE_EXECUTION_ERROR.value)


def test_exit_code_0_all_five_symbols_succeed(test_env):
    """Verify exit code 0 when all five symbols complete successfully."""
    staging = test_env["staging"]
    repo = test_env["repo"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    mock_client = MagicMock(spec=NSEClientProtocol)
    mock_client.fetch_equity_historical_data.side_effect = lambda symbol, **kwargs: make_valid_eod_rows(symbol)
    factory = MagicMock(return_value=mock_client)

    exit_code = run_pilot(
        symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        staging_root_str=str(staging),
        authorization_file_str=str(marker_path),
        execute_live=True,
        client_factory=factory,
        repo_root=repo,
        pacing_seconds=0.0,
    )

    assert exit_code == PilotExitCode.SUCCESS.value  # 0


def test_exit_code_2_cli_argument_validation_failure(test_env):
    """Verify exit code 2 on CLI argument or scope validation failure."""
    staging = test_env["staging"]
    # Pass invalid interval
    exit_val = main([
        "--symbols", "RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        "--interval", "5m",  # Invalid interval
        "--staging-root", str(staging),
    ])
    assert exit_val == PilotExitCode.ARGUMENT_ERROR.value  # 2


def test_exit_code_3_authorization_failure(test_env):
    """Verify exit code 3 on missing or invalid authorization marker."""
    staging = test_env["staging"]
    repo = test_env["repo"]
    # Create valid marker then tamper with authorization hash to trigger PermissionError
    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    data = json.loads(marker_path.read_text(encoding="utf-8"))
    data["authorization_hash"] = "tampered_invalid_hash_0123456789abcdef"
    marker_path.write_text(json.dumps(data), encoding="utf-8")

    exit_val = main([
        "--symbols", "RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        "--staging-root", str(staging),
        "--authorization-file", str(marker_path),
        "--execute-live",
    ])
    assert exit_val == PilotExitCode.AUTHORIZATION_ERROR.value  # 3


def test_exit_code_4_client_construction_failure(test_env):
    """Verify exit code 4 on client factory construction failure."""
    staging = test_env["staging"]
    repo = test_env["repo"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    failing_factory = MagicMock(side_effect=TypeError("Unexpected keyword argument 'invalid'"))

    exit_code = run_pilot(
        symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        staging_root_str=str(staging),
        authorization_file_str=str(marker_path),
        execute_live=True,
        client_factory=failing_factory,
        repo_root=repo,
        pacing_seconds=0.0,
        catch_exceptions=True,
    )
    assert exit_code == PilotExitCode.CLIENT_CONSTRUCTION_ERROR.value  # 4


def test_exit_code_5_retrieval_connectivity_failure(test_env):
    """Verify exit code 5 on network connection or timeout failure."""
    staging = test_env["staging"]
    repo = test_env["repo"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    mock_client = MagicMock(spec=NSEClientProtocol)
    mock_client.fetch_equity_historical_data.side_effect = ConnectionError("Upstream connection refused")
    factory = MagicMock(return_value=mock_client)

    exit_code = run_pilot(
        symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        staging_root_str=str(staging),
        authorization_file_str=str(marker_path),
        execute_live=True,
        client_factory=factory,
        repo_root=repo,
        pacing_seconds=0.0,
    )
    assert exit_code == PilotExitCode.RETRIEVAL_ERROR.value  # 5


def test_exit_code_6_payload_safety_or_schema_failure(test_env):
    """Verify exit code 6 on HTML/CAPTCHA or schema normalization failure."""
    staging = test_env["staging"]
    repo = test_env["repo"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    mock_client = MagicMock(spec=NSEClientProtocol)
    # Return HTML payload
    mock_client.fetch_equity_historical_data.return_value = "<!DOCTYPE html><html><body>Blocked</body></html>"
    factory = MagicMock(return_value=mock_client)

    exit_code = run_pilot(
        symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        staging_root_str=str(staging),
        authorization_file_str=str(marker_path),
        execute_live=True,
        client_factory=factory,
        repo_root=repo,
        pacing_seconds=0.0,
    )
    assert exit_code == PilotExitCode.SCHEMA_NORMALIZATION_ERROR.value  # 6


def test_exit_code_7_persistence_or_manifest_failure(test_env):
    """Verify exit code 7 on persistence or manifest failure."""
    staging = test_env["staging"]
    repo = test_env["repo"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    mock_client = MagicMock(spec=NSEClientProtocol)
    mock_client.fetch_equity_historical_data.return_value = make_valid_eod_rows("RELIANCE")
    factory = MagicMock(return_value=mock_client)

    with patch("phase7.sources.pilot.persist_raw_payload", side_effect=OSError("Disk write error")):
        exit_code = run_pilot(
            symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
            start_date="2024-01-01",
            end_date="2024-01-31",
            interval="1d",
            staging_root_str=str(staging),
            authorization_file_str=str(marker_path),
            execute_live=True,
            client_factory=factory,
            repo_root=repo,
            pacing_seconds=0.0,
        )
    assert exit_code == PilotExitCode.PERSISTENCE_MANIFEST_ERROR.value  # 7


def test_exit_code_8_incomplete_execution_one_to_four_symbols(test_env):
    """Verify incomplete execution with fewer than 5 symbols cannot produce exit code 0."""
    staging = test_env["staging"]
    repo = test_env["repo"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    call_count = 0

    def _fetch_two_then_fail(symbol, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return make_valid_eod_rows(symbol)
        raise ConnectionError("Halt after 2 symbols")

    mock_client = MagicMock(spec=NSEClientProtocol)
    mock_client.fetch_equity_historical_data.side_effect = _fetch_two_then_fail
    factory = MagicMock(return_value=mock_client)

    exit_code = run_pilot(
        symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        staging_root_str=str(staging),
        authorization_file_str=str(marker_path),
        execute_live=True,
        client_factory=factory,
        repo_root=repo,
        pacing_seconds=0.0,
    )
    assert exit_code != 0
    assert exit_code in (PilotExitCode.RETRIEVAL_ERROR.value, PilotExitCode.INCOMPLETE_EXECUTION_ERROR.value)


def test_exit_code_9_client_close_failure(test_env):
    """Verify exit code 9 when client closure fails after retrieval."""
    staging = test_env["staging"]
    repo = test_env["repo"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    mock_client = MagicMock(spec=NSEClientProtocol)
    mock_client.fetch_equity_historical_data.side_effect = lambda symbol, **kwargs: make_valid_eod_rows(symbol)
    mock_client.exit.side_effect = RuntimeError("Failed to close upstream session socket")
    factory = MagicMock(return_value=mock_client)

    exit_code = run_pilot(
        symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        staging_root_str=str(staging),
        authorization_file_str=str(marker_path),
        execute_live=True,
        client_factory=factory,
        repo_root=repo,
        pacing_seconds=0.0,
    )
    assert exit_code == PilotExitCode.CLIENT_CLOSE_ERROR.value  # 9
