"""Usage metering tests (S03-03).

Validates that:
  - Recording N evaluations yields a usage summary of N for that tenant.
  - Usage is tenant-isolated: tenant A's evaluations are never counted for B.
  - The evaluate endpoint increments usage automatically.
  - GET /usage requires auth (401 without token).
  - GET /usage returns only the caller's own tenant counts (cross-tenant).
  - The record_usage helper is idempotent to repeated calls (append-only).

Uses the SQLite-backed TestClient (conftest.py pattern). Direct row inspection
via the shared session factory for white-box assertions.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import yaml
from fastapi.testclient import TestClient
from ipermit_api.usage import get_period_summary, record_usage
from ipermit_tenancy import UsageRecord
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[2]
_BENCHMARK = ROOT / "packages/benchmark-projects/benchmarks"
_FEDERAL_NEXUS = _BENCHMARK / "federal-nexus-transmission-stream-crossing.yaml"
_LEVELS = {"us": ("federal", "United States"), "us-tx": ("state", "Texas")}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _evaluate_body() -> dict:
    """Minimal valid evaluate request from the federal-nexus benchmark."""
    data = yaml.safe_load(_FEDERAL_NEXUS.read_text())
    inputs = data["project_inputs"]
    ctx = inputs["engine_context"]
    jurisdictions = [
        {
            "jurisdiction_id": jid,
            "jurisdiction_level": _LEVELS[jid][0],
            "canonical_name": _LEVELS[jid][1],
        }
        for jid in inputs["applicable_jurisdiction_ids"]
    ]
    return {
        "project_type": inputs["project_type"],
        "project": ctx.get("project", {}),
        "derived": ctx.get("derived", {}),
        "overlays": ctx.get("geometry", {}),
        "jurisdictions": jurisdictions,
        "evaluation_date": data["evaluation_date"],
    }


def _create_project(client: TestClient, token: str, name: str = "P1") -> str:
    resp = client.post("/api/v1/projects", json={"name": name}, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()["project_id"]


def _run_evaluation(client: TestClient, token: str, project_id: str) -> None:
    resp = client.post(
        f"/api/v1/projects/{project_id}/evaluate",
        json=_evaluate_body(),
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text


def _usage_rows(factory: sessionmaker[Session], tenant_id: str) -> list[UsageRecord]:
    with factory() as s:
        return list(
            s.scalars(
                select(UsageRecord).where(UsageRecord.tenant_id == tenant_id)
            ).all()
        )


# ---------------------------------------------------------------------------
# Unit-level: record_usage helper
# ---------------------------------------------------------------------------


def test_record_usage_inserts_row(factory: sessionmaker[Session]) -> None:
    """record_usage appends one row with the correct tenant/metric/quantity."""
    with factory() as s:
        record = record_usage(s, tenant_id="t-unit-1", metric="evaluation")
        s.commit()
        assert record.id is not None
        assert record.tenant_id == "t-unit-1"
        assert record.metric == "evaluation"
        assert record.quantity == 1
        assert record.occurred_at is not None


def test_record_usage_custom_quantity(factory: sessionmaker[Session]) -> None:
    """record_usage respects a non-default quantity."""
    with factory() as s:
        record = record_usage(s, tenant_id="t-unit-2", metric="evaluation", quantity=5)
        s.commit()
        assert record.quantity == 5


def test_record_usage_multiple_appends(factory: sessionmaker[Session]) -> None:
    """Each call to record_usage appends a new row (no upsert, purely append-only)."""
    with factory() as s:
        for _ in range(3):
            record_usage(s, tenant_id="t-unit-3", metric="evaluation")
        s.commit()
        rows = list(
            s.scalars(
                select(UsageRecord).where(UsageRecord.tenant_id == "t-unit-3")
            ).all()
        )
    assert len(rows) == 3


# ---------------------------------------------------------------------------
# Unit-level: get_period_summary
# ---------------------------------------------------------------------------


def test_get_period_summary_aggregates_by_metric(
    factory: sessionmaker[Session],
) -> None:
    """get_period_summary returns {metric: sum(quantity)} within the window."""
    tid = "t-sum-1"
    now = datetime.datetime.now(tz=datetime.UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (
        start.replace(month=start.month + 1)
        if start.month < 12
        else start.replace(year=start.year + 1, month=1)
    )
    with factory() as s:
        for _ in range(4):
            record_usage(s, tenant_id=tid, metric="evaluation")
        s.commit()
        summary = get_period_summary(
            s, tenant_id=tid, period_start=start, period_end=end
        )
    assert summary == {"evaluation": 4}


def test_get_period_summary_tenant_isolated(
    factory: sessionmaker[Session],
) -> None:
    """get_period_summary only returns counts for the requested tenant."""
    now = datetime.datetime.now(tz=datetime.UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (
        start.replace(month=start.month + 1)
        if start.month < 12
        else start.replace(year=start.year + 1, month=1)
    )
    with factory() as s:
        record_usage(s, tenant_id="t-iso-a", metric="evaluation")
        record_usage(s, tenant_id="t-iso-a", metric="evaluation")
        record_usage(s, tenant_id="t-iso-b", metric="evaluation")
        s.commit()
        summary_a = get_period_summary(
            s, tenant_id="t-iso-a", period_start=start, period_end=end
        )
        summary_b = get_period_summary(
            s, tenant_id="t-iso-b", period_start=start, period_end=end
        )
    assert summary_a == {"evaluation": 2}
    assert summary_b == {"evaluation": 1}


def test_get_period_summary_excludes_out_of_window(
    factory: sessionmaker[Session],
) -> None:
    """Records outside the period window do not appear in the summary."""
    now = datetime.datetime.now(tz=datetime.UTC)
    past_start = now.replace(
        year=now.year - 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
    )
    past_end = past_start.replace(month=2)
    # Record in the current month — should NOT appear in the past window query.
    with factory() as s:
        record_usage(s, tenant_id="t-window-1", metric="evaluation")
        s.commit()
        summary = get_period_summary(
            s, tenant_id="t-window-1", period_start=past_start, period_end=past_end
        )
    assert summary == {}


def test_get_period_summary_empty_when_no_records(
    factory: sessionmaker[Session],
) -> None:
    """get_period_summary returns {} for a tenant with no usage yet."""
    now = datetime.datetime.now(tz=datetime.UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (
        start.replace(month=start.month + 1)
        if start.month < 12
        else start.replace(year=start.year + 1, month=1)
    )
    with factory() as s:
        summary = get_period_summary(
            s, tenant_id="t-empty-1", period_start=start, period_end=end
        )
    assert summary == {}


# ---------------------------------------------------------------------------
# Integration: evaluate endpoint increments usage
# ---------------------------------------------------------------------------


def test_evaluate_increments_usage(
    client: TestClient,
    login,
    seeded: dict,
    factory: sessionmaker[Session],
) -> None:
    """Each successful evaluation call adds one usage row for the tenant."""
    token = login(seeded["email_a"])
    project_id = _create_project(client, token)
    assert len(_usage_rows(factory, seeded["tenant_a"])) == 0

    _run_evaluation(client, token, project_id)
    rows = _usage_rows(factory, seeded["tenant_a"])
    assert len(rows) == 1
    assert rows[0].metric == "evaluation"
    assert rows[0].quantity == 1


def test_evaluate_n_times_yields_n_usage_records(
    client: TestClient,
    login,
    seeded: dict,
    factory: sessionmaker[Session],
) -> None:
    """Recording N evaluations yields N usage rows summing to N."""
    n = 3
    token = login(seeded["email_a"])
    project_id = _create_project(client, token)
    for _ in range(n):
        _run_evaluation(client, token, project_id)
    rows = _usage_rows(factory, seeded["tenant_a"])
    assert len(rows) == n
    assert sum(r.quantity for r in rows) == n


# ---------------------------------------------------------------------------
# Integration: GET /usage endpoint
# ---------------------------------------------------------------------------


def test_get_usage_requires_auth(client: TestClient) -> None:
    """GET /usage returns 401 without a bearer token."""
    resp = client.get("/api/v1/usage")
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/problem+json")


def test_get_usage_empty_before_any_evaluation(
    client: TestClient, login, seeded: dict
) -> None:
    """GET /usage returns an empty metrics dict before any metered actions."""
    token = login(seeded["email_a"])
    resp = client.get("/api/v1/usage", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["tenant_id"] == seeded["tenant_a"]
    assert body["metrics"] == {}


def test_get_usage_reflects_evaluations(
    client: TestClient, login, seeded: dict
) -> None:
    """GET /usage reports the correct count after N evaluations."""
    token = login(seeded["email_a"])
    project_id = _create_project(client, token)
    _run_evaluation(client, token, project_id)
    _run_evaluation(client, token, project_id)

    resp = client.get("/api/v1/usage", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["metrics"].get("evaluation") == 2


def test_get_usage_tenant_isolation(client: TestClient, login, seeded: dict) -> None:
    """Tenant A's evaluations never appear in tenant B's usage summary."""
    token_a = login(seeded["email_a"])
    token_b = login(seeded["email_b"])

    # Tenant A runs 2 evaluations.
    proj_a = _create_project(client, token_a, name="A-proj")
    _run_evaluation(client, token_a, proj_a)
    _run_evaluation(client, token_a, proj_a)

    # Tenant B has not run any evaluations.
    resp_b = client.get("/api/v1/usage", headers=_auth(token_b))
    assert resp_b.status_code == 200, resp_b.text
    assert resp_b.json()["metrics"] == {}

    # Tenant A sees only their 2 evaluations.
    resp_a = client.get("/api/v1/usage", headers=_auth(token_a))
    assert resp_a.json()["metrics"].get("evaluation") == 2


def test_get_usage_response_shape(client: TestClient, login, seeded: dict) -> None:
    """GET /usage response includes tenant_id, period_start, period_end, metrics."""
    token = login(seeded["email_a"])
    resp = client.get("/api/v1/usage", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "tenant_id" in body
    assert "period_start" in body
    assert "period_end" in body
    assert "metrics" in body
    assert isinstance(body["metrics"], dict)


def test_get_usage_with_explicit_period_start(
    client: TestClient, login, seeded: dict
) -> None:
    """GET /usage?period_start=YYYY-MM-DD queries that calendar month."""
    token = login(seeded["email_a"])
    resp = client.get(
        "/api/v1/usage",
        params={"period_start": "2026-01-15"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["period_start"] == "2026-01-01"
    assert body["period_end"] == "2026-02-01"


def test_get_usage_invalid_period_start(
    client: TestClient, login, seeded: dict
) -> None:
    """An invalid period_start returns a 422 problem detail."""
    token = login(seeded["email_a"])
    resp = client.get(
        "/api/v1/usage",
        params={"period_start": "not-a-date"},
        headers=_auth(token),
    )
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")
