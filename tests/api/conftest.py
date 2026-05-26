"""Fixtures for the API tests (S01-07).

Boots the FastAPI app over an in-memory SQLite database with the tenancy tables
created and a seeded consultant in tenant A plus a second consultant in tenant B
(for cross-tenant isolation tests). RLS is a Postgres feature; on SQLite these
tests assert the application-layer tenant scope (ADR-0002 two-layer model). A
dedicated Postgres RLS test lives in test_rls.py and is skipped without a DB.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from ipermit_api.app import create_app
from ipermit_api.auth import hash_password
from ipermit_api.db import get_session
from ipermit_persistence import Base
from ipermit_tenancy import Membership, Tenant, User
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

PASSWORD = "consultant-pw-123"


@pytest.fixture
def factory() -> sessionmaker[Session]:
    # StaticPool + a single shared connection so the TestClient's worker thread
    # sees the same in-memory database the fixtures seed (each new :memory:
    # connection would otherwise get a fresh, empty database).
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def seeded(factory: sessionmaker[Session]) -> dict[str, str]:
    """Seed two tenants, each with one consultant; return their ids/emails."""
    ids = {
        "tenant_a": uuid.uuid4().hex,
        "tenant_b": uuid.uuid4().hex,
        "user_a": uuid.uuid4().hex,
        "user_b": uuid.uuid4().hex,
        "email_a": "a@example.com",
        "email_b": "b@example.com",
    }
    with factory() as s:
        for suffix in ("a", "b"):
            s.add(Tenant(tenant_id=ids[f"tenant_{suffix}"], name=f"Tenant {suffix}"))
            s.add(
                User(
                    user_id=ids[f"user_{suffix}"],
                    email=ids[f"email_{suffix}"],
                    password_hash=hash_password(PASSWORD),
                )
            )
            s.add(
                Membership(
                    user_id=ids[f"user_{suffix}"], tenant_id=ids[f"tenant_{suffix}"]
                )
            )
        s.commit()
    return ids


@pytest.fixture
def client(factory: sessionmaker[Session]) -> Iterator[TestClient]:
    app = create_app()

    def _session() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = _session
    with TestClient(app) as c:
        yield c


@pytest.fixture
def login(client: TestClient):
    """Return a helper that logs in by email and yields a bearer token."""

    def _login(email: str) -> str:
        resp = client.post(
            "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
        )
        assert resp.status_code == 200, resp.text
        return resp.json()["access_token"]

    return _login
