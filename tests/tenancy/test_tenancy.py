"""Unit tests for the multi-tenant data layer (S01-01).

Run against in-memory SQLite so CI needs no PostgreSQL (ADR-0005). Package
import paths are set up in tests/conftest.py.

ISOLATION NOTE. On SQLite the application-layer scope (``ipermit_tenancy.session``)
is the *only* tenant isolation, so these tests exercise it directly. PostgreSQL
Row-Level Security is the defense-in-depth backstop (ADR-0002) attached by the
Alembic migration; RLS cannot be exercised on SQLite and must be verified against
a live PostgreSQL instance (current_setting('app.tenant_id')-keyed policies). See
``test_postgres_rls_is_the_db_backstop`` for that boundary.
"""

from __future__ import annotations

import pytest
from ipermit_persistence import Base
from ipermit_tenancy import (
    MEMBERSHIP_ROLES,
    TENANT_KINDS,
    Project,
    ProjectEvaluation,
    Tenant,
    TenantMembership,
    tenant_session,
)
from ipermit_tenancy.session import _install_tenant_filter
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _make_tenant(factory: sessionmaker[Session], name: str, kind: str) -> int:
    """Create a tenant outside any tenant scope; return its id."""
    with factory() as plain:
        tenant = Tenant(name=name, kind=kind)
        plain.add(tenant)
        plain.commit()
        return tenant.id


def test_create_all_builds_all_four_tables(
    session_factory: sessionmaker[Session],
) -> None:
    expected = {"tenant", "tenant_membership", "project", "project_evaluation"}
    assert expected <= set(Base.metadata.tables)


def test_create_and_list_projects_scoped_to_tenant(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _make_tenant(session_factory, "Acme", "enterprise")
    with tenant_session(session_factory, tenant_id) as scope:
        scope.create_project(name="Bridge", created_by_user_id="u-1")
        scope.create_project(name="Levee", created_by_user_id="u-1")
    with tenant_session(session_factory, tenant_id) as scope:
        names = [p.name for p in scope.list_projects()]
    assert names == ["Bridge", "Levee"]


def test_project_isolation_between_tenants(
    session_factory: sessionmaker[Session],
) -> None:
    """The core security property: a scope sees only its own tenant's projects."""
    tenant_a = _make_tenant(session_factory, "Tenant A", "individual")
    tenant_b = _make_tenant(session_factory, "Tenant B", "individual")
    with tenant_session(session_factory, tenant_a) as scope:
        project_a = scope.create_project(name="A-Proj", created_by_user_id="ua")
        a_id = project_a.id
    with tenant_session(session_factory, tenant_b) as scope:
        project_b = scope.create_project(name="B-Proj", created_by_user_id="ub")
        b_id = project_b.id

    with tenant_session(session_factory, tenant_a) as scope:
        assert [p.name for p in scope.list_projects()] == ["A-Proj"]
        assert scope.get_project(a_id) is not None
        # B's project is invisible through A's scope, even by its real id.
        assert scope.get_project(b_id) is None

    with tenant_session(session_factory, tenant_b) as scope:
        assert [p.name for p in scope.list_projects()] == ["B-Proj"]
        assert scope.get_project(a_id) is None


def test_evaluation_isolation_between_tenants(
    session_factory: sessionmaker[Session],
) -> None:
    """ProjectEvaluation is tenant-scoped too, never cross-readable."""
    tenant_a = _make_tenant(session_factory, "A", "individual")
    tenant_b = _make_tenant(session_factory, "B", "individual")
    with tenant_session(session_factory, tenant_a) as scope:
        proj = scope.create_project(name="A", created_by_user_id="ua")
        scope.record_evaluation(
            project_id=proj.id,
            ruleset_version={"v": 1},
            inputs_hash="h-a",
            result_summary={"ok": True},
        )
        a_proj_id = proj.id

    # B cannot see A's evaluations and cannot fetch A's project to attach one.
    with tenant_session(session_factory, tenant_b) as scope:
        assert scope.list_evaluations(a_proj_id) == []
        with pytest.raises(ValueError):
            scope.record_evaluation(
                project_id=a_proj_id,
                ruleset_version={"v": 1},
                inputs_hash="h-b",
                result_summary={"ok": False},
            )

    with tenant_session(session_factory, tenant_a) as scope:
        evals = scope.list_evaluations(a_proj_id)
    assert [e.inputs_hash for e in evals] == ["h-a"]


def test_record_evaluation_roundtrips_json(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _make_tenant(session_factory, "Acme", "enterprise")
    ruleset = {"ruleset_id": "tx-2026", "version": "3.2.1", "rules": [1, 2, 3]}
    summary = {"required": ["permit-a"], "score": 0.91, "details": {"k": "v"}}
    with tenant_session(session_factory, tenant_id) as scope:
        proj = scope.create_project(name="P", created_by_user_id="u")
        evaluation = scope.record_evaluation(
            project_id=proj.id,
            ruleset_version=ruleset,
            inputs_hash="abc123",
            result_summary=summary,
        )
        eval_id = evaluation.id

    with tenant_session(session_factory, tenant_id) as scope:
        stored = scope.session.get(ProjectEvaluation, eval_id)
        assert stored is not None
        assert stored.ruleset_version == ruleset
        assert stored.result_summary == summary
        assert stored.inputs_hash == "abc123"


def test_membership_unique_per_tenant_user(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _make_tenant(session_factory, "Acme", "enterprise")
    with session_factory() as plain:
        plain.add(
            TenantMembership(tenant_id=tenant_id, user_id="u-1", role="consultant_user")
        )
        plain.commit()
    with session_factory() as plain:
        plain.add(
            TenantMembership(
                tenant_id=tenant_id, user_id="u-1", role="regulatory_analyst"
            )
        )
        with pytest.raises(IntegrityError):
            plain.commit()


def test_same_user_can_belong_to_two_tenants(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_a = _make_tenant(session_factory, "A", "enterprise")
    tenant_b = _make_tenant(session_factory, "B", "enterprise")
    with session_factory() as plain:
        plain.add(
            TenantMembership(tenant_id=tenant_a, user_id="u", role="consultant_user")
        )
        plain.add(
            TenantMembership(tenant_id=tenant_b, user_id="u", role="platform_admin")
        )
        plain.commit()
        rows = plain.scalars(select(TenantMembership)).all()
    assert {r.tenant_id for r in rows} == {tenant_a, tenant_b}


def test_role_enum_rejects_unknown_value(
    session_factory: sessionmaker[Session],
) -> None:
    """The native_enum=False CHECK constraint rejects an off-list role."""
    tenant_id = _make_tenant(session_factory, "Acme", "enterprise")
    with session_factory() as plain:
        plain.add(TenantMembership(tenant_id=tenant_id, user_id="u", role="superadmin"))
        with pytest.raises(IntegrityError):
            plain.commit()


def test_tenant_kind_enum_rejects_unknown_value(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as plain:
        plain.add(Tenant(name="X", kind="reseller"))
        with pytest.raises(IntegrityError):
            plain.commit()


def test_enum_value_tuples_match_adr_0002() -> None:
    assert TENANT_KINDS == ("individual", "enterprise")
    assert MEMBERSHIP_ROLES == (
        "platform_admin",
        "regulatory_analyst",
        "consultant_user",
    )


def test_scope_without_tenant_id_fails_loudly(
    session_factory: sessionmaker[Session],
) -> None:
    """A query through a session missing the tenant id raises, never leaks."""
    session = session_factory()
    _install_tenant_filter(session)
    with pytest.raises(RuntimeError):
        session.scalars(select(Project)).all()
    session.close()


def test_postgres_rls_is_the_db_backstop() -> None:
    """RLS is the database backstop and is NOT exercised here.

    ADR-0002 mandates two-layer isolation. The Alembic migration attaches
    PostgreSQL Row-Level Security policies keyed on ``current_setting('app.tenant_id')``
    to every tenant-owned table (``project``, ``project_evaluation``), enabled and
    FORCED so even the table owner is bound by them. SQLite has no RLS, so this
    test suite verifies only the application-layer scope. The RLS policies must be
    verified against a live PostgreSQL instance (set the GUC, attempt a
    cross-tenant read, assert zero rows) in a Postgres-backed integration test —
    out of scope for this SQLite-only unit suite.
    """
    assert True
