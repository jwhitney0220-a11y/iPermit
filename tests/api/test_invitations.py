"""Team-invite + acceptance flow tests (S07-02)."""

from __future__ import annotations

import datetime
import re

from fastapi.testclient import TestClient
from ipermit_api.email import get_local_sender
from ipermit_api.invitations import find_active_invitation
from ipermit_tenancy import Invitation
from sqlalchemy.orm import Session, sessionmaker

PASSWORD = "consultant-pw-123"
NEW_PASSWORD = "brand-new-pw-456"


def _token_from_last_email() -> str:
    """Pull the acceptance token out of the most recent captured email."""
    sender = get_local_sender()
    match = re.search(r"token=([^\s)]+)", sender.sent[-1].body)
    assert match is not None, sender.sent[-1].body
    return match.group(1)


def test_invite_unregistered_email_sends_invitation(
    client: TestClient, seeded: dict[str, str], login
) -> None:
    sender = get_local_sender()
    before = len(sender.sent)
    token = login(seeded["email_a"])
    resp = client.post(
        "/api/v1/team/invitations",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "newhire@example.com", "is_team_admin": False},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == "newhire@example.com"
    assert body["is_team_admin"] is False
    assert "invitation_id" in body
    # The raw token must not leak in the API response.
    assert "token" not in body
    assert len(sender.sent) == before + 1
    assert sender.sent[-1].to == "newhire@example.com"
    assert "invited you to join" in sender.sent[-1].body


def test_existing_user_invite_returns_409(
    client: TestClient, seeded: dict[str, str], login
) -> None:
    token = login(seeded["email_a"])
    resp = client.post(
        "/api/v1/team/invitations",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": seeded["email_b"]},
    )
    assert resp.status_code == 409


def test_add_member_unregistered_points_to_invite(
    client: TestClient, seeded: dict[str, str], login
) -> None:
    token = login(seeded["email_a"])
    resp = client.post(
        "/api/v1/team/members",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "stranger@example.com"},
    )
    assert resp.status_code == 404
    body = resp.json()
    assert "invitations" in (body.get("detail") or "")


def test_preview_returns_tenant_context(
    client: TestClient, seeded: dict[str, str], login
) -> None:
    token = login(seeded["email_a"])
    client.post(
        "/api/v1/team/invitations",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "preview-me@example.com"},
    )
    raw = _token_from_last_email()
    resp = client.get(f"/api/v1/invitations/{raw}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] == "preview-me@example.com"
    assert body["tenant_id"] == seeded["tenant_a"]
    assert body["tenant_name"] == "Tenant a"


def test_preview_unknown_token_is_410(client: TestClient) -> None:
    resp = client.get("/api/v1/invitations/this-is-not-a-real-token-abc")
    assert resp.status_code == 410


def test_accept_creates_user_and_membership(
    client: TestClient, seeded: dict[str, str], login
) -> None:
    token = login(seeded["email_a"])
    client.post(
        "/api/v1/team/invitations",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "fresh@example.com", "is_team_admin": True},
    )
    raw = _token_from_last_email()
    accept = client.post(
        "/api/v1/invitations/accept",
        json={"token": raw, "password": NEW_PASSWORD, "full_name": "Fresh User"},
    )
    assert accept.status_code == 201, accept.text
    body = accept.json()
    assert body["email"] == "fresh@example.com"
    assert body["is_team_admin"] is True
    # The new user can now log in.
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "fresh@example.com", "password": NEW_PASSWORD},
    )
    assert login_resp.status_code == 200, login_resp.text


def test_accept_consumes_token(
    client: TestClient, seeded: dict[str, str], login
) -> None:
    token = login(seeded["email_a"])
    client.post(
        "/api/v1/team/invitations",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "single-use@example.com"},
    )
    raw = _token_from_last_email()
    first = client.post(
        "/api/v1/invitations/accept", json={"token": raw, "password": NEW_PASSWORD}
    )
    assert first.status_code == 201
    # A second use of the same token must fail with the generic 410.
    second = client.post(
        "/api/v1/invitations/accept", json={"token": raw, "password": NEW_PASSWORD}
    )
    assert second.status_code == 410


def test_expired_invitation_is_410(
    client: TestClient,
    seeded: dict[str, str],
    factory: sessionmaker[Session],
    login,
) -> None:
    token = login(seeded["email_a"])
    client.post(
        "/api/v1/team/invitations",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "stale@example.com"},
    )
    raw = _token_from_last_email()
    # Backdate the invitation past its expiry by reaching directly into the DB.
    with factory() as s:
        inv = find_active_invitation(s, raw)
        assert inv is not None
        inv.expires_at = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(
            minutes=1
        )
        s.commit()
    resp = client.post(
        "/api/v1/invitations/accept", json={"token": raw, "password": NEW_PASSWORD}
    )
    assert resp.status_code == 410


def test_invite_requires_team_admin(
    client: TestClient,
    seeded: dict[str, str],
    factory: sessionmaker[Session],
    login,
) -> None:
    # Promote tenant-a to two members so the sole-member bootstrap path no
    # longer applies, then ensure a non-admin member is forbidden from inviting.
    with factory() as s:
        s.add(
            Invitation(
                invitation_id="placeholder",
                tenant_id=seeded["tenant_a"],
                email="dummy@example.com",
                token_hash="0" * 64,
                invited_by=seeded["user_a"],
                is_team_admin=False,
                created_at=datetime.datetime.now(tz=datetime.UTC),
                expires_at=datetime.datetime.now(tz=datetime.UTC)
                + datetime.timedelta(days=7),
            )
        )
        s.commit()
    # The unauthenticated path is also rejected.
    resp = client.post("/api/v1/team/invitations", json={"email": "x@example.com"})
    assert resp.status_code == 401
