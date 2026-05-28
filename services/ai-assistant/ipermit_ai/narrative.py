"""Permit-matrix narrative summarization (SAAS-08, T09-02 sub-slice).

Renders the structured permit matrix (from ``ipermit_engine.simulation``) as a
consultant-friendly paragraph. The function never decides anything new — it
only synthesizes language *over* what the deterministic engine already
produced. The system prompt enforces advisory framing (no "guaranteed", no
"certified"), and the response is delivered alongside a dedicated AI-content
:class:`~ipermit_api.envelope.Advisory` so the consultant cannot mistake the
text for a legal determination.

Inputs to the model:
- the matrix's permits (name, agency, confidence tier, citations, sequencing)
- the active ruleset version + evaluation date (for traceability in the prompt)

The matrix is the source of truth; the narrative is one rendering of it.
"""

from __future__ import annotations

import json
from typing import Any

from .client import AIClient, NarrativeResult

#: Default max output tokens. Keeps the narrative tight (one paragraph) and
#: bounds cost; callers can raise it for longer-form features later.
DEFAULT_NARRATIVE_MAX_TOKENS = 600

#: Advisory attached to every AI-generated narrative response (AGENTS.md
#: *Liability Strategy* §4.4). Mirrors the platform advisory shape so the
#: front-end can render both with the same component.
AI_ADVISORY: dict[str, str] = {
    "text": (
        "This narrative was synthesized by an AI model from the deterministic"
        " permit matrix. The matrix and its citations remain the source of"
        " truth; the narrative is advisory and must not be relied on as a"
        " legal determination."
    ),
    "origin": "ai_assistant",
    "category": "advisory_disclaimer",
}

#: System prompt: hard-bounds the model's behavior. The phrasing constraints
#: are AGENTS.md *Liability Strategy* and *AI Strategy*, made literal so the
#: model never produces "guaranteed", "certified", or "final determination".
NARRATIVE_SYSTEM_PROMPT = (
    "You are an advisory writing assistant for environmental permit consultants."
    " You will receive a structured permit matrix produced by a deterministic"
    " rules engine. Summarize it as ONE short paragraph (3-6 sentences) a"
    " consultant can paste into a project memo.\n\n"
    "Strict rules:\n"
    "- Use advisory phrasing only ('likely required', 'commonly encountered',"
    " 'additional review recommended'). Never use 'guaranteed', 'complete"
    " certainty', 'final determination', 'certified', or 'legal compliance"
    " certification'.\n"
    "- Reference permits by the exact ``permit_name`` and ``agency`` from the"
    " matrix. Do NOT invent permits, agencies, statutes, or numbers.\n"
    "- Mention Tier 2/3 permits as needing consultant confirmation.\n"
    "- If the matrix is empty, say so plainly and recommend consultant"
    " review of the intake.\n"
    "- Do not produce headings, lists, or markdown — one prose paragraph."
)


def _matrix_payload(matrix: dict[str, Any]) -> str:
    """Project the matrix into a compact JSON the model can read.

    Drops verbose fields (full citation URLs, full explanations) that the
    narrative does not need, keeping the input token count predictable while
    preserving every name/agency/tier the prompt insists on.
    """
    permits = []
    for permit in matrix.get("permits", []):
        permits.append(
            {
                "permit_name": permit.get("permit_name"),
                "agency": permit.get("agency"),
                "confidence_tier": permit.get("confidence", {}).get("tier"),
                "sequencing": permit.get("sequencing"),
            }
        )
    return json.dumps(
        {
            "ruleset_version": matrix.get("ruleset_version", {}),
            "evaluation_date": matrix.get("evaluation_date"),
            "permits": permits,
        },
        separators=(",", ":"),
        default=str,
    )


def summarize_matrix(
    matrix: dict[str, Any],
    client: AIClient,
    *,
    max_tokens: int = DEFAULT_NARRATIVE_MAX_TOKENS,
) -> NarrativeResult:
    """Return one advisory paragraph synthesised from *matrix* via *client*."""
    payload = _matrix_payload(matrix)
    user = (
        "Summarize this permit matrix as one advisory paragraph for a project"
        " memo. Matrix (JSON):\n```json\n" + payload + "\n```"
    )
    return client.complete(
        system=NARRATIVE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user}],
        max_tokens=max_tokens,
    )


__all__ = [
    "AI_ADVISORY",
    "DEFAULT_NARRATIVE_MAX_TOKENS",
    "NARRATIVE_SYSTEM_PROMPT",
    "summarize_matrix",
]
