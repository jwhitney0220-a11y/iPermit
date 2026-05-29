"""Invitation acceptance routes (S07-02, SAAS-07).

The ``POST /api/v1/team/invitations`` endpoint in :mod:`routers.team` mints an
:class:`~ipermit_tenancy.Invitation` for an unregistered email and delivers
the token by email. The invitee then hits the two endpoints here to complete
the registration:

* ``GET /api/v1/invitations/{token}`` — preview the invite so the front-end
  can show "you've been invited to <tenant> as <email>" before asking for a
  password. Never echoes the token back.
* ``POST /api/v1/invitations/accept`` — create the :class:`User` row, attach
  the :class:`Membership`, and mark the invitation consumed in one transaction.

Token discipline (T07-02): every invalid/expired/consumed/missing token
returns the same ``410 Gone`` body so a brute-force probe cannot distinguish
between the failure modes.
"""

from __future__ import annotations

import datetime
import uuid

from fastapi import APIRouter, Depends
from ipermit_tenancy import Membership, Tenant, User
from sqlalchemy.orm import Session

from ..audit import append_audit
from ..auth import hash_password
from ..db import get_session
from ..envelope import ProblemException
from ..invitations import find_active_invitation
from ..schemas import (
    AcceptInvitationRequest,
    InvitationPreviewResponse,
    TeamMemberResponse,
)

router = APIRouter(prefix="/api/v1/invitations", tags=["invitations"])

_INVALID_INVITATION_TITLE = "Invitation not found or expired"


def _require_invitation(session: Session, token: str):  # type: ignore[no-untyped-def]
    invitation = find_active_invitation(session, token)
    if invitation is None:
        raise ProblemException(410, _INVALID_INVITATION_TITLE)
    return invitation


@router.get("/{token}", response_model=InvitationPreviewResponse)
def preview(
    token: str, session: Session = Depends(get_session)
) -> InvitationPreviewResponse:
    """Return the inviting tenant + invitee email for a still-valid token."""
    invitation = _require_invitation(session, token)
    tenant = session.get(Tenant, invitation.tenant_id)
    return InvitationPreviewResponse(
        email=invitation.email,
        tenant_id=invitation.tenant_id,
        tenant_name=tenant.name if tenant else "",
        expires_at=invitation.expires_at,
    )


@router.post("/accept", response_model=TeamMemberResponse, status_code=201)
def accept(
    body: AcceptInvitationRequest, session: Session = Depends(get_session)
) -> TeamMemberResponse:
    """Consume the invitation: register the user + attach the membership."""
    invitation = _require_invitation(session, body.token)
    if session.scalar(User.__table__.select().where(User.email == invitation.email)):
        raise ProblemException(
            409, "Email already has an account; sign in to accept the invitation."
        )
    user = User(
        user_id=uuid.uuid4().hex,
        email=invitation.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
    )
    session.add(user)
    session.flush()
    member = Membership(
        user_id=user.user_id,
        tenant_id=invitation.tenant_id,
        is_team_admin=invitation.is_team_admin,
    )
    session.add(member)
    invitation.consumed_at = datetime.datetime.now(tz=datetime.UTC)
    session.flush()
    append_audit(
        session,
        actor=invitation.email,
        action="team.invitation_accepted",
        subject=user.user_id,
        payload={
            "tenant_id": invitation.tenant_id,
            "invitation_id": invitation.invitation_id,
            "is_team_admin": invitation.is_team_admin,
        },
    )
    session.commit()
    return TeamMemberResponse(
        user_id=user.user_id,
        email=user.email,
        is_team_admin=member.is_team_admin,
        created_at=member.created_at,
    )
