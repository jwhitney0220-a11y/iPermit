"""Production-hardening middleware for the API (S07-01).

Three concerns the consultant-facing surface needs before it can be reached
from a browser outside ``localhost``:

* **CORS** — explicit allow-list for browser origins (Starlette's
  ``CORSMiddleware``; the wildcard ``*`` is rejected outside local by
  ``validate_security`` because credentialed requests forbid it).
* **Trusted hosts** — drops requests with a forged ``Host`` header before
  they reach a route (Starlette's ``TrustedHostMiddleware``).
* **Request IDs** — every request gets an ``X-Request-ID`` propagated to the
  response so a consultant report and an API log line can be cross-referenced.
* **Login rate-limit** — a fixed-window per-IP counter applied to
  ``POST /api/v1/auth/login`` so a stolen email list can't be sprayed against
  the password-grant endpoint. Process-local for the first slice; the
  ``LoginRateLimiter`` protocol lets a shared-state implementation (Redis)
  slot in for multi-instance staging/prod without touching the router.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Protocol

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .envelope import PROBLEM_CONTENT_TYPE, Problem
from .settings import Settings

REQUEST_ID_HEADER = "X-Request-ID"
_LOGIN_PATH = "/api/v1/auth/login"


class LoginRateLimiter(Protocol):
    """Seam for the login rate-limit so Redis/etc can slot in later."""

    def hit(self, client_ip: str) -> bool:
        """Record a hit; return ``True`` if the caller is over the limit."""


class _FixedWindowLimiter:
    """In-memory, per-process fixed-window counter (one-minute windows)."""

    def __init__(self, max_per_minute: int) -> None:
        self._max = max_per_minute
        self._hits: dict[str, list[float]] = defaultdict(list)

    def hit(self, client_ip: str) -> bool:
        now = time.monotonic()
        window_start = now - 60.0
        hits = [t for t in self._hits[client_ip] if t >= window_start]
        hits.append(now)
        self._hits[client_ip] = hits
        return len(hits) > self._max


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Generate or propagate an ``X-Request-ID`` per request/response."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


class LoginRateLimitMiddleware(BaseHTTPMiddleware):
    """429 the ``POST /api/v1/auth/login`` endpoint past the configured rate."""

    def __init__(self, app: FastAPI, limiter: LoginRateLimiter) -> None:
        super().__init__(app)
        self._limiter = limiter

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method == "POST" and request.url.path == _LOGIN_PATH:
            client_ip = request.client.host if request.client else "unknown"
            if self._limiter.hit(client_ip):
                return _rate_limited_response(str(request.url))
        return await call_next(request)


def _rate_limited_response(instance: str) -> JSONResponse:
    """Render the 429 problem-details body for an over-limit login attempt."""
    problem = Problem(
        title="Too many login attempts",
        status=429,
        detail="Login is rate-limited per client IP; retry shortly.",
        instance=instance,
    )
    return JSONResponse(
        status_code=429,
        content=problem.model_dump(exclude_none=True),
        media_type=PROBLEM_CONTENT_TYPE,
        headers={"Retry-After": "60"},
    )


def install_middleware(app: FastAPI, settings: Settings) -> None:
    """Wire CORS, trusted-host, request-id, and login rate-limit middleware.

    Starlette runs middleware **last-added-first**, so the order here is the
    *outermost-first* reading order: a request first crosses TrustedHost,
    then CORS, then RequestId, then the login rate-limit, then the routes.
    """
    limiter = _FixedWindowLimiter(settings.auth_login_rate_per_minute)
    app.add_middleware(LoginRateLimitMiddleware, limiter=limiter)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.api_trusted_hosts,
    )


__all__ = [
    "REQUEST_ID_HEADER",
    "LoginRateLimitMiddleware",
    "LoginRateLimiter",
    "RequestIdMiddleware",
    "install_middleware",
]
