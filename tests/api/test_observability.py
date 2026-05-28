"""Observability surface tests (S07-03, SAAS-07)."""

from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient
from ipermit_api.observability import (
    ACCESS_LOGGER,
    JsonFormatter,
    configure_logging,
    get_metrics,
)


def test_readyz_returns_200_when_db_alive(client: TestClient) -> None:
    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


def test_metrics_endpoint_emits_prometheus_lines(client: TestClient) -> None:
    # Drive a few requests through known routes so the counters increment.
    client.get("/healthz")
    client.get("/healthz")
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    body = resp.text
    assert "ipermit_http_requests_total" in body
    assert 'method="GET"' in body
    assert "ipermit_http_request_duration_ms_bucket" in body
    assert "ipermit_http_requests_in_flight" in body


def test_access_log_emits_structured_json(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger=ACCESS_LOGGER)
    client.get("/healthz")
    matches = [
        r
        for r in caplog.records
        if r.name == ACCESS_LOGGER and r.message == "http_request"
    ]
    assert matches, [r.name for r in caplog.records]
    extras = matches[-1].extras
    assert extras["method"] == "GET"
    assert extras["path"] == "/healthz"
    assert extras["status"] == 200
    assert isinstance(extras["duration_ms"], float)


def test_json_formatter_serialises_extras() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="ipermit.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.extras = {"request_id": "abc-123", "tenant_id": "t-1"}
    out = json.loads(formatter.format(record))
    assert out["msg"] == "hello"
    assert out["request_id"] == "abc-123"
    assert out["tenant_id"] == "t-1"
    assert out["level"] == "INFO"


def test_configure_logging_replaces_handlers() -> None:
    configure_logging("debug")
    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JsonFormatter)
    assert root.level == logging.DEBUG


def test_metrics_counts_status_codes(client: TestClient) -> None:
    # An auth-required path should produce a 401, which the counter must record.
    metrics = get_metrics()
    rendered_before = metrics.render()
    client.get("/api/v1/projects")
    rendered_after = metrics.render()
    assert 'status="401"' in rendered_after
    # Sanity: the rendered body grew (or at least counts increased).
    assert rendered_after != rendered_before
