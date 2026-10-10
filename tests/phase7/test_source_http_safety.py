"""Tests for Phase 7 HTTP safety guardrails, denial detection, and zero-retry enforcement."""

import pytest

from phase7.sources.http_client import (
    HTTPSafetyError,
    HTTPSafetyViolationType,
    inspect_payload_safety,
)
from phase7.sources.nse_data_fetcher_adapter import (
    NSEDataFetcherAdapter,
)


class HTMLOrCaptchaFetcher:
    """Mock fetcher returning denial or CAPTCHA payloads."""

    def __init__(self, payload: str):
        self.payload = payload

    def get_live_quote(self, symbol: str):
        return self.payload

    def get_market_status(self):
        return self.payload

    def get_historical_data(self, symbol: str, start: str, end: str):
        return [{"CH_TIMESTAMP": "2024-01-05", "CH_SERIES": "EQ", "RAW_HTML": self.payload}]


def test_http_401_authentication_failure():
    """Verify HTTP 401 raises unretryable authentication failure."""
    with pytest.raises(HTTPSafetyError) as exc_info:
        inspect_payload_safety(status_code=401)
    err = exc_info.value
    assert err.violation_type == HTTPSafetyViolationType.AUTHENTICATION_FAILURE
    assert err.status_code == 401
    assert err.retryable is False


def test_http_403_access_denied():
    """Verify HTTP 403 raises unretryable access denied exception."""
    with pytest.raises(HTTPSafetyError) as exc_info:
        inspect_payload_safety(status_code=403)
    err = exc_info.value
    assert err.violation_type == HTTPSafetyViolationType.ACCESS_DENIED
    assert err.status_code == 403
    assert err.retryable is False


def test_http_429_rate_limited():
    """Verify HTTP 429 raises unretryable rate limited exception."""
    with pytest.raises(HTTPSafetyError) as exc_info:
        inspect_payload_safety(status_code=429)
    err = exc_info.value
    assert err.violation_type == HTTPSafetyViolationType.RATE_LIMITED
    assert err.status_code == 429
    assert err.retryable is False


def test_html_payload_rejection():
    """Verify HTML response is rejected as non-JSON data."""
    html_sample = "<!DOCTYPE html><html><body><h1>Service Unavailable</h1></body></html>"
    with pytest.raises(HTTPSafetyError) as exc_info:
        inspect_payload_safety(text_content=html_sample)
    assert exc_info.value.violation_type == HTTPSafetyViolationType.HTML_PAYLOAD_REJECTED


def test_captcha_and_waf_rejection():
    """Verify CAPTCHA and WAF block signatures are detected and rejected."""
    waf_samples = [
        "Please complete the CAPTCHA to verify your identity.",
        "Error: Access Denied by Cloudflare Turnstile cf-turnstile",
        "WAF-BLOCK: Automated bot activity detected.",
        "Request blocked by Distil_Identification shield security.",
    ]
    for sample in waf_samples:
        with pytest.raises(HTTPSafetyError) as exc_info:
            inspect_payload_safety(text_content=sample)
        assert exc_info.value.violation_type == HTTPSafetyViolationType.CAPTCHA_DETECTED


def test_payload_size_limit():
    """Verify payload size exceeding maximum limit is rejected."""
    huge_bytes = 20 * 1024 * 1024  # 20 MB
    with pytest.raises(HTTPSafetyError) as exc_info:
        inspect_payload_safety(byte_length=huge_bytes, max_payload_bytes=10 * 1024 * 1024)
    assert exc_info.value.violation_type == HTTPSafetyViolationType.PAYLOAD_TOO_LARGE


def test_adapter_rejects_html_or_captcha_content():
    """Verify NSEDataFetcherAdapter detects and aborts on HTML/CAPTCHA in responses."""
    fetcher = HTMLOrCaptchaFetcher("<html><body>Access Denied - Captcha Challenge</body></html>")
    adapter = NSEDataFetcherAdapter(fetcher=fetcher)

    # Rejection on get_live_quote
    with pytest.raises(HTTPSafetyError):
        adapter.get_live_quote("RELIANCE")

    # Rejection on get_market_status
    with pytest.raises(HTTPSafetyError):
        adapter.get_market_status()

    # Rejection on fetch_historical_eod
    with pytest.raises(HTTPSafetyError):
        adapter.fetch_historical_eod("RELIANCE", "2024-01-01", "2024-01-31")
