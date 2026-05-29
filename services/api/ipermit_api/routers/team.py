"""Team & account management (S04-02 / S07-02, SAAS-04 / SAAS-07).

A tenant's members manage their own team: list members, add a user (existing
or by invitation), toggle the tenant-local ``is_team_admin`` flag, and remove
a member. All scoped to the caller's active tenant (app-layer ``tenant_id``
filter).

Authority model (ADR-0002): membership admin is a *tenant-local* capability
(``is_team_admin``), distinct from the platform roles. Mutations require the
caller to be a team admin OR the tenant's sole member (bootstrap for a solo
consultant inviting their first teammate) OR a ``platform_admin``. Inviting an
*unregistered* user (S07-02) mints a time-bounded :class:`Invitation` and
delivers the acceptance token by email; the invitee completes registration via
``POST /api/v1/invitations/accept``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from ipermit_tenancy import Membership, Tenant, User
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit import append_audit
from ..auth import AuthenticatedIdentity, get_current_identity
from ..db import get_session
from ..email import EmailMessage, get_email_sender
from ..envelope import ProblemException
from ..invitations import new_invitation
from ..schemas import (
    AddMemberRequest,
    InvitationResponse,
    TeamMemberResponse,
    UpdateMemberRequest,
)
from ..settings import get_settings

router = APIRouter(prefix="/api/v1/team", tags=["team"])


def _require_tenant(identity: AuthenticatedIdentity) -> str:
    if identity.tenant_id is None:
        raise ProblemException(403, "No tenant membership")
    return identity.tenant_id


def _membership(session: Session, tenant_id: str, user_id: str) -> Membership | None:
    return session.scalar(
        select(Membership).where(
            Membership.tenant_id == tenant_id, Membership.user_id == user_id
        )
    )


def _member_count(session: Session, tenant_id: str) -> int:
    return session.scalar(
        select(func.count())
        .select_from(Membership)
        .where(Membership.tenant_id == tenant_id)
    )


def _require_team_admin(
    session: Session, identity: AuthenticatedIdentity, tenant_id: str
) -> None:
    """Allow team admins, a tenant's sole member (bootstrap), or platform_admin.

    A sole member granted access this way is promoted to ``is_team_admin`` so they
    retain control once they add a second member (and stop being "sole").
    """
    if identity.has_role("platform_admin"):
        return
    mine = _membership(session, tenant_id, identity.subject)
    if mine is None:
        raise ProblemException(403, "Team admin required")
    if mine.is_team_admin:
        return
    if _member_count(session, tenant_id) <= 1:
        mine.is_team_admin = True  # promote the bootstrapping sole member
        session.flush()
        return
    raise ProblemException(403, "Team admin required")


def _to_response(member: Membership, email: str) -> TeamMemberResponse:
    return TeamMemberResponse(
        user_id=member.user_id,
        email=email,
        is_team_admin=member.is_team_admin,
        created_at=member.created_at,
    )


@router.get("/members", response_model=list[TeamMemberResponse])
def list_members(
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> list[TeamMemberResponse]:
    """List the members of the caller's active tenant (any member)."""
    tenant_id = _require_tenant(identity)
    rows = session.execute(
        select(Membership, User.email)
        .join(User, User.user_id == Membership.user_id)
        .where(Membership.tenant_id == tenant_id)
        .order_by(User.email)
    ).all()
    return [_to_response(m, email) for m, email in rows]


@router.post("/members", response_model=TeamMemberResponse, status_code=201)
def add_member(
    body: AddMemberRequest,
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> TeamMemberResponse:
    """Add an existing user to the tenant by email (team admin only)."""
    tenant_id = _require_tenant(identity)
    _require_team_admin(session, identity, tenant_id)
    user = session.scalar(select(User).where(User.email == body.email))
    if user is None:
        raise ProblemException(
            404,
            "No registered user with that email",
            detail="Use POST /api/v1/team/invitations to invite an unregistered colleague.",
        )
    if _membership(session, tenant_id, user.user_id) is not None:
        raise ProblemException(409, "User is already a member")
    member = Membership(
        user_id=user.user_id, tenant_id=tenant_id, is_team_admin=body.is_team_admin
    )
    session.add(member)
    session.flush()
    append_audit(
        session,
        actor=identity.email,
        action="team.member_added",
        subject=user.user_id,
        payload={"tenant_id": tenant_id, "is_team_admin": body.is_team_admin},
    )
    session.commit()
    return _to_response(member, user.email)


def _invitation_email(
    tenant_name: str, inviter_email: str, accept_url: str, token: str
) -> EmailMessage:
    """Render the invitation email body (kept short + linked, S07-02)."""
    link = f"{accept_url}?token={token}"
    body = (
        f"{inviter_email} invited you to join {tenant_name} on iPermit.\n\n"
        f"Accept the invitation here (expires soon): {link}\n\n"
        "If you weren't expecting this, you can ignore this message."
    )
    return EmailMessage(
        to="",  # filled in by the caller
        subject=f"You're invited to {tenant_name} on iPermit",
        body=body,
        category="invitation",
    )


@router.post(
    "/invitations", response_model=InvitationResponse, status_code=201, tags=["team"]
)
def invite_member(
    body: AddMemberRequest,
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> InvitationResponse:
    """Invite an unregistered colleague by email (S07-02, team admin only).

    Existing users are added immediately via ``POST /members``; this route is
    the path for emails that have no account yet. The acceptance token is
    delivered only by email — the response carries an ``invitation_id`` but
    never the raw token.
    """
    tenant_id = _require_tenant(identity)
    _require_team_admin(session, identity, tenant_id)
    if session.scalar(select(User).where(User.email == body.email)) is not None:
        raise ProblemException(409, "Email already has an account; use POST /members")
    settings = get_settings()
    invitation, token = new_invitation(
        tenant_id=tenant_id,
        email=body.email,
        invited_by=identity.subject,
        is_team_admin=body.is_team_admin,
        ttl_minutes=settings.invitation_ttl_minutes,
    )
    session.add(invitation)
    session.flush()
    tenant = session.get(Tenant, tenant_id)
    message = _invitation_email(
        tenant_name=tenant.name if tenant else "your team",
        inviter_email=identity.email,
        accept_url=settings.invitation_accept_url,
        token=token,
    )
    get_email_sender(settings).send(
        EmailMessage(
            to=body.email,
            subject=message.subject,
            body=message.body,
            category=message.category,
        )
    )
    append_audit(
        session,
        actor=identity.email,
        action="team.member_invited",
        subject=body.email,
        payload={"tenant_id": tenant_id, "invitation_id": invitation.invitation_id},
    )
    session.commit()
    return InvitationResponse(
        invitation_id=invitation.invitation_id,
        email=invitation.email,
        is_team_admin=invitation.is_team_admin,
        expires_at=invitation.expires_at,
    )


@router.patch("/members/{user_id}", response_model=TeamMemberResponse)
def update_member(
    user_id: str,
    body: UpdateMemberRequest,
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> TeamMemberResponse:
    """Set a member's tenant-local admin flag (team admin only)."""
    tenant_id = _require_tenant(identity)
    _require_team_admin(session, identity, tenant_id)
    member = _membership(session, tenant_id, user_id)
    if member is None:
        raise ProblemException(404, "Not a member of this tenant")
    member.is_team_admin = body.is_team_admin
    session.flush()
    email = session.scalar(select(User.email).where(User.user_id == user_id))
    append_audit(
        session,
        actor=identity.email,
        action="team.member_role_changed",
        subject=user_id,
        payload={"tenant_id": tenant_id, "is_team_admin": body.is_team_admin},
    )
    session.commit()
    return _to_response(member, email or "")


@router.delete("/members/{user_id}", status_code=204)
def remove_member(
    user_id: str,
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> None:
    """Remove a member from the tenant (team admin only; not the last member)."""
    tenant_id = _require_tenant(identity)
    _require_team_admin(session, identity, tenant_id)
    member = _membership(session, tenant_id, user_id)
    if member is None:
        raise ProblemException(404, "Not a member of this tenant")
    if _member_count(session, tenant_id) <= 1:
        raise ProblemException(409, "Cannot remove the last member")
    session.delete(member)
    append_audit(
        session,
        actor=identity.email,
        action="team.member_removed",
        subject=user_id,
        payload={"tenant_id": tenant_id},
    )
    session.commit()
