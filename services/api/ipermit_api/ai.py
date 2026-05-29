"""AI-client factory for the API surface (SAAS-08, S08-01).

The constrained AI features in :mod:`routers.ai` route through this seam so
the production Claude API path can be swapped for the :class:`StubAIClient`
in tests without touching the route. The factory is built once per process
and cached; tests inject a stub via :func:`set_ai_client`.
"""

from __future__ import annotations

from ipermit_ai import AIClient, AnthropicClient, StubAIClient

from .settings import Settings, get_settings

_AI_CLIENT: AIClient | None = None


def get_ai_client(settings: Settings | None = None) -> AIClient:
    """Return the process-wide :class:`AIClient` (lazy, cached)."""
    global _AI_CLIENT  # noqa: PLW0603 — module-level lazy singleton
    settings = settings or get_settings()
    if _AI_CLIENT is None:
        _AI_CLIENT = _build_client(settings)
    return _AI_CLIENT


def set_ai_client(client: AIClient | None) -> None:
    """Override the cached client (tests inject a deterministic stub)."""
    global _AI_CLIENT  # noqa: PLW0603 — module-level lazy singleton
    _AI_CLIENT = client


def _build_client(settings: Settings) -> AIClient:
    """Pick a real or stub client based on ``AI_PROVIDER`` and feature flag."""
    if settings.ai_provider in ("stub", "local") or not settings.ai_api_key:
        return StubAIClient()
    return AnthropicClient(api_key=settings.ai_api_key, model=settings.ai_model_id)


__all__ = ["get_ai_client", "set_ai_client"]
