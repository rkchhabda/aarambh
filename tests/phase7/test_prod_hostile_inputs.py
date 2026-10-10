"""Production-readiness hardening tests: Security Boundaries and Hostile Inputs (Workstream E).

Module docstring:
- Protected production invariants: All external inputs, URLs, JSON payloads, ticker symbols, and paths
  must be strictly validated and sanitized. Injections (shell, path traversal, NTFS streams, control chars,
  Unicode bidi/slashes, credential leakage) must be rejected fail-closed with zero network calls.
- Fault classes covered: Command injection, PowerShell metacharacters, path traversal, UNC/device paths,
  NTFS alternate data streams, Unicode spoofing, deeply nested JSON, NaN/Inf floats, and HTML/CAPTCHA masquerading.
- Why tests are not duplicates: Existing Phase 7 tests verify standard symbol validation;
  these tests systematically challenge the parser against specific hostile attack payloads and security boundaries.
"""

from datetime import datetime, timezone
import json
import math
from pathlib import Path

import pytest

from phase7.operations.atomic_io import (
    FilenameValidationError,
    StagingPathViolation,
    validate_filename,
    validate_safe_staging_path,
)
from phase7.operations.security_validation import (
    HostileInputError,
    MaliciousPayloadError,
    SecurityBoundaryError,
    detect_html_or_captcha_masquerade,
    redact_sensitive_data,
    sanitize_numeric_values,
    validate_json_payload_depth,
    validate_symbol_security,
    validate_url_security,
)

pytestmark = [pytest.mark.unit]


# 1. Command-injection characters in a symbol
@pytest.mark.parametrize("hostile_sym", [
    "RELIANCE;rm -rf",
    "TCS&&calc",
])
def test_command_injection_symbols_rejected(hostile_sym: str):
    with pytest.raises(HostileInputError):
        validate_symbol_security(hostile_sym)


# 2. PowerShell metacharacters in a symbol
@pytest.mark.parametrize("ps_char", ["$", ";", "`"])
def test_powershell_metacharacters_rejected(ps_char: str):
    with pytest.raises(HostileInputError):
        validate_symbol_security(f"SYM{ps_char}1")


# 3. Windows path traversal in path validation
@pytest.mark.parametrize("traversal", [
    "..\\..\\windows\\system32",
    "staging\\..\\..\\secret.txt",
])
def test_windows_path_traversal_rejected(traversal: str, repo_root: Path):
    with pytest.raises(StagingPathViolation):
        validate_safe_staging_path(traversal, repo_root=repo_root)


# 4. POSIX path traversal in path validation
@pytest.mark.parametrize("posix_traversal", [
    "../../etc/passwd",
    "staging/../../secret.txt",
])
def test_posix_path_traversal_rejected(posix_traversal: str, repo_root: Path):
    with pytest.raises(StagingPathViolation):
        validate_safe_staging_path(posix_traversal, repo_root=repo_root)


# 5. UNC network paths rejected
@pytest.mark.parametrize("unc", [
    r"\\192.168.1.1\share\evidence.csv",
    r"//remote-server/share/file.json",
])
def test_unc_paths_rejected(unc: str, repo_root: Path):
    with pytest.raises(StagingPathViolation, match="UNC network paths are strictly prohibited"):
        validate_safe_staging_path(unc, repo_root=repo_root)


# 6. Device paths rejected
@pytest.mark.parametrize("dev", [
    r"\\.\COM1",
    r"\\?\C:\secret",
])
def test_device_paths_rejected(dev: str, repo_root: Path):
    with pytest.raises(StagingPathViolation, match="Device paths are strictly prohibited"):
        validate_safe_staging_path(dev, repo_root=repo_root)


# 7. NTFS alternate data stream rejected
def test_ntfs_alternate_data_stream_rejected():
    with pytest.raises(FilenameValidationError, match="NTFS alternate data stream"):
        validate_filename("manifest.json:hidden_stream")


# 8. Null byte in symbol rejected
def test_null_byte_in_symbol_rejected():
    with pytest.raises(HostileInputError, match="Control character"):
        validate_symbol_security("RELIANCE\x00")


# 9. Newline injection in symbol rejected
def test_newline_in_symbol_rejected():
    with pytest.raises(HostileInputError, match="Control character"):
        validate_symbol_security("RELIANCE\nEVIL")


# 10. Carriage-return injection in symbol rejected
def test_carriage_return_in_symbol_rejected():
    with pytest.raises(HostileInputError, match="Control character"):
        validate_symbol_security("RELIANCE\rEVIL")


# 11. Tab injection in symbol rejected
def test_tab_in_symbol_rejected():
    with pytest.raises(HostileInputError, match="Control character"):
        validate_symbol_security("RELIANCE\tEVIL")


# 12. Unicode slash lookalikes in symbol rejected
@pytest.mark.parametrize("slash_char", ["\u2215", "\uff0f"])
def test_unicode_slash_lookalikes_rejected(slash_char: str):
    with pytest.raises(HostileInputError, match="Unicode slash lookalike"):
        validate_symbol_security(f"RELIANCE{slash_char}SUB")


# 13. Bidirectional control characters rejected
@pytest.mark.parametrize("bidi", ["\u202e", "\u202a"])
def test_bidirectional_control_characters_rejected(bidi: str):
    with pytest.raises(HostileInputError, match="Bidirectional control character"):
        validate_symbol_security(f"REL{bidi}IANCE")


# 14. Extremely long symbol rejected
def test_extremely_long_symbol_rejected():
    with pytest.raises(HostileInputError, match="exceeds safe length limit"):
        validate_symbol_security("A" * 31)


# 15. Valid symbols accepted
@pytest.mark.parametrize("good_sym", ["RELIANCE", "M&M", "BAJAJ-AUTO"])
def test_valid_symbols_accepted(good_sym: str):
    validate_symbol_security(good_sym)  # Should not raise


# 16. Malicious JSON nesting depth guard
def test_malicious_json_depth_guard():
    nested = {"level": 1}
    curr = nested
    for i in range(20):
        curr["child"] = {"level": i + 2}
        curr = curr["child"]

    with pytest.raises(MaliciousPayloadError, match="JSON nesting depth exceeds safety threshold"):
        validate_json_payload_depth(nested, max_depth=10)


# 17. Safe JSON depth accepted
def test_safe_json_depth_accepted():
    data = {"a": {"b": {"c": 123}}}
    validate_json_payload_depth(data, max_depth=10)


# 18. Extremely large JSON list guard
def test_oversized_json_list_guard():
    oversized = [1] * 100_001
    with pytest.raises(MaliciousPayloadError, match="JSON list length .* exceeds limit"):
        validate_json_payload_depth(oversized, max_depth=10)


# 19. NaN numeric payload values rejected
def test_nan_payload_values_rejected():
    payload = {"symbol": "SYN0001", "close": float("nan")}
    with pytest.raises(MaliciousPayloadError, match="Illegal non-finite numeric value"):
        sanitize_numeric_values(payload)


# 20. Positive infinity rejected
def test_infinity_payload_values_rejected():
    payload = {"symbol": "SYN0001", "close": float("inf")}
    with pytest.raises(MaliciousPayloadError, match="Illegal non-finite numeric value"):
        sanitize_numeric_values(payload)


# 21. Negative infinity rejected
def test_negative_infinity_payload_values_rejected():
    payload = {"symbol": "SYN0001", "close": float("-inf")}
    with pytest.raises(MaliciousPayloadError, match="Illegal non-finite numeric value"):
        sanitize_numeric_values(payload)


# 22. Finite numeric values accepted
def test_finite_numeric_values_accepted():
    payload = {"symbol": "SYN0001", "close": 2500.50, "volume": 100000}
    sanitize_numeric_values(payload)


# 23. HTML masquerading as JSON response detected
def test_html_masquerade_detected():
    html_resp = "<!DOCTYPE html><html><head><title>Error</title></head><body>Server Error</body></html>"
    with pytest.raises(MaliciousPayloadError, match="Upstream returned HTML document"):
        detect_html_or_captcha_masquerade(html_resp)


# 24. CAPTCHA challenge masquerading as data detected
def test_captcha_challenge_detected():
    captcha_resp = '{"status": "blocked", "message": "Please solve CAPTCHA challenge to proceed"}'
    with pytest.raises(MaliciousPayloadError, match="Upstream returned CAPTCHA"):
        detect_html_or_captcha_masquerade(captcha_resp)


# 25. Cookie header redaction in strings
def test_cookie_redaction():
    log_text = "Sent request with headers: Cookie: nsit=SECRET123; ak_bmsc=ABC;"
    redacted = redact_sensitive_data(log_text)
    assert "SECRET123" not in redacted
    assert "[REDACTED]" in redacted


# 26. Bearer token authorization redaction
def test_bearer_token_redaction():
    msg = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret"
    redacted = redact_sensitive_data(msg)
    assert "eyJhb" not in redacted
    assert "Bearer [REDACTED]" in redacted


# 27. Secret key-value redaction in JSON strings
def test_secret_key_value_redaction():
    json_str = '{"user": "admin", "token": "secret_token_val_999"}'
    redacted = redact_sensitive_data(json_str)
    assert "secret_token_val_999" not in redacted
    assert '"token": "[REDACTED]"' in redacted


# 28. Insecure HTTP downgrade rejected
def test_http_downgrade_rejected():
    allowed_hosts = {"nsearchives.nseindia.com", "www.sebi.gov.in"}
    with pytest.raises(SecurityBoundaryError, match="Insecure scheme 'http'"):
        validate_url_security("http://www.sebi.gov.in/filings.pdf", allowed_hosts)


# 29. Embedded URL credentials rejected
def test_embedded_url_credentials_rejected():
    allowed_hosts = {"nsearchives.nseindia.com", "www.sebi.gov.in"}
    with pytest.raises(SecurityBoundaryError, match="Embedded URL credentials are strictly forbidden"):
        validate_url_security("https://user:password@www.sebi.gov.in/filings.pdf", allowed_hosts)


# 30. Unapproved host rejected
def test_unapproved_host_rejected():
    allowed_hosts = {"nsearchives.nseindia.com", "www.sebi.gov.in"}
    with pytest.raises(SecurityBoundaryError, match="Unapproved host 'evil.com'"):
        validate_url_security("https://evil.com/fake_circular.pdf", allowed_hosts)


# 31. Hostname confusion / spoofing rejected
def test_hostname_confusion_rejected():
    allowed_hosts = {"www.sebi.gov.in"}
    with pytest.raises(SecurityBoundaryError, match="Unapproved host 'www.sebi.gov.in.attacker.com'"):
        validate_url_security("https://www.sebi.gov.in.attacker.com/fake.pdf", allowed_hosts)


# 32. Approved canonical host accepted
def test_approved_host_accepted():
    allowed_hosts = {"nsearchives.nseindia.com", "www.sebi.gov.in"}
    validate_url_security("https://www.sebi.gov.in/filings/doc.pdf", allowed_hosts)
    validate_url_security("https://nsearchives.nseindia.com/circulars/doc.pdf", allowed_hosts)


# 33. Manifest path injection attempt rejected
def test_manifest_path_injection_rejected(repo_root: Path):
    hostile_path = r"/staging/../../system32/manifest.json"
    with pytest.raises(StagingPathViolation):
        validate_safe_staging_path(hostile_path, repo_root=repo_root)


# 34. Checkpoint path injection attempt rejected
def test_checkpoint_path_injection_rejected(repo_root: Path):
    hostile_path = r"\\attacker\share\checkpoint.json"
    with pytest.raises(StagingPathViolation):
        validate_safe_staging_path(hostile_path, repo_root=repo_root)


# 35. Empty symbol rejected
def test_empty_symbol_rejected():
    with pytest.raises(HostileInputError, match="must be a non-empty string"):
        validate_symbol_security("")


# 36. Non-string symbol rejected
def test_non_string_symbol_rejected():
    with pytest.raises(HostileInputError, match="must be a non-empty string"):
        validate_symbol_security(None)  # type: ignore


# 37. Lowercase symbol rejected (governed tickers are uppercase)
def test_lowercase_symbol_rejected():
    with pytest.raises(HostileInputError, match="illegal characters"):
        validate_symbol_security("reliance")


# 38. Symbol with spaces rejected
def test_symbol_with_spaces_rejected():
    with pytest.raises(HostileInputError, match="illegal characters"):
        validate_symbol_security("RELIANCE LTD")


# 39. Password redaction in logs
def test_password_redaction():
    text = '{"username": "svc", "password": "SuperSecretPassword123!"}'
    redacted = redact_sensitive_data(text)
    assert "SuperSecretPassword123!" not in redacted
    assert '"password": "[REDACTED]"' in redacted


# 40. Repository boundary escape attempt inside data dir
def test_repository_boundary_escape_data_dir(repo_root: Path):
    target = repo_root / "data" / "leak.csv"
    with pytest.raises(StagingPathViolation, match="cannot reside within Git repository"):
        validate_safe_staging_path(target, repo_root=repo_root)
