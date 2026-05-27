"""API service configuration (S01-03).

Reads the environment-variable contract from ``.env.example`` (T01-08): the
``IPERMIT_*`` runtime vars, ``DATABASE_URL`` (shared by the app engine and
Alembic), and the ``AUTH_*`` block. Secrets are never hard-coded — local dev may
set a throwaway ``AUTH_JWT_SECRET``; staging/production resolve it from the
secret manager (``AUTH_JWT_SECRET_REF``).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

_LOCAL_DB = "sqlite+pysqlite:///./ipermit.db"


class Settings(BaseSettings):
    """Typed view over the API's environment configuration."""

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    ipermit_env: str = "local"
    database_url: str = _LOCAL_DB
    auth_jwt_secret: str = "CHANGE_ME_LOCAL_ONLY"
    auth_jwt_algorithm: str = "HS256"
    auth_token_ttl_minutes: int = 60

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


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
