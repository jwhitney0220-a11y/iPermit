"""OIDC identity-token verifier (S07-04, SAAS-07).

iPermit's day-one verifier is the HS256/password issuer in :mod:`auth`. SSO
arrives behind the same :class:`AuthenticatedIdentity` (ADR-0002): a second
verifier that consumes a third-party OpenID Connect ID token, validates its
signature against the issuer's JWKS, checks the standard registered claims
(``iss``, ``aud``, ``exp``), and maps the token to an existing iPermit
:class:`~ipermit_tenancy.User` row by email. Role + tenant membership stay
iPermit-owned — the IdP never assigns iPermit roles.

This module provides the verifier + claim mapper; the routing into the auth
dependency lives in :mod:`auth`. The :class:`JwksResolver` seam means tests
inject a deterministic JWKS without hitting an HTTP endpoint, and production
swaps in an HTTPS resolver against the IdP's ``/.well-known/jwks.json``.

**Just-in-time provisioning** is deliberately deferred: a verified ID token
whose email has no matching ``User`` row results in a 401. Auto-provisioning
adds enterprise-onboarding complexity (default role, default tenant, audit)
that belongs in the SSO-rollout ticket once the IdP is wired.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import jwt
from jwt import PyJWKClient

from .envelope import ProblemException

#: Default JWKS cache TTL in seconds. Long enough to survive bursts, short
#: enough that an IdP-side key rotation propagates within minutes.
_DEFAULT_JWKS_TTL_SECONDS = 5 * 60


@dataclass(frozen=True)
class OidcClaims:
    """The subset of ID-token claims iPermit consumes."""

    subject: str
    email: str
    issuer: str


class JwksResolver(Protocol):
    """Seam for retrieving the IdP's JWKS (HTTP in prod, fake in tests)."""

    def fetch(self) -> dict[str, Any]:
        """Return the current JWKS document as a plain ``dict``."""


@dataclass
class _CachedJwksResolver:
    """Wraps an underlying resolver with a TTL cache for the JWKS document."""

    inner: Callable[[], dict[str, Any]]
    ttl_seconds: int = _DEFAULT_JWKS_TTL_SECONDS
    _cache: dict[str, Any] | None = None
    _fetched_at: float = 0.0

    def fetch(self) -> dict[str, Any]:
        """Return a cached JWKS document, refreshing when the TTL expires."""
        now = time.monotonic()
        if self._cache is None or (now - self._fetched_at) > self.ttl_seconds:
            self._cache = self.inner()
            self._fetched_at = now
        return self._cache


def make_jwks_resolver(
    inner: Callable[[], dict[str, Any]], ttl_seconds: int = _DEFAULT_JWKS_TTL_SECONDS
) -> JwksResolver:
    """Construct a TTL-cached :class:`JwksResolver` over a fetch callable."""
    return _CachedJwksResolver(inner=inner, ttl_seconds=ttl_seconds)


def http_jwks_resolver(jwks_uri: str) -> JwksResolver:
    """Default production JWKS resolver (``PyJWKClient`` over HTTPS).

    Returns a resolver that hands :class:`PyJWKClient` to the verifier; that
    client maintains its own internal caching, so the outer TTL cache is a
    no-op when this path is selected.
    """
    client = PyJWKClient(jwks_uri)
    return _PyJwkClientResolver(client=client)


@dataclass
class _PyJwkClientResolver:
    """Resolver that exposes a :class:`PyJWKClient` for direct key lookup."""

    client: PyJWKClient

    def fetch(self) -> dict[str, Any]:
        """Return the JWKS document the client has already fetched."""
        return self.client.get_jwk_set().to_dict()


@dataclass(frozen=True)
class OidcVerifier:
    """Verifies third-party OIDC ID tokens and projects them to claims."""

    issuer: str
    audience: str
    resolver: JwksResolver

    def verify(self, token: str) -> OidcClaims:
        """Return the validated :class:`OidcClaims` or raise a 401 problem."""
        jwks = self.resolver.fetch()
        try:
            header = jwt.get_unverified_header(token)
            key = _find_key(jwks, header.get("kid"))
            decoded = jwt.decode(
                token,
                key=key,
                algorithms=[header.get("alg", "RS256")],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["iss", "aud", "exp", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise ProblemException(401, "Invalid OIDC token") from exc
        email = decoded.get("email")
        if not email:
            raise ProblemException(401, "OIDC token missing email claim")
        return OidcClaims(subject=decoded["sub"], email=email, issuer=decoded["iss"])


def _find_key(jwks: dict[str, Any], kid: str | None) -> Any:
    """Return the PEM-shaped public key matching *kid* from a JWKS document."""
    for entry in jwks.get("keys", []):
        if entry.get("kid") == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(entry)
    raise ProblemException(401, "OIDC signing key not found")


__all__ = [
    "JwksResolver",
    "OidcClaims",
    "OidcVerifier",
    "http_jwks_resolver",
    "make_jwks_resolver",
]
