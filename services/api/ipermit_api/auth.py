"""Authentication and identity (S01-02, ADR-0002).

Implements the ADR-0002 ``AuthenticatedIdentity`` abstraction: identity is
resolved from a bearer token on each request, behind a single swappable verifier.
Day-one verifier is self-managed email/password with bcrypt hashing and a
short-lived HS256 JWT. Enterprise SSO (OIDC/SAML) is additive — a second verifier
that produces the same ``AuthenticatedIdentity`` — and is deferred (S07-04).

Role and tenant membership are always iPermit-owned (ADR-0002): the token asserts
*who you are*; the database decides *what you may do* and *which tenant you are in*.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

import bcrypt
import jwt
from fastapi import Depends, Request
from ipermit_tenancy import PLATFORM_ROLES, User
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_session
from .envelope import ProblemException
from .oidc import OidcVerifier, http_jwks_resolver
from .settings import Settings, get_settings

#: Role hierarchy rank (ADR-0002): higher rank is a superset of lower capability.
_ROLE_RANK = {role: index for index, role in enumerate(PLATFORM_ROLES)}

# bcrypt operates on at most 72 bytes; reject longer passwords at the boundary
# rather than silently truncating (avoids a class of auth-bypass surprises).
MAX_PASSWORD_BYTES = 72


@dataclass(frozen=True)
class AuthenticatedIdentity:
    """The resolved caller (ADR-0002): subject, email, role, tenant scope."""

    subject: str
    email: str
    platform_role: str
    tenant_ids: tuple[str, ...] = ()
    tenant_id: str | None = None
    capabilities: frozenset[str] = field(default_factory=frozenset)

    def has_role(self, minimum: str) -> bool:
        """True if this identity meets or exceeds *minimum* in the hierarchy."""
        return _ROLE_RANK[self.platform_role] >= _ROLE_RANK[minimum]


def hash_password(password: str) -> str:
    """Return a bcrypt hash for *password* (UTF-8, max 72 bytes)."""
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time check of *password* against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(_password_bytes(password), password_hash.encode("ascii"))
    except ValueError:
        return False


def _password_bytes(password: str) -> bytes:
    """Encode a password to bytes, rejecting anything over the bcrypt limit."""
    raw = password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        raise ProblemException(
            422, "Password too long", f"Maximum {MAX_PASSWORD_BYTES} bytes."
        )
    return raw


def create_access_token(identity: AuthenticatedIdentity) -> str:
    """Issue a short-lived HS256 access token for *identity*."""
    settings = get_settings()
    now = datetime.datetime.now(tz=datetime.UTC)
    expires = now + datetime.timedelta(minutes=settings.auth_token_ttl_minutes)
    claims = {
        "sub": identity.subject,
        "email": identity.email,
        "role": identity.platform_role,
        "tid": identity.tenant_id,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    return jwt.encode(
        claims, settings.auth_jwt_secret, algorithm=settings.auth_jwt_algorithm
    )


def _decode(token: str, settings: Settings) -> dict:
    """Decode and verify a bearer token, or raise a 401 problem."""
    try:
        return jwt.decode(
            token, settings.auth_jwt_secret, algorithms=[settings.auth_jwt_algorithm]
        )
    except jwt.PyJWTError as exc:
        raise ProblemException(401, "Invalid or expired token") from exc


_OIDC_VERIFIER: OidcVerifier | None = None


def _is_oidc_token(token: str, settings: Settings) -> bool:
    """Heuristic: an unverified peek at the token's ``iss`` selects the path.

    Only used to *route* — the OIDC verifier still validates signature,
    expiry, and the registered claims before any iPermit identity is returned.
    """
    if not settings.auth_oidc_issuer_url:
        return False
    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError:
        return False
    return unverified.get("iss") == settings.auth_oidc_issuer_url


def get_oidc_verifier(settings: Settings | None = None) -> OidcVerifier:
    """Lazily construct the singleton :class:`OidcVerifier` from settings."""
    global _OIDC_VERIFIER  # noqa: PLW0603 — module-level lazy singleton
    settings = settings or get_settings()
    if _OIDC_VERIFIER is None:
        if not (settings.auth_oidc_issuer_url and settings.auth_oidc_jwks_uri):
            raise ProblemException(401, "OIDC verifier not configured")
        _OIDC_VERIFIER = OidcVerifier(
            issuer=settings.auth_oidc_issuer_url,
            audience=settings.auth_oidc_audience,
            resolver=http_jwks_resolver(settings.auth_oidc_jwks_uri),
        )
    return _OIDC_VERIFIER


def set_oidc_verifier(verifier: OidcVerifier | None) -> None:
    """Override the cached OIDC verifier (tests inject a fake JWKS resolver)."""
    global _OIDC_VERIFIER  # noqa: PLW0603 — module-level lazy singleton
    _OIDC_VERIFIER = verifier


def _resolve_via_oidc(token: str, session: Session) -> User:
    """Validate an OIDC ID token and resolve it to an iPermit user by email."""
    claims = get_oidc_verifier().verify(token)
    user = session.scalar(select(User).where(User.email == claims.email))
    if user is None or not user.is_active:
        raise ProblemException(401, "OIDC user not provisioned in iPermit")
    return user


def _bearer_token(request: Request) -> str:
    """Extract the bearer token from the Authorization header, or raise 401."""
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise ProblemException(401, "Missing bearer token")
    return token


def get_current_identity(
    request: Request, session: Session = Depends(get_session)
) -> AuthenticatedIdentity:
    """Resolve the request's :class:`AuthenticatedIdentity` from its token.

    Re-loads the user and tenant memberships from the database so a deactivated
    user or revoked membership cannot ride a still-valid token (ADR-0002:
    the database decides what you may do). Two verifier paths share this
    seam: the day-one HS256 password issuer and the OIDC RS256 verifier
    (S07-04). Routing is based on the unverified ``iss`` claim; signature
    validation happens inside each verifier.
    """
    settings = get_settings()
    token = _bearer_token(request)
    user = _resolve_user(token, settings, session)
    tenant_ids = tuple(sorted(m.tenant_id for m in user.memberships))
    primary = _select_tenant(token, settings, tenant_ids)
    return AuthenticatedIdentity(
        subject=user.user_id,
        email=user.email,
        platform_role=user.platform_role,
        tenant_ids=tenant_ids,
        tenant_id=primary,
        capabilities=frozenset(user.capabilities or ()),
    )


def _resolve_user(token: str, settings: Settings, session: Session) -> User:
    """Return the iPermit user for *token*, routing OIDC vs HS256 by issuer."""
    if _is_oidc_token(token, settings):
        return _resolve_via_oidc(token, session)
    claims = _decode(token, settings)
    user = session.scalar(select(User).where(User.user_id == claims.get("sub")))
    if user is None or not user.is_active:
        raise ProblemException(401, "Unknown or inactive user")
    return user


def _select_tenant(
    token: str, settings: Settings, tenant_ids: tuple[str, ...]
) -> str | None:
    """Pick the primary tenant: explicit ``tid`` claim (HS256) or first id."""
    if _is_oidc_token(token, settings):
        return tenant_ids[0] if tenant_ids else None
    claims = _decode(token, settings)
    primary = claims.get("tid") if claims.get("tid") in tenant_ids else None
    return primary or (tenant_ids[0] if tenant_ids else None)


def require_role(minimum: str):
    """Dependency factory enforcing a minimum platform role (ADR-0002)."""

    def dependency(
        identity: AuthenticatedIdentity = Depends(get_current_identity),
    ) -> AuthenticatedIdentity:
        if not identity.has_role(minimum):
            raise ProblemException(403, "Insufficient role")
        return identity

    return dependency


def require_capability(flag: str):
    """Dependency factory enforcing an analyst capability flag (ADR-0002).

    A ``platform_admin`` implicitly holds every capability (the role hierarchy is
    a superset); otherwise the flag must be explicitly granted on the identity.
    """

    def dependency(
        identity: AuthenticatedIdentity = Depends(get_current_identity),
    ) -> AuthenticatedIdentity:
        if identity.has_role("platform_admin") or flag in identity.capabilities:
            return identity
        raise ProblemException(403, f"Missing capability {flag}")

    return dependency
