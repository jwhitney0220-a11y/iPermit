"""Postgres Row-Level-Security isolation test (S01-07, ADR-0002).

Skipped unless ``IPERMIT_TEST_DATABASE_URL`` names a reachable PostgreSQL — the
default CI/dev path is SQLite, which has no RLS (isolation there is asserted at
the application layer in test_api.py). When a Postgres URL is provided, this
proves the second isolation layer: with ``app.current_tenant_id`` set to tenant
A, tenant B's rows are invisible even to a query that omits the tenant filter.

Requires a NON-superuser role: Postgres superusers and table owners with
``BYPASSRLS`` ignore policies. The migration uses ``FORCE ROW LEVEL SECURITY`` so
the owning role is still subject to them, but a superuser connection bypasses RLS
entirely — run this against an application-grade role.
"""

from __future__ import annotations

import os
import uuid

import pytest
from ipermit_persistence import Base
from ipermit_tenancy import Project, Tenant, User
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

_URL = os.environ.get("IPERMIT_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not _URL.startswith("postgresql"),
    reason="IPERMIT_TEST_DATABASE_URL is not a PostgreSQL URL",
)

_RLS_DDL = (
    "ALTER TABLE project ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE project FORCE ROW LEVEL SECURITY",
    "DROP POLICY IF EXISTS project_tenant_isolation ON project",
    "CREATE POLICY project_tenant_isolation ON project "
    "USING (tenant_id = current_setting('app.current_tenant_id', true))",
)


def _scope(session: Session, tenant_id: str) -> None:
    session.execute(
        text("SELECT set_config('app.current_tenant_id', :tid, false)"),
        {"tid": tenant_id},
    )


def test_rls_hides_other_tenant_rows() -> None:
    engine = create_engine(_URL, future=True)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for stmt in _RLS_DDL:
            conn.execute(text(stmt))
    a, b = uuid.uuid4().hex, uuid.uuid4().hex
    with Session(engine) as s:
        s.add_all([Tenant(tenant_id=a, name="A"), Tenant(tenant_id=b, name="B")])
        s.add(User(user_id="u", email=f"{a}@x.io", password_hash="x"))
        s.flush()
        s.add(Project(project_id="pa", tenant_id=a, name="A", created_by="u"))
        s.add(Project(project_id="pb", tenant_id=b, name="B", created_by="u"))
        s.commit()
    with Session(engine) as s:
        _scope(s, a)
        visible = s.scalars(select(Project.tenant_id)).all()
        assert set(visible) == {a}, "RLS must hide tenant B's rows from tenant A"
