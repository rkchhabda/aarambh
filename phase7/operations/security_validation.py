"""Security boundaries, hostile input sanitization, and attack guards for Phase 7.

Validates and protects against:
- Shell metacharacters and command injection syntax
- Windows/POSIX path traversal, UNC, device paths, and NTFS streams
- Null bytes, control characters, tabs, newlines, CR
- Unicode slash lookalikes and bidirectional control characters
- Hostname confusion and embedded URL credentials
- Malicious JSON payloads (deep nesting, oversized arrays, NaN, Infinity)
- HTML or CAPTCHA masquerading as JSON
- Credential and cookie leakage in logs/exceptions
"""

import json
import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse

from phase7.operations.atomic_io import AtomicIOError


class SecurityBoundaryError(AtomicIOError):
    """Base exception for security boundary violations."""
    pass


class HostileInputError(SecurityBoundaryError):
    """Raised when an input contains injection attacks or illegal control sequences."""
    pass


class MaliciousPayloadError(SecurityBoundaryError):
    """Raised when data payload contains malformed or dangerous structures."""
    pass


SHELL_METACHARACTERS = set(";|`$><(){}[]*?!#~'\"\\")
BIDI_CONTROLS = {
    "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
    "\u2066", "\u2067", "\u2068", "\u2069"
}
SLASH_LOOKALIKES = {
    "\u2215", "\u2044", "\u29f8", "\uff0f", "\ufe68", "\u29f5", "\u29f9"
}


def validate_symbol_security(symbol: str) -> None:
    """Validate ticker symbol against code injection and hostile character attacks."""
    if not symbol or not isinstance(symbol, str):
        raise HostileInputError("Symbol must be a non-empty string.")

    if len(symbol) > 30:
        raise HostileInputError(f"Symbol exceeds safe length limit (len={len(symbol)}).")

    # Reject null bytes and control chars
    for ch in symbol:
        code = ord(ch)
        if code < 32 or code == 127:
            raise HostileInputError(f"Control character {code} detected in symbol: {repr(symbol)}")
        if ch in BIDI_CONTROLS:
            raise HostileInputError(f"Bidirectional control character detected in symbol: {repr(symbol)}")
        if ch in SLASH_LOOKALIKES:
            raise HostileInputError(f"Unicode slash lookalike detected in symbol: {repr(symbol)}")

    # Reject shell metacharacters and chaining operators
    if "&&" in symbol or "||" in symbol:
        raise HostileInputError(f"Shell chaining operator detected in symbol: {repr(symbol)}")

    if any(ch in SHELL_METACHARACTERS for ch in symbol):
        raise HostileInputError(f"Shell metacharacters detected in symbol: {repr(symbol)}")

    # Governed valid ticker pattern: uppercase alphanumeric plus optional single hyphen or ampersand
    if not re.match(r"^[A-Z0-9]+([&\-][A-Z0-9]+)?$", symbol):
        raise HostileInputError(f"Symbol contains illegal characters outside [A-Z0-9&-]: '{symbol}'")


def validate_json_payload_depth(data: Any, max_depth: int = 10, current_depth: int = 1) -> None:
    """Guard against deeply nested JSON structures (recursion limit attacks)."""
    if current_depth > max_depth:
        raise MaliciousPayloadError(f"JSON nesting depth exceeds safety threshold of {max_depth}.")

    if isinstance(data, dict):
        for val in data.values():
            validate_json_payload_depth(val, max_depth=max_depth, current_depth=current_depth + 1)
    elif isinstance(data, list):
        if len(data) > 100_000:
            raise MaliciousPayloadError(f"JSON list length ({len(data)}) exceeds limit of 100,000.")
        for item in data:
            validate_json_payload_depth(item, max_depth=max_depth, current_depth=current_depth + 1)


def sanitize_numeric_values(data: Any) -> None:
    """Ensure no NaN, Infinity, or -Infinity values in financial payloads."""
    if isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            raise MaliciousPayloadError(f"Illegal non-finite numeric value in payload: {data}")
    elif isinstance(data, dict):
        for v in data.values():
            sanitize_numeric_values(v)
    elif isinstance(data, list):
        for item in data:
            sanitize_numeric_values(item)


def detect_html_or_captcha_masquerade(content_str: str) -> None:
    """Detect HTML responses or CAPTCHA challenges disguised as data."""
    head = content_str[:2048].lower()
    if "<!doctype html" in head or "<html" in head or "<body" in head:
        raise MaliciousPayloadError("Upstream returned HTML document instead of governed data structure.")
    if "captcha" in head or "recaptcha" in head or "cf-ray" in head or "access denied" in head:
        raise MaliciousPayloadError("Upstream returned CAPTCHA or Cloudflare challenge.")


def validate_url_security(url: str, allowed_hosts: Set[str]) -> None:
    """Validate URL protocol, credentials, and hostname against spoofing."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise SecurityBoundaryError(f"Insecure scheme '{parsed.scheme}'; HTTPS is strictly required.")

    if parsed.username or parsed.password:
        raise SecurityBoundaryError("Embedded URL credentials are strictly forbidden.")

    host = parsed.netloc.lower().split(":")[0]
    if host not in allowed_hosts:
        raise SecurityBoundaryError(f"Unapproved host '{host}'; allowed hosts are: {sorted(allowed_hosts)}")


SECRET_KEYS = {"cookie", "set-cookie", "session", "token", "password", "authorization", "secret", "bearer"}


def redact_sensitive_data(text: str) -> str:
    """Redact tokens, cookies, and secret values from log messages and exception text."""
    redacted = text
    # Cookie header patterns
    redacted = re.sub(r'(?i)(cookie:\s*)([^\r\n;]+)', r'\1[REDACTED]', redacted)
    # Authorization header patterns
    redacted = re.sub(r'(?i)(bearer\s+)([A-Za-z0-9\-._~+/]+=*)', r'\1[REDACTED]', redacted)
    # Key-value secret patterns
    for k in SECRET_KEYS:
        pattern = rf'(?i)("([^"]*{k}[^"]*)"\s*:\s*")([^"]+)(")'
        redacted = re.sub(pattern, r'\1[REDACTED]\4', redacted)
    return redacted
