"""Observability surface for the API (S07-03, SAAS-07).

Three pieces production operators need before the platform leaves local:

* **Structured access logs** — every HTTP request emits one JSON line with
  method, path, status, duration, and the per-request id. JSON keeps the
  log shape stable for a log-shipper without forcing operators to grep
  free-form text. Configured globally on import via :func:`configure_logging`.
* **Readiness probe** (``/readyz``) — separate from ``/healthz`` (which is
  liveness): only goes green when the DB session can ``SELECT 1``. Lets a
  load-balancer drain an instance whose database backend is unreachable
  without killing the process.
* **Prometheus metrics** (``/metrics``) — process-local counters and a
  duration histogram (request count, in-flight gauge, latency by route +
  status). Tiny in-process implementation so a fresh deploy does not
  require the ``prometheus-client`` dependency before observability is
  even configured; a real exporter slots in behind the same endpoint.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from threading import Lock
from typing import Any

from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from .db import get_session

ACCESS_LOGGER = "ipermit.access"
APP_LOGGER = "ipermit.app"

#: Default histogram buckets in milliseconds — coarse but useful for a SaaS
#: serving p50/p95 over web-rate traffic. Aligned with common dashboards
#: (Datadog/Grafana) so a real exporter swap doesn't change SLO graphs.
_LATENCY_BUCKETS_MS = (5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000)


class JsonFormatter(logging.Formatter):
    """Render a log record as a single JSON object (one line per event)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extras = getattr(record, "extras", None)
        if isinstance(extras, dict):
            payload.update(extras)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging(level: str = "info") -> None:
    """Install the JSON formatter on stdout (idempotent on repeat calls)."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


class _Metrics:
    """In-process counter + latency histogram (Prometheus text exposition)."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._req_count: dict[tuple[str, str, int], int] = defaultdict(int)
        self._req_latency_sum: dict[tuple[str, str], float] = defaultdict(float)
        self._req_latency_buckets: dict[tuple[str, str, int], int] = defaultdict(int)
        self._in_flight: int = 0

    def observe(self, method: str, route: str, status: int, ms: float) -> None:
        """Record one finished request (called from the middleware)."""
        with self._lock:
            self._req_count[(method, route, status)] += 1
            self._req_latency_sum[(method, route)] += ms
            for bucket in _LATENCY_BUCKETS_MS:
                if ms <= bucket:
                    self._req_latency_buckets[(method, route, bucket)] += 1

    def inc_in_flight(self, delta: int) -> None:
        """Track concurrent in-flight requests for a gauge."""
        with self._lock:
            self._in_flight += delta

    def render(self) -> str:
        """Emit the Prometheus text-exposition body for ``/metrics``."""
        with self._lock:
            return _render_metrics(
                req_count=dict(self._req_count),
                latency_sum=dict(self._req_latency_sum),
                latency_buckets=dict(self._req_latency_buckets),
                in_flight=self._in_flight,
            )


_METRICS = _Metrics()


def get_metrics() -> _Metrics:
    """Return the process-wide metrics registry."""
    return _METRICS


def _render_metrics(
    *,
    req_count: dict[tuple[str, str, int], int],
    latency_sum: dict[tuple[str, str], float],
    latency_buckets: dict[tuple[str, str, int], int],
    in_flight: int,
) -> str:
    """Format the in-memory metrics as Prometheus text exposition."""
    lines: list[str] = [
        "# HELP ipermit_http_requests_total Total HTTP requests.",
        "# TYPE ipermit_http_requests_total counter",
    ]
    for (method, route, status), count in sorted(req_count.items()):
        labels = f'method="{method}",route="{route}",status="{status}"'
        lines.append(f"ipermit_http_requests_total{{{labels}}} {count}")
    lines += [
        "# HELP ipermit_http_request_duration_ms HTTP latency in milliseconds.",
        "# TYPE ipermit_http_request_duration_ms histogram",
    ]
    for (method, route, bucket), count in sorted(latency_buckets.items()):
        labels = f'method="{method}",route="{route}",le="{bucket}"'
        lines.append(f"ipermit_http_request_duration_ms_bucket{{{labels}}} {count}")
    for (method, route), total in sorted(latency_sum.items()):
        labels = f'method="{method}",route="{route}"'
        lines.append(f"ipermit_http_request_duration_ms_sum{{{labels}}} {total:.3f}")
    lines += [
        "# HELP ipermit_http_requests_in_flight Concurrent in-flight requests.",
        "# TYPE ipermit_http_requests_in_flight gauge",
        f"ipermit_http_requests_in_flight {in_flight}",
    ]
    return "\n".join(lines) + "\n"


def _route_label(request: Request) -> str:
    """Return the templated path for stable metric cardinality."""
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Emit one JSON access-log line + metric per finished request."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()
        _METRICS.inc_in_flight(1)
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            _METRICS.inc_in_flight(-1)
            duration_ms = (time.perf_counter() - start) * 1000.0
            route = _route_label(request)
            _METRICS.observe(request.method, route, status, duration_ms)
            logging.getLogger(ACCESS_LOGGER).info(
                "http_request",
                extra={
                    "extras": {
                        "method": request.method,
                        "path": request.url.path,
                        "route": route,
                        "status": status,
                        "duration_ms": round(duration_ms, 3),
                        "request_id": getattr(request.state, "request_id", None),
                    }
                },
            )


router = APIRouter(tags=["meta"])


@router.get("/readyz", include_in_schema=False)
def readyz(session: Session = Depends(get_session)) -> dict[str, str]:
    """Readiness probe — only green when the DB session can SELECT 1."""
    session.execute(text("SELECT 1"))
    return {"status": "ready"}


@router.get("/metrics", include_in_schema=False, response_class=PlainTextResponse)
def metrics() -> PlainTextResponse:
    """Prometheus text-exposition endpoint for the in-process metrics."""
    return PlainTextResponse(_METRICS.render(), media_type="text/plain; version=0.0.4")


def install_observability(app: FastAPI) -> None:
    """Wire the access-log middleware + ``/readyz`` + ``/metrics`` onto *app*."""
    app.add_middleware(AccessLogMiddleware)
    app.include_router(router)


__all__ = [
    "ACCESS_LOGGER",
    "APP_LOGGER",
    "AccessLogMiddleware",
    "JsonFormatter",
    "configure_logging",
    "get_metrics",
    "install_observability",
    "router",
]
