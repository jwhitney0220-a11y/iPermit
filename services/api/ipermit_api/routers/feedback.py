"""Feedback queue (S02-05, roadmap T08-06).

Consultants submit feedback on an evaluation and see only their own tenant's
items (tenant-scoped: app-layer filter + Postgres RLS). Analysts triage a
platform-wide queue and disposition items (confirm/reject) — disposition is
``regulatory_analyst``-gated and never changes a rule (AGENTS.md *User Feedback
Queue*: no auto-publish, no bypass of analyst review). Every submit and
disposition is written to the audit log (ADR-0004).
"""

from __future__ import annotations

import datetime
import uuid

from fastapi import APIRouter, Depends
from ipermit_tenancy import Feedback
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import append_audit
from ..auth import AuthenticatedIdentity, get_current_identity, require_role
from ..db import apply_tenant_scope, get_session
from ..envelope import ProblemException
from ..schemas import DispositionRequest, FeedbackResponse, SubmitFeedbackRequest

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


def _to_response(item: Feedback) -> FeedbackResponse:
    return FeedbackResponse(
        feedback_id=item.feedback_id,
        tenant_id=item.tenant_id,
        project_id=item.project_id,
        evaluation_id=item.evaluation_id,
        submitted_by=item.submitted_by,
        category=item.category,
        message=item.message,
        status=item.status,
        disposition_note=item.disposition_note,
        dispositioned_by=item.dispositioned_by,
        created_at=item.created_at,
        dispositioned_at=item.dispositioned_at,
    )


def _require_tenant(identity: AuthenticatedIdentity) -> str:
    if identity.tenant_id is None:
        raise ProblemException(403, "No tenant membership")
    return identity.tenant_id


@router.post("", response_model=FeedbackResponse, status_code=201)
def submit_feedback(
    body: SubmitFeedbackRequest,
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> FeedbackResponse:
    """Submit feedback within the caller's tenant (consultant)."""
    tenant_id = _require_tenant(identity)
    apply_tenant_scope(session, tenant_id)
    item = Feedback(
        feedback_id=uuid.uuid4().hex,
        tenant_id=tenant_id,
        project_id=body.project_id,
        evaluation_id=body.evaluation_id,
        submitted_by=identity.subject,
        category=body.category,
        message=body.message,
    )
    session.add(item)
    session.flush()
    append_audit(
        session,
        actor=identity.email,
        action="feedback.submitted",
        subject=item.feedback_id,
        payload={"tenant_id": tenant_id, "category": body.category},
    )
    session.commit()
    return _to_response(item)


@router.get("", response_model=list[FeedbackResponse])
def list_feedback(
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> list[FeedbackResponse]:
    """List the caller's own-tenant feedback, newest first (consultant)."""
    tenant_id = _require_tenant(identity)
    apply_tenant_scope(session, tenant_id)
    rows = session.scalars(
        select(Feedback)
        .where(Feedback.tenant_id == tenant_id)
        .order_by(Feedback.created_at.desc())
    )
    return [_to_response(f) for f in rows]


@router.get("/queue", response_model=list[FeedbackResponse])
def feedback_queue(
    _identity: AuthenticatedIdentity = Depends(require_role("regulatory_analyst")),
    session: Session = Depends(get_session),
) -> list[FeedbackResponse]:
    """List open feedback across all tenants (analyst triage, platform-wide)."""
    rows = session.scalars(
        select(Feedback).where(Feedback.status == "open").order_by(Feedback.created_at)
    )
    return [_to_response(f) for f in rows]


@router.post("/{feedback_id}/disposition", response_model=FeedbackResponse)
def disposition_feedback(
    feedback_id: str,
    body: DispositionRequest,
    identity: AuthenticatedIdentity = Depends(require_role("regulatory_analyst")),
    session: Session = Depends(get_session),
) -> FeedbackResponse:
    """Confirm or reject a feedback item (analyst-only; never edits rules)."""
    item = session.scalar(select(Feedback).where(Feedback.feedback_id == feedback_id))
    if item is None:
        raise ProblemException(404, "Feedback not found")
    if item.status != "open":
        raise ProblemException(409, "Feedback already dispositioned")
    item.status = body.decision
    item.disposition_note = body.note
    item.dispositioned_by = identity.email
    item.dispositioned_at = datetime.datetime.now(tz=datetime.UTC)
    session.flush()
    append_audit(
        session,
        actor=identity.email,
        action="feedback.dispositioned",
        subject=item.feedback_id,
        payload={"decision": body.decision, "tenant_id": item.tenant_id},
    )
    session.commit()
    return _to_response(item)
