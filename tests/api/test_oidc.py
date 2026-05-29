"""OIDC ID-token verifier + identity routing tests (S07-04)."""

from __future__ import annotations

import datetime
import json
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from ipermit_api.auth import set_oidc_verifier
from ipermit_api.envelope import ProblemException
from ipermit_api.oidc import OidcVerifier, make_jwks_resolver
from ipermit_api.settings import get_settings

_ISSUER = "https://idp.example.com/"
_AUDIENCE = "ipermit-test"
_KID = "test-kid"


@pytest.fixture
def rsa_key() -> dict[str, Any]:
    """Generate a fresh RSA key for signing/verifying OIDC tokens in-test."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key()
    public_pem = public.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(public))
    jwk["kid"] = _KID
    jwk["alg"] = "RS256"
    return {"private": private, "public_pem": public_pem, "jwk": jwk}


def _sign_token(
    private_key: Any,
    *,
    email: str,
    sub: str = "user-123",
    expires_in: int = 600,
    issuer: str = _ISSUER,
    audience: str = _AUDIENCE,
) -> str:
    now = datetime.datetime.now(tz=datetime.UTC)
    return jwt.encode(
        {
            "iss": issuer,
            "aud": audience,
            "sub": sub,
            "email": email,
            "iat": int(now.timestamp()),
            "exp": int((now + datetime.timedelta(seconds=expires_in)).timestamp()),
        },
        key=private_key,
        algorithm="RS256",
        headers={"kid": _KID},
    )


@pytest.fixture
def oidc_configured(rsa_key: dict[str, Any]):
    """Install a verifier wired to the in-test JWKS and configure settings."""
    resolver = make_jwks_resolver(lambda: {"keys": [rsa_key["jwk"]]})
    verifier = OidcVerifier(issuer=_ISSUER, audience=_AUDIENCE, resolver=resolver)
    set_oidc_verifier(verifier)
    settings = get_settings()
    settings.auth_oidc_issuer_url = _ISSUER
    settings.auth_oidc_audience = _AUDIENCE
    settings.auth_oidc_jwks_uri = "https://idp.example.com/jwks"
    yield rsa_key
    set_oidc_verifier(None)
    settings.auth_oidc_issuer_url = ""
    settings.auth_oidc_audience = ""
    settings.auth_oidc_jwks_uri = ""


def test_valid_oidc_token_authenticates(
    client: TestClient, seeded: dict[str, str], oidc_configured: dict[str, Any]
) -> None:
    token = _sign_token(oidc_configured["private"], email=seeded["email_a"])
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] == seeded["email_a"]
    assert body["tenant_id"] == seeded["tenant_a"]


def test_oidc_token_for_unprovisioned_email_is_401(
    client: TestClient, oidc_configured: dict[str, Any]
) -> None:
    token = _sign_token(oidc_configured["private"], email="ghost@example.com")
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert "not provisioned" in (resp.json().get("detail") or resp.json()["title"])


def test_oidc_wrong_audience_is_401(
    client: TestClient, seeded: dict[str, str], oidc_configured: dict[str, Any]
) -> None:
    token = _sign_token(
        oidc_configured["private"], email=seeded["email_a"], audience="other-app"
    )
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_oidc_expired_token_is_401(
    client: TestClient, seeded: dict[str, str], oidc_configured: dict[str, Any]
) -> None:
    token = _sign_token(
        oidc_configured["private"], email=seeded["email_a"], expires_in=-30
    )
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_hs256_token_still_works_alongside_oidc(
    client: TestClient, seeded: dict[str, str], oidc_configured: dict[str, Any], login
) -> None:
    """Day-one password tokens keep authenticating with OIDC also configured."""
    bearer = login(seeded["email_a"])
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {bearer}"})
    assert resp.status_code == 200


def test_jwks_resolver_caches_within_ttl() -> None:
    calls = {"n": 0}

    def fetch() -> dict[str, Any]:
        calls["n"] += 1
        return {"keys": []}

    resolver = make_jwks_resolver(fetch, ttl_seconds=60)
    resolver.fetch()
    resolver.fetch()
    resolver.fetch()
    assert calls["n"] == 1


def test_verifier_rejects_unknown_kid(rsa_key: dict[str, Any]) -> None:
    """A token signed with a key whose ``kid`` isn't in the JWKS is rejected."""
    verifier = OidcVerifier(
        issuer=_ISSUER,
        audience=_AUDIENCE,
        resolver=make_jwks_resolver(lambda: {"keys": []}),
    )
    token = _sign_token(rsa_key["private"], email="a@example.com")
    with pytest.raises(ProblemException) as exc:
        verifier.verify(token)
    assert exc.value.problem.status == 401
