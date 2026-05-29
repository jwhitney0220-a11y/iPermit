"""QA dashboard endpoint tests (S05-03)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from ipermit_api.auth import hash_password
from ipermit_tenancy import User
from sqlalchemy.orm import Session, sessionmaker

PASSWORD = "consultant-pw-123"  # matches tests/api/conftest.py


def _analyst(factory: sessionmaker[Session], email: str) -> None:
    with factory() as s:
        s.add(
            User(
                user_id=uuid.uuid4().hex,
                email=email,
                password_hash=hash_password(PASSWORD),
                platform_role="regulatory_analyst",
            )
        )
        s.commit()


def test_qa_requires_analyst(client: TestClient, seeded: dict, login) -> None:
    token = login(seeded["email_a"])
    resp = client.get("/api/v1/qa/report", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_analyst_gets_report(
    client: TestClient, factory: sessionmaker[Session], login
) -> None:
    _analyst(factory, "qa-analyst@example.com")
    token = login("qa-analyst@example.com")
    resp = client.get("/api/v1/qa/report", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_rules"] >= 1
    assert sum(body["by_status"].values()) == body["total_rules"]
    assert sum(body["by_tier"].values()) == body["total_rules"]
    assert isinstance(body["stale_rules"], list)


def test_qa_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/qa/report").status_code == 401
