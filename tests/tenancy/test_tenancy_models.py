"""Unit tests for the tenancy/project/evaluation/audit models (S01-01).

Run against in-memory SQLite so CI needs no PostgreSQL. Postgres RLS is verified
separately (see tests/api). Package import paths come from tests/conftest.py.
"""

from __future__ import annotations

import pytest
from ipermit_persistence import Base
from ipermit_tenancy import (
    TENANT_OWNED_TABLES,
    AuditRecord,
    Evaluation,
    Membership,
    Project,
    Tenant,
    User,
)
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_create_all_builds_tenancy_tables(session: Session) -> None:
    expected = {"tenant", "app_user", "membership", "project", "evaluation"}
    assert expected <= set(Base.metadata.tables)
    assert set(TENANT_OWNED_TABLES) == {"project", "evaluation"}


def test_persist_full_graph(session: Session) -> None:
    tenant = Tenant(tenant_id="t1", name="Acme")
    user = User(user_id="u1", email="a@example.com", password_hash="x")
    session.add_all([tenant, user, Membership(user_id="u1", tenant_id="t1")])
    session.flush()
    project = Project(project_id="p1", tenant_id="t1", name="Bridge", created_by="u1")
    session.add(project)
    session.flush()
    session.add(
        Evaluation(
            evaluation_id="e1",
            tenant_id="t1",
            project_id="p1",
            evaluation_date="2026-05-26",
            inputs_hash="sha256:a",
            ruleset_content_hash="sha256:b",
            matrix={"permits": []},
            created_by="u1",
        )
    )
    session.commit()
    assert session.get(Evaluation, "e1").tenant_id == "t1"
    assert session.get(User, "u1").platform_role == "consultant_user"


def test_email_is_unique(session: Session) -> None:
    session.add(User(user_id="u1", email="dup@example.com", password_hash="x"))
    session.add(User(user_id="u2", email="dup@example.com", password_hash="y"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_audit_record_persists(session: Session) -> None:
    session.add(
        AuditRecord(
            actor="u1",
            action="project.evaluated",
            subject="e1",
            payload={"inputs_hash": "sha256:a"},
            prev_hash=None,
            hash="sha256:c",
        )
    )
    session.commit()
    rec = session.query(AuditRecord).one()
    assert rec.id == 1
    assert rec.prev_hash is None
