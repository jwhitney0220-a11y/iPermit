"""Constrained AI matrix-narrative tests (S08-01, SAAS-08).

The advisory narrative route composes three gates: feature flag, pro
entitlement, tenant-scoped project ownership. These tests exercise each
gate plus the happy path, the envelope's mandatory advisories, and the
audit emission. The stub :class:`StubAIClient` is injected so no API call
leaves the process.
"""

from __future__ import annotations

import datetime
import uuid

import pytest
from fastapi.testclient import TestClient
from ipermit_ai import NARRATIVE_SYSTEM_PROMPT, StubAIClient, summarize_matrix
from ipermit_api.ai import set_ai_client
from ipermit_api.app import create_app
from ipermit_api.auth import hash_password
from ipermit_api.db import get_session
from ipermit_api.settings import get_settings
from ipermit_persistence import Base
from ipermit_tenancy import (
    AuditRecord,
    Evaluation,
    Membership,
    Project,
    Tenant,
    TenantBilling,
    User,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

PASSWORD = "ai-narrative-pw-123"
CANNED = (
    "Stub narrative — likely required permits noted, additional review recommended."
)


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
def ai_on():
    """Enable the AI feature flag for the duration of one test."""
    settings = get_settings()
    settings.ai_features_enabled = True
    set_ai_client(StubAIClient(canned_text=CANNED))
    yield
    settings.ai_features_enabled = False
    set_ai_client(None)


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
    return {
        "schema_version": "1.0.0",
        "evaluation_id": evaluation_id,
        "project_id": project_id,
        "evaluation_date": "2026-01-01",
        "ruleset_version": {"content_hash": "abc123"},
        "inputs_hash": "def456",
        "permits": [
            {
                "permit_name": "Section 404 Permit",
                "agency": "U.S. Army Corps of Engineers",
                "confidence": {"tier": 2},
                "sequencing": "early",
            }
        ],
        "sequencing": {
            "stages": [],
            "critical_path": [],
            "critical_path_total_days": 0,
        },
    }


def _seed(factory: sessionmaker[Session], *, plan: str = "pro") -> dict[str, str]:
    """Seed a tenant + pro billing + project + evaluation."""
    ids = {
        "tenant_id": uuid.uuid4().hex,
        "user_id": uuid.uuid4().hex,
        "project_id": uuid.uuid4().hex,
        "evaluation_id": uuid.uuid4().hex,
        "email": f"{uuid.uuid4().hex[:8]}@example.com",
    }
    matrix = _minimal_matrix(ids["project_id"], ids["evaluation_id"])
    with factory() as s:
        s.add(Tenant(tenant_id=ids["tenant_id"], name="AI Tenant"))
        s.add(
            User(
                user_id=ids["user_id"],
                email=ids["email"],
                password_hash=hash_password(PASSWORD),
            )
        )
        s.add(Membership(user_id=ids["user_id"], tenant_id=ids["tenant_id"]))
        s.add(
            Project(
                project_id=ids["project_id"],
                tenant_id=ids["tenant_id"],
                name="AI Project",
                created_by=ids["user_id"],
            )
        )
        s.add(
            Evaluation(
                evaluation_id=ids["evaluation_id"],
                tenant_id=ids["tenant_id"],
                project_id=ids["project_id"],
                evaluation_date="2026-01-01",
                inputs_hash="def456",
                ruleset_content_hash="abc123",
                matrix=matrix,
                created_by=ids["user_id"],
            )
        )
        if plan != "free":
            s.add(
                TenantBilling(
                    tenant_id=ids["tenant_id"],
                    plan=plan,
                    status="active",
                    current_period_end=datetime.datetime.now(tz=datetime.UTC)
                    + datetime.timedelta(days=30),
                )
            )
        s.commit()
    return ids


def _login(client: TestClient, email: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_happy_path_returns_envelope_with_two_advisories(
    client: TestClient, factory: sessionmaker[Session], ai_on
) -> None:
    ids = _seed(factory)
    token = _login(client, ids["email"])
    resp = client.post(
        f"/api/v1/projects/{ids['project_id']}/narrative",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["data"]["narrative"] == CANNED
    assert body["data"]["evaluation_id"] == ids["evaluation_id"]
    assert body["data"]["model"] == "stub-claude"
    # Mandatory: platform advisory + AI-content advisory.
    categories = {a["category"] for a in body["advisories"]}
    origins = {a["origin"] for a in body["advisories"]}
    assert "advisory_disclaimer" in categories
    assert {"platform", "ai_assistant"} == origins


def test_feature_flag_off_returns_403(
    client: TestClient, factory: sessionmaker[Session]
) -> None:
    ids = _seed(factory)
    token = _login(client, ids["email"])
    # ai_on fixture is NOT requested — feature flag stays the default False.
    resp = client.post(
        f"/api/v1/projects/{ids['project_id']}/narrative",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    body = resp.json()
    combined = ((body.get("detail") or "") + " " + body["title"]).lower()
    assert "disabled" in combined or "ai_features_enabled" in combined


def test_free_tier_gets_402(
    client: TestClient, factory: sessionmaker[Session], ai_on
) -> None:
    ids = _seed(factory, plan="free")
    token = _login(client, ids["email"])
    resp = client.post(
        f"/api/v1/projects/{ids['project_id']}/narrative",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 402


def test_unauthenticated_is_401(
    client: TestClient, factory: sessionmaker[Session], ai_on
) -> None:
    ids = _seed(factory)
    resp = client.post(f"/api/v1/projects/{ids['project_id']}/narrative")
    assert resp.status_code == 401


def test_other_tenants_project_is_404(
    client: TestClient, factory: sessionmaker[Session], ai_on
) -> None:
    a = _seed(factory)
    b = _seed(factory)
    token = _login(client, a["email"])
    resp = client.post(
        f"/api/v1/projects/{b['project_id']}/narrative",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_audit_record_written(
    client: TestClient, factory: sessionmaker[Session], ai_on
) -> None:
    ids = _seed(factory)
    token = _login(client, ids["email"])
    resp = client.post(
        f"/api/v1/projects/{ids['project_id']}/narrative",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    with factory() as s:
        records = s.scalars(
            select(AuditRecord).where(AuditRecord.action == "ai.narrative_generated")
        ).all()
    assert len(records) == 1
    payload = records[0].payload
    assert payload["model"] == "stub-claude"
    assert "matrix_hash" in payload
    assert payload["input_tokens"] >= 0
    assert payload["output_tokens"] >= 0


def test_stub_summarize_matrix_round_trip() -> None:
    """The library-level call works without the API service."""
    stub = StubAIClient()
    matrix = _minimal_matrix("p", "e")
    result = summarize_matrix(matrix, stub)
    assert result.text == StubAIClient.canned_text
    assert result.model == "stub-claude"


def test_system_prompt_forbids_certified_language() -> None:
    """Codifies the AGENTS.md advisory-language list inside the prompt itself."""
    for forbidden in ("guaranteed", "certified", "final determination"):
        assert forbidden in NARRATIVE_SYSTEM_PROMPT
