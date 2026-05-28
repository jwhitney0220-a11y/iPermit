"""Rule-publication workflow (S05-02, roadmap T08-04).

The analyst governance trail: an ``analyst:draft`` proposes a rule transition
(``draft`` -> ``effective`` or ``effective`` -> ``archived``); an
``analyst:publish`` approves, rejects, or rolls back. ADR-0002 separation-of-
duties is enforced server-side: the approver / rejecter MUST be a different
identity from the proposer (the SOP's "drafter != reviewer" rule).

This module records the governance state and writes audit events; the engine's
file-system rule store stays the canonical content. Linking the in-force
``status`` back into the engine's load path is a follow-up — what UNBLOCKS now
is the auditable promotion record real governance depends on.
"""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, Query
from ipermit_tenancy import RulePublication
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import append_audit
from ..auth import AuthenticatedIdentity, get_current_identity, require_capability
from ..db import get_session
from ..envelope import ProblemException
from ..schemas import (
    ProposePublicationRequest,
    PublicationDecisionRequest,
    PublicationResponse,
)

router = APIRouter(prefix="/api/v1/rules/publications", tags=["publications"])


def _to_response(row: RulePublication) -> PublicationResponse:
    return PublicationResponse(
        id=row.id,
        rule_id=row.rule_id,
        rule_version=row.rule_version,
        target_status=row.target_status,
        status=row.status,
        proposed_by=row.proposed_by,
        proposed_at=row.proposed_at,
        reason=row.reason,
        decided_by=row.decided_by,
        decided_at=row.decided_at,
        decision_note=row.decision_note,
    )


def _load(session: Session, publication_id: int) -> RulePublication:
    row = session.get(RulePublication, publication_id)
    if row is None:
        raise ProblemException(404, "Publication not found")
    return row


def _decide(
    session: Session,
    identity: AuthenticatedIdentity,
    publication_id: int,
    note: str | None,
    *,
    new_status: str,
    require_from: tuple[str, ...],
    audit_action: str,
    enforce_sod: bool,
) -> RulePublication:
    """Common path for approve/reject/rollback transitions + audit + SoD."""
    row = _load(session, publication_id)
    if row.status not in require_from:
        raise ProblemException(409, f"Publication is {row.status}")
    if enforce_sod and row.proposed_by == identity.email:
        raise ProblemException(403, "Separation of duties: proposer cannot decide")
    row.status = new_status
    row.decided_by = identity.email
    row.decided_at = datetime.datetime.now(tz=datetime.UTC)
    row.decision_note = note
    session.flush()
    append_audit(
        session,
        actor=identity.email,
        action=audit_action,
        subject=f"{row.rule_id}@{row.rule_version}",
        payload={
            "publication_id": row.id,
            "target_status": row.target_status,
            "status": new_status,
        },
    )
    session.commit()
    return row


@router.post("", response_model=PublicationResponse, status_code=201)
def propose_publication(
    body: ProposePublicationRequest,
    identity: AuthenticatedIdentity = Depends(require_capability("analyst:draft")),
    session: Session = Depends(get_session),
) -> PublicationResponse:
    """Open a publication proposal (analyst:draft)."""
    row = RulePublication(
        rule_id=body.rule_id,
        rule_version=body.rule_version,
        target_status=body.target_status,
        proposed_by=identity.email,
        reason=body.reason,
    )
    session.add(row)
    session.flush()
    append_audit(
        session,
        actor=identity.email,
        action="rule.publication_proposed",
        subject=f"{body.rule_id}@{body.rule_version}",
        payload={"publication_id": row.id, "target_status": body.target_status},
    )
    session.commit()
    return _to_response(row)


@router.get("", response_model=list[PublicationResponse])
def list_publications(
    status: str | None = Query(None),
    _identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> list[PublicationResponse]:
    """List publications (any authenticated identity; defaults newest first)."""
    if not _identity.has_role("regulatory_analyst"):
        raise ProblemException(403, "Analyst access required")
    stmt = select(RulePublication).order_by(RulePublication.id.desc())
    if status is not None:
        stmt = stmt.where(RulePublication.status == status)
    return [_to_response(r) for r in session.scalars(stmt)]


@router.post("/{publication_id}/approve", response_model=PublicationResponse)
def approve_publication(
    publication_id: int,
    body: PublicationDecisionRequest,
    identity: AuthenticatedIdentity = Depends(require_capability("analyst:publish")),
    session: Session = Depends(get_session),
) -> PublicationResponse:
    """Approve a proposal (analyst:publish; proposer != approver)."""
    row = _decide(
        session,
        identity,
        publication_id,
        body.note,
        new_status="approved",
        require_from=("proposed",),
        audit_action="rule.publication_approved",
        enforce_sod=True,
    )
    return _to_response(row)


@router.post("/{publication_id}/reject", response_model=PublicationResponse)
def reject_publication(
    publication_id: int,
    body: PublicationDecisionRequest,
    identity: AuthenticatedIdentity = Depends(require_capability("analyst:publish")),
    session: Session = Depends(get_session),
) -> PublicationResponse:
    """Reject a proposal (analyst:publish; proposer != rejecter)."""
    row = _decide(
        session,
        identity,
        publication_id,
        body.note,
        new_status="rejected",
        require_from=("proposed",),
        audit_action="rule.publication_rejected",
        enforce_sod=True,
    )
    return _to_response(row)


@router.post("/{publication_id}/rollback", response_model=PublicationResponse)
def rollback_publication(
    publication_id: int,
    body: PublicationDecisionRequest,
    identity: AuthenticatedIdentity = Depends(require_capability("analyst:publish")),
    session: Session = Depends(get_session),
) -> PublicationResponse:
    """Roll back an approved publication (analyst:publish)."""
    row = _decide(
        session,
        identity,
        publication_id,
        body.note,
        new_status="rolled_back",
        require_from=("approved",),
        audit_action="rule.publication_rolled_back",
        enforce_sod=False,
    )
    return _to_response(row)
