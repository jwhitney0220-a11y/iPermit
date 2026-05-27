"""Security guardrail tests (S01-07)."""

from __future__ import annotations

import pytest
from ipermit_api.settings import Settings, validate_security


def test_local_allows_default_secret() -> None:
    validate_security(
        Settings(ipermit_env="local", auth_jwt_secret="CHANGE_ME_LOCAL_ONLY")
    )


def test_non_local_rejects_default_secret() -> None:
    with pytest.raises(RuntimeError):
        validate_security(
            Settings(ipermit_env="production", auth_jwt_secret="CHANGE_ME_LOCAL_ONLY")
        )


def test_non_local_rejects_short_secret() -> None:
    with pytest.raises(RuntimeError):
        validate_security(Settings(ipermit_env="staging", auth_jwt_secret="too-short"))


def _prod_settings(**overrides: str) -> Settings:
    """Production settings with a strong JWT secret + real Stripe keys.

    The Stripe defaults are inert placeholders rejected outside local, so a
    valid non-local config must override them (S03-01).
    """
    base = {
        "ipermit_env": "production",
        "auth_jwt_secret": "x" * 32,
        "stripe_secret_key": "sk_live_real",
        "stripe_webhook_secret": "whsec_real",
    }
    base.update(overrides)
    return Settings(**base)


def test_non_local_accepts_strong_secret() -> None:
    validate_security(_prod_settings())


def test_non_local_rejects_placeholder_stripe_keys() -> None:
    """A non-local env must not run with the inert Stripe placeholders (S03-01)."""
    with pytest.raises(RuntimeError):
        validate_security(_prod_settings(stripe_secret_key="sk_test_PLACEHOLDER"))
    with pytest.raises(RuntimeError):
        validate_security(
            _prod_settings(stripe_webhook_secret="whsec_test_PLACEHOLDER")
        )
