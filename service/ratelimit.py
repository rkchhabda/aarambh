"""Rate limiting middleware — simple in-memory sliding-window limiter.

Tier-based limits:
  free:  30 requests/min
  pro:   120 requests/min
  premium: 300 requests/min
  admin: unlimited
"""

import time
from collections import defaultdict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

TIER_LIMITS = {
    "free": 30,
    "pro": 120,
    "premium": 300,
    "admin": 999999,
    "anonymous": 20,
}

WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _get_client_id(self, request: Request) -> tuple[str, str]:
        """Return (client_id, tier) for rate-limiting key."""
        # Try API key first
        api_key = request.headers.get("x-api-key", "")
        if api_key:
            return f"apikey:{api_key[:16]}", "pro"

        # Try JWT token
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:40]
            return f"jwt:{token}", "pro"  # tier resolved later if needed

        # Fall back to IP
        ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        return f"ip:{ip}", "anonymous"

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health and static
        if request.url.path in ("/health", "/docs", "/openapi.json") or request.url.path.startswith("/static"):
            return await call_next(request)

        client_id, tier = self._get_client_id(request)
        limit = TIER_LIMITS.get(tier, TIER_LIMITS["anonymous"])

        now = time.time()
        cutoff = now - WINDOW_SECONDS
        self._hits[client_id] = [t for t in self._hits[client_id] if t > cutoff]

        if len(self._hits[client_id]) >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded ({limit} requests per minute). Upgrade your plan for higher limits.",
            )

        self._hits[client_id].append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - len(self._hits[client_id])))
        return response
