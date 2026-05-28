"""AI provider seam for the constrained assistance surface (SAAS-08).

A single :class:`AIClient` protocol lets every assistance feature consume
``complete(messages, system, max_tokens) -> NarrativeResult`` without caring
which provider answered. Two implementations ship:

* :class:`AnthropicClient` — production path. Lazy-imports the ``anthropic``
  SDK so the package loads in test/dev environments that intentionally do not
  pull the runtime dep; the failure is loud and actionable when a non-local
  deploy is missing it.
* :class:`StubAIClient` — deterministic fixture for tests and the local dev
  loop. Returns a canned narrative + token counts so the route + audit + the
  envelope's advisory framing can be exercised end-to-end without an API key.

Prompt caching, structured outputs, and tool use are all out of scope for the
first slice — keep the seam minimal and add capability behind it later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class NarrativeResult:
    """One completion: the rendered text + book-keeping for audit/usage."""

    text: str
    model: str
    input_tokens: int
    output_tokens: int


class AIClient(Protocol):
    """Minimum AI surface every constrained feature uses (SAAS-08)."""

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
    ) -> NarrativeResult:
        """Return the model's completion for *messages* under *system*."""


@dataclass
class AnthropicClient:
    """Production :class:`AIClient` backed by the Anthropic SDK (Claude API).

    The SDK is imported lazily — importing this module must not require the
    ``anthropic`` package to be installed, so tests + CI can run with only
    the stub. Construction without an API key raises immediately so a
    misconfigured non-local env fails loudly rather than silently degrading.
    """

    api_key: str
    model: str

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
    ) -> NarrativeResult:
        """Call ``messages.create`` on the Claude API and project the result."""
        if not self.api_key:
            raise RuntimeError(
                "AnthropicClient requires AI_API_KEY (resolved from secrets in non-local)."
            )
        import anthropic  # noqa: PLC0415 — lazy so tests do not require the SDK

        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        text = "".join(
            block.text
            for block in response.content
            if getattr(block, "type", "") == "text"
        )
        return NarrativeResult(
            text=text.strip(),
            model=response.model,
            input_tokens=getattr(response.usage, "input_tokens", 0),
            output_tokens=getattr(response.usage, "output_tokens", 0),
        )


@dataclass
class StubAIClient:
    """Deterministic :class:`AIClient` for tests and the local dev loop."""

    canned_text: str = "Sample advisory narrative from the stub AI client."
    model: str = "stub-claude"

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
    ) -> NarrativeResult:
        """Echo a canned narrative; the system + messages prove framing is intact."""
        assert system, "narrative call must include a constrained system prompt"
        assert messages, "narrative call must include at least one user message"
        return NarrativeResult(
            text=self.canned_text,
            model=self.model,
            input_tokens=len(system) // 4,
            output_tokens=len(self.canned_text) // 4,
        )


__all__ = ["AIClient", "AnthropicClient", "NarrativeResult", "StubAIClient"]
