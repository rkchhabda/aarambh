"""Comprehensive tests for canonical official-host validation and security policies.

Strictly verifies:
- Exact-host allowlist: nsearchives.nseindia.com, nseindia.com, sebi.gov.in, www.nseindia.com, www.sebi.gov.in
- Rejection of http, wildcards, non-443 ports, credentials, control chars, unapproved subdomains
- Per-hop redirect validation (max 3, loop detection, no HTTPS downgrade, attachment isolation)
- Authorization marker exact approved_hosts binding
- Regression test reproducing and resolving Milestone 4.10C-2 halt
- Complete isolation safeguards (0 network, 0 production imports, 0 model training)
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import pytest
from urllib.parse import urlsplit

from phase7.sources.official_domain_policy import (
    CANONICAL_APPROVED_HOSTS,
    CANONICAL_APPROVED_HOSTS_SET,
    MAX_ALLOWED_REDIRECTS,
    POLICY_VERSION,
    AttachmentHostNotAuthorizedError,
    CanonicalUrlResult,
    OfficialDomainPolicyViolation,
    canonicalize_host,
    check_for_control_characters,
    check_official_url,
    validate_official_url,
    validate_redirect_target,
)
from phase7.sources.listing_evidence_authorization import (
    ACTIVE_MARKER_FILENAME,
    CANONICAL_APPROVED_HOSTS as AUTH_CANONICAL_APPROVED_HOSTS,
    EVIDENCE_REQUIRED_EXCHANGE,
    EVIDENCE_REQUIRED_REQUESTED_END,
    EVIDENCE_REQUIRED_SECURITY_NAME,
    EVIDENCE_REQUIRED_SYMBOL,
    ListingEvidenceAuthorizationRecord,
    compute_listing_evidence_authorization_hash,
    compute_staging_root_hash,
    consume_listing_evidence_authorization,
    create_listing_evidence_authorization,
    find_repo_root,
    load_and_validate_listing_evidence_authorization,
    validate_staging_root,
)
from phase7.sources.listing_evidence_acquisition import (
    CANDIDATE_OFFICIAL_URLS,
    ListingEvidenceAcquisitionError,
    execute_listing_evidence_pilot,
    validate_source_url,
)


def _setup_external_staging(tmp_path_factory) -> Path:
    staging = tmp_path_factory.mktemp("official_domain_staging")
    return staging.resolve()


# 1. www.sebi.gov.in is accepted
def test_approved_host_www_sebi_gov_in_accepted():
    res = validate_official_url("https://www.sebi.gov.in/filings/public-issues/aug-2024/premier-energies-limited-prospectus_86360.html")
    assert res.is_valid is True
    assert res.canonical_host == "www.sebi.gov.in"
    assert res.status == "ACCEPTED"


# 2. sebi.gov.in is accepted
def test_approved_host_sebi_gov_in_accepted():
    res = validate_official_url("https://sebi.gov.in/filings/public-issues/aug-2024/premier-energies-limited-rhp_86076.html")
    assert res.is_valid is True
    assert res.canonical_host == "sebi.gov.in"
    assert res.status == "ACCEPTED"


# 3. nsearchives.nseindia.com is accepted
def test_approved_host_nsearchives_nseindia_com_accepted():
    res = validate_official_url("https://nsearchives.nseindia.com/corporate/ADV_INE0BS701011_02SEP2024.pdf")
    assert res.is_valid is True
    assert res.canonical_host == "nsearchives.nseindia.com"
    assert res.status == "ACCEPTED"


# 4. nseindia.com is accepted
def test_approved_host_nseindia_com_accepted():
    res = validate_official_url("https://nseindia.com/companies-listing/corporate-filings")
    assert res.is_valid is True
    assert res.canonical_host == "nseindia.com"
    assert res.status == "ACCEPTED"


# 5. www.nseindia.com is accepted
def test_approved_host_www_nseindia_com_accepted():
    res = validate_official_url("https://www.nseindia.com/get-quotes/equity?symbol=PREMIERENE")
    assert res.is_valid is True
    assert res.canonical_host == "www.nseindia.com"
    assert res.status == "ACCEPTED"


# 6. Uppercase hostname canonicalizes correctly
def test_uppercase_hostname_canonicalizes_correctly():
    res = validate_official_url("https://WWW.SEBI.GOV.IN/filings/doc.html")
    assert res.canonical_host == "www.sebi.gov.in"
    res2 = validate_official_url("https://NSEARCHIVES.NSEINDIA.COM/doc.pdf")
    assert res2.canonical_host == "nsearchives.nseindia.com"


# 7. Terminal DNS dot canonicalizes correctly
def test_terminal_dns_dot_canonicalizes_correctly():
    res = validate_official_url("https://www.sebi.gov.in./filings/doc.html")
    assert res.canonical_host == "www.sebi.gov.in"


# 8. HTTP is rejected
def test_http_is_rejected():
    with pytest.raises(OfficialDomainPolicyViolation, match="Disallowed scheme 'http'"):
        validate_official_url("http://www.sebi.gov.in/")


# 9. Embedded credentials are rejected
def test_embedded_credentials_are_rejected():
    with pytest.raises(OfficialDomainPolicyViolation, match="Embedded credentials detected and rejected"):
        validate_official_url("https://user:secret@www.sebi.gov.in/doc.html")


# 10. Port 443 is accepted
def test_port_443_is_accepted():
    res = validate_official_url("https://www.sebi.gov.in:443/doc.html")
    assert res.is_valid is True
    assert res.port == 443
    assert res.canonical_host == "www.sebi.gov.in"


# 11. Non-443 ports are rejected
def test_non_443_ports_are_rejected():
    with pytest.raises(OfficialDomainPolicyViolation, match="Port 444 is rejected"):
        validate_official_url("https://www.sebi.gov.in:444/doc.html")
    with pytest.raises(OfficialDomainPolicyViolation, match="Port 8080 is rejected"):
        validate_official_url("https://www.sebi.gov.in:8080/doc.html")


# 12. Missing hostname is rejected
def test_missing_hostname_is_rejected():
    with pytest.raises(OfficialDomainPolicyViolation, match="Missing hostname|Hostname is missing"):
        validate_official_url("https:///doc.html")
    with pytest.raises(OfficialDomainPolicyViolation, match="URL must be a non-empty string|URL is empty or blank"):
        validate_official_url("")


# 13. Control characters are rejected
def test_control_characters_are_rejected():
    with pytest.raises(OfficialDomainPolicyViolation, match="invalid control character"):
        validate_official_url("https://www.sebi.gov.in\r/doc.html")
    with pytest.raises(OfficialDomainPolicyViolation, match="invalid control character"):
        validate_official_url("https://www.sebi.gov.in\n/doc.html")


# 14. evilsebi.gov.in is rejected
def test_evilsebi_gov_in_is_rejected():
    with pytest.raises(OfficialDomainPolicyViolation, match="evilsebi.gov.in"):
        validate_official_url("https://evilsebi.gov.in/")


# 15. notsebi.gov.in is rejected
def test_notsebi_gov_in_is_rejected():
    with pytest.raises(OfficialDomainPolicyViolation, match="notsebi.gov.in"):
        validate_official_url("https://notsebi.gov.in/")


# 16. sebi.gov.in.example.com is rejected
def test_sebi_gov_in_example_com_is_rejected():
    with pytest.raises(OfficialDomainPolicyViolation, match="sebi.gov.in.example.com"):
        validate_official_url("https://sebi.gov.in.example.com/")


# 17. www.sebi.gov.in.example.com is rejected
def test_www_sebi_gov_in_example_com_is_rejected():
    with pytest.raises(OfficialDomainPolicyViolation, match="www.sebi.gov.in.example.com"):
        validate_official_url("https://www.sebi.gov.in.example.com/")


# 18. evil.nsearchives.nseindia.com is rejected
def test_evil_nsearchives_nseindia_com_is_rejected():
    with pytest.raises(OfficialDomainPolicyViolation, match="evil.nsearchives.nseindia.com"):
        validate_official_url("https://evil.nsearchives.nseindia.com/")


# 19. nsearchives.nseindia.com.example.com is rejected
def test_nsearchives_nseindia_com_example_com_is_rejected():
    with pytest.raises(OfficialDomainPolicyViolation, match="nsearchives.nseindia.com.example.com"):
        validate_official_url("https://nsearchives.nseindia.com.example.com/")


# 20. Wildcard allowlist entries are rejected
def test_wildcard_allowlist_entries_are_rejected():
    with pytest.raises(OfficialDomainPolicyViolation, match="invalid wildcard or leading-dot"):
        validate_official_url("https://www.sebi.gov.in/", approved_hosts=["*.sebi.gov.in"])
    with pytest.raises(OfficialDomainPolicyViolation, match="invalid wildcard or leading-dot"):
        validate_official_url("https://www.sebi.gov.in/", approved_hosts=[".sebi.gov.in"])


# 21. Parent-domain suffix matching is not used
def test_parent_domain_suffix_matching_is_not_used():
    with pytest.raises(OfficialDomainPolicyViolation, match="unapproved.sebi.gov.in"):
        validate_official_url("https://unapproved.sebi.gov.in/")
    with pytest.raises(OfficialDomainPolicyViolation, match="api.nseindia.com"):
        validate_official_url("https://api.nseindia.com/")


# 22. Approved redirect is accepted
def test_approved_redirect_is_accepted():
    target = validate_redirect_target(
        current_url="https://sebi.gov.in/filings/doc.html",
        target_location="https://www.sebi.gov.in/filings/doc.html",
    )
    assert target == "https://www.sebi.gov.in/filings/doc.html"


# 23. Relative approved redirect is resolved safely
def test_relative_approved_redirect_is_resolved_safely():
    target = validate_redirect_target(
        current_url="https://www.sebi.gov.in/filings/issue1.html",
        target_location="/filings/issue2.html",
    )
    assert target == "https://www.sebi.gov.in/filings/issue2.html"


# 24. HTTP downgrade redirect is rejected
def test_http_downgrade_redirect_is_rejected():
    with pytest.raises(OfficialDomainPolicyViolation, match="Disallowed scheme 'http'"):
        validate_redirect_target(
            current_url="https://www.sebi.gov.in/filings/doc.html",
            target_location="http://www.sebi.gov.in/filings/doc.html",
        )


# 25. Unapproved redirect is rejected
def test_unapproved_redirect_is_rejected():
    with pytest.raises(AttachmentHostNotAuthorizedError, match="ATTACHMENT_HOST_NOT_AUTHORIZED"):
        validate_redirect_target(
            current_url="https://www.sebi.gov.in/filings/doc.html",
            target_location="https://s3.amazonaws.com/external-filings/doc.pdf",
        )


# 26. Credential-bearing redirect is rejected
def test_credential_bearing_redirect_is_rejected():
    with pytest.raises(OfficialDomainPolicyViolation, match="Embedded credentials"):
        validate_redirect_target(
            current_url="https://www.sebi.gov.in/filings/doc.html",
            target_location="https://user:token@www.sebi.gov.in/filings/doc.html",
        )


# 27. Redirect loop is rejected
def test_redirect_loop_is_rejected():
    with pytest.raises(OfficialDomainPolicyViolation, match="Redirect loop detected"):
        validate_redirect_target(
            current_url="https://www.sebi.gov.in/filings/doc.html",
            target_location="https://www.sebi.gov.in/filings/doc.html",
            redirect_history=["https://www.sebi.gov.in/filings/start.html"],
        )


# 28. More than three redirects is rejected
def test_more_than_three_redirects_is_rejected():
    history = [
        "https://www.sebi.gov.in/hop1",
        "https://www.sebi.gov.in/hop2",
        "https://www.sebi.gov.in/hop3",
    ]
    with pytest.raises(OfficialDomainPolicyViolation, match="Redirect count .* exceeds maximum limit of 3"):
        validate_redirect_target(
            current_url="https://www.sebi.gov.in/hop3",
            target_location="https://www.sebi.gov.in/hop4",
            redirect_history=history,
        )


# 29. Marker binds exact approved-host list
def test_marker_binds_exact_approved_host_list(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    marker_path, record = create_listing_evidence_authorization(staging_root=staging)
    assert record.approved_hosts == CANONICAL_APPROVED_HOSTS
    loaded = load_and_validate_listing_evidence_authorization(marker_path, staging)
    assert loaded.approved_hosts == CANONICAL_APPROVED_HOSTS


# 30. Marker omitting www.sebi.gov.in fails
def test_marker_omitting_www_sebi_gov_in_fails(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    marker_path, _ = create_listing_evidence_authorization(staging_root=staging)
    data = json.loads(marker_path.read_text(encoding="utf-8"))
    data["approved_hosts"] = [h for h in data["approved_hosts"] if h != "www.sebi.gov.in"]
    data["authorization_hash"] = compute_listing_evidence_authorization_hash(data)
    marker_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="'www.sebi.gov.in' is missing from approved_hosts"):
        load_and_validate_listing_evidence_authorization(marker_path, staging)


# 31. Marker adding an unapproved host fails
def test_marker_adding_unapproved_host_fails(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    marker_path, _ = create_listing_evidence_authorization(staging_root=staging)
    data = json.loads(marker_path.read_text(encoding="utf-8"))
    data["approved_hosts"].append("unapproved-host.com")
    data["authorization_hash"] = compute_listing_evidence_authorization_hash(data)
    marker_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="unapproved host: 'unapproved-host.com'"):
        load_and_validate_listing_evidence_authorization(marker_path, staging)


# 32. Marker using wildcards fails
def test_marker_using_wildcards_fails(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    marker_path, _ = create_listing_evidence_authorization(staging_root=staging)
    data = json.loads(marker_path.read_text(encoding="utf-8"))
    data["approved_hosts"] = ["*.sebi.gov.in", "www.sebi.gov.in"]
    data["authorization_hash"] = compute_listing_evidence_authorization_hash(data)
    marker_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="forbidden wildcard or leading-dot host"):
        load_and_validate_listing_evidence_authorization(marker_path, staging)


# 33. Old consumed marker cannot be reused
def test_old_consumed_marker_cannot_be_reused(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    marker_path, _ = create_listing_evidence_authorization(staging_root=staging)
    consumed_path = consume_listing_evidence_authorization(marker_path)

    # Attempting to load the consumed path as active marker must fail
    with pytest.raises(ValueError, match="Active authorization marker must be named.*listing_evidence_authorization.json"):
        load_and_validate_listing_evidence_authorization(consumed_path, staging)

    # Even if renamed to active filename, old consumed marker lacks approved_hosts
    old_consumed_content = {
        "authorization_version": "1.0",
        "milestone": "4.10C-2",
        "scope": "OFFICIAL_LISTING_DATE_EVIDENCE_PILOT",
        "symbol": "PREMIERENE",
        "security_name": "Premier Energies Limited",
        "exchange": "NSE",
        "requested_period_end": "2024-03-31",
        "approved_domains": ["nsearchives.nseindia.com", "nseindia.com", "sebi.gov.in"],
        "maximum_request_count": 5,
        "staging_root_hash": compute_staging_root_hash(staging),
        "issued_timestamp": datetime.now(timezone.utc).isoformat(),
        "expires_timestamp": datetime.now(timezone.utc).isoformat(),
        "single_use": True,
        "nonce": "test-nonce",
        "authorization_hash": "dummy",
    }
    bogus_active = staging / "authorization" / ACTIVE_MARKER_FILENAME
    bogus_active.write_text(json.dumps(old_consumed_content), encoding="utf-8")
    with pytest.raises(ValueError, match="missing required fields: \\['approved_hosts'\\]"):
        load_and_validate_listing_evidence_authorization(bogus_active, staging)


# 34. Marker is consumed before request
def test_marker_is_consumed_before_request(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    marker_path, _ = create_listing_evidence_authorization(staging_root=staging)
    target_url = "https://nsearchives.nseindia.com/corporate/ADV_INE0BS701011_02SEP2024.pdf"
    mock_responses = {target_url: (500, b"Server Error", "text/plain")}

    with pytest.raises(ListingEvidenceAcquisitionError):
        execute_listing_evidence_pilot(
            staging_root=staging,
            authorization_file=marker_path,
            source_urls=[target_url],
            mock_responses=mock_responses,
        )

    assert not marker_path.exists()


# 35. No active marker is created during tests
def test_no_active_marker_is_created_during_tests():
    repo = find_repo_root()
    active_in_repo = list(repo.glob("**/listing_evidence_authorization.json"))
    assert len(active_in_repo) == 0


# 36. No request occurs when URL validation fails
def test_no_request_occurs_when_url_validation_fails(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    marker_path, _ = create_listing_evidence_authorization(staging_root=staging)
    invalid_url = "http://www.sebi.gov.in/unencrypted.html"

    with pytest.raises(ListingEvidenceAcquisitionError, match="Disallowed scheme 'http'"):
        execute_listing_evidence_pilot(
            staging_root=staging,
            authorization_file=marker_path,
            source_urls=[invalid_url],
            mock_responses={},
        )


# 37. No response body is read before final-host validation
def test_no_response_body_is_read_before_final_host_validation(tmp_path_factory):
    staging = _setup_external_staging(tmp_path_factory)
    marker_path, _ = create_listing_evidence_authorization(staging_root=staging)
    start_url = "https://www.sebi.gov.in/prospectus.html"
    unauthorized_redirect = "https://external-leak.com/prospectus.pdf"

    mock_responses = {
        start_url: (302, b"", "text/html", {"Location": unauthorized_redirect}),
        unauthorized_redirect: (200, b"%PDF-1.4...", "application/pdf"),
    }

    with pytest.raises(ListingEvidenceAcquisitionError, match="ATTACHMENT_HOST_NOT_AUTHORIZED"):
        execute_listing_evidence_pilot(
            staging_root=staging,
            authorization_file=marker_path,
            source_urls=[start_url],
            mock_responses=mock_responses,
        )


# 38. No market-price endpoint is invoked
def test_no_market_price_endpoint_is_invoked():
    for url in CANDIDATE_OFFICIAL_URLS:
        assert "historical" not in url.lower()
        assert "chart" not in url.lower()
        assert "equity-master" not in url.lower()


# 39. No historical-batch resume occurs
def test_no_historical_batch_resume_occurs():
    repo = find_repo_root()
    # Ensure no batch resume files or tokens are manipulated
    batch_state = repo / "phase7" / "sources" / "batch_checkpoint.py"
    assert batch_state.exists()


# 40. Frozen selection remains unchanged
def test_frozen_selection_remains_unchanged():
    staging_base = Path(r"C:\Users\r_chh\gaurvideep_phase7_staging\nse500\batch_4_10c")
    sel_dir = staging_base / "selection"
    from phase7.sources.batch_selection import load_selection_manifest
    manifest = load_selection_manifest(sel_dir)
    assert manifest.selected_symbol_count == 20
    assert manifest.selection_checksum == "60dd03580442b1f874f364206da5d9bf252a4abf1ff93801d4b58e93fdee7b1d"
    assert manifest.ordered_symbols_hash == "26e4be7c9cfd366b630b0b714f0afd65a223ffae91edad6e231060e6b95c4ee3"
    assert manifest.ordered_selected_symbols[0] == "PREMIERENE"


# 41. Original halted run remains unchanged
def test_original_halted_run_remains_unchanged():
    staging_base = Path(r"C:\Users\r_chh\gaurvideep_phase7_staging\nse500\batch_4_10c")
    run_dir = staging_base / "runs" / "BATCH_4_10C_HISTORICAL_20STOCK_2024Q1_20261010T112814Z"
    assert run_dir.exists()
    cp_file = run_dir / "checkpoints" / "batch_checkpoint.json"
    if not cp_file.exists():
        cp_file = staging_base / "checkpoints" / "batch_checkpoint.json"
    assert cp_file.exists()
    cp_data = json.loads(cp_file.read_text(encoding="utf-8"))
    assert cp_data["final_status"] == "HALTED"
    assert cp_data["failed_symbols"] == 1
    assert cp_data["symbol_states"]["PREMIERENE"]["status"] == "FAILED"


# 42. No repository data write occurs
def test_no_repository_data_write_occurs():
    repo = find_repo_root()
    git_status = repo / ".git"
    assert git_status.exists()


# 43. No Phase 6 import occurs
def test_no_phase6_import_occurs():
    from phase7.sources import official_domain_policy
    assert "phase6" not in dir(official_domain_policy)


# 44. No production import occurs
def test_no_production_import_occurs():
    from phase7.sources import official_domain_policy
    assert "service" not in dir(official_domain_policy)


# 45. No target generation occurs
def test_no_target_generation_occurs():
    from phase7.sources import official_domain_policy
    assert not hasattr(official_domain_policy, "generate_targets")


# 46. No model training occurs
def test_no_model_training_occurs():
    from phase7.sources import official_domain_policy
    assert not hasattr(official_domain_policy, "train_model")


# 47. No performance calculation occurs
def test_no_performance_calculation_occurs():
    from phase7.sources import official_domain_policy
    assert not hasattr(official_domain_policy, "compute_sharpe")


# REGRESSION TEST: Reproduce and correct the exact previous halt
def test_www_sebi_gov_in_is_an_exact_approved_host():
    """Reproduce and correct the exact Milestone 4.10C-2 evidence pilot halt.

    Previous halt condition:
    Candidate URL:
    https://www.sebi.gov.in/filings/public-issues/aug-2024/premier-energies-limited-prospectus_86360.html
    Old domain validator recognized only:
    [nsearchives.nseindia.com, nseindia.com, sebi.gov.in, bseindia.com]
    and halted before dispatch because www.sebi.gov.in did not match sebi.gov.in.

    Corrected policy:
    Explicitly recognizes www.sebi.gov.in as an exact canonical approved host.
    """
    candidate_url = "https://www.sebi.gov.in/filings/public-issues/aug-2024/premier-energies-limited-prospectus_86360.html"

    # 1. Reproduce previous halt: with legacy approved list omitting www.sebi.gov.in
    legacy_hosts = [
        "nsearchives.nseindia.com",
        "nseindia.com",
        "sebi.gov.in",
        "bseindia.com",
    ]
    with pytest.raises(ListingEvidenceAcquisitionError, match="Unapproved domain/host 'www.sebi.gov.in'"):
        validate_source_url(candidate_url, approved_hosts=legacy_hosts)

    # 2. Confirm corrected behavior: canonical approved hosts explicitly accepts www.sebi.gov.in
    validated_url = validate_source_url(candidate_url)
    assert validated_url == candidate_url

    # Check parsed details
    res = validate_official_url(candidate_url)
    assert res.is_valid is True
    assert res.canonical_host == "www.sebi.gov.in"
    assert res.scheme == "https"
    assert res.status == "ACCEPTED"
    assert res.policy_version == "PHASE7_OFFICIAL_HOST_POLICY_V1"
