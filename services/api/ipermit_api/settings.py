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
    billing_provider: str = "stub"
    billing_webhook_secret: str = "CHANGE_ME_LOCAL_ONLY"

    @property
    def is_local(self) -> bool:
        """True for the local development environment."""
        return self.ipermit_env == "local"


# Placeholder secret from .env.example — must never sign tokens off local.
_PLACEHOLDER_SECRET = "CHANGE_ME_LOCAL_ONLY"
_MIN_SECRET_BYTES = 32


def _check_secret(name: str, value: str) -> None:
    """Raise if a security secret is the placeholder or too short."""
    if value == _PLACEHOLDER_SECRET or len(value.encode()) < _MIN_SECRET_BYTES:
        raise RuntimeError(
            f"{name} must be set to a strong value "
            f"(>= {_MIN_SECRET_BYTES} bytes) outside the local environment."
        )


def validate_security(settings: Settings) -> None:
    """Fail fast if a non-local env would run with weak/default secrets."""
    if settings.is_local:
        return
    _check_secret("AUTH_JWT_SECRET", settings.auth_jwt_secret)
    _check_secret("BILLING_WEBHOOK_SECRET", settings.billing_webhook_secret)


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
