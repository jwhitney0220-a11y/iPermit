"""Constrained AI assistance package (SAAS-08, EPIC-09).

The deterministic rules engine is the source of truth (AGENTS.md *AI Strategy*).
The pieces in this package never override an engine output — they only
synthesize *advisory* artefacts (narrative summaries, consultant-friendly
explanations) from already-evaluated structured data, and every API surface
that exposes them carries the standard platform advisory plus an AI-content
advisory so a consultant cannot mistake them for legal determinations.

Public surface:
- :class:`AIClient` — protocol every AI provider implements.
- :class:`AnthropicClient` — production client (Claude API, lazy SDK import).
- :class:`StubAIClient` — deterministic fixture used by tests + dev.
- :func:`summarize_matrix` — render a structured permit matrix as a
  consultant-friendly paragraph; advisory framing is enforced via the system
  prompt and round-tripped to the caller as advisory metadata.
"""

from .client import AIClient, AnthropicClient, NarrativeResult, StubAIClient
from .narrative import (
    AI_ADVISORY,
    DEFAULT_NARRATIVE_MAX_TOKENS,
    NARRATIVE_SYSTEM_PROMPT,
    summarize_matrix,
)

__all__ = [
    "AI_ADVISORY",
    "DEFAULT_NARRATIVE_MAX_TOKENS",
    "NARRATIVE_SYSTEM_PROMPT",
    "AIClient",
    "AnthropicClient",
    "NarrativeResult",
    "StubAIClient",
    "summarize_matrix",
]
