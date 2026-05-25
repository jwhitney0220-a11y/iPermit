"""Rule diff and change analysis (T04-04).

Generates explainable comparisons between rule revisions and between whole
rulesets, plus the output impact of a ruleset change on a given project:

- :func:`diff_rules` — field-level diff of two revisions of one rule.
- :func:`diff_rulesets` — added / removed / changed rules across two rulesets.
- :func:`output_impact` — re-runs the simulation engine on both rulesets and
  reports which permits and confidence tiers changed, and which jurisdiction
  levels are affected.

Pure and deterministic: every collection is sorted; structural fields are
compared by canonical JSON so key order never produces a spurious diff.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .context import ProjectContext
from .simulation import simulate_project

_SCALAR_FIELDS = (
    "version",
    "status",
    "confidence_tier",
    "jurisdiction_id",
    "jurisdiction_level",
    "source_agency",
    "permit_code",
    "effective_from",
    "effective_to",
    "superseded_by",
)
_SET_FIELDS = ("applicable_project_types", "supersedes")
_STRUCT_FIELDS = ("triggers", "outputs", "sequencing")


@dataclass(frozen=True)
class FieldChange:
    """One changed field between two rule revisions."""

    field: str
    old: Any
    new: Any


@dataclass(frozen=True)
class RuleDiff:
    """The difference between two revisions of a single rule."""

    rule_id: str
    changed: tuple[FieldChange, ...]
    added: bool
    removed: bool
    summary: str


def _canon(value: Any) -> str:
    """Canonical JSON of a value so key/element order never spoofs a diff."""
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _field_changes(old: Mapping[str, Any], new: Mapping[str, Any]) -> list[FieldChange]:
    """Collect the load-bearing field changes between two rule revisions."""
    changes: list[FieldChange] = []
    for field in _SCALAR_FIELDS:
        if old.get(field) != new.get(field):
            changes.append(FieldChange(field, old.get(field), new.get(field)))
    for field in _SET_FIELDS:
        old_set, new_set = set(old.get(field) or []), set(new.get(field) or [])
        if old_set != new_set:
            changes.append(FieldChange(field, sorted(old_set), sorted(new_set)))
    for field in _STRUCT_FIELDS:
        if _canon(old.get(field)) != _canon(new.get(field)):
            changes.append(FieldChange(field, old.get(field), new.get(field)))
    return changes


def _scalar_phrase(change: FieldChange) -> str:
    """Render one scalar/set field change as a compact phrase."""
    if change.field in _STRUCT_FIELDS:
        return f"{change.field} changed"
    return f"{change.field} {change.old!r}->{change.new!r}"


def diff_rules(old: Mapping[str, Any], new: Mapping[str, Any]) -> RuleDiff:
    """Diff two revisions of one rule (same rule_id) into a RuleDiff."""
    rule_id = new.get("rule_id") or old.get("rule_id") or "<unknown>"
    changes = _field_changes(old, new)
    if changes:
        summary = f"{rule_id}: " + "; ".join(_scalar_phrase(c) for c in changes)
    else:
        summary = f"{rule_id}: no load-bearing change"
    return RuleDiff(
        rule_id, tuple(changes), added=False, removed=False, summary=summary
    )


@dataclass(frozen=True)
class RulesetDiff:
    """Added, removed, and changed rules between two rulesets."""

    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[RuleDiff, ...]
    summary: str


def diff_rulesets(
    old_rules: Iterable[Mapping[str, Any]],
    new_rules: Iterable[Mapping[str, Any]],
) -> RulesetDiff:
    """Diff two rulesets by rule_id into added / removed / changed sets."""
    old_by_id = {r["rule_id"]: r for r in old_rules}
    new_by_id = {r["rule_id"]: r for r in new_rules}
    added = tuple(sorted(set(new_by_id) - set(old_by_id)))
    removed = tuple(sorted(set(old_by_id) - set(new_by_id)))
    changed = [
        diff
        for rule_id in sorted(set(old_by_id) & set(new_by_id))
        if (diff := diff_rules(old_by_id[rule_id], new_by_id[rule_id])).changed
    ]
    summary = f"{len(added)} added, {len(removed)} removed, {len(changed)} changed"
    return RulesetDiff(added, removed, tuple(changed), summary)


@dataclass(frozen=True)
class OutputImpact:
    """The effect of a ruleset change on one project's evaluation."""

    added_permits: tuple[tuple[str, str], ...]
    removed_permits: tuple[tuple[str, str], ...]
    confidence_changes: tuple[tuple[str, int, int], ...]
    jurisdiction_levels_affected: tuple[str, ...]
    summary: str


def _permit_set(simulation: Any) -> set[tuple[str, str]]:
    """Set of (permit name, agency) from a simulation's fired rules."""
    return {
        (permit["name"], permit["agency"])
        for rule in simulation.fired_rules
        for permit in rule.get("outputs", {}).get("permits", [])
    }


def _permit_tiers(simulation: Any) -> dict[str, int]:
    """Map permit name to confidence tier from a simulation's fired rules."""
    tiers: dict[str, int] = {}
    for rule in simulation.fired_rules:
        for permit in rule.get("outputs", {}).get("permits", []):
            tiers[permit["name"]] = rule["confidence_tier"]
    return tiers


def _levels_affected(
    old_sim: Any, new_sim: Any, changed_permits: set[tuple[str, str]]
) -> tuple[str, ...]:
    """Jurisdiction levels of rules whose emitted permits changed membership."""
    levels: set[str] = set()
    for simulation in (old_sim, new_sim):
        for rule in simulation.fired_rules:
            permits = {
                (p["name"], p["agency"])
                for p in rule.get("outputs", {}).get("permits", [])
            }
            if permits & changed_permits and rule.get("jurisdiction_level"):
                levels.add(rule["jurisdiction_level"])
    return tuple(sorted(levels))


def output_impact(
    old_rules: Iterable[Mapping[str, Any]],
    new_rules: Iterable[Mapping[str, Any]],
    *,
    context: ProjectContext,
    applicable_jurisdiction_ids: Iterable[str],
    project_types: Iterable[str],
    jurisdiction_chain: list[dict[str, Any]],
    evaluation_date: str,
) -> OutputImpact:
    """Report how a project's permits/confidence change between two rulesets."""
    common = {
        "context": context,
        "applicable_jurisdiction_ids": list(applicable_jurisdiction_ids),
        "project_types": list(project_types),
        "jurisdiction_chain": jurisdiction_chain,
        "evaluation_date": evaluation_date,
    }
    old_sim = simulate_project(rules=old_rules, **common)
    new_sim = simulate_project(rules=new_rules, **common)
    old_permits, new_permits = _permit_set(old_sim), _permit_set(new_sim)
    old_tiers, new_tiers = _permit_tiers(old_sim), _permit_tiers(new_sim)
    confidence_changes = tuple(
        (name, old_tiers[name], new_tiers[name])
        for name in sorted(set(old_tiers) & set(new_tiers))
        if old_tiers[name] != new_tiers[name]
    )
    added = tuple(sorted(new_permits - old_permits))
    removed = tuple(sorted(old_permits - new_permits))
    levels = _levels_affected(old_sim, new_sim, (new_permits ^ old_permits))
    summary = (
        f"{len(added)} permit(s) added, {len(removed)} removed, "
        f"{len(confidence_changes)} confidence change(s); "
        f"levels affected: {', '.join(levels) or 'none'}"
    )
    return OutputImpact(added, removed, confidence_changes, levels, summary)
