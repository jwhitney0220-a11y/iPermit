"""Team management tests (S04-02).

A tenant's sole member can bootstrap (add the first teammate); after that,
mutations require the tenant-local team-admin flag. All scoped to the caller's
tenant. Inviting an unregistered email is a 404 (account-verification deferred).
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from ipermit_api.auth import hash_password
from ipermit_tenancy import Membership, User
from sqlalchemy.orm import Session, sessionmaker

PASSWORD = "consultant-pw-123"  # matches tests/api/conftest.py


def _make_user(factory: sessionmaker[Session], email: str) -> str:
    uid = uuid.uuid4().hex
    with factory() as s:
        s.add(User(user_id=uid, email=email, password_hash=hash_password(PASSWORD)))
        s.commit()
    return uid


def _add_to_tenant(factory: sessionmaker[Session], uid: str, tenant_id: str) -> None:
    with factory() as s:
        s.add(Membership(user_id=uid, tenant_id=tenant_id))
        s.commit()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_sole_member_can_add_existing_user(
    client: TestClient, seeded: dict, login, factory: sessionmaker[Session]
) -> None:
    _make_user(factory, "teammate@example.com")
    token = login(seeded["email_a"])  # tenant A sole member
    resp = client.post(
        "/api/v1/team/members",
        json={"email": "teammate@example.com"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    members = client.get("/api/v1/team/members", headers=_auth(token)).json()
    assert {m["email"] for m in members} == {seeded["email_a"], "teammate@example.com"}


def test_add_unknown_email_is_404(client: TestClient, seeded: dict, login) -> None:
    token = login(seeded["email_a"])
    resp = client.post(
        "/api/v1/team/members",
        json={"email": "nobody@example.com"},
        headers=_auth(token),
    )
    assert resp.status_code == 404


def test_non_admin_member_cannot_manage(
    client: TestClient, seeded: dict, login, factory: sessionmaker[Session]
) -> None:
    # Two members, neither flagged admin -> not sole -> cannot mutate.
    uid_b = _make_user(factory, "memberb@example.com")
    _add_to_tenant(factory, uid_b, seeded["tenant_a"])
    other = _make_user(factory, "memberc@example.com")
    token_b = login("memberb@example.com")
    resp = client.post(
        "/api/v1/team/members",
        json={"email": "memberc@example.com"},
        headers=_auth(token_b),
    )
    assert resp.status_code == 403
    assert other  # silence unused


def test_promote_and_remove_member(
    client: TestClient, seeded: dict, login, factory: sessionmaker[Session]
) -> None:
    uid_b = _make_user(factory, "promote@example.com")
    token_a = login(seeded["email_a"])  # sole-member bootstrap admin
    client.post(
        "/api/v1/team/members",
        json={"email": "promote@example.com"},
        headers=_auth(token_a),
    )
    # Promote B to team admin.
    patched = client.patch(
        f"/api/v1/team/members/{uid_b}",
        json={"is_team_admin": True},
        headers=_auth(token_a),
    )
    assert patched.status_code == 200
    assert patched.json()["is_team_admin"] is True
    # Now B (admin) can remove A.
    token_b = login("promote@example.com")
    removed = client.delete(
        f"/api/v1/team/members/{seeded['user_a']}", headers=_auth(token_b)
    )
    assert removed.status_code == 204
    members = client.get("/api/v1/team/members", headers=_auth(token_b)).json()
    assert [m["email"] for m in members] == ["promote@example.com"]


def test_team_is_tenant_scoped(client: TestClient, seeded: dict, login) -> None:
    token_b = login(seeded["email_b"])  # tenant B
    members = client.get("/api/v1/team/members", headers=_auth(token_b)).json()
    assert [m["email"] for m in members] == [seeded["email_b"]]
