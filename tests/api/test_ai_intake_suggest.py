"""AI intake-suggestion tests (S08-02, SAAS-08).

Same three-gate composition as the narrative route (S08-01): feature flag,
premium entitlement, identity. Additionally tests the JSON-contract gate —
the stub returns valid JSON in the happy path and garbage in the parse-error
path, the route maps the latter to 422.
"""

from __future__ import annotations

import datetime
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from ipermit_ai import (
    SUGGEST_SYSTEM_PROMPT,
    IntakeSuggestion,
    StubAIClient,
    parse_suggestion,
    suggest_intake,
)
from ipermit_ai.client import NarrativeResult
from ipermit_ai.suggest import SuggestionParseError
from ipermit_api.ai import set_ai_client
from ipermit_api.app import create_app
from ipermit_api.auth import hash_password
from ipermit_api.db import get_session
from ipermit_api.settings import get_settings
from ipermit_persistence import Base
from ipermit_tenancy import (
    AuditRecord,
    Membership,
    Tenant,
    TenantBilling,
    User,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

PASSWORD = "intake-suggest-pw-123"

_GOOD_JSON = json.dumps(
    {
        "project_type": "subdivision",
        "linear": False,
        "estimated_acres": 60,
        "county_hint": "Travis",
        "stream_crossings": True,
        "wetlands_present": None,
        "federal_nexus": None,
        "row_type": None,
        "advisory_notes": ["wetlands not stated", "federal nexus unclear"],
    }
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
    settings = get_settings()
    settings.ai_features_enabled = True
    set_ai_client(StubAIClient(canned_text=_GOOD_JSON))
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


def _seed(factory: sessionmaker[Session], *, plan: str = "pro") -> dict[str, str]:
    ids = {
        "tenant_id": uuid.uuid4().hex,
        "user_id": uuid.uuid4().hex,
        "email": f"{uuid.uuid4().hex[:8]}@example.com",
    }
    with factory() as s:
        s.add(Tenant(tenant_id=ids["tenant_id"], name="AI Intake Tenant"))
        s.add(
            User(
                user_id=ids["user_id"],
                email=ids["email"],
                password_hash=hash_password(PASSWORD),
            )
        )
        s.add(Membership(user_id=ids["user_id"], tenant_id=ids["tenant_id"]))
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


def test_happy_path_returns_parsed_suggestion(
    client: TestClient, factory: sessionmaker[Session], ai_on
) -> None:
    ids = _seed(factory)
    token = _login(client, ids["email"])
    resp = client.post(
        "/api/v1/intake/suggest",
        headers={"Authorization": f"Bearer {token}"},
        json={"description": "60-acre subdivision in Travis County with two creeks."},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["project_type"] == "subdivision"
    assert data["estimated_acres"] == 60
    assert data["county_hint"] == "Travis"
    assert data["stream_crossings"] is True
    assert data["wetlands_present"] is None
    assert "wetlands not stated" in data["advisory_notes"]
    # Both mandatory advisories present.
    origins = {a["origin"] for a in resp.json()["advisories"]}
    assert {"platform", "ai_assistant"} == origins


def test_feature_flag_off_returns_403(
    client: TestClient, factory: sessionmaker[Session]
) -> None:
    ids = _seed(factory)
    token = _login(client, ids["email"])
    resp = client.post(
        "/api/v1/intake/suggest",
        headers={"Authorization": f"Bearer {token}"},
        json={"description": "anything"},
    )
    assert resp.status_code == 403


def test_free_tier_gets_402(
    client: TestClient, factory: sessionmaker[Session], ai_on
) -> None:
    ids = _seed(factory, plan="free")
    token = _login(client, ids["email"])
    resp = client.post(
        "/api/v1/intake/suggest",
        headers={"Authorization": f"Bearer {token}"},
        json={"description": "60-acre subdivision in Travis County."},
    )
    assert resp.status_code == 402


def test_empty_description_is_422(
    client: TestClient, factory: sessionmaker[Session], ai_on
) -> None:
    ids = _seed(factory)
    token = _login(client, ids["email"])
    resp = client.post(
        "/api/v1/intake/suggest",
        headers={"Authorization": f"Bearer {token}"},
        json={"description": ""},
    )
    assert resp.status_code == 422


def test_unparseable_ai_response_is_422(
    client: TestClient, factory: sessionmaker[Session]
) -> None:
    settings = get_settings()
    settings.ai_features_enabled = True
    set_ai_client(StubAIClient(canned_text="not-json-at-all"))
    try:
        ids = _seed(factory)
        token = _login(client, ids["email"])
        resp = client.post(
            "/api/v1/intake/suggest",
            headers={"Authorization": f"Bearer {token}"},
            json={"description": "60-acre subdivision"},
        )
        assert resp.status_code == 422
        assert "unusable" in (resp.json().get("title") or "").lower()
    finally:
        settings.ai_features_enabled = False
        set_ai_client(None)


def test_audit_record_written(
    client: TestClient, factory: sessionmaker[Session], ai_on
) -> None:
    ids = _seed(factory)
    token = _login(client, ids["email"])
    resp = client.post(
        "/api/v1/intake/suggest",
        headers={"Authorization": f"Bearer {token}"},
        json={"description": "60-acre subdivision in Travis County."},
    )
    assert resp.status_code == 200
    with factory() as s:
        records = s.scalars(
            select(AuditRecord).where(AuditRecord.action == "ai.intake_suggested")
        ).all()
    assert len(records) == 1
    assert records[0].payload["description_chars"] > 0
    assert records[0].payload["model"] == "stub-claude"


def test_parse_suggestion_round_trip() -> None:
    result = NarrativeResult(
        text=_GOOD_JSON, model="stub-claude", input_tokens=10, output_tokens=20
    )
    suggestion = parse_suggestion(result)
    assert isinstance(suggestion, IntakeSuggestion)
    assert suggestion.project_type == "subdivision"
    assert suggestion.estimated_acres == 60.0
    assert suggestion.stream_crossings is True


def test_parse_suggestion_rejects_non_object() -> None:
    result = NarrativeResult(
        text="[]", model="stub-claude", input_tokens=0, output_tokens=0
    )
    with pytest.raises(SuggestionParseError):
        parse_suggestion(result)


def test_suggest_intake_rejects_overlong_input() -> None:
    too_long = "x" * 5000
    with pytest.raises(SuggestionParseError):
        suggest_intake(too_long, StubAIClient(canned_text=_GOOD_JSON))


def test_system_prompt_forbids_decision_language() -> None:
    """The model is told never to name permits, agencies, or rules."""
    assert "permits" in SUGGEST_SYSTEM_PROMPT
    assert "MUST NOT name" in SUGGEST_SYSTEM_PROMPT
    assert "guaranteed" in SUGGEST_SYSTEM_PROMPT
