"""Phase 7 HTTP safety enforcement and transport guardrails.

Enforces zero-retry on 401/403/429, CAPTCHA detection, HTML rejection,
and response size limits.
"""

from enum import Enum
import re
from typing import Any, Dict, Optional, Protocol, runtime_checkable


class HTTPSafetyViolationType(str, Enum):
    AUTHENTICATION_FAILURE = "AUTHENTICATION_FAILURE"  # HTTP 401
    ACCESS_DENIED = "ACCESS_DENIED"                    # HTTP 403
    RATE_LIMITED = "RATE_LIMITED"                      # HTTP 429
    CAPTCHA_DETECTED = "CAPTCHA_DETECTED"
    HTML_PAYLOAD_REJECTED = "HTML_PAYLOAD_REJECTED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    MALFORMED_PAYLOAD = "MALFORMED_PAYLOAD"
    TIMEOUT = "TIMEOUT"


class HTTPSafetyError(RuntimeError):
    """Base exception for HTTP safety violations."""

    def __init__(self, violation_type: HTTPSafetyViolationType, message: str, status_code: Optional[int] = None):
        super().__init__(f"[{violation_type.value}] {message}")
        self.violation_type = violation_type
        self.status_code = status_code
        self.retryable = False  # Strict fail-closed: NO retries on safety violations


CAPTCHA_PATTERNS = [
    re.compile(r"captcha", re.IGNORECASE),
    re.compile(r"cf-turnstile", re.IGNORECASE),
    re.compile(r"recaptcha", re.IGNORECASE),
    re.compile(r"access denied", re.IGNORECASE),
    re.compile(r"waf-block", re.IGNORECASE),
    re.compile(r"distil_identification", re.IGNORECASE),
    re.compile(r"shield.*security", re.IGNORECASE),
]

HTML_START_PATTERNS = [
    re.compile(r"^\s*<!doctype\s+html", re.IGNORECASE),
    re.compile(r"^\s*<html", re.IGNORECASE),
]

DEFAULT_MAX_PAYLOAD_BYTES = 15 * 1024 * 1024  # 15 MB limit


def inspect_payload_safety(
    status_code: Optional[int] = None,
    content_type: Optional[str] = None,
    text_content: Optional[str] = None,
    byte_length: Optional[int] = None,
    max_payload_bytes: int = DEFAULT_MAX_PAYLOAD_BYTES,
) -> None:
    """Validate HTTP response attributes against Phase 7 safety invariants.

    Raises HTTPSafetyError immediately upon detecting safety violations.
    All safety exceptions are marked retryable=False.
    """
    if status_code is not None:
        if status_code == 401:
            raise HTTPSafetyError(
                HTTPSafetyViolationType.AUTHENTICATION_FAILURE,
                "HTTP 401 Unauthorized encountered. Automated retry prohibited.",
                status_code=401,
            )
        if status_code == 403:
            raise HTTPSafetyError(
                HTTPSafetyViolationType.ACCESS_DENIED,
                "HTTP 403 Forbidden / Access Denied. Automated retry prohibited.",
                status_code=403,
            )
        if status_code == 429:
            raise HTTPSafetyError(
                HTTPSafetyViolationType.RATE_LIMITED,
                "HTTP 429 Rate Limit / Throttling encountered. Automated retry prohibited.",
                status_code=429,
            )

    if byte_length is not None and byte_length > max_payload_bytes:
        raise HTTPSafetyError(
            HTTPSafetyViolationType.PAYLOAD_TOO_LARGE,
            f"Response payload size {byte_length} bytes exceeds maximum allowed limit {max_payload_bytes} bytes.",
        )

    if text_content:
        # Check payload size from string length
        if len(text_content.encode("utf-8")) > max_payload_bytes:
            raise HTTPSafetyError(
                HTTPSafetyViolationType.PAYLOAD_TOO_LARGE,
                f"Response text size exceeds maximum allowed limit {max_payload_bytes} bytes.",
            )

        # Check for HTML when API expected JSON/structured
        for pattern in HTML_START_PATTERNS:
            if pattern.search(text_content):
                raise HTTPSafetyError(
                    HTTPSafetyViolationType.HTML_PAYLOAD_REJECTED,
                    "HTML payload returned instead of structured JSON data.",
                )

        # Check for CAPTCHA / WAF / access denial markers in body
        for pattern in CAPTCHA_PATTERNS:
            if pattern.search(text_content):
                raise HTTPSafetyError(
                    HTTPSafetyViolationType.CAPTCHA_DETECTED,
                    f"Access denial or CAPTCHA marker detected in response body: pattern '{pattern.pattern}'.",
                )


@runtime_checkable
class SafeHTTPTransportProtocol(Protocol):
    """Protocol for safely isolated HTTP transport."""

    def get(self, url: str, headers: Optional[Dict[str, str]] = None, timeout: float = 10.0) -> Any:
        ...
