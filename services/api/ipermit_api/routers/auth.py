"""Authentication endpoints (S01-02): login and identity."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from ipermit_tenancy import User
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import (
    AuthenticatedIdentity,
    create_access_token,
    get_current_identity,
    verify_password,
)
from ..db import get_session
from ..envelope import ProblemException
from ..schemas import IdentityResponse, LoginRequest, TokenResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, session: Session = Depends(get_session)) -> TokenResponse:
    """Exchange email/password for a short-lived bearer token."""
    user = session.scalar(select(User).where(User.email == body.email))
    if (
        user is None
        or not user.is_active
        or not verify_password(body.password, user.password_hash)
    ):
        raise ProblemException(401, "Invalid credentials")
    tenant_ids = tuple(sorted(m.tenant_id for m in user.memberships))
    identity = AuthenticatedIdentity(
        subject=user.user_id,
        email=user.email,
        platform_role=user.platform_role,
        tenant_ids=tenant_ids,
        tenant_id=tenant_ids[0] if tenant_ids else None,
    )
    return TokenResponse(access_token=create_access_token(identity))


@router.get("/me", response_model=IdentityResponse)
def me(
    identity: AuthenticatedIdentity = Depends(get_current_identity),
) -> IdentityResponse:
    """Return the resolved identity for the bearer token."""
    return IdentityResponse(
        subject=identity.subject,
        email=identity.email,
        platform_role=identity.platform_role,
        tenant_ids=list(identity.tenant_ids),
        tenant_id=identity.tenant_id,
    )
