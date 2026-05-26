"""Tenant-aware data path: the single sanctioned way to touch tenant data (S01-01).

ADR-0002 mandates two-layer isolation. This module is the *application* layer: a
``TenantScope`` bound to one ``tenant_id`` that transparently injects
``tenant_id == <current>`` into every ORM query against a tenant-owned entity, via
a ``do_orm_execute`` event and ``with_loader_criteria``. There is no "fetch by id
without a tenant" path here — cross-tenant reads are impossible through this API.

On PostgreSQL the migration adds Row-Level Security as the backstop (verified
against Postgres, not SQLite). SQLite has no RLS, so these helpers ARE the
isolation under test; see ``tests/tenancy``.

The repository helpers (create_project, list_projects, get_project,
record_evaluation) all flow through a scoped session and stamp ``tenant_id`` on
write, so callers never hand-write a tenant filter (the classic leak vector).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import event, select
from sqlalchemy.orm import Session, sessionmaker, with_loader_criteria

from .models import TENANT_OWNED_MODELS, Project, ProjectEvaluation

_SCOPE_KEY = "ipermit_tenant_id"


def _tenant_criteria(model: type, tenant_id: int) -> Any:
    """Build a tenant filter for ``model`` whose value is a tracked bindparam.

    ``with_loader_criteria`` caches the criteria lambda by its code object. A
    captured closure variable (``tenant_id`` here) is extracted as a *bound
    parameter*, so the same compiled lambda safely carries a different value per
    invocation — using a default-argument value instead would bake the first
    tenant id into the cache and leak it to later scopes.
    """
    return with_loader_criteria(
        model,
        lambda cls: cls.tenant_id == tenant_id,
        include_aliases=True,
    )


def _install_tenant_filter(session: Session) -> None:
    """Attach a one-time event that scopes every query to the session's tenant.

    The handler reads the tenant id stashed in ``session.info`` and adds a
    ``with_loader_criteria`` for each tenant-owned model. ``include_aliases`` so
    joined/aliased references are scoped too. A missing tenant id is a
    programming error — fail loudly rather than leak.
    """

    @event.listens_for(session, "do_orm_execute")
    def _scope(orm_execute_state: Any) -> None:
        if not orm_execute_state.is_select:
            return
        tenant_id = session.info.get(_SCOPE_KEY)
        if tenant_id is None:
            raise RuntimeError("tenant-scoped session used without a tenant id")
        for model in TENANT_OWNED_MODELS:
            orm_execute_state.statement = orm_execute_state.statement.options(
                _tenant_criteria(model, tenant_id)
            )


class TenantScope:
    """A tenant-bound facade over a SQLAlchemy session.

    Construct via ``tenant_session`` (a context manager) rather than directly so
    the underlying session is opened, scoped, committed/rolled back, and closed
    deterministically.
    """

    def __init__(self, session: Session, tenant_id: int) -> None:
        self.session = session
        self.tenant_id = tenant_id
        session.info[_SCOPE_KEY] = tenant_id

    def create_project(self, *, name: str, created_by_user_id: str) -> Project:
        """Create a project owned by this scope's tenant and flush it."""
        project = Project(
            tenant_id=self.tenant_id,
            name=name,
            created_by_user_id=created_by_user_id,
        )
        self.session.add(project)
        self.session.flush()
        return project

    def list_projects(self) -> list[Project]:
        """Return this tenant's projects (deterministic order); never another's."""
        return list(self.session.scalars(select(Project).order_by(Project.id)))

    def get_project(self, project_id: int) -> Project | None:
        """Fetch one project by id, scoped to this tenant (None if not theirs)."""
        return self.session.scalars(
            select(Project).where(Project.id == project_id)
        ).one_or_none()

    def record_evaluation(
        self,
        *,
        project_id: int,
        ruleset_version: dict,
        inputs_hash: str,
        result_summary: dict,
    ) -> ProjectEvaluation:
        """Persist an evaluation run for a project this tenant owns.

        Raises ``ValueError`` if the project is not visible in this scope, so a
        caller cannot attach an evaluation to another tenant's project.
        """
        if self.get_project(project_id) is None:
            raise ValueError(f"project {project_id} not found in this tenant scope")
        evaluation = ProjectEvaluation(
            tenant_id=self.tenant_id,
            project_id=project_id,
            ruleset_version=ruleset_version,
            inputs_hash=inputs_hash,
            result_summary=result_summary,
        )
        self.session.add(evaluation)
        self.session.flush()
        return evaluation

    def list_evaluations(self, project_id: int) -> list[ProjectEvaluation]:
        """Return a project's evaluations, scoped to this tenant."""
        return list(
            self.session.scalars(
                select(ProjectEvaluation)
                .where(ProjectEvaluation.project_id == project_id)
                .order_by(ProjectEvaluation.id)
            )
        )


@contextmanager
def tenant_session(
    session_factory: sessionmaker[Session], tenant_id: int
) -> Iterator[TenantScope]:
    """Open a tenant-scoped session, commit on success, roll back on error.

    This is the only sanctioned entry point for tenant data. Every query made
    through the yielded ``TenantScope`` is filtered to ``tenant_id``.
    """
    session = session_factory()
    _install_tenant_filter(session)
    scope = TenantScope(session, tenant_id)
    try:
        yield scope
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
