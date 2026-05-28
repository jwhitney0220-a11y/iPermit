"""Intake-field suggestion from a free-form project description (SAAS-08).

A consultant pastes a one-paragraph project description ("60-acre subdivision
in Travis County with two stream crossings...") and the model returns a
*suggested* :class:`IntakeSuggestion` they can pre-fill into the intake form.
The deterministic engine still runs only after the consultant manually
confirms every field — nothing here decides anything (AGENTS.md *AI
Strategy*). The output is structured JSON the server parses + validates so a
malformed completion is a 422 rather than free-form text leaking into the
form.

Hard constraints baked into the system prompt:
- Output JSON only matching :data:`SUGGEST_SCHEMA`.
- Use the values the model is confident in; leave others null.
- Never produce permit names, agency decisions, or rule applicability —
  those are the engine's job.
- ``advisory_notes`` lists what the model is unsure about so the consultant
  knows where to look.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .client import AIClient, NarrativeResult

#: Soft cap on the description the API accepts; keeps token cost bounded
#: and matches a one-page memo (one paragraph or two).
MAX_DESCRIPTION_CHARS = 4000

#: Default max output tokens — small JSON document, ~200 tokens is plenty.
DEFAULT_SUGGEST_MAX_TOKENS = 600

#: JSON shape the model MUST emit. Asserted by :func:`parse_suggestion`; an
#: invalid completion raises :class:`SuggestionParseError` so the router can
#: return a 422 instead of leaking malformed data into the intake form.
SUGGEST_SCHEMA: dict[str, Any] = {
    "project_type": "str | null",
    "linear": "bool | null",
    "estimated_acres": "number | null",
    "county_hint": "str | null",
    "stream_crossings": "bool | null",
    "wetlands_present": "bool | null",
    "federal_nexus": "bool | null",
    "row_type": "str | null",
    "advisory_notes": "list[str]",
}

#: System prompt: forces strict JSON output, advisory framing, and forbids the
#: model from making rule-applicability decisions (that's the engine's job).
SUGGEST_SYSTEM_PROMPT = (
    "You are an intake assistant for environmental permit consultants. You will"
    " be given a short project description in plain English. Your job is to"
    " extract the fields the deterministic rules engine uses for evaluation —"
    " NOT to decide which permits apply (the engine does that, you do not).\n\n"
    "Output STRICT JSON only — no commentary, no markdown, no code fences."
    " Match this shape exactly (use null for unknown/uncertain values):\n"
    + json.dumps(SUGGEST_SCHEMA, indent=2)
    + "\n\nField rules:\n"
    "- ``project_type``: one of 'subdivision', 'roadway', 'pipeline',"
    " 'transmission', 'water_line', 'commercial', or 'other'.\n"
    "- ``linear``: true for roads/pipelines/transmission/water lines.\n"
    "- ``estimated_acres``: numeric only; null if the description is unclear.\n"
    "- ``county_hint``: a county name if explicitly mentioned; never a guess.\n"
    "- booleans default to null when the description does not say.\n"
    "- ``row_type``: 'public', 'private', 'mixed', or null.\n"
    "- ``advisory_notes``: list of short strings naming anything you were"
    " unsure about. ALWAYS non-empty if any field is null.\n\n"
    "You MUST NOT name permits, agencies, statutes, or applicability rules."
    " You MUST NOT use 'guaranteed', 'certified', or 'final determination'."
)


class SuggestionParseError(ValueError):
    """Raised when the model's JSON output does not match the contract."""


@dataclass(frozen=True)
class IntakeSuggestion:
    """One parsed AI intake suggestion (advisory; consultant confirms each field)."""

    project_type: str | None
    linear: bool | None
    estimated_acres: float | None
    county_hint: str | None
    stream_crossings: bool | None
    wetlands_present: bool | None
    federal_nexus: bool | None
    row_type: str | None
    advisory_notes: tuple[str, ...]
    model: str
    input_tokens: int
    output_tokens: int

    def to_dict(self) -> dict[str, Any]:
        """Return the suggestion as a plain dict for the API envelope."""
        return {
            "project_type": self.project_type,
            "linear": self.linear,
            "estimated_acres": self.estimated_acres,
            "county_hint": self.county_hint,
            "stream_crossings": self.stream_crossings,
            "wetlands_present": self.wetlands_present,
            "federal_nexus": self.federal_nexus,
            "row_type": self.row_type,
            "advisory_notes": list(self.advisory_notes),
            "model": self.model,
        }


def parse_suggestion(result: NarrativeResult) -> IntakeSuggestion:
    """Parse the model's JSON output into an :class:`IntakeSuggestion`."""
    try:
        payload = json.loads(result.text)
    except json.JSONDecodeError as exc:
        raise SuggestionParseError("AI intake response was not valid JSON") from exc
    if not isinstance(payload, dict):
        raise SuggestionParseError("AI intake response must be a JSON object")
    notes = payload.get("advisory_notes") or []
    if not isinstance(notes, list) or not all(isinstance(n, str) for n in notes):
        raise SuggestionParseError("advisory_notes must be a list of strings")
    return IntakeSuggestion(
        project_type=_str_or_none(payload.get("project_type")),
        linear=_bool_or_none(payload.get("linear")),
        estimated_acres=_num_or_none(payload.get("estimated_acres")),
        county_hint=_str_or_none(payload.get("county_hint")),
        stream_crossings=_bool_or_none(payload.get("stream_crossings")),
        wetlands_present=_bool_or_none(payload.get("wetlands_present")),
        federal_nexus=_bool_or_none(payload.get("federal_nexus")),
        row_type=_str_or_none(payload.get("row_type")),
        advisory_notes=tuple(notes),
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )


def suggest_intake(
    description: str,
    client: AIClient,
    *,
    max_tokens: int = DEFAULT_SUGGEST_MAX_TOKENS,
) -> IntakeSuggestion:
    """Return an :class:`IntakeSuggestion` parsed from *client*'s completion."""
    if not description.strip():
        raise SuggestionParseError("description is empty")
    if len(description) > MAX_DESCRIPTION_CHARS:
        raise SuggestionParseError(
            f"description exceeds {MAX_DESCRIPTION_CHARS} characters"
        )
    result = client.complete(
        system=SUGGEST_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": description}],
        max_tokens=max_tokens,
    )
    return parse_suggestion(result)


def _str_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _bool_or_none(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _num_or_none(value: Any) -> float | None:
    return (
        float(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        else None
    )


__all__ = [
    "DEFAULT_SUGGEST_MAX_TOKENS",
    "MAX_DESCRIPTION_CHARS",
    "SUGGEST_SCHEMA",
    "SUGGEST_SYSTEM_PROMPT",
    "IntakeSuggestion",
    "SuggestionParseError",
    "parse_suggestion",
    "suggest_intake",
]
