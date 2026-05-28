"""Source/citation health endpoint tests (S05-04)."""

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


def test_sources_requires_analyst(client: TestClient, seeded: dict, login) -> None:
    token = login(seeded["email_a"])
    resp = client.get(
        "/api/v1/qa/sources", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


def test_analyst_gets_sources_report(
    client: TestClient, factory: sessionmaker[Session], login
) -> None:
    _analyst(factory, "src-analyst@example.com")
    token = login("src-analyst@example.com")
    resp = client.get(
        "/api/v1/qa/sources", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_citations"] >= 1
    assert body["total_citations"] == len(body["citations"])
    # health_counts sum to total
    assert sum(body["health_counts"].values()) == body["total_citations"]
    # Every item has the expected shape + a valid health value
    valid = {"ok", "stale", "missing_url"}
    for item in body["citations"]:
        assert item["health"] in valid
        assert item["reference"]
        assert item["rule_id"]
    # Missing-url + stale items sort before ok items
    healths = [c["health"] for c in body["citations"]]
    last_ok = next((i for i, h in enumerate(healths) if h == "ok"), len(healths))
    assert all(h != "ok" for h in healths[:last_ok])


def test_sources_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/qa/sources").status_code == 401
