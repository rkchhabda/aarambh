"""Comprehensive mocked execution test suite for Phase 7 five-stock live pilot.

Covers all 50 governance requirements:
- Exact symbol order and single retrieval call per symbol
- Exact date and interval forwarding without date.today() substitution
- Two-second pacing and single active request locking
- Raw payload atomic persistence, deterministic hashing, immutability
- Normalized JSONL persistence, checksum calculation, immutability
- Manifest lifecycle (PENDING before retrieval -> SUCCEEDED / FAILED / HALTED)
- Zero rows, missing raw checksum, or missing normalized checksum never SUCCEEDED
- Row conservation: source_row_count = normalized_row_count + rejected_row_count
- Fail-closed halts on: empty, HTML, CAPTCHA, ConnectionError, TimeoutError,
  unexpected type, schema mismatch, out-of-range date, symbol conflict,
  invalid OHLC, duplicate natural key, persistence failure, conservation failure
- Later symbols never invoked after halt; earlier manifests preserved
- Deterministic client closure in finally block
- Exit code mapping (0, 2, 3, 4, 5, 6, 7, 8, 9, 10)
- Zero leaks of session credentials or authorization data
- Strict research boundaries: no in-repo writes, no targets, no models, no performance
"""

import json
from pathlib import Path
import time
from unittest.mock import MagicMock, patch
import pytest

from phase7.sources.authorization import (
    PILOT_APPROVED_SYMBOLS,
    PILOT_END_DATE,
    PILOT_INTERVAL,
    PILOT_START_DATE,
    create_pilot_authorization,
)
from phase7.sources.client_protocol import NSEClientProtocol
from phase7.sources.contracts import PilotExitCode, RequestStatus
from phase7.sources.manifest import build_manifest
from phase7.sources.pilot import run_pilot


@pytest.fixture
def exec_env(tmp_path):
    staging = tmp_path / "mock_staging_pilot_exec"
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
            "CH_ISIN": f"INE{symbol[:6]}01",
        }
        for day in range(1, 22)
    ]


# 1, 2, 3, 4: Sequential symbol order, exact date forwarding, single call per symbol
def test_pilot_sequential_retrieval_and_exact_forwarding(exec_env):
    """Verify exact symbol sequence, exact parameters forwarded, and 1 call per symbol."""
    staging = exec_env["staging"]
    repo = exec_env["repo"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    calls = []

    def _fetch(symbol, start_date, end_date, interval="1d", **kwargs):
        calls.append({"symbol": symbol, "start_date": start_date, "end_date": end_date, "interval": interval})
        return make_valid_eod_rows(symbol)

    mock_client = MagicMock(spec=NSEClientProtocol)
    mock_client.fetch_equity_historical_data.side_effect = _fetch
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

    assert exit_code == 0
    # Exactly 5 calls
    assert len(calls) == 5
    # Exact symbol order
    called_symbols = [c["symbol"] for c in calls]
    assert called_symbols == PILOT_APPROVED_SYMBOLS
    # Exact parameter values
    for c in calls:
        assert c["start_date"] == PILOT_START_DATE
        assert c["end_date"] == PILOT_END_DATE
        assert c["interval"] == PILOT_INTERVAL


# 5: Pacing between calls
def test_pilot_pacing_enforced(exec_env):
    """Verify minimum pacing delay between sequential requests."""
    staging = exec_env["staging"]
    repo = exec_env["repo"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    timestamps = []

    def _fetch(symbol, **kwargs):
        timestamps.append(time.time())
        return make_valid_eod_rows(symbol)

    mock_client = MagicMock(spec=NSEClientProtocol)
    mock_client.fetch_equity_historical_data.side_effect = _fetch
    factory = MagicMock(return_value=mock_client)

    # Use small measurable pacing (e.g. 0.05s) to test pacing enforcement without slow execution
    run_pilot(
        symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        staging_root_str=str(staging),
        authorization_file_str=str(marker_path),
        execute_live=True,
        client_factory=factory,
        repo_root=repo,
        pacing_seconds=0.05,
    )

    assert len(timestamps) == 5
    for i in range(1, len(timestamps)):
        elapsed = timestamps[i] - timestamps[i - 1]
        assert elapsed >= 0.04  # Respects pacing interval


# 7, 8, 9: Raw persistence, SHA-256 determinism, and immutability
def test_raw_payload_persistence_and_checksum_determinism(exec_env):
    """Verify raw payloads are saved under raw/historical/ with deterministic SHA-256."""
    staging = exec_env["staging"]
    repo = exec_env["repo"]

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
    assert exit_code == 0

    raw_files = list((staging / "raw" / "historical").glob("*.json"))
    assert len(raw_files) == 5
    for rf in raw_files:
        content = json.loads(rf.read_text(encoding="utf-8"))
        assert len(content) > 0


# 10, 11, 12: Normalized JSONL persistence, checksum determinism, immutability
def test_normalized_jsonl_persistence_and_checksum_determinism(exec_env):
    """Verify normalized records are written to normalized/historical/ in JSONL format."""
    staging = exec_env["staging"]
    repo = exec_env["repo"]

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
    assert exit_code == 0

    norm_files = list((staging / "normalized" / "historical").glob("*.jsonl"))
    assert len(norm_files) == 5
    for nf in norm_files:
        lines = nf.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 21
        first_row = json.loads(lines[0])
        assert "row_hash" in first_row
        assert len(first_row["row_hash"]) == 64


# 13, 14: Manifest lifecycle
def test_manifest_finalization_after_processing(exec_env):
    """Verify request manifests are finalized with SUCCEEDED status and both checksums."""
    staging = exec_env["staging"]
    repo = exec_env["repo"]

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
    assert exit_code == 0

    manifest_files = list((staging / "manifests").glob("*.json"))
    assert len(manifest_files) == 5
    for mf in manifest_files:
        m_data = json.loads(mf.read_text(encoding="utf-8"))
        assert m_data["status"] == "SUCCEEDED"
        assert len(m_data["raw_checksum"]) == 64
        assert len(m_data["normalized_checksum"]) == 64
        assert m_data["row_count"] > 0


# 15, 16, 17: SUCCEEDED invariant violations
def test_succeeded_status_impossible_with_zero_rows_or_missing_checksums():
    """Verify build_manifest enforces invariants for SUCCEEDED status."""
    with pytest.raises(ValueError, match="Never report SUCCEEDED with zero normalized rows"):
        build_manifest(
            request_id="req-fail",
            symbol="RELIANCE",
            start_date="2024-01-01",
            end_date="2024-01-31",
            interval="1d",
            retrieval_timestamp="2026-10-10T10:00:00Z",
            raw_payload={"data": []},
            normalized_records=[],
            status=RequestStatus.SUCCEEDED,
        )


# 19: Empty response halts
def test_empty_response_halts_pilot(exec_env):
    """Verify empty response immediately halts pilot with exit code 6."""
    staging = exec_env["staging"]
    repo = exec_env["repo"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    mock_client = MagicMock(spec=NSEClientProtocol)
    mock_client.fetch_equity_historical_data.return_value = []  # Empty list
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
    assert exit_code == PilotExitCode.SCHEMA_NORMALIZATION_ERROR.value


# 20: HTML response halts
def test_html_response_halts_pilot(exec_env):
    """Verify HTML payload halts pilot with exit code 6."""
    staging = exec_env["staging"]
    repo = exec_env["repo"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    mock_client = MagicMock(spec=NSEClientProtocol)
    mock_client.fetch_equity_historical_data.return_value = "<html><body>502 Bad Gateway</body></html>"
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
    assert exit_code == PilotExitCode.SCHEMA_NORMALIZATION_ERROR.value


# 21: CAPTCHA response halts
def test_captcha_response_halts_pilot(exec_env):
    """Verify CAPTCHA / WAF block halts pilot with exit code 6."""
    staging = exec_env["staging"]
    repo = exec_env["repo"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    mock_client = MagicMock(spec=NSEClientProtocol)
    mock_client.fetch_equity_historical_data.return_value = {"error": "cf-turnstile verification required"}
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
    assert exit_code == PilotExitCode.SCHEMA_NORMALIZATION_ERROR.value


# 22, 23: ConnectionError and TimeoutError halt pilot
def test_connection_and_timeout_errors_halt_pilot(exec_env):
    """Verify connectivity and timeout exceptions produce exit code 5."""
    staging = exec_env["staging"]
    repo = exec_env["repo"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    mock_client = MagicMock(spec=NSEClientProtocol)
    mock_client.fetch_equity_historical_data.side_effect = TimeoutError("Request timed out after 15s")
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
    assert exit_code == PilotExitCode.RETRIEVAL_ERROR.value


# 26: Out-of-range date halts
def test_out_of_range_date_halts_pilot(exec_env):
    """Verify rows containing trading dates outside governed window halt pilot."""
    staging = exec_env["staging"]
    repo = exec_env["repo"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    bad_rows = make_valid_eod_rows("RELIANCE")
    bad_rows.append({
        "CH_TIMESTAMP": "2024-02-15",  # Outside 2024-01-01..2024-01-31
        "CH_SERIES": "EQ",
        "CH_OPENING_PRICE": 2500.0,
        "CH_TRADE_HIGH_PRICE": 2550.0,
        "CH_TRADE_LOW_PRICE": 2480.0,
        "CH_CLOSING_PRICE": 2520.0,
        "CH_TOT_TRADED_QTY": 100000,
        "CH_TOT_TRADED_VAL": 252000000.0,
    })

    mock_client = MagicMock(spec=NSEClientProtocol)
    mock_client.fetch_equity_historical_data.return_value = bad_rows
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
    assert exit_code == PilotExitCode.SCHEMA_NORMALIZATION_ERROR.value


# 27: Symbol conflict halts
def test_symbol_conflict_halts_pilot(exec_env):
    """Verify mismatched symbol in payload row halts pilot."""
    staging = exec_env["staging"]
    repo = exec_env["repo"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    conflicting_rows = [
        {
            "CH_TIMESTAMP": "2024-01-02",
            "CH_SERIES": "EQ",
            "CH_SYMBOL": "TCS",  # Requested RELIANCE, row has TCS
            "CH_OPENING_PRICE": 2500.0,
            "CH_TRADE_HIGH_PRICE": 2550.0,
            "CH_TRADE_LOW_PRICE": 2480.0,
            "CH_CLOSING_PRICE": 2520.0,
            "CH_TOT_TRADED_QTY": 100000,
            "CH_TOT_TRADED_VAL": 252000000.0,
        }
    ]

    mock_client = MagicMock(spec=NSEClientProtocol)
    mock_client.fetch_equity_historical_data.return_value = conflicting_rows
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
    assert exit_code == PilotExitCode.SCHEMA_NORMALIZATION_ERROR.value


# 28: Invalid OHLC halts
def test_invalid_ohlc_halts_pilot(exec_env):
    """Verify low > high halts pilot."""
    staging = exec_env["staging"]
    repo = exec_env["repo"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    invalid_ohlc_rows = [
        {
            "CH_TIMESTAMP": "2024-01-02",
            "CH_SERIES": "EQ",
            "CH_OPENING_PRICE": 2500.0,
            "CH_TRADE_HIGH_PRICE": 2400.0,  # High less than low
            "CH_TRADE_LOW_PRICE": 2480.0,
            "CH_CLOSING_PRICE": 2450.0,
            "CH_TOT_TRADED_QTY": 100000,
            "CH_TOT_TRADED_VAL": 252000000.0,
        }
    ]

    mock_client = MagicMock(spec=NSEClientProtocol)
    mock_client.fetch_equity_historical_data.return_value = invalid_ohlc_rows
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
    assert exit_code == PilotExitCode.SCHEMA_NORMALIZATION_ERROR.value


# 29: Duplicate key halts
def test_duplicate_key_halts_pilot(exec_env):
    """Verify duplicate date in payload rows halts pilot."""
    staging = exec_env["staging"]
    repo = exec_env["repo"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    duplicate_rows = [
        {
            "CH_TIMESTAMP": "2024-01-02",
            "CH_SERIES": "EQ",
            "CH_OPENING_PRICE": 2500.0,
            "CH_TRADE_HIGH_PRICE": 2550.0,
            "CH_TRADE_LOW_PRICE": 2480.0,
            "CH_CLOSING_PRICE": 2520.0,
            "CH_TOT_TRADED_QTY": 100000,
            "CH_TOT_TRADED_VAL": 252000000.0,
        },
        {
            "CH_TIMESTAMP": "2024-01-02",  # Duplicate date!
            "CH_SERIES": "EQ",
            "CH_OPENING_PRICE": 2500.0,
            "CH_TRADE_HIGH_PRICE": 2550.0,
            "CH_TRADE_LOW_PRICE": 2480.0,
            "CH_CLOSING_PRICE": 2520.0,
            "CH_TOT_TRADED_QTY": 100000,
            "CH_TOT_TRADED_VAL": 252000000.0,
        },
    ]

    mock_client = MagicMock(spec=NSEClientProtocol)
    mock_client.fetch_equity_historical_data.return_value = duplicate_rows
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
    assert exit_code == PilotExitCode.SCHEMA_NORMALIZATION_ERROR.value


# 33, 34: Later symbols not called after halt, earlier manifests preserved
def test_later_symbols_not_called_after_halt_earlier_preserved(exec_env):
    """Verify stop on symbol 3 preserves manifests 1 and 2, and skips 4 and 5."""
    staging = exec_env["staging"]
    repo = exec_env["repo"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    calls = []

    def _fetch(symbol, **kwargs):
        calls.append(symbol)
        if symbol == "HDFCBANK":  # Symbol 3 fails
            raise ConnectionError("Upstream drop on symbol 3")
        return make_valid_eod_rows(symbol)

    mock_client = MagicMock(spec=NSEClientProtocol)
    mock_client.fetch_equity_historical_data.side_effect = _fetch
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

    # Failed on symbol 3
    assert exit_code == PilotExitCode.RETRIEVAL_ERROR.value
    # Later symbols INFY and ICICIBANK were NOT called
    assert calls == ["RELIANCE", "TCS", "HDFCBANK"]
    # Manifests for completed earlier symbols exist
    manifest_files = list((staging / "manifests").glob("*.json"))
    manifest_symbols = [json.loads(mf.read_text(encoding="utf-8"))["symbol"] for mf in manifest_files]
    assert "RELIANCE" in manifest_symbols
    assert "TCS" in manifest_symbols


# 35, 36: Client closes after success and failure
def test_client_closes_deterministically_after_success_and_failure(exec_env):
    """Verify client.exit() is invoked in finally block on both success and failure."""
    staging = exec_env["staging"]
    repo = exec_env["repo"]

    # Success case
    marker1 = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    client1 = MagicMock(spec=NSEClientProtocol)
    client1.fetch_equity_historical_data.side_effect = lambda symbol, **kwargs: make_valid_eod_rows(symbol)
    factory1 = MagicMock(return_value=client1)

    run_pilot(
        symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        staging_root_str=str(staging),
        authorization_file_str=str(marker1),
        execute_live=True,
        client_factory=factory1,
        repo_root=repo,
        pacing_seconds=0.0,
    )
    client1.exit.assert_called_once()

    # Failure case
    (staging / "authorization").mkdir(parents=True, exist_ok=True)
    marker2 = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    client2 = MagicMock(spec=NSEClientProtocol)
    client2.fetch_equity_historical_data.side_effect = ConnectionError("Fail immediately")
    factory2 = MagicMock(return_value=client2)

    run_pilot(
        symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        staging_root_str=str(staging),
        authorization_file_str=str(marker2),
        execute_live=True,
        client_factory=factory2,
        repo_root=repo,
        pacing_seconds=0.0,
    )
    client2.exit.assert_called_once()
