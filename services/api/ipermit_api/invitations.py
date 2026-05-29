"""Invitation token helpers for the team-invite flow (S07-02).

Centralised so :mod:`routers.team` (which mints the invitation) and
:mod:`routers.invitations` (which validates and consumes it) share the same
token + hash conventions. The token itself is high-entropy bytes from
:mod:`secrets`; only its sha256 digest is persisted, so a database read alone
cannot reconstruct the value that was emailed to the invitee.
"""

from __future__ import annotations

import datetime
import hashlib
import secrets
import uuid

from ipermit_tenancy import Invitation
from sqlalchemy import select
from sqlalchemy.orm import Session

#: Bytes of entropy per token (urlsafe base64 -> ~43 characters).
_TOKEN_BYTES = 32


def mint_token() -> str:
    """Return a fresh urlsafe token (only its hash is persisted)."""
    return secrets.token_urlsafe(_TOKEN_BYTES)


def hash_token(token: str) -> str:
    """Return the canonical sha256 hex digest used for storage + lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _as_utc(value: datetime.datetime) -> datetime.datetime:
    """SQLite drops tz info on read; ensure both sides of the comparison match."""
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.UTC)
    return value


def find_active_invitation(session: Session, token: str) -> Invitation | None:
    """Return a not-yet-consumed, not-yet-expired invitation matching *token*.

    Returns ``None`` for unknown, consumed, or expired tokens — the router
    layer maps that to a generic ``410 Gone`` so a brute-force probe cannot
    distinguish between the three states.
    """
    invitation = session.scalar(
        select(Invitation).where(Invitation.token_hash == hash_token(token))
    )
    if invitation is None:
        return None
    if invitation.consumed_at is not None:
        return None
    if _as_utc(invitation.expires_at) <= datetime.datetime.now(tz=datetime.UTC):
        return None
    return invitation


def new_invitation(
    *,
    tenant_id: str,
    email: str,
    invited_by: str,
    is_team_admin: bool,
    ttl_minutes: int,
) -> tuple[Invitation, str]:
    """Build a fresh :class:`Invitation` row + return the (unhashed) token."""
    token = mint_token()
    now = datetime.datetime.now(tz=datetime.UTC)
    invitation = Invitation(
        invitation_id=uuid.uuid4().hex,
        tenant_id=tenant_id,
        email=email,
        token_hash=hash_token(token),
        invited_by=invited_by,
        is_team_admin=is_team_admin,
        expires_at=now + datetime.timedelta(minutes=ttl_minutes),
    )
    return invitation, token


__all__ = [
    "find_active_invitation",
    "hash_token",
    "mint_token",
    "new_invitation",
]
