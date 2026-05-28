"""Rule-publication workflow tests (S05-02, T08-04).

The governance flow: an analyst:draft proposes a rule transition; an
analyst:publish approves/rejects, with separation-of-duties enforced
(proposer != approver). Rollback returns an approved promotion to
``rolled_back``. Every transition writes an audit record.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from ipermit_api.auth import hash_password
from ipermit_tenancy import AuditRecord, RulePublication, User
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

PASSWORD = "consultant-pw-123"  # matches tests/api/conftest.py


def _analyst(
    factory: sessionmaker[Session],
    email: str,
    capabilities: list[str],
    role: str = "regulatory_analyst",
) -> None:
    with factory() as s:
        s.add(
            User(
                user_id=uuid.uuid4().hex,
                email=email,
                password_hash=hash_password(PASSWORD),
                platform_role=role,
                capabilities=capabilities,
            )
        )
        s.commit()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _propose(client: TestClient, token: str, *, rule_id: str = "us-tx-x") -> int:
    resp = client.post(
        "/api/v1/rules/publications",
        json={
            "rule_id": rule_id,
            "rule_version": "1.0.0",
            "target_status": "effective",
            "reason": "promote",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_consultant_cannot_propose(client: TestClient, seeded: dict, login) -> None:
    token = login(seeded["email_a"])
    resp = client.post(
        "/api/v1/rules/publications",
        json={
            "rule_id": "us-tx-x",
            "rule_version": "1.0.0",
            "target_status": "effective",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 403


def test_drafter_proposes_publisher_approves(
    client: TestClient, factory: sessionmaker[Session], login
) -> None:
    _analyst(factory, "drafter@example.com", ["analyst:draft"])
    _analyst(factory, "publisher@example.com", ["analyst:publish"])
    drafter = login("drafter@example.com")
    publisher = login("publisher@example.com")
    pub_id = _propose(client, drafter)
    resp = client.post(
        f"/api/v1/rules/publications/{pub_id}/approve",
        json={"note": "looks good"},
        headers=_auth(publisher),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "approved"
    assert body["decided_by"] == "publisher@example.com"
    with factory() as s:
        actions = set(s.scalars(select(AuditRecord.action)))
    assert "rule.publication_proposed" in actions
    assert "rule.publication_approved" in actions


def test_separation_of_duties_blocks_self_approve(
    client: TestClient, factory: sessionmaker[Session], login
) -> None:
    # Same identity holds both capabilities.
    _analyst(factory, "both@example.com", ["analyst:draft", "analyst:publish"])
    token = login("both@example.com")
    pub_id = _propose(client, token)
    resp = client.post(
        f"/api/v1/rules/publications/{pub_id}/approve",
        json={},
        headers=_auth(token),
    )
    assert resp.status_code == 403


def test_reject_and_rollback(
    client: TestClient, factory: sessionmaker[Session], login
) -> None:
    _analyst(factory, "drafter2@example.com", ["analyst:draft"])
    _analyst(factory, "publisher2@example.com", ["analyst:publish"])
    drafter = login("drafter2@example.com")
    publisher = login("publisher2@example.com")
    # Reject path.
    r_id = _propose(client, drafter, rule_id="us-tx-r")
    reject = client.post(
        f"/api/v1/rules/publications/{r_id}/reject",
        json={"note": "stale citation"},
        headers=_auth(publisher),
    )
    assert reject.json()["status"] == "rejected"
    # Approve-then-rollback path; rollback skips SoD.
    p_id = _propose(client, drafter, rule_id="us-tx-y")
    client.post(
        f"/api/v1/rules/publications/{p_id}/approve",
        json={},
        headers=_auth(publisher),
    )
    rolled = client.post(
        f"/api/v1/rules/publications/{p_id}/rollback",
        json={"note": "regression"},
        headers=_auth(publisher),
    )
    assert rolled.json()["status"] == "rolled_back"
    # Cannot rollback a non-approved record.
    again = client.post(
        f"/api/v1/rules/publications/{r_id}/rollback",
        json={},
        headers=_auth(publisher),
    )
    assert again.status_code == 409


def test_list_requires_analyst(client: TestClient, seeded: dict, login) -> None:
    token = login(seeded["email_a"])
    resp = client.get("/api/v1/rules/publications", headers=_auth(token))
    assert resp.status_code == 403


def test_list_returns_publications(
    client: TestClient, factory: sessionmaker[Session], login
) -> None:
    _analyst(factory, "drafter3@example.com", ["analyst:draft"])
    drafter = login("drafter3@example.com")
    _propose(client, drafter, rule_id="us-tx-a")
    _propose(client, drafter, rule_id="us-tx-b")
    rows = client.get("/api/v1/rules/publications", headers=_auth(drafter)).json()
    assert {r["rule_id"] for r in rows} == {"us-tx-a", "us-tx-b"}
    with factory() as s:
        assert s.scalar(
            select(RulePublication).where(RulePublication.rule_id == "us-tx-a")
        )
