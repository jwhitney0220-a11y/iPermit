"""API service configuration (S01-03).

Reads the environment-variable contract from ``.env.example`` (T01-08): the
``IPERMIT_*`` runtime vars, ``DATABASE_URL`` (shared by the app engine and
Alembic), and the ``AUTH_*`` block. Secrets are never hard-coded — local dev may
set a throwaway ``AUTH_JWT_SECRET``; staging/production resolve it from the
secret manager (``AUTH_JWT_SECRET_REF``).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOCAL_DB = "sqlite+pysqlite:///./ipermit.db"


class Settings(BaseSettings):
    """Typed view over the API's environment configuration."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    ipermit_env: str = "local"
    # Root logging level applied at startup (S07-03). One of:
    # debug | info | warning | error.
    ipermit_log_level: str = "info"
    database_url: str = _LOCAL_DB
    auth_jwt_secret: str = "CHANGE_ME_LOCAL_ONLY"
    auth_jwt_algorithm: str = "HS256"
    auth_token_ttl_minutes: int = 60
    # OIDC SSO (S07-04). When the issuer + audience are set, an inbound bearer
    # token whose ``iss`` matches is verified against the IdP's JWKS (RS256)
    # and mapped to an existing iPermit user by email. Day-one verifier
    # (HS256/password) keeps working as the unchanged fallback.
    auth_oidc_issuer_url: str = ""
    auth_oidc_audience: str = ""
    auth_oidc_jwks_uri: str = ""

    # Stripe billing (S03-01, SAAS-03). Secrets are env-sourced; the placeholder
    # test defaults are inert (test keys, never a live secret) and are rejected
    # outside the local environment by ``validate_security``. Prices are server-
    # side Stripe Price IDs — the API never accepts a client-supplied amount.
    stripe_secret_key: str = "sk_test_PLACEHOLDER"
    stripe_webhook_secret: str = "whsec_test_PLACEHOLDER"
    stripe_price_starter: str = "price_test_starter"
    stripe_price_pro: str = "price_test_pro"
    # Where Stripe Checkout returns the browser after success/cancel.
    stripe_checkout_success_url: str = "http://localhost:5173/billing?status=success"
    stripe_checkout_cancel_url: str = "http://localhost:5173/billing?status=cancel"

    # Object storage for uploaded route files (S04-03). "local" writes to a
    # filesystem path for dev/CI; an S3 provider slots in behind get_storage().
    storage_provider: str = "local"
    storage_local_path: str = "./.local-storage"
    gis_max_upload_mb: int = 50

    # Production-hardening middleware (S07-01). Comma-separated lists in the
    # env; pydantic-settings splits via the validators below. Both default to
    # ``["*"]`` for zero-config local dev, and both are forbidden from being
    # wildcards/empty outside ``local`` by ``validate_security``.
    api_cors_allowed_origins: list[str] = ["*"]
    api_trusted_hosts: list[str] = ["*"]
    # Per-client-IP login rate limit. A simple fixed-window counter that
    # protects the password-grant endpoint against credential stuffing without
    # standing up Redis for the first slice. Staging/production swap in a
    # shared-state limiter behind the same ``RateLimiter`` seam.
    auth_login_rate_per_minute: int = 10

    @field_validator("api_cors_allowed_origins", "api_trusted_hosts", mode="before")
    @classmethod
    def _split_csv(cls, value: Any) -> Any:
        """Accept comma-separated env strings for list-valued settings.

        Operators set ``API_CORS_ALLOWED_ORIGINS=https://a,https://b`` in IaC;
        pydantic-settings' default tries JSON-decode first, which would fail.
        """
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    # Email (S07-02). "local" captures messages in process memory so tests
    # assert on subject/body without SMTP. Any other value with no provider
    # wired triggers a fail-fast sender so non-local deploys do not silently
    # drop mail. ``invitation_ttl_minutes`` bounds how long an emailed invite
    # link is valid before the invitee must request a fresh one.
    email_provider: str = "local"
    email_from_address: str = "noreply@ipermit.local"
    invitation_ttl_minutes: int = 60 * 24 * 7  # 7 days
    # The frontend acceptance URL — token is appended as a query string.
    invitation_accept_url: str = "http://localhost:5173/accept-invitation"

    # Constrained AI assistance (SAAS-08). Day-one client is the stub (no
    # network); ``AI_PROVIDER=anthropic`` + an ``AI_API_KEY`` flips to the
    # Claude API path. ``AI_FEATURES_ENABLED`` is the global gate every
    # AI route checks first, so the surface ships dark in environments that
    # have not opted in.
    ai_provider: str = "stub"
    ai_api_key: str = ""
    ai_model_id: str = "claude-haiku-4-5-20251001"
    ai_features_enabled: bool = False

    @property
    def is_local(self) -> bool:
        """True for the local development environment."""
        return self.ipermit_env == "local"

    @property
    def stripe_price_by_plan(self) -> dict[str, str]:
        """Server-side plan -> Stripe Price ID map (paid plans only)."""
        return {"starter": self.stripe_price_starter, "pro": self.stripe_price_pro}


# Placeholder secret from .env.example — must never sign tokens off local.
_PLACEHOLDER_SECRET = "CHANGE_ME_LOCAL_ONLY"
_MIN_SECRET_BYTES = 32
# Inert Stripe test defaults — must be replaced with real (test/live) keys before
# the billing surface runs anywhere but local.
_STRIPE_PLACEHOLDERS = ("sk_test_PLACEHOLDER", "whsec_test_PLACEHOLDER")


def validate_security(settings: Settings) -> None:
    """Fail fast if a non-local env would run with weak/default secrets."""
    if settings.is_local:
        return
    secret = settings.auth_jwt_secret
    if secret == _PLACEHOLDER_SECRET or len(secret.encode()) < _MIN_SECRET_BYTES:
        raise RuntimeError(
            f"AUTH_JWT_SECRET must be set to a strong value "
            f"(>= {_MIN_SECRET_BYTES} bytes) outside the local environment."
        )
    if settings.stripe_secret_key in _STRIPE_PLACEHOLDERS or (
        settings.stripe_webhook_secret in _STRIPE_PLACEHOLDERS
    ):
        raise RuntimeError(
            "STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET must be set outside the "
            "local environment (never the inert placeholder defaults)."
        )
    # S07-01: wildcard origins are unsafe with credentialed requests; force an
    # explicit allow-list outside local. Trusted hosts default to ``["*"]`` for
    # local; a non-local deploy must enumerate its public hostnames.
    if (
        "*" in settings.api_cors_allowed_origins
        or not settings.api_cors_allowed_origins
    ):
        raise RuntimeError(
            "API_CORS_ALLOWED_ORIGINS must be a non-empty, non-wildcard list "
            "outside the local environment (credentialed CORS forbids '*')."
        )
    if "*" in settings.api_trusted_hosts:
        raise RuntimeError(
            "API_TRUSTED_HOSTS must enumerate exact hostnames outside the local "
            "environment ('*' disables the Host-header check)."
        )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
