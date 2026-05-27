"""Feedback queue tests (S02-05, T08-06).

Consultants submit and see only their own tenant's feedback. The triage queue
and disposition are analyst-gated; consultants are forbidden. Disposition records
a decision and is audited — it never changes a rule.
"""

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


def _submit(
    client: TestClient, token: str, message: str = "Permit X looks wrong"
) -> str:
    resp = client.post(
        "/api/v1/feedback",
        json={"category": "incorrect_permit", "message": message},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["feedback_id"]


def test_consultant_submits_and_lists_own(
    client: TestClient, seeded: dict, login
) -> None:
    token = login(seeded["email_a"])
    fid = _submit(client, token)
    resp = client.get("/api/v1/feedback", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert [f["feedback_id"] for f in resp.json()] == [fid]
    assert resp.json()[0]["status"] == "open"


def test_feedback_is_tenant_scoped(client: TestClient, seeded: dict, login) -> None:
    token_a = login(seeded["email_a"])
    _submit(client, token_a)
    token_b = login(seeded["email_b"])
    resp = client.get(
        "/api/v1/feedback", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.json() == []


def test_consultant_cannot_access_queue_or_disposition(
    client: TestClient, seeded: dict, login
) -> None:
    token = login(seeded["email_a"])
    fid = _submit(client, token)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/feedback/queue", headers=headers).status_code == 403
    resp = client.post(
        f"/api/v1/feedback/{fid}/disposition",
        json={"decision": "confirmed"},
        headers=headers,
    )
    assert resp.status_code == 403


def test_analyst_dispositions_feedback(
    client: TestClient, seeded: dict, login, factory: sessionmaker[Session]
) -> None:
    consultant = login(seeded["email_a"])
    fid = _submit(client, consultant)
    _analyst(factory, "analyst@example.com")
    analyst = login("analyst@example.com")
    headers = {"Authorization": f"Bearer {analyst}"}
    # The analyst sees the item in the platform-wide queue.
    queue = client.get("/api/v1/feedback/queue", headers=headers).json()
    assert fid in [f["feedback_id"] for f in queue]
    # ...and can disposition it.
    resp = client.post(
        f"/api/v1/feedback/{fid}/disposition",
        json={"decision": "rejected", "note": "Not a defect"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert resp.json()["dispositioned_by"] == "analyst@example.com"
    # No longer open -> gone from the queue, and re-disposition is a conflict.
    assert client.get("/api/v1/feedback/queue", headers=headers).json() == []
    again = client.post(
        f"/api/v1/feedback/{fid}/disposition",
        json={"decision": "confirmed"},
        headers=headers,
    )
    assert again.status_code == 409


def test_bad_decision_rejected(
    client: TestClient, seeded: dict, login, factory: sessionmaker[Session]
) -> None:
    consultant = login(seeded["email_a"])
    fid = _submit(client, consultant)
    _analyst(factory, "analyst2@example.com")
    analyst = login("analyst2@example.com")
    resp = client.post(
        f"/api/v1/feedback/{fid}/disposition",
        json={"decision": "maybe"},
        headers={"Authorization": f"Bearer {analyst}"},
    )
    assert resp.status_code == 422
