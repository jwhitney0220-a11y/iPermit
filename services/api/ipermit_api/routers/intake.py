"""AI intake suggestion route (S08-02, SAAS-08).

A consultant pastes a short project description and the AI returns *suggested*
intake-form values they can accept, edit, or discard. Nothing here is sent to
the deterministic rules engine — the consultant must confirm every field on
the existing intake form first. The route wears the same three S08-01 gates
(feature flag, premium entitlement, authenticated identity) plus an
audit-on-success and the standard advisory framing.
"""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends
from ipermit_ai import AI_ADVISORY, SuggestionParseError, suggest_intake
from sqlalchemy.orm import Session

from ..ai import get_ai_client
from ..audit import append_audit
from ..auth import AuthenticatedIdentity
from ..db import get_session
from ..entitlements import require_entitlement
from ..envelope import PLATFORM_ADVISORY, Advisory, Envelope, Meta, ProblemException
from ..schemas import IntakeSuggestData, IntakeSuggestRequest
from ..settings import get_settings

router = APIRouter(prefix="/api/v1/intake", tags=["ai"])


def _require_ai_enabled() -> None:
    if not get_settings().ai_features_enabled:
        raise ProblemException(
            403,
            "AI assistance is disabled",
            detail="AI_FEATURES_ENABLED is false in this environment.",
        )


@router.post("/suggest", response_model=Envelope)
def suggest(
    body: IntakeSuggestRequest,
    identity: AuthenticatedIdentity = Depends(require_entitlement("starter", "pro")),
    session: Session = Depends(get_session),
) -> Envelope:
    """Return advisory intake fields parsed from a free-form description."""
    _require_ai_enabled()
    try:
        suggestion = suggest_intake(body.description, get_ai_client())
    except SuggestionParseError as exc:
        raise ProblemException(
            422, "AI returned an unusable suggestion", str(exc)
        ) from exc
    append_audit(
        session,
        actor=identity.email,
        action="ai.intake_suggested",
        subject=identity.tenant_id or "",
        payload={
            "model": suggestion.model,
            "input_tokens": suggestion.input_tokens,
            "output_tokens": suggestion.output_tokens,
            "description_chars": len(body.description),
        },
    )
    session.commit()
    return Envelope(
        data=IntakeSuggestData(**suggestion.to_dict()),
        meta=Meta(
            ruleset_version={},
            evaluation_date=datetime.date.today().isoformat(),
            evaluation_mode="advisory",
        ),
        advisories=[Advisory(**PLATFORM_ADVISORY), Advisory(**AI_ADVISORY)],
    )
