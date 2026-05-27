"""Entitlement-gating tests (S03-02).

Asserts the ``require_entitlement`` dependency on the export route:
- No billing row (free by default) → 402
- Free plan explicitly → 402
- Active qualifying plan (starter/pro) → 200 (passes through)
- Expired active plan (current_period_end in the past) → 402
- GET /billing/plans is public and returns the catalog

Builds TenantBilling rows directly in the test DB (no Stripe network).
The gated route is ``GET /projects/{id}/matrix/export`` (starter/pro only).
We exercise the entitlement check against a project/evaluation that was
pre-seeded via the test DB.
"""

from __future__ import annotations

import datetime
import uuid

import pytest
from fastapi.testclient import TestClient
from ipermit_api.app import create_app
from ipermit_api.auth import hash_password
from ipermit_api.db import get_session
from ipermit_persistence import Base
from ipermit_tenancy import Evaluation, Membership, Project, Tenant, TenantBilling, User
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

PASSWORD = "entitlement-pw-123"
GATED_ROUTE_FMT = "/api/v1/projects/{project_id}/matrix/export?format=json"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def client(factory: sessionmaker[Session]) -> TestClient:
    app = create_app()

    def _session():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = _session
    with TestClient(app) as c:
        yield c


def _minimal_matrix(project_id: str, evaluation_id: str) -> dict:
    """A schema-shaped permit matrix with no permits (enough to persist)."""
    return {
        "schema_version": "1.0.0",
        "evaluation_id": evaluation_id,
        "project_id": project_id,
        "evaluation_date": "2026-01-01",
        "ruleset_version": {"content_hash": "abc123"},
        "inputs_hash": "def456",
        "permits": [],
        "sequencing": {
            "stages": [],
            "critical_path": [],
            "critical_path_total_days": 0,
        },
    }


def _seed_tenant(
    factory: sessionmaker[Session],
    *,
    plan: str = "free",
    status: str = "none",
    current_period_end: datetime.datetime | None = None,
) -> dict[str, str]:
    """Seed a tenant+user+project+evaluation; return ids and email."""
    tenant_id = uuid.uuid4().hex
    user_id = uuid.uuid4().hex
    project_id = uuid.uuid4().hex
    evaluation_id = uuid.uuid4().hex
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    minimal_matrix = _minimal_matrix(project_id, evaluation_id)

    with factory() as s:
        s.add(Tenant(tenant_id=tenant_id, name="Test Tenant"))
        s.add(
            User(
                user_id=user_id,
                email=email,
                password_hash=hash_password(PASSWORD),
            )
        )
        s.add(Membership(user_id=user_id, tenant_id=tenant_id))
        s.add(
            Project(
                project_id=project_id,
                tenant_id=tenant_id,
                name="Test Project",
                created_by=user_id,
            )
        )
        s.add(
            Evaluation(
                evaluation_id=evaluation_id,
                tenant_id=tenant_id,
                project_id=project_id,
                evaluation_date="2026-01-01",
                inputs_hash="def456",
                ruleset_content_hash="abc123",
                matrix=minimal_matrix,
                created_by=user_id,
            )
        )
        if plan != "free" or status != "none":
            s.add(
                TenantBilling(
                    tenant_id=tenant_id,
                    plan=plan,
                    status=status,
                    current_period_end=current_period_end,
                )
            )
        s.commit()

    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "project_id": project_id,
        "email": email,
    }


def _token(client: TestClient, email: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Entitlement gating on the export route
# ---------------------------------------------------------------------------


def test_no_billing_row_is_denied(
    client: TestClient, factory: sessionmaker[Session]
) -> None:
    """A tenant with no billing row (free by default) cannot use the gated route."""
    ids = _seed_tenant(factory)
    token = _token(client, ids["email"])
    resp = client.get(
        GATED_ROUTE_FMT.format(project_id=ids["project_id"]),
        headers=_auth(token),
    )
    assert resp.status_code == 402
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["status"] == 402
    assert "starter" in body["detail"] or "pro" in body["detail"]


def test_free_plan_is_denied(
    client: TestClient, factory: sessionmaker[Session]
) -> None:
    """An explicit free plan row is also denied (402)."""
    ids = _seed_tenant(factory, plan="free", status="active")
    token = _token(client, ids["email"])
    resp = client.get(
        GATED_ROUTE_FMT.format(project_id=ids["project_id"]),
        headers=_auth(token),
    )
    assert resp.status_code == 402


def test_active_starter_plan_is_allowed(
    client: TestClient, factory: sessionmaker[Session]
) -> None:
    """An active starter plan passes the entitlement check (200)."""
    ids = _seed_tenant(factory, plan="starter", status="active")
    token = _token(client, ids["email"])
    resp = client.get(
        GATED_ROUTE_FMT.format(project_id=ids["project_id"]),
        headers=_auth(token),
    )
    assert resp.status_code == 200


def test_active_pro_plan_is_allowed(
    client: TestClient, factory: sessionmaker[Session]
) -> None:
    """An active pro plan also passes the entitlement check (200)."""
    ids = _seed_tenant(factory, plan="pro", status="active")
    token = _token(client, ids["email"])
    resp = client.get(
        GATED_ROUTE_FMT.format(project_id=ids["project_id"]),
        headers=_auth(token),
    )
    assert resp.status_code == 200


def test_expired_active_plan_is_denied(
    client: TestClient, factory: sessionmaker[Session]
) -> None:
    """A plan with status=active but current_period_end in the past is denied (402)."""
    past = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(hours=1)
    ids = _seed_tenant(factory, plan="pro", status="active", current_period_end=past)
    token = _token(client, ids["email"])
    resp = client.get(
        GATED_ROUTE_FMT.format(project_id=ids["project_id"]),
        headers=_auth(token),
    )
    assert resp.status_code == 402


def test_past_due_plan_is_denied(
    client: TestClient, factory: sessionmaker[Session]
) -> None:
    """A pro plan with status=past_due is denied (402) — not active."""
    ids = _seed_tenant(factory, plan="pro", status="past_due")
    token = _token(client, ids["email"])
    resp = client.get(
        GATED_ROUTE_FMT.format(project_id=ids["project_id"]),
        headers=_auth(token),
    )
    assert resp.status_code == 402


def test_canceled_plan_is_denied(
    client: TestClient, factory: sessionmaker[Session]
) -> None:
    """A canceled pro plan is denied (402)."""
    ids = _seed_tenant(factory, plan="pro", status="canceled")
    token = _token(client, ids["email"])
    resp = client.get(
        GATED_ROUTE_FMT.format(project_id=ids["project_id"]),
        headers=_auth(token),
    )
    assert resp.status_code == 402


def test_gated_route_requires_auth(client: TestClient) -> None:
    """The gated route still requires a valid bearer token (401 without one)."""
    resp = client.get("/api/v1/projects/fake-id/matrix/export?format=json")
    assert resp.status_code == 401


def test_future_period_end_is_active(
    client: TestClient, factory: sessionmaker[Session]
) -> None:
    """A plan with current_period_end in the future is treated as active."""
    future = datetime.datetime.now(tz=datetime.UTC) + datetime.timedelta(days=30)
    ids = _seed_tenant(
        factory, plan="starter", status="active", current_period_end=future
    )
    token = _token(client, ids["email"])
    resp = client.get(
        GATED_ROUTE_FMT.format(project_id=ids["project_id"]),
        headers=_auth(token),
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /billing/plans — public catalog
# ---------------------------------------------------------------------------


def test_plans_is_public(client: TestClient) -> None:
    """GET /billing/plans is unauthenticated — no bearer token required."""
    resp = client.get("/api/v1/billing/plans")
    assert resp.status_code == 200


def test_plans_returns_catalog(client: TestClient) -> None:
    """GET /billing/plans returns all plans including free/starter/pro."""
    resp = client.get("/api/v1/billing/plans")
    assert resp.status_code == 200
    body = resp.json()
    assert "plans" in body
    plan_names = {p["plan"] for p in body["plans"]}
    assert plan_names == {"free", "starter", "pro"}


def test_plans_catalog_shape(client: TestClient) -> None:
    """Each plan entry has the required fields."""
    resp = client.get("/api/v1/billing/plans")
    for plan in resp.json()["plans"]:
        assert "plan" in plan
        assert "display_name" in plan
        assert "description" in plan
        assert "features" in plan
        assert "premium" in plan


def test_plans_free_is_not_premium(client: TestClient) -> None:
    """The free plan is marked as not premium."""
    resp = client.get("/api/v1/billing/plans")
    free_plan = next(p for p in resp.json()["plans"] if p["plan"] == "free")
    assert free_plan["premium"] is False


def test_plans_paid_are_premium(client: TestClient) -> None:
    """Starter and pro plans are marked as premium."""
    resp = client.get("/api/v1/billing/plans")
    for plan in resp.json()["plans"]:
        if plan["plan"] in ("starter", "pro"):
            assert plan["premium"] is True
