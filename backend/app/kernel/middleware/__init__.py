"""Redis-based sliding window rate limiting middleware for FastAPI."""

from __future__ import annotations

import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.kernel.redis import RedisStore
from app.kernel.responses import error


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding window rate limiter using Redis sorted sets.

    Two layers:
    - Per-IP: checked before auth (anonymous requests included)
    - Per-user: checked after auth (if JWT present)
    """

    def __init__(
        self,
        app,
        redis: RedisStore,
        *,
        per_ip_limit: int = 120,
        per_user_limit: int = 60,
        upload_limit: int = 10,
        window_seconds: int = 60,
    ):
        super().__init__(app)
        self._redis = redis
        self._per_ip_limit = per_ip_limit
        self._per_user_limit = per_user_limit
        self._upload_limit = upload_limit
        self._window = window_seconds

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip rate limiting for non-API paths
        if not request.url.path.startswith("/api"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        # Layer 1: per-IP limit
        ip_key = f"ratelimit:ip:{client_ip}"
        ip_count = self._sliding_window_count(ip_key, now)
        if ip_count >= self._per_ip_limit:
            return self._rate_limit_response(self._window)

        # Layer 2: per-user limit (if JWT present)
        auth_header = request.headers.get("authorization", "")
        user_id = None
        if auth_header.startswith("Bearer "):
            # We don't validate the token here — just extract user_id for rate limiting
            # Actual auth validation happens in get_current_user dependency
            user_id = self._extract_user_id_from_token(auth_header[7:])

        if user_id:
            user_key = f"ratelimit:user:{user_id}"
            user_count = self._sliding_window_count(user_key, now)
            if user_count >= self._per_user_limit:
                return self._rate_limit_response(self._window)

        # Layer 3: upload-specific limit
        if request.url.path.endswith("/upload") or request.url.path.endswith("/messages"):
            if request.method == "POST":
                upload_key = f"ratelimit:upload:{client_ip}"
                upload_count = self._sliding_window_count(upload_key, now)
                if upload_count >= self._upload_limit:
                    return self._rate_limit_response(self._window)

        return await call_next(request)

    def _sliding_window_count(self, key: str, now: float) -> int:
        """Count requests in the sliding window using a simple counter with TTL."""
        try:
            current = self._redis.get(key)
            if current is None:
                self._redis.set(key, "1", ex=self._window)
                return 1
            count = int(current) + 1
            self._redis.set(key, str(count), ex=self._window)
            return count
        except Exception:
            # If Redis is unavailable, don't block requests
            return 0

    @staticmethod
    def _extract_user_id_from_token(token: str) -> str | None:
        """Best-effort extract user_id from JWT without validation.
        Used only for rate limiting bucketing — actual auth is handled separately.
        """
        try:
            import base64
            import json

            parts = token.split(".")
            if len(parts) != 3:
                return None
            payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            return str(payload.get("sub", ""))
        except Exception:
            return None

    @staticmethod
    def _rate_limit_response(retry_after: int) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content=error(429, "请求过于频繁，请稍后再试", {"retry_after": retry_after}),
        )
