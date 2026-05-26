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


def test_non_local_accepts_strong_secret() -> None:
    validate_security(Settings(ipermit_env="production", auth_jwt_secret="x" * 32))
