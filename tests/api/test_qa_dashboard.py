"""Analyst QA dashboard API tests (S05-02)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from ipermit_api.auth import hash_password
from ipermit_tenancy import User
from sqlalchemy.orm import Session, sessionmaker

PASSWORD = "consultant-pw-123"


def _analyst(factory: sessionmaker[Session], email: str) -> None:
    with factory() as session:
        session.add(
            User(
                user_id=uuid.uuid4().hex,
                email=email,
                password_hash=hash_password(PASSWORD),
                platform_role="regulatory_analyst",
                capabilities=["analyst:review"],
            )
        )
        session.commit()


def test_consultant_cannot_read_qa_summary(
    client: TestClient, seeded: dict, login
) -> None:
    token = login(seeded["email_a"])
    resp = client.get(
        "/api/v1/qa/summary", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


def test_analyst_reads_qa_summary(client: TestClient, factory, login) -> None:
    _analyst(factory, "qa-analyst@example.com")
    token = login("qa-analyst@example.com")
    resp = client.get(
        "/api/v1/qa/summary", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["tier_counts"]["tier_1"] >= 0
    assert data["publication_gate_count"] >= 1
    assert isinstance(data["pending_review_rule_ids"], list)


def test_consultant_cannot_read_publication_readiness(
    client: TestClient, seeded: dict, login
) -> None:
    token = login(seeded["email_a"])
    resp = client.get(
        "/api/v1/qa/rules/us-tx-usace-section-404-da-permit/publication-readiness",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_analyst_reads_publication_readiness(client: TestClient, factory, login) -> None:
    _analyst(factory, "qa-readiness@example.com")
    token = login("qa-readiness@example.com")
    resp = client.get(
        "/api/v1/qa/rules/us-tx-usace-section-404-da-permit/publication-readiness",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["rule_id"] == "us-tx-usace-section-404-da-permit"
    assert data["title"]
    assert data["citation_count"] >= 1
    assert "publication_gate" in data


def test_unknown_rule_publication_readiness_returns_404(
    client: TestClient, factory, login
) -> None:
    _analyst(factory, "qa-missing@example.com")
    token = login("qa-missing@example.com")
    resp = client.get(
        "/api/v1/qa/rules/not-a-real-rule/publication-readiness",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
