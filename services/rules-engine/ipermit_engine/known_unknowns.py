"""Known-unknown detection for fired rules (T03-06).

Given a fired :class:`~ipermit_engine.engine.RuleEvaluation` and the canonical
rule object dict, this module identifies situations requiring consultant review,
agency coordination, discretionary interpretation, or manual confirmation.

Two source families are merged into a deterministic list of
:class:`KnownUnknownItem` records:

1. **Authored** — ``rule["known_unknowns"]`` strings surfaced verbatim.
2. **Detected** — engine signals derived from the evaluation tree and the rule
   object at runtime:

   - ``low_confidence``: rule ``confidence_tier == 3`` (informational → requires
     consultant confirmation per AGENTS.md *Permit Confidence Tiers*).
   - ``missing_input``: a trigger leaf matched (or evaluated) against a field
     whose ``actual_value`` was ``None`` (the serialised form of ``MISSING``)
     — the rule fired via a default/fallback path without a real value.
   - ``discretionary``: the rule carries authored ``advisories`` whose text
     contains discretionary-interpretation signals (``discretion``, ``may vary``,
     ``locally variable``, ``interpretation``).

Advisory-language contract (AGENTS.md *Liability Strategy*): every detected
item description uses advisory phrasing ("additional review recommended") and
MUST NOT contain prohibited certainty language (e.g. "guaranteed").

Ordering is deterministic per T00-05 §6 (arrays sorted by ``(category, text)``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .engine import RuleEvaluation

# Wording that signals discretionary or locally-variable interpretation.
_DISCRETIONARY_SIGNALS = (
    "discretion",
    "may vary",
    "locally variable",
    "interpretation",
)

# Confidence tier that requires consultant confirmation (AGENTS.md Tier 3).
_INFORMATIONAL_TIER = 3


@dataclass(frozen=True, order=True)
class KnownUnknownItem:
    """A single known-unknown or uncertainty item for a fired rule.

    Attributes:
        category: One of ``authored``, ``low_confidence``, ``missing_input``,
            ``discretionary``.
        text: Advisory-compliant description of the uncertainty.
    """

    category: str
    text: str


def collect_known_unknowns(
    evaluation: RuleEvaluation,
    rule: dict[str, Any],
    *,
    context: Any = None,  # ProjectContext; reserved for future detection signals
) -> list[KnownUnknownItem]:
    """Return a deterministic list of known-unknown items for a fired rule.

    Args:
        evaluation: The :class:`~ipermit_engine.engine.RuleEvaluation` for this
            rule (must have ``fired = True``).
        rule: The canonical rule object dict (T00-01 shape).
        context: Optional :class:`~ipermit_engine.context.ProjectContext`;
            reserved for future signals; not used in this implementation.

    Returns:
        Sorted list of :class:`KnownUnknownItem` (deterministic by
        ``(category, text)``).
    """
    items: list[KnownUnknownItem] = []
    items.extend(_authored_items(rule))
    items.extend(_detected_items(evaluation, rule))
    return sorted(set(items))


# ---------------------------------------------------------------------------
# Source 1: authored known_unknowns
# ---------------------------------------------------------------------------


def _authored_items(rule: dict[str, Any]) -> list[KnownUnknownItem]:
    """Surface the rule's authored ``known_unknowns`` strings verbatim."""
    return [
        KnownUnknownItem(category="authored", text=text)
        for text in rule.get("known_unknowns", [])
        if isinstance(text, str) and text.strip()
    ]


# ---------------------------------------------------------------------------
# Source 2: detected uncertainty conditions
# ---------------------------------------------------------------------------


def _detected_items(
    evaluation: RuleEvaluation, rule: dict[str, Any]
) -> list[KnownUnknownItem]:
    """Collect engine-detected uncertainty items from the evaluation and rule."""
    items: list[KnownUnknownItem] = []
    items.extend(_low_confidence_items(rule))
    items.extend(_missing_input_items(evaluation))
    items.extend(_discretionary_items(rule))
    return items


def _low_confidence_items(rule: dict[str, Any]) -> list[KnownUnknownItem]:
    """Emit a low_confidence item when the rule is Tier 3 (informational)."""
    if rule.get("confidence_tier") != _INFORMATIONAL_TIER:
        return []
    return [
        KnownUnknownItem(
            category="low_confidence",
            text=(
                "This permit identification is informational only. "
                "Additional review recommended — consultant confirmation required "
                "before relying on this result."
            ),
        )
    ]


def _missing_input_items(evaluation: RuleEvaluation) -> list[KnownUnknownItem]:
    """Emit missing_input items for trigger leaves that evaluated against MISSING.

    A leaf with ``actual_value = None`` in the evaluated tree means the context
    did not supply the field; the rule fired through a branch that did not
    require that field, but any leaf that was evaluated without a real value
    represents an input the consultant should verify.
    """
    if evaluation.evaluated_triggers is None:
        return []
    missing_fields = _collect_missing_fields(evaluation.evaluated_triggers)
    return [
        KnownUnknownItem(
            category="missing_input",
            text=(
                f"Input field {field!r} was not provided. "
                "Additional review recommended — verify this value with the "
                "project record before relying on this result."
            ),
        )
        for field in sorted(missing_fields)
    ]


def _discretionary_items(rule: dict[str, Any]) -> list[KnownUnknownItem]:
    """Emit a discretionary item when authored advisories indicate variability."""
    advisories = rule.get("advisories", [])
    combined = " ".join(a.lower() for a in advisories if isinstance(a, str))
    if not any(signal in combined for signal in _DISCRETIONARY_SIGNALS):
        return []
    return [
        KnownUnknownItem(
            category="discretionary",
            text=(
                "One or more advisories indicate discretionary or locally variable "
                "interpretation. Agency coordination recommended before submission."
            ),
        )
    ]


# ---------------------------------------------------------------------------
# Helper: walk the evaluated trigger tree for MISSING leaves
# ---------------------------------------------------------------------------


def _collect_missing_fields(node: dict[str, Any]) -> set[str]:
    """Recursively find leaf fields whose actual_value was None (MISSING)."""
    if "field" in node:
        if node.get("actual_value") is None:
            return {node["field"]}
        return set()
    fields: set[str] = set()
    for key in ("all", "any"):
        if key in node:
            for child in node[key]:
                fields |= _collect_missing_fields(child)
    if "not" in node:
        fields |= _collect_missing_fields(node["not"])
    return fields
