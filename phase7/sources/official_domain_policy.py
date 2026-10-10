"""Canonical official-host policy and strict URL validation engine for Phase 7 evidence acquisition.

Strictly enforces:
- Explicit exact-host allowlist:
    nsearchives.nseindia.com, nseindia.com, sebi.gov.in, www.nseindia.com, www.sebi.gov.in
- Strict HTTPS enforcement (no HTTP, no javascript:, no file:, no protocol-relative)
- Port restrictions: only explicit port 443 or default scheme port permitted
- Credential rejection: URLs with embedded usernames or secret tokens strictly rejected
- Hostname normalization: lowercase, ASCII IDNA conversion, stripping single terminal DNS dot
- Rejection of parent-domain suffix wildcards (*.sebi.gov.in, .sebi.gov.in)
- Safe per-hop redirect validation (max 3 redirects, no loops, no protocol downgrades)
- Attachment host authorization isolation
"""

from dataclasses import asdict, dataclass
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlsplit

CANONICAL_APPROVED_HOSTS: List[str] = [
    "nsearchives.nseindia.com",
    "nseindia.com",
    "sebi.gov.in",
    "www.nseindia.com",
    "www.sebi.gov.in",
]

CANONICAL_APPROVED_HOSTS_SET: Set[str] = set(CANONICAL_APPROVED_HOSTS)
MAX_ALLOWED_REDIRECTS: int = 3
POLICY_VERSION: str = "PHASE7_OFFICIAL_HOST_POLICY_V1"


class OfficialDomainPolicyViolation(ValueError):
    """Raised when a URL violates the canonical official-host security policy."""
    pass


class AttachmentHostNotAuthorizedError(OfficialDomainPolicyViolation):
    """Raised when an official attachment is hosted on an unapproved external domain."""
    pass


@dataclass(frozen=True)
class CanonicalUrlResult:
    original_url: str
    canonical_url: str
    scheme: str
    canonical_host: str
    port: Optional[int]
    is_valid: bool
    status: str
    policy_version: str = POLICY_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def check_for_control_characters(url: str) -> None:
    """Verify that URL contains no control characters or invalid whitespace."""
    for ch in url:
        code = ord(ch)
        if code < 32 or code == 127:
            raise OfficialDomainPolicyViolation(
                f"URL contains invalid control character (code {code}): '{url}'"
            )


def canonicalize_host(raw_host: str) -> str:
    """Normalize hostname to canonical ASCII representation."""
    if not raw_host:
        raise OfficialDomainPolicyViolation("Hostname is missing or empty.")

    # Remove trailing dot if present
    h = raw_host.strip()
    if h.endswith("."):
        h = h[:-1]

    if not h:
        raise OfficialDomainPolicyViolation("Hostname is empty after normalization.")

    # Reject wildcard indicators
    if "*" in h or h.startswith("."):
        raise OfficialDomainPolicyViolation(f"Wildcard or leading-dot host rejected: '{raw_host}'")

    # IDNA conversion and lowercase
    try:
        ascii_host = h.encode("idna").decode("ascii").lower()
    except Exception as exc:
        raise OfficialDomainPolicyViolation(f"Failed to convert hostname '{raw_host}' to ASCII IDNA: {exc}") from exc

    return ascii_host


def validate_official_url(
    url: str,
    approved_hosts: Optional[Iterable[str]] = None,
) -> CanonicalUrlResult:
    """Validate a URL against the strict canonical official-host policy."""
    if not url or not isinstance(url, str):
        raise OfficialDomainPolicyViolation("URL must be a non-empty string.")

    cleaned_url = url.strip()
    if not cleaned_url:
        raise OfficialDomainPolicyViolation("URL is empty or blank.")

    check_for_control_characters(cleaned_url)

    # Check for protocol-relative URL
    if cleaned_url.startswith("//"):
        raise OfficialDomainPolicyViolation(f"Protocol-relative URL rejected: '{url}'")

    try:
        parsed = urlsplit(cleaned_url)
    except Exception as exc:
        raise OfficialDomainPolicyViolation(f"Failed to parse URL '{url}': {exc}") from exc

    # 1. Scheme validation: strictly HTTPS
    scheme = parsed.scheme.lower() if parsed.scheme else ""
    if scheme != "https":
        raise OfficialDomainPolicyViolation(
            f"Disallowed scheme '{scheme}' in URL '{url}'. Strictly 'https' is permitted."
        )

    # 2. Credential rejection: check netloc for embedded user/auth info
    netloc = parsed.netloc
    if "@" in netloc or parsed.username is not None:
        raise OfficialDomainPolicyViolation(
            f"Embedded credentials detected and rejected in URL '{url}'."
        )

    # 3. Hostname extraction
    raw_host = parsed.hostname
    if not raw_host:
        raise OfficialDomainPolicyViolation(f"Missing hostname in URL '{url}'.")

    canonical_host = canonicalize_host(raw_host)

    # 4. Port validation: only 443 or None allowed
    port: Optional[int] = None
    try:
        port = parsed.port
    except ValueError as val_err:
        raise OfficialDomainPolicyViolation(f"Malformed port in URL '{url}': {val_err}") from val_err

    if port is not None and port != 443:
        raise OfficialDomainPolicyViolation(
            f"Port {port} is rejected in URL '{url}'. Only default port 443 is permitted."
        )

    # 5. Exact approved-host match
    allowed_set = set(approved_hosts) if approved_hosts is not None else CANONICAL_APPROVED_HOSTS_SET
    for ah in allowed_set:
        if "*" in ah or ah.startswith("."):
            raise OfficialDomainPolicyViolation(
                f"Approved-hosts set contains invalid wildcard or leading-dot entry: '{ah}'"
            )

    if canonical_host not in allowed_set:
        raise OfficialDomainPolicyViolation(
            f"Unapproved domain/host '{canonical_host}' is not in approved exact-hosts set: {sorted(allowed_set)}"
        )

    canonical_url = f"https://{canonical_host}{parsed.path}"
    if parsed.query:
        canonical_url += f"?{parsed.query}"
    if parsed.fragment:
        canonical_url += f"#{parsed.fragment}"

    return CanonicalUrlResult(
        original_url=url,
        canonical_url=canonical_url,
        scheme="https",
        canonical_host=canonical_host,
        port=port,
        is_valid=True,
        status="ACCEPTED",
        policy_version=POLICY_VERSION,
    )


def check_official_url(
    url: str,
    approved_hosts: Optional[Iterable[str]] = None,
) -> CanonicalUrlResult:
    """Check a URL and return a structured CanonicalUrlResult without raising exceptions."""
    try:
        return validate_official_url(url, approved_hosts=approved_hosts)
    except OfficialDomainPolicyViolation as violation:
        return CanonicalUrlResult(
            original_url=url,
            canonical_url="",
            scheme="",
            canonical_host="",
            port=None,
            is_valid=False,
            status=f"REJECTED: {violation}",
            policy_version=POLICY_VERSION,
        )


def validate_redirect_target(
    current_url: str,
    target_location: str,
    approved_hosts: Optional[Iterable[str]] = None,
    redirect_history: Optional[List[str]] = None,
) -> str:
    """Validate a redirect target Location against canonical redirect security policy."""
    history = redirect_history or []

    if len(history) >= MAX_ALLOWED_REDIRECTS:
        raise OfficialDomainPolicyViolation(
            f"Redirect count ({len(history)}) exceeds maximum limit of {MAX_ALLOWED_REDIRECTS}."
        )

    if not target_location or not target_location.strip():
        raise OfficialDomainPolicyViolation("Empty redirect Location header received.")

    # Resolve relative URL against current URL
    resolved_url = urljoin(current_url, target_location.strip())

    # Check for redirect loop
    if resolved_url in history or resolved_url == current_url:
        raise OfficialDomainPolicyViolation(
            f"Redirect loop detected: '{resolved_url}' has already been visited."
        )

    # Validate resolved redirect URL
    try:
        res = validate_official_url(resolved_url, approved_hosts=approved_hosts)
    except OfficialDomainPolicyViolation as exc:
        parsed_target = urlsplit(resolved_url)
        target_host = parsed_target.hostname or ""
        allowed = set(approved_hosts) if approved_hosts is not None else CANONICAL_APPROVED_HOSTS_SET
        if target_host and target_host not in allowed:
            raise AttachmentHostNotAuthorizedError(
                f"ATTACHMENT_HOST_NOT_AUTHORIZED: Redirect target host '{target_host}' is not approved."
            ) from exc
        raise

    return res.canonical_url
