"""Constrained AI assistance routes (SAAS-08, S08-01).

A single endpoint for the first slice: render the latest permit matrix as a
consultant-friendly advisory narrative. Three gates compose, in order:

1. **Feature flag** — ``AI_FEATURES_ENABLED`` defaults ``false`` so the AI
   surface ships dark until an environment opts in.
2. **Tenant entitlement** — AI features are premium (starter/pro), gated by
   the same :func:`require_entitlement` dependency used by exports (S03-02).
3. **Tenant scope + project ownership** — the matrix the narrative is
   built from is the *caller's* latest evaluation, never another tenant's.

The deterministic permit matrix is the source of truth (AGENTS.md *AI
Strategy*); the narrative is delivered alongside the platform advisory AND
an AI-content advisory (see :data:`ipermit_ai.AI_ADVISORY`) so a consultant
cannot mistake the prose for a legal determination.
"""

from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends
from ipermit_ai import AI_ADVISORY, summarize_matrix
from ipermit_tenancy import Evaluation
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai import get_ai_client
from ..audit import append_audit
from ..auth import AuthenticatedIdentity
from ..db import apply_tenant_scope, get_session
from ..entitlements import require_entitlement
from ..envelope import PLATFORM_ADVISORY, Advisory, Envelope, Meta, ProblemException
from ..schemas import NarrativeData
from ..settings import get_settings

router = APIRouter(prefix="/api/v1/projects", tags=["ai"])


def _require_tenant(identity: AuthenticatedIdentity) -> str:
    if identity.tenant_id is None:
        raise ProblemException(403, "No tenant membership")
    return identity.tenant_id


def _require_ai_enabled() -> None:
    if not get_settings().ai_features_enabled:
        raise ProblemException(
            403,
            "AI assistance is disabled",
            detail="AI_FEATURES_ENABLED is false in this environment.",
        )


def _latest_for_tenant(session: Session, tenant_id: str, project_id: str) -> Evaluation:
    evaluation = session.scalar(
        select(Evaluation)
        .where(Evaluation.project_id == project_id, Evaluation.tenant_id == tenant_id)
        .order_by(Evaluation.created_at.desc())
    )
    if evaluation is None:
        raise ProblemException(404, "No evaluation yet for this project")
    return evaluation


@router.post("/{project_id}/narrative", response_model=Envelope)
def matrix_narrative(
    project_id: str,
    identity: AuthenticatedIdentity = Depends(require_entitlement("starter", "pro")),
    session: Session = Depends(get_session),
) -> Envelope:
    """Render the latest permit matrix as an advisory narrative (S08-01)."""
    _require_ai_enabled()
    tenant_id = _require_tenant(identity)
    apply_tenant_scope(session, tenant_id)
    evaluation = _latest_for_tenant(session, tenant_id, project_id)
    result = summarize_matrix(evaluation.matrix, get_ai_client())
    matrix_hash = hashlib.sha256(
        json.dumps(evaluation.matrix, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    append_audit(
        session,
        actor=identity.email,
        action="ai.narrative_generated",
        subject=evaluation.evaluation_id,
        payload={
            "model": result.model,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "matrix_hash": matrix_hash,
        },
    )
    session.commit()
    matrix = evaluation.matrix
    return Envelope(
        data=NarrativeData(
            evaluation_id=evaluation.evaluation_id,
            narrative=result.text,
            model=result.model,
        ),
        meta=Meta(
            ruleset_version=matrix["ruleset_version"],
            evaluation_date=matrix["evaluation_date"],
            evaluation_id=matrix["evaluation_id"],
        ),
        advisories=[Advisory(**PLATFORM_ADVISORY), Advisory(**AI_ADVISORY)],
    )
