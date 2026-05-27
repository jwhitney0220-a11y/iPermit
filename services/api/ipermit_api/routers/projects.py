"""Project endpoints (S01-04): create, list, evaluate, fetch matrix.

Every handler is tenant-scoped at the application layer (an explicit
``tenant_id`` filter, never a fetch-by-id without it — ADR-0002) and pins the
Postgres RLS GUC for the transaction (defense in depth). A project that belongs
to another tenant is reported as 404, not 403 — its existence is not revealed.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from ipermit_tenancy import Evaluation, Project
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import append_audit
from ..auth import AuthenticatedIdentity, get_current_identity
from ..db import apply_tenant_scope, get_session
from ..envelope import PLATFORM_ADVISORY, Advisory, Envelope, Meta, ProblemException
from ..evaluate import evaluate_project
from ..export import EXPORT_FORMATS, export_matrix
from ..schemas import (
    CreateProjectRequest,
    EvaluateRequest,
    EvaluationSummary,
    ProjectResponse,
)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

# Tier at or above which a permit warrants a confidence warning (Tier 1 is
# statutory/verified; Tier 2/3 need consultant confirmation — AGENTS.md tiers).
_CONFIDENCE_WARNING_TIER = 2


def _require_tenant(identity: AuthenticatedIdentity) -> str:
    """Return the caller's active tenant, or raise 403 if they have none."""
    if identity.tenant_id is None:
        raise ProblemException(403, "No tenant membership")
    return identity.tenant_id


def _load_project(session: Session, tenant_id: str, project_id: str) -> Project:
    """Load a tenant-scoped project or raise 404 (existence not revealed)."""
    project = session.scalar(
        select(Project).where(
            Project.project_id == project_id, Project.tenant_id == tenant_id
        )
    )
    if project is None:
        raise ProblemException(404, "Project not found")
    return project


def _warnings(matrix: dict[str, Any]) -> list[Advisory]:
    """Surface a confidence warning for every Tier 2/3 permit (ADR-0003)."""
    return [
        Advisory(
            text=f"{p['permit_name']} is Tier {p['confidence']['tier']}; "
            "consultant confirmation required.",
            origin="engine",
            category="confidence_warning",
        )
        for p in matrix["permits"]
        if p["confidence"]["tier"] >= _CONFIDENCE_WARNING_TIER
    ]


def _envelope(matrix: dict[str, Any]) -> Envelope:
    """Wrap a permit matrix in the ADR-0003 envelope with mandatory advisories."""
    return Envelope(
        data=matrix,
        meta=Meta(
            ruleset_version=matrix["ruleset_version"],
            evaluation_date=matrix["evaluation_date"],
            evaluation_id=matrix["evaluation_id"],
        ),
        advisories=[Advisory(**PLATFORM_ADVISORY)],
        warnings=_warnings(matrix),
    )


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(
    body: CreateProjectRequest,
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> ProjectResponse:
    """Create a project owned by the caller's active tenant."""
    tenant_id = _require_tenant(identity)
    apply_tenant_scope(session, tenant_id)
    project = Project(
        project_id=uuid.uuid4().hex,
        tenant_id=tenant_id,
        name=body.name,
        created_by=identity.subject,
    )
    session.add(project)
    session.commit()
    return ProjectResponse(
        project_id=project.project_id,
        tenant_id=project.tenant_id,
        name=project.name,
        created_by=project.created_by,
    )


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> list[ProjectResponse]:
    """List projects owned by the caller's active tenant."""
    tenant_id = _require_tenant(identity)
    apply_tenant_scope(session, tenant_id)
    projects = session.scalars(
        select(Project).where(Project.tenant_id == tenant_id).order_by(Project.name)
    )
    return [
        ProjectResponse(
            project_id=p.project_id,
            tenant_id=p.tenant_id,
            name=p.name,
            created_by=p.created_by,
        )
        for p in projects
    ]


@router.post("/{project_id}/evaluate", response_model=Envelope)
def evaluate(
    project_id: str,
    body: EvaluateRequest,
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> Envelope:
    """Evaluate the project and return the explainable permit matrix."""
    tenant_id = _require_tenant(identity)
    apply_tenant_scope(session, tenant_id)
    _load_project(session, tenant_id, project_id)
    evaluation = evaluate_project(
        session,
        project_id=project_id,
        tenant_id=tenant_id,
        actor=identity.subject,
        request=body,
    )
    append_audit(
        session,
        actor=identity.email,
        action="project.evaluated",
        subject=evaluation.evaluation_id,
        payload={
            "project_id": project_id,
            "tenant_id": tenant_id,
            "inputs_hash": evaluation.inputs_hash,
            "ruleset_content_hash": evaluation.ruleset_content_hash,
            "permit_count": len(evaluation.matrix["permits"]),
        },
    )
    session.commit()
    return _envelope(evaluation.matrix)


def _latest_evaluation(session: Session, tenant_id: str, project_id: str) -> Evaluation:
    """Load the most recent tenant-scoped evaluation, or raise 404."""
    _load_project(session, tenant_id, project_id)
    evaluation = session.scalar(
        select(Evaluation)
        .where(Evaluation.project_id == project_id, Evaluation.tenant_id == tenant_id)
        .order_by(Evaluation.created_at.desc())
    )
    if evaluation is None:
        raise ProblemException(404, "No evaluation yet for this project")
    return evaluation


@router.get("/{project_id}/matrix", response_model=Envelope)
def get_matrix(
    project_id: str,
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> Envelope:
    """Return the most recent permit matrix for the project."""
    tenant_id = _require_tenant(identity)
    apply_tenant_scope(session, tenant_id)
    return _envelope(_latest_evaluation(session, tenant_id, project_id).matrix)


@router.get("/{project_id}/evaluations", response_model=list[EvaluationSummary])
def list_evaluations(
    project_id: str,
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> list[EvaluationSummary]:
    """List the project's evaluation history, newest first (S02-03)."""
    tenant_id = _require_tenant(identity)
    apply_tenant_scope(session, tenant_id)
    _load_project(session, tenant_id, project_id)
    rows = session.scalars(
        select(Evaluation)
        .where(Evaluation.project_id == project_id, Evaluation.tenant_id == tenant_id)
        .order_by(Evaluation.created_at.desc())
    )
    return [
        EvaluationSummary(
            evaluation_id=e.evaluation_id,
            evaluation_date=e.evaluation_date,
            inputs_hash=e.inputs_hash,
            ruleset_content_hash=e.ruleset_content_hash,
            permit_count=len(e.matrix["permits"]),
            created_at=e.created_at,
        )
        for e in rows
    ]


@router.get("/{project_id}/evaluations/{evaluation_id}", response_model=Envelope)
def get_evaluation(
    project_id: str,
    evaluation_id: str,
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> Envelope:
    """Return a specific historical evaluation's matrix (S02-03)."""
    tenant_id = _require_tenant(identity)
    apply_tenant_scope(session, tenant_id)
    _load_project(session, tenant_id, project_id)
    evaluation = session.scalar(
        select(Evaluation).where(
            Evaluation.evaluation_id == evaluation_id,
            Evaluation.project_id == project_id,
            Evaluation.tenant_id == tenant_id,
        )
    )
    if evaluation is None:
        raise ProblemException(404, "Evaluation not found")
    return _envelope(evaluation.matrix)


@router.get("/{project_id}/matrix/export")
def export_matrix_endpoint(
    project_id: str,
    format: str = Query("json", pattern="^(json|xlsx|pdf)$"),
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> Response:
    """Export the latest permit matrix as a json/xlsx/pdf deliverable (T07-04)."""
    tenant_id = _require_tenant(identity)
    apply_tenant_scope(session, tenant_id)
    if format not in EXPORT_FORMATS:
        raise ProblemException(422, "Unsupported export format")
    evaluation = _latest_evaluation(session, tenant_id, project_id)
    content, media_type, filename = export_matrix(evaluation.matrix, format)
    append_audit(
        session,
        actor=identity.email,
        action="matrix.exported",
        subject=evaluation.evaluation_id,
        payload={"project_id": project_id, "tenant_id": tenant_id, "format": format},
    )
    session.commit()
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
