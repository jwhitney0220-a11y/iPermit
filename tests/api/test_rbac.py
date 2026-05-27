"""RBAC tests (S02-01): role-gated audit read + capability flag logic.

The audit log is platform-global and readable only by platform_admin (ADR-0002 /
ADR-0004). Capability flags (analyst:*) gate per-action analyst surfaces; a
platform_admin implicitly holds every capability.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from ipermit_api.auth import AuthenticatedIdentity, hash_password, require_capability
from ipermit_api.envelope import ProblemException
from ipermit_tenancy import User
from sqlalchemy.orm import Session, sessionmaker

# Must match tests/api/conftest.py PASSWORD (tests are not a package).
PASSWORD = "consultant-pw-123"


def _make_user(
    factory: sessionmaker[Session], email: str, role: str, caps: list[str]
) -> None:
    with factory() as s:
        s.add(
            User(
                user_id=uuid.uuid4().hex,
                email=email,
                password_hash=hash_password(PASSWORD),
                platform_role=role,
                capabilities=caps,
            )
        )
        s.commit()


def test_audit_requires_authentication(client: TestClient, seeded: dict) -> None:
    assert client.get("/api/v1/audit").status_code == 401


def test_consultant_cannot_read_audit(client: TestClient, seeded: dict, login) -> None:
    token = login(seeded["email_a"])
    resp = client.get("/api/v1/audit", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.headers["content-type"].startswith("application/problem+json")


def test_admin_reads_audit_chain(
    client: TestClient, seeded: dict, login, factory: sessionmaker[Session]
) -> None:
    # A consultant evaluation writes an audit record...
    consultant = login(seeded["email_a"])
    headers = {"Authorization": f"Bearer {consultant}"}
    pid = client.post("/api/v1/projects", json={"name": "P"}, headers=headers).json()[
        "project_id"
    ]
    client.post(
        f"/api/v1/projects/{pid}/evaluate",
        json={"project_type": "transmission_line"},
        headers=headers,
    )
    # ...which a platform_admin can read.
    _make_user(factory, "admin@example.com", "platform_admin", [])
    admin = login("admin@example.com")
    resp = client.get("/api/v1/audit", headers={"Authorization": f"Bearer {admin}"})
    assert resp.status_code == 200
    records = resp.json()
    assert any(r["action"] == "project.evaluated" for r in records)
    assert all("hash" in r for r in records)


def _identity(role: str, caps: frozenset[str]) -> AuthenticatedIdentity:
    return AuthenticatedIdentity(
        subject="u", email="u@x", platform_role=role, capabilities=caps
    )


def test_require_capability_admin_implies_all() -> None:
    dep = require_capability("analyst:publish")
    assert (
        dep(_identity("platform_admin", frozenset())).platform_role == "platform_admin"
    )


def test_require_capability_explicit_flag_passes() -> None:
    dep = require_capability("analyst:draft")
    ident = _identity("regulatory_analyst", frozenset({"analyst:draft"}))
    assert dep(ident) is ident


def test_require_capability_missing_flag_rejected() -> None:
    dep = require_capability("analyst:publish")
    with pytest.raises(ProblemException):
        dep(_identity("regulatory_analyst", frozenset({"analyst:draft"})))
    with pytest.raises(ProblemException):
        dep(_identity("consultant_user", frozenset()))
