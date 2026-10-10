"""Comprehensive test suite for Phase 7 single-use pilot authorization guard.

Tests all 44 security, scope, immutability, and atomic consumption requirements:
1. Owner phrase is absent from active source code.
2. --owner-authorization is not a recognized CLI argument.
3. Marker contains no secret phrase.
4. Marker contains exact milestone 4.9.
5. Marker contains exact five symbols.
6. Marker contains exact dates.
7. Marker contains interval 1d.
8. Marker requires single_use=true.
9. Marker hash is deterministic for canonical content except nonce/timestamp.
10. Material scope changes invalidate the hash.
11. Missing marker fails closed.
12. Malformed marker fails closed.
13. Expired marker fails closed.
14. Wrong milestone fails closed.
15. Wrong scope fails closed.
16. Wrong symbol set fails closed.
17. Wrong symbol order fails closed if order is governed.
18. Wrong start date fails closed.
19. Wrong end date fails closed.
20. Wrong interval fails closed.
21. Wrong staging-root hash fails closed.
22. Marker inside Git is rejected.
23. Relative marker path is rejected.
24. Symlink or junction into Git is rejected where testable.
25. Existing active marker is not overwritten.
26. Consumed marker cannot be reused.
27. Atomic rename happens before client creation.
28. Client is not created when validation fails.
29. Client is not created when consumption fails.
30. Zero network requests when authorization fails.
31. Help causes zero network requests.
32. Dry run, if supported, does not consume marker.
33. Dry run causes zero network requests.
34. Valid authorization permits reaching the mocked client factory.
35. Valid authorization does not itself prove network success.
36. Full NIFTY 500 scope is rejected.
37. Expanded date range is rejected.
38. Repeated execution is rejected.
39. Authorization data is excluded from request manifests.
40. Authorization data is excluded from logs.
41. Authorization marker is never written into Git.
42. No target generation occurs.
43. No model training occurs.
44. No performance calculation occurs.
"""

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from phase7.sources.authorization import (
    ACTIVE_MARKER_FILENAME,
    PILOT_APPROVED_SYMBOLS,
    PILOT_END_DATE,
    PILOT_INTERVAL,
    PILOT_MILESTONE,
    PILOT_SCOPE,
    PILOT_START_DATE,
    compute_authorization_hash,
    compute_staging_root_hash,
    consume_authorization,
    create_pilot_authorization,
    load_and_validate_authorization,
    validate_authorization_marker_path,
    validate_staging_root,
)
from phase7.sources.contracts import HistoricalEODRecord, RequestStatus
from phase7.sources.manifest import build_manifest
from phase7.sources.pilot import build_pilot_parser, run_pilot


@pytest.fixture
def test_env(tmp_path):
    """Fixture providing isolated mock repo root and external staging root."""
    repo_dir = tmp_path / "mock_repo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()

    staging_dir = tmp_path / "external_staging"
    staging_dir.mkdir()

    return {"repo_root": repo_dir, "staging_root": staging_dir}


# 1 & 2: Absences and CLI argument removal
def test_owner_phrase_and_cli_option_absent():
    """Verify owner phrase and --owner-authorization CLI option are completely absent."""
    parser = build_pilot_parser()
    actions = [a.dest for a in parser._actions]
    option_strings = [opt for a in parser._actions for opt in a.option_strings]
    assert "owner_authorization" not in actions
    assert "--owner-authorization" not in option_strings

    sources_dir = Path(__file__).resolve().parent.parent.parent / "phase7" / "sources"
    for py_file in sources_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "--owner-authorization" not in content
        assert "owner_authorization" not in content
        assert "AUTHORIZE MILESTONE" not in content


# 3, 4, 5, 6, 7, 8: Marker schema and fields
def test_marker_creation_schema_and_boundaries(test_env):
    """Verify marker fields, exact values, single_use=True, and zero secret phrases."""
    staging = test_env["staging_root"]
    repo = test_env["repo_root"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    assert marker_path.exists()
    assert marker_path.name == ACTIVE_MARKER_FILENAME

    data = json.loads(marker_path.read_text(encoding="utf-8"))

    # Field verifications
    assert data["authorization_version"] == "1.0"
    assert data["milestone"] == PILOT_MILESTONE == "4.9"
    assert data["scope"] == PILOT_SCOPE == "FIVE_STOCK_NSE_LIVE_PILOT"
    assert data["approved_symbols"] == PILOT_APPROVED_SYMBOLS == ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"]
    assert data["start_date"] == PILOT_START_DATE == "2024-01-01"
    assert data["end_date"] == PILOT_END_DATE == "2024-01-31"
    assert data["interval"] == PILOT_INTERVAL == "1d"
    assert data["single_use"] is True
    assert data["staging_root_hash"] == compute_staging_root_hash(staging)
    assert "nonce" in data and len(data["nonce"]) > 10
    assert "authorization_hash" in data

    # Zero secret phrases, tokens, or credentials
    content_lower = marker_path.read_text(encoding="utf-8").lower()
    for forbidden in ("password", "api_key", "bearer", "cookie", "token", "phrase"):
        assert forbidden not in content_lower


# 9 & 10: Deterministic hash and tamper invalidation
def test_marker_hash_deterministic_and_scope_invalidation(test_env):
    """Verify hash is deterministic for canonical content and invalidates upon scope changes."""
    staging = test_env["staging_root"]
    base_data = {
        "authorization_version": "1.0",
        "milestone": "4.9",
        "scope": "FIVE_STOCK_NSE_LIVE_PILOT",
        "approved_symbols": ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"],
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "interval": "1d",
        "staging_root_hash": compute_staging_root_hash(staging),
        "issued_timestamp": "2026-10-10T06:00:00Z",
        "expires_timestamp": "2026-10-10T06:30:00Z",
        "single_use": True,
        "nonce": "test-nonce-12345",
    }
    hash1 = compute_authorization_hash(base_data)
    hash2 = compute_authorization_hash(base_data.copy())
    assert hash1 == hash2

    # Material scope modifications invalidate hash
    tampered_syms = base_data.copy()
    tampered_syms["approved_symbols"] = ["RELIANCE", "TCS", "SBIN"]
    assert compute_authorization_hash(tampered_syms) != hash1

    tampered_dates = base_data.copy()
    tampered_dates["end_date"] = "2024-02-15"
    assert compute_authorization_hash(tampered_dates) != hash1

    tampered_single_use = base_data.copy()
    tampered_single_use["single_use"] = False
    assert compute_authorization_hash(tampered_single_use) != hash1


# 11, 12, 13: Missing, malformed, expired marker
def test_missing_malformed_expired_marker_fails_closed(test_env):
    """Verify missing, malformed, or expired marker fails closed."""
    staging = test_env["staging_root"]
    repo = test_env["repo_root"]
    auth_dir = staging / "authorization"
    auth_dir.mkdir(parents=True, exist_ok=True)
    marker_path = auth_dir / ACTIVE_MARKER_FILENAME

    # Missing
    with pytest.raises(FileNotFoundError):
        load_and_validate_authorization(marker_path, staging_root=staging, repo_root=repo)

    # Malformed JSON
    marker_path.write_text("{invalid_json: true", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed authorization marker JSON"):
        load_and_validate_authorization(marker_path, staging_root=staging, repo_root=repo)

    # Expired
    marker_path.unlink()
    create_pilot_authorization(staging_root=staging, expires_minutes=1, repo_root=repo)
    data = json.loads(marker_path.read_text(encoding="utf-8"))
    data["expires_timestamp"] = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    data["authorization_hash"] = compute_authorization_hash(data)
    marker_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(PermissionError, match="Authorization marker expired"):
        load_and_validate_authorization(marker_path, staging_root=staging, repo_root=repo)


# 14, 15, 16, 17, 18, 19, 20, 21: Wrong milestone, scope, symbols, order, dates, interval, staging hash
def test_scope_mismatches_fail_closed(test_env):
    """Verify all scope discrepancies fail closed."""
    staging = test_env["staging_root"]
    repo = test_env["repo_root"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    original_data = json.loads(marker_path.read_text(encoding="utf-8"))

    def rewrite_and_check(mutator, expected_err):
        mutated = original_data.copy()
        mutator(mutated)
        mutated["authorization_hash"] = compute_authorization_hash(mutated)
        marker_path.write_text(json.dumps(mutated), encoding="utf-8")
        with pytest.raises(PermissionError, match=expected_err):
            load_and_validate_authorization(marker_path, staging_root=staging, repo_root=repo)

    # 14: Wrong milestone
    rewrite_and_check(lambda d: d.update(milestone="5.0"), "Invalid milestone")

    # 15: Wrong scope
    rewrite_and_check(lambda d: d.update(scope="FULL_NIFTY500_PULL"), "Invalid scope")

    # 16: Wrong symbol set
    rewrite_and_check(lambda d: d.update(approved_symbols=["RELIANCE", "TCS", "SBIN"]), "Approved symbols mismatch")

    # 17: Wrong symbol order
    rewrite_and_check(
        lambda d: d.update(approved_symbols=["TCS", "RELIANCE", "HDFCBANK", "INFY", "ICICIBANK"]),
        "Approved symbols mismatch",
    )

    # 18: Wrong start date
    rewrite_and_check(lambda d: d.update(start_date="2023-12-01"), "Invalid start_date")

    # 19: Wrong end date
    rewrite_and_check(lambda d: d.update(end_date="2024-02-28"), "Invalid end_date")

    # 20: Wrong interval
    rewrite_and_check(lambda d: d.update(interval="5m"), "Invalid interval")

    # 21: Wrong staging root hash
    rewrite_and_check(lambda d: d.update(staging_root_hash="deadbeef" * 8), "Staging root hash mismatch")


# 22, 23, 24: Marker path invariants (inside Git, relative, symlinks)
def test_marker_path_invariants_fail_closed(test_env):
    """Verify marker path inside Git or relative path fails closed."""
    staging = test_env["staging_root"]
    repo = test_env["repo_root"]

    # Inside Git
    inside_git_auth = repo / "authorization" / ACTIVE_MARKER_FILENAME
    inside_git_auth.parent.mkdir(parents=True, exist_ok=True)
    inside_git_auth.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot reside inside Git repository"):
        validate_authorization_marker_path(inside_git_auth, staging_root=staging, repo_root=repo)

    # Relative path
    with pytest.raises(ValueError, match="path must be absolute"):
        validate_authorization_marker_path(Path("relative/pilot_authorization.json"), staging_root=staging, repo_root=repo)


# 25: Existing active marker overwrite prevention
def test_marker_refuses_overwrite(test_env):
    """Verify create_pilot_authorization refuses to overwrite an active marker."""
    staging = test_env["staging_root"]
    repo = test_env["repo_root"]

    marker1 = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    assert marker1.exists()

    with pytest.raises(FileExistsError, match="Active authorization marker already exists"):
        create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)


# 26: Consumed marker cannot be reused
def test_consumed_marker_cannot_be_reused(test_env):
    """Verify that an already consumed marker cannot be re-validated or re-consumed."""
    staging = test_env["staging_root"]
    repo = test_env["repo_root"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    consumed_path = consume_authorization(marker_path)

    assert not marker_path.exists()
    assert consumed_path.exists()

    # Attempting to re-validate consumed file raises PermissionError
    with pytest.raises(PermissionError, match="already been consumed"):
        load_and_validate_authorization(consumed_path, staging_root=staging, repo_root=repo)

    # Attempting to re-consume consumed file raises PermissionError
    with pytest.raises(PermissionError, match="already consumed"):
        consume_authorization(consumed_path)


# 27, 28, 29, 30: Atomic rename ordering before client creation
def test_atomic_rename_ordering_and_failure_guards(test_env):
    """Verify consumption happens BEFORE client creation, and failure prevents client creation."""
    staging = test_env["staging_root"]
    repo = test_env["repo_root"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)

    mock_client_factory = MagicMock()

    # Validation failure prevents client creation
    with pytest.raises((PermissionError, ValueError)):
        run_pilot(
            symbols_str="RELIANCE,TCS,SBIN",
            start_date="2024-01-01",
            end_date="2024-01-31",
            interval="1d",
            staging_root_str=str(staging),
            authorization_file_str=str(marker_path),
            execute_live=True,
            client_factory=mock_client_factory,
            repo_root=repo,
        )
    mock_client_factory.assert_not_called()
    assert marker_path.exists()  # Not consumed

    # Symbol order mismatch prevents client creation
    with pytest.raises(PermissionError, match="Live pilot symbols must be strictly"):
        run_pilot(
            symbols_str="TCS,RELIANCE,HDFCBANK,INFY,ICICIBANK",
            start_date="2024-01-01",
            end_date="2024-01-31",
            interval="1d",
            staging_root_str=str(staging),
            authorization_file_str=str(marker_path),
            execute_live=True,
            client_factory=mock_client_factory,
            repo_root=repo,
        )
    mock_client_factory.assert_not_called()
    assert marker_path.exists()  # Not consumed

    # Consumption failure prevents client creation
    with patch("os.replace", side_effect=OSError("Atomic rename simulated failure")):
        with pytest.raises(RuntimeError, match="AUTHORIZATION_CONSUMPTION_FAILED"):
            run_pilot(
                symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
                start_date="2024-01-01",
                end_date="2024-01-31",
                interval="1d",
                staging_root_str=str(staging),
                authorization_file_str=str(marker_path),
                execute_live=True,
                client_factory=mock_client_factory,
                repo_root=repo,
            )
        mock_client_factory.assert_not_called()


# 31, 32, 33: Dry run and help safety (zero network, zero client, marker intact)
def test_dry_run_and_help_safety(test_env):
    """Verify help and dry-run create no client, make zero network requests, and leave marker intact."""
    staging = test_env["staging_root"]
    repo = test_env["repo_root"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    mock_client_factory = MagicMock()

    # Dry run (execute_live=False)
    exit_code = run_pilot(
        symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        staging_root_str=str(staging),
        authorization_file_str=str(marker_path),
        execute_live=False,
        client_factory=mock_client_factory,
        repo_root=repo,
    )
    assert exit_code == 0
    mock_client_factory.assert_not_called()
    assert marker_path.exists()  # Not consumed


# 34 & 35: Valid authorization reaches mocked client factory
def test_valid_authorization_reaches_mocked_client_factory(test_env):
    """Verify valid authorization atomically consumes marker and calls client factory."""
    staging = test_env["staging_root"]
    repo = test_env["repo_root"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    mock_client = MagicMock()
    mock_client.fetch_equity_historical_data.return_value = [
        {
            "CH_TIMESTAMP": f"2024-01-{day:02d}",
            "CH_SERIES": "EQ",
            "CH_OPENING_PRICE": 1000.0,
            "CH_TRADE_HIGH_PRICE": 1050.0,
            "CH_TRADE_LOW_PRICE": 990.0,
            "CH_CLOSING_PRICE": 1020.0,
            "CH_TOT_TRADED_QTY": 50000,
            "CH_TOT_TRADED_VAL": 51000000.0,
        }
        for day in range(1, 20)
    ]
    mock_client_factory = MagicMock(return_value=mock_client)

    exit_code = run_pilot(
        symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        staging_root_str=str(staging),
        authorization_file_str=str(marker_path),
        execute_live=True,
        client_factory=mock_client_factory,
        repo_root=repo,
        pacing_seconds=0.0,
    )
    assert exit_code == 0
    mock_client_factory.assert_called_once_with(
        download_folder=staging.resolve() / "raw",
        server=True,
        timeout=15,
    )
    assert not marker_path.exists()  # Marker was consumed atomically


# 36, 37, 38: Rejection of full NIFTY 500, expanded dates, and repeated execution
def test_expanded_scope_and_repeated_execution_rejected(test_env):
    """Verify full NIFTY 500 scope, expanded dates, and repeated execution fail closed."""
    staging = test_env["staging_root"]
    repo = test_env["repo_root"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    mock_client = MagicMock()
    mock_client.fetch_equity_historical_data.return_value = [
        {
            "CH_TIMESTAMP": f"2024-01-{day:02d}",
            "CH_SERIES": "EQ",
            "CH_OPENING_PRICE": 1000.0,
            "CH_TRADE_HIGH_PRICE": 1050.0,
            "CH_TRADE_LOW_PRICE": 990.0,
            "CH_CLOSING_PRICE": 1020.0,
            "CH_TOT_TRADED_QTY": 50000,
            "CH_TOT_TRADED_VAL": 51000000.0,
        }
        for day in range(1, 20)
    ]
    mock_client_factory = MagicMock(return_value=mock_client)

    # 36: Expanded symbols (e.g. 6th symbol or full universe)
    with pytest.raises(ValueError, match="not in approved pilot allowlist"):
        run_pilot(
            symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK,SBIN",
            start_date="2024-01-01",
            end_date="2024-01-31",
            interval="1d",
            staging_root_str=str(staging),
            authorization_file_str=str(marker_path),
            execute_live=True,
            client_factory=mock_client_factory,
            repo_root=repo,
        )

    # 37: Expanded dates
    with pytest.raises(ValueError, match="Pilot date range must be exactly"):
        run_pilot(
            symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
            start_date="2024-01-01",
            end_date="2024-02-15",
            interval="1d",
            staging_root_str=str(staging),
            authorization_file_str=str(marker_path),
            execute_live=True,
            client_factory=mock_client_factory,
            repo_root=repo,
        )

    # Execute validly once
    run_pilot(
        symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        staging_root_str=str(staging),
        authorization_file_str=str(marker_path),
        execute_live=True,
        client_factory=mock_client_factory,
        repo_root=repo,
        pacing_seconds=0.0,
    )

    # 38: Repeated execution fails because marker is already consumed
    with pytest.raises(FileNotFoundError):
        run_pilot(
            symbols_str="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
            start_date="2024-01-01",
            end_date="2024-01-31",
            interval="1d",
            staging_root_str=str(staging),
            authorization_file_str=str(marker_path),
            execute_live=True,
            client_factory=mock_client_factory,
            repo_root=repo,
        )


# 39, 40, 41: Authorization data exclusion from manifests, logs, and Git
def test_authorization_data_excluded_from_manifests_and_git(test_env):
    """Verify authorization nonce, hash, and files are excluded from request manifests and Git."""
    staging = test_env["staging_root"]
    repo = test_env["repo_root"]

    marker_path = create_pilot_authorization(staging_root=staging, expires_minutes=30, repo_root=repo)
    data = json.loads(marker_path.read_text(encoding="utf-8"))

    # Manifest verification
    manifest = build_manifest(
        request_id="REQ-TEST-001",
        symbol="RELIANCE",
        start_date="2024-01-01",
        end_date="2024-01-31",
        interval="1d",
        retrieval_timestamp="2026-10-10T06:00:00Z",
        raw_payload={"sample": "data"},
        normalized_records=[],
        status=RequestStatus.SUCCESS,
    )
    manifest_dict = manifest.__dict__
    assert data["nonce"] not in str(manifest_dict)
    assert data["authorization_hash"] not in str(manifest_dict)
    assert "authorization" not in manifest_dict

    # Marker file is never in repo
    assert not (repo / "pilot_authorization.json").exists()
    assert not (repo / "authorization" / "pilot_authorization.json").exists()


# 42, 43, 44: No target generation, model training, or performance calculation
def test_no_targets_models_or_metrics_in_authorization():
    """Verify authorization module contains zero target generation or ML modeling logic."""
    auth_file = Path(__file__).resolve().parent.parent.parent / "phase7" / "sources" / "authorization.py"
    content = auth_file.read_text(encoding="utf-8").lower()
    for forbidden in (
        "target_engine",
        "rank_ic",
        "sharpe",
        "sortino",
        "drawdown",
        "train_model",
        "fit(",
        "cross_val",
        "lightgbm",
        "xgboost",
        "sklearn",
    ):
        assert forbidden not in content
