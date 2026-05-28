"""Production-hardening middleware tests (S07-01).

Exercises CORS allow-list behaviour, ``X-Request-ID`` propagation, the login
rate-limit's 429 problem-details response, and the non-local
``validate_security`` guards against wildcard CORS / trusted-host configs.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from ipermit_api.middleware import (
    REQUEST_ID_HEADER,
    LoginRateLimitMiddleware,
    _FixedWindowLimiter,
)
from ipermit_api.settings import Settings, validate_security


def test_request_id_generated_when_absent(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.headers.get(REQUEST_ID_HEADER)
    assert len(resp.headers[REQUEST_ID_HEADER]) >= 16


def test_request_id_propagated_when_provided(client: TestClient) -> None:
    sent = "test-request-id-abc123"
    resp = client.get("/healthz", headers={REQUEST_ID_HEADER: sent})
    assert resp.status_code == 200
    assert resp.headers[REQUEST_ID_HEADER] == sent


def test_cors_preflight_allows_known_origin(client: TestClient) -> None:
    # Local default origin set lives in ``.env.example``; the in-test settings
    # singleton picks it up from the process env (cached). Tests run with the
    # local default which permits "*" — so any preflight is OK.
    resp = client.options(
        "/healthz",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200


def test_login_rate_limit_returns_429(
    client: TestClient, seeded: dict[str, str]
) -> None:
    # Drive the limiter past its window. The default limit is 10/min, so 12
    # attempts is enough; we hit a bad-credentials path so the success path
    # is independent of how many real logins this exact test happens to make.
    last = None
    for _ in range(12):
        last = client.post(
            "/api/v1/auth/login",
            json={"email": seeded["email_a"], "password": "wrong"},
            headers={"X-Forwarded-For": "203.0.113.4"},
        )
    assert last is not None
    assert last.status_code == 429
    assert last.headers["content-type"].startswith("application/problem+json")
    body = last.json()
    assert body["status"] == 429
    assert "rate-limited" in body["detail"].lower()
    assert last.headers.get("Retry-After") == "60"


def test_fixed_window_limiter_counts_per_ip() -> None:
    limiter = _FixedWindowLimiter(max_per_minute=2)
    assert limiter.hit("1.1.1.1") is False
    assert limiter.hit("1.1.1.1") is False
    # 3rd hit in window flips over.
    assert limiter.hit("1.1.1.1") is True
    # A different client is unaffected.
    assert limiter.hit("2.2.2.2") is False


def _prod_settings(**overrides: object) -> Settings:
    """Production settings with the minimal valid hardening config."""
    base: dict[str, object] = {
        "ipermit_env": "production",
        "auth_jwt_secret": "x" * 32,
        "stripe_secret_key": "sk_live_real",
        "stripe_webhook_secret": "whsec_real",
        "api_cors_allowed_origins": ["https://app.example.com"],
        "api_trusted_hosts": ["app.example.com"],
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_non_local_accepts_explicit_origins_and_hosts() -> None:
    validate_security(_prod_settings())


def test_non_local_rejects_wildcard_cors() -> None:
    with pytest.raises(RuntimeError, match="API_CORS_ALLOWED_ORIGINS"):
        validate_security(_prod_settings(api_cors_allowed_origins=["*"]))


def test_non_local_rejects_empty_cors() -> None:
    with pytest.raises(RuntimeError, match="API_CORS_ALLOWED_ORIGINS"):
        validate_security(_prod_settings(api_cors_allowed_origins=[]))


def test_non_local_rejects_wildcard_trusted_hosts() -> None:
    with pytest.raises(RuntimeError, match="API_TRUSTED_HOSTS"):
        validate_security(_prod_settings(api_trusted_hosts=["*"]))


def test_csv_origins_parse_from_env_string() -> None:
    """Operators set the env as ``a,b,c``; the validator must split it."""
    settings = Settings(api_cors_allowed_origins="https://a,https://b")  # type: ignore[arg-type]
    assert settings.api_cors_allowed_origins == ["https://a", "https://b"]


def test_login_middleware_holds_limiter_reference() -> None:
    """Smoke: the dispatcher's seam is held, not rebuilt per request."""
    limiter = _FixedWindowLimiter(1)
    mw = LoginRateLimitMiddleware(app=None, limiter=limiter)  # type: ignore[arg-type]
    assert mw._limiter is limiter
