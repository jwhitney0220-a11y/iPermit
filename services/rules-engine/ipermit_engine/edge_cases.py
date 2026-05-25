"""Edge-case analysis primitives for the rules engine (T04-03).

Reusable, pure helpers that surface the four edge categories the QA/QC process
must guard against (AGENTS.md *Rule validation, simulation & QA/QC*):

- **incomplete project data** — :func:`find_missing_inputs` lifts the
  ``missing_input`` known-unknowns the engine raised for absent trigger fields.
- **ambiguous thresholds** — :func:`numeric_threshold_leaves` /
  :func:`boundary_probe_values` expose numeric comparison leaves and the values
  to probe on either side of each threshold.
- **overlapping jurisdictions** — :func:`overlapping_requirements` lists the
  requirements where more than one fired rule contended (parent always
  preserved by the conflict resolver).
- **conflicting triggers** — determinism is an engine contract; the test suite
  asserts it by re-running a simulation.

These are analysis primitives consumed by ``tests/engine/test_edge_cases.py``
and by the QA report (T04-05). The runtime engine never imports this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .operators import comparison_operators

_MISSING_FIELD_RE = re.compile(r"Input field '([^']+)'")
_NUMERIC_OPERATORS = frozenset(comparison_operators())


@dataclass(frozen=True)
class ThresholdLeaf:
    """A numeric comparison leaf lifted from a rule's trigger tree."""

    field: str
    operator: str
    value: float


def numeric_threshold_leaves(triggers: dict[str, Any]) -> list[ThresholdLeaf]:
    """Return every numeric comparison leaf in a rule's *triggers* tree.

    Walks ``all`` / ``any`` / ``not`` composites and collects leaves whose
    operator is a comparison and whose ``value`` is a real number (booleans are
    excluded, matching the engine's ordered-operator contract).
    """
    out: list[ThresholdLeaf] = []
    _walk(triggers, out)
    return out


def _walk(node: dict[str, Any] | None, out: list[ThresholdLeaf]) -> None:
    """Recursively collect numeric comparison leaves from a trigger tree."""
    if not isinstance(node, dict):
        return
    if "field" in node:
        value = node.get("value")
        if node.get("operator") in _NUMERIC_OPERATORS and _is_number(value):
            out.append(ThresholdLeaf(node["field"], node["operator"], float(value)))
        return
    for key in ("all", "any"):
        for child in node.get(key, []):
            _walk(child, out)
    if "not" in node:
        _walk(node["not"], out)


def _is_number(value: Any) -> bool:
    """True for int/float values, excluding booleans."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def boundary_probe_values(threshold: float, step: float = 1.0) -> list[float]:
    """Return [below, exact, above] probe values for a numeric *threshold*.

    Used to exercise both sides of a threshold so analysts can confirm the
    engine fires (or not) deterministically at the boundary.
    """
    return [threshold - step, threshold, threshold + step]


def find_missing_inputs(simulation: Any) -> dict[str, list[str]]:
    """Map each fired rule_id to the trigger fields the engine flagged as absent.

    Reads the ``missing_input`` known-unknowns from a ``SimulationResult`` so the
    QA report can surface "incomplete project data" cases.
    """
    out: dict[str, list[str]] = {}
    for rule_id, items in simulation.known_unknowns.items():
        fields = sorted(
            match.group(1)
            for item in items
            if item.category == "missing_input"
            and (match := _MISSING_FIELD_RE.search(item.text))
        )
        if fields:
            out[rule_id] = fields
    return out


@dataclass(frozen=True)
class OverlapRecord:
    """A requirement contended over by more than one fired rule."""

    requirement_key: str
    governing_rule_id: str
    contributing_rule_ids: tuple[str, ...]


def overlapping_requirements(resolution: Any) -> list[OverlapRecord]:
    """List requirements where multiple fired rules overlap on the same permit.

    The conflict resolver always preserves the parent rule(s) as ``contributing``
    (override, never delete); this surfaces those overlaps for QA review.
    """
    records: list[OverlapRecord] = []
    for requirement in resolution.requirements:
        if requirement.contributing:
            records.append(
                OverlapRecord(
                    requirement_key=requirement.requirement_key,
                    governing_rule_id=requirement.governing.rule_id,
                    contributing_rule_ids=tuple(
                        fr.rule_id for fr in requirement.contributing
                    ),
                )
            )
    return records
