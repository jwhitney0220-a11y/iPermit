"""Rule simulation engine (T04-01).

Runs a project against a ruleset and bundles the full deterministic pipeline
output — fired rules, conflict resolution, sequencing, explanation records, and
known-unknowns — into one :class:`SimulationResult`.

Three modes, all via :func:`simulate_project`:

- **active / direct** (default): evaluate exactly the rules supplied.
- **historical replay**: ``governing_only=True`` first selects the versions
  governing ``evaluation_date`` (a dict mirror of temporal-versioning.md §4 /
  ``ipermit_regulatory.temporal`` for the on-disk rule-store dicts).
- **hypothetical**: ``overlay`` adds, replaces, or removes rules before
  evaluation.

Pure and DB-free: rules come in as plain dicts (T00-01 shape), like the rest of
``ipermit_engine``.
"""

from __future__ import annotations

import datetime
import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .conflict import ResolutionResult, resolve_conflicts
from .context import ProjectContext
from .engine import RuleEvaluation, evaluate_ruleset
from .explain import build_explanation, hash_inputs
from .known_unknowns import KnownUnknownItem, collect_known_unknowns
from .sequencing import SequencerResult, sequence_rules

_GOVERNING_STATUSES = frozenset({"effective", "archived"})


@dataclass(frozen=True)
class SimulationResult:
    """Bundled deterministic output of one project simulation (T04-01)."""

    evaluation_date: str
    ruleset_version: dict[str, Any]
    inputs_hash: str
    fired: tuple[RuleEvaluation, ...]
    fired_rules: tuple[dict[str, Any], ...]
    resolution: ResolutionResult
    sequencing: SequencerResult
    explanations: tuple[dict[str, Any], ...]
    known_unknowns: dict[str, tuple[KnownUnknownItem, ...]]


def ruleset_content_hash(rules: Iterable[Mapping[str, Any]]) -> str:
    """Return a deterministic ``sha256:<hex>`` over a ruleset (order-independent)."""
    ordered = sorted(
        (dict(r) for r in rules),
        key=lambda r: (r.get("rule_id", ""), r.get("version", "")),
    )
    canonical = json.dumps(
        ordered, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def apply_overlay(
    base_rules: Iterable[Mapping[str, Any]],
    overlay: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return *base_rules* with a hypothetical *overlay* applied.

    ``overlay`` keys: ``upsert`` (rule dicts added or replacing by ``rule_id``)
    and ``remove`` (``rule_id`` strings to drop). Output is sorted by ``rule_id``.
    """
    by_id = {r["rule_id"]: dict(r) for r in base_rules}
    for rule in overlay.get("upsert", []):
        by_id[rule["rule_id"]] = dict(rule)
    for rule_id in overlay.get("remove", []):
        by_id.pop(rule_id, None)
    return [by_id[key] for key in sorted(by_id)]


def _version_key(version: str) -> tuple[int | str, ...]:
    """Sortable semver key; falls back to the raw string (mirrors temporal)."""
    try:
        return tuple(int(p) for p in version.split("."))
    except ValueError:
        return (version,)


def _governs(rule: Mapping[str, Any], on_date: datetime.date) -> bool:
    """True if a rule dict governs *on_date* (temporal-versioning.md §4, inclusive)."""
    if rule.get("status") not in _GOVERNING_STATUSES:
        return False
    effective_from = rule.get("effective_from")
    if not effective_from or datetime.date.fromisoformat(effective_from) > on_date:
        return False
    effective_to = rule.get("effective_to")
    return not effective_to or datetime.date.fromisoformat(effective_to) >= on_date


def _best_version(group: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick latest effective_from, then highest semver, from one rule_id group."""
    latest = max(g["effective_from"] for g in group)
    finalists = [g for g in group if g["effective_from"] == latest]
    return max(finalists, key=lambda g: _version_key(g.get("version", "")))


def select_governing(
    rules: Iterable[Mapping[str, Any]],
    evaluation_date: str,
) -> list[dict[str, Any]]:
    """Select the version of each rule_id governing *evaluation_date*.

    Dict-based mirror of ``ipermit_regulatory.temporal.effective_ruleset``:
    keeps only effective/archived rules whose inclusive date window contains the
    date, then per rule_id the latest effective_from, then highest semver.
    Returns a list sorted by rule_id.
    """
    on_date = datetime.date.fromisoformat(evaluation_date)
    by_id: dict[str, list[dict[str, Any]]] = {}
    for rule in rules:
        if _governs(rule, on_date):
            by_id.setdefault(rule["rule_id"], []).append(dict(rule))
    return [_best_version(group) for _, group in sorted(by_id.items())]


def simulate_project(
    *,
    rules: Iterable[Mapping[str, Any]],
    context: ProjectContext,
    applicable_jurisdiction_ids: Iterable[str],
    project_types: Iterable[str],
    jurisdiction_chain: list[dict[str, Any]],
    evaluation_date: str,
    overlay: Mapping[str, Any] | None = None,
    governing_only: bool = False,
) -> SimulationResult:
    """Evaluate a project against a ruleset and bundle the full pipeline output.

    Applies *overlay* (hypothetical) then optional temporal selection
    (*governing_only* — historical replay), evaluates the ruleset, resolves
    conflicts, sequences dependencies, and builds an explanation record plus
    known-unknowns for every fired rule. Pure; see module docstring for modes.
    """
    working = apply_overlay(rules, overlay) if overlay else [dict(r) for r in rules]
    if governing_only:
        working = select_governing(working, evaluation_date)
    by_id = {r["rule_id"]: r for r in working}
    fired = evaluate_ruleset(
        working, context, applicable_jurisdiction_ids, project_types
    )
    fired_rules = [by_id[result.rule_id] for result in fired]
    inputs_hash = hash_inputs(context.as_dict())
    ruleset_version = {"content_hash": ruleset_content_hash(working)}
    explanations = tuple(
        build_explanation(
            evaluation=result,
            rule=by_id[result.rule_id],
            jurisdiction_chain=jurisdiction_chain,
            evaluation_date=evaluation_date,
            ruleset_version=ruleset_version,
            inputs_hash=inputs_hash,
        )
        for result in fired
    )
    known = {
        result.rule_id: tuple(
            collect_known_unknowns(result, by_id[result.rule_id], context=context)
        )
        for result in fired
    }
    return SimulationResult(
        evaluation_date=evaluation_date,
        ruleset_version=ruleset_version,
        inputs_hash=inputs_hash,
        fired=tuple(fired),
        fired_rules=tuple(fired_rules),
        resolution=resolve_conflicts(fired_rules, fired),
        sequencing=sequence_rules(fired_rules),
        explanations=explanations,
        known_unknowns=known,
    )
