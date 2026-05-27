"""Audit coverage across event types (S02-02, ADR-0004).

The hash-chained audit log now records auth-significant events (login success /
failure) and project creation in addition to evaluations and exports. A separate
Postgres-only test proves the append-only trigger blocks UPDATE/DELETE.
"""

from __future__ import annotations

import os
from itertools import pairwise

import pytest
from fastapi.testclient import TestClient
from ipermit_persistence import Base
from ipermit_tenancy import AuditRecord
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.orm import Session, sessionmaker


def _actions(factory: sessionmaker[Session]) -> list[str]:
    with factory() as s:
        return [
            r.action for r in s.scalars(select(AuditRecord).order_by(AuditRecord.id))
        ]


def test_successful_login_is_audited(
    client: TestClient, seeded: dict, login, factory: sessionmaker[Session]
) -> None:
    login(seeded["email_a"])
    assert "auth.login" in _actions(factory)


def test_failed_login_is_audited(
    client: TestClient, seeded: dict, factory: sessionmaker[Session]
) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": seeded["email_a"], "password": "wrong"},
    )
    assert resp.status_code == 401
    assert "auth.login_failed" in _actions(factory)


def test_project_creation_is_audited(
    client: TestClient, seeded: dict, login, factory: sessionmaker[Session]
) -> None:
    token = login(seeded["email_a"])
    client.post(
        "/api/v1/projects",
        json={"name": "Audited"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert "project.created" in _actions(factory)


def test_chain_links_across_event_types(
    client: TestClient, seeded: dict, login, factory: sessionmaker[Session]
) -> None:
    token = login(seeded["email_a"])  # auth.login
    headers = {"Authorization": f"Bearer {token}"}
    pid = client.post("/api/v1/projects", json={"name": "C"}, headers=headers).json()[
        "project_id"
    ]  # project.created
    client.post(
        f"/api/v1/projects/{pid}/evaluate",
        json={"project_type": "transmission_line"},
        headers=headers,
    )  # project.evaluated
    with factory() as s:
        records = list(s.scalars(select(AuditRecord).order_by(AuditRecord.id)))
    assert len(records) >= 3
    assert records[0].prev_hash is None
    for prev, curr in pairwise(records):
        assert curr.prev_hash == prev.hash


_URL = os.environ.get("IPERMIT_TEST_DATABASE_URL", "")


@pytest.mark.skipif(
    not _URL.startswith("postgresql"),
    reason="IPERMIT_TEST_DATABASE_URL is not a PostgreSQL URL",
)
def test_postgres_audit_is_append_only() -> None:
    engine = create_engine(_URL, future=True)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE OR REPLACE FUNCTION ipermit_audit_append_only() RETURNS trigger "
                "AS $$ BEGIN RAISE EXCEPTION 'append-only'; END; $$ LANGUAGE plpgsql"
            )
        )
        conn.execute(
            text(
                "DROP TRIGGER IF EXISTS audit_record_append_only ON audit_record; "
                "CREATE TRIGGER audit_record_append_only BEFORE UPDATE OR DELETE ON "
                "audit_record FOR EACH ROW EXECUTE FUNCTION ipermit_audit_append_only()"
            )
        )
    with Session(engine) as s:
        s.add(
            AuditRecord(
                actor="a", action="x", subject="s", payload={}, prev_hash=None, hash="h"
            )
        )
        s.commit()
        with pytest.raises(Exception, match="append-only"):
            s.execute(update(AuditRecord).values(action="tampered"))
            s.commit()
