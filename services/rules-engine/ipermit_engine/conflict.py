"""Deterministic conflict resolution for fired rules (T03-03).

Takes the rules that **fired** for a project (per T03-02 ``evaluate_ruleset``)
and resolves contradictory guidance between overlapping jurisdictions into a
single, deterministic, explainable result. This module is **pure** and DB-free:
every input is passed in, and there is NO hardcoded permit logic — resolution is
driven entirely by the rule data plus the jurisdiction precedence ladder of the
T00-02 ontology spec.

What is and is not a conflict
-----------------------------
The governing invariant (AGENTS.md *Rules Engine Architecture*; ontology §5.1,
§5.3): a lower jurisdiction may add requirements, override thresholds, and append
advisories, but MUST NOT silently delete a parent jurisdiction's requirement.

Consequently (ontology §7.2 "overlap union, not overlap merge"):

- Two fired rules from different jurisdictions requiring **distinct** permits are
  NOT a conflict. Both apply and both are preserved. The engine never merges or
  suppresses one in favour of the other.
- A conflict is **contradictory guidance on the same requirement** — two fired
  rules that target the *same permit* (same identity) from *different jurisdiction
  levels*. The classic case is a lower jurisdiction overriding a parent's
  threshold or submission detail for that permit.

Resolution semantics (ontology §5.2, §5.4)
------------------------------------------
The level order in ontology §4.1 is a precedence ladder running from least
specific (``federal``) to most specific (``special``). When two fired rules touch
the same permit:

- The **more specific (lower) jurisdiction's rule governs** the requirement — its
  outputs are the *governing* version surfaced for that requirement group.
- The parent (higher-level) rule is **always preserved** in the result as a
  contributing rule; it is never dropped. This is the operational form of
  "override/append, never delete".
- Both rules' jurisdiction context, outputs, advisories, and known-unknowns
  remain available to downstream consumers (T07-02 renders both; T03-05 explains
  the choice). The platform does not rank permits by severity (ontology §5.4).

Explicit supersession (ontology §5.3)
-------------------------------------
``supersedes`` / ``superseded_by`` (rule_id@version refs, rule-object spec §5.4)
are honoured first, before precedence. A fired rule that is superseded by another
fired rule is removed from the *governing* set (the superseding rule formally
takes its place — the only legitimate cross-level deletion), but the superseded
rule is still **recorded** in the conflict report so the deletion is never
silent. A ``supersedes`` reference to a rule that did NOT fire is a no-op.

Documented assumption (spec ambiguity, flagged per ticket)
----------------------------------------------------------
The ontology §5.2 resolves the "stricter-threshold-wins vs lower-jurisdiction-
wins" question in favour of **lower-jurisdiction-wins**: precedence is by
jurisdiction level, never by threshold strictness, and §5.4 states all applicable
permits stay in the matrix. This module therefore makes the lower level's rule the
*governing* one purely by level, and does NOT compare threshold values to pick a
"stricter" winner. Where the spec is silent on what "same requirement" means at
the data level, we group by permit identity (name + code + agency, normalised)
because that is the unit the ontology calls a "requirement", and grouping this way
preserves parent requirements by construction (distinct permits never collide).

Determinism
-----------
Every collection produced here is ordered by ``(precedence_rank, rule_id)``:
precedence rank ascending (federal first), then rule_id lexicographically. The
output is identical across runs (the T00-05 reproducibility contract).

Out of scope (clean seams): dependency sequencing (T03-04), explanation-record
generation (T03-05), known-unknown detection (T03-06). This module produces the
resolved set and a structured conflict report those tickets consume.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from .engine import RuleEvaluation

# Jurisdiction precedence ladder (ontology §4.1). Index = precedence rank:
# lower index is *less* specific (federal), higher index is *more* specific
# (special) and therefore governs an overridden requirement.
JURISDICTION_PRECEDENCE: tuple[str, ...] = (
    "federal",
    "state",
    "county",
    "municipality",
    "etj",
    "utility_district",
    "drainage_district",
    "river_authority",
    "special",
)

_PRECEDENCE_INDEX: dict[str, int] = {
    level: rank for rank, level in enumerate(JURISDICTION_PRECEDENCE)
}

# Unknown / absent jurisdiction levels sort *after* every known level so a
# malformed rule never silently outranks a real parent requirement.
_UNKNOWN_RANK: int = len(JURISDICTION_PRECEDENCE)


def precedence_rank(jurisdiction_level: str | None) -> int:
    """Return the precedence rank for a *jurisdiction_level* (ontology §4.1).

    Lower rank = less specific (federal) = lower precedence for overrides. An
    unknown or missing level ranks after every known level so it can never
    silently outrank a real parent requirement.
    """
    if jurisdiction_level is None:
        return _UNKNOWN_RANK
    return _PRECEDENCE_INDEX.get(jurisdiction_level, _UNKNOWN_RANK)


def is_more_specific(level_a: str | None, level_b: str | None) -> bool:
    """Return True if *level_a* is more specific (lower) than *level_b*."""
    return precedence_rank(level_a) > precedence_rank(level_b)


@dataclass(frozen=True)
class FiredRule:
    """A fired rule paired with the conflict-relevant fields read from its dict.

    Bundles the :class:`~ipermit_engine.engine.RuleEvaluation` (so consumers can
    trace back to the evaluated trigger tree) with the rule's identity,
    jurisdiction, supersession refs, and outputs — everything resolution needs,
    extracted once so the rest of the module never re-parses the raw dict.
    """

    rule_id: str
    jurisdiction_level: str | None
    jurisdiction_id: str | None
    supersedes: tuple[str, ...]
    superseded_by: str | None
    rule: dict[str, Any]
    evaluation: RuleEvaluation | None

    @property
    def rank(self) -> int:
        """Precedence rank of this rule's jurisdiction level."""
        return precedence_rank(self.jurisdiction_level)

    @property
    def version_ref(self) -> str:
        """The ``rule_id@version`` reference this rule answers to (spec §5.4)."""
        version = self.rule.get("version")
        return f"{self.rule_id}@{version}" if version else self.rule_id


@dataclass(frozen=True)
class ConflictRecord:
    """One resolved conflict, for the explainability engine and analysts (T03-05).

    Records which fired rules contended over the same requirement, the dimension
    they contended on, which rule governs, which parent rules are preserved, and
    the precedence rationale — never discarding a parent requirement.
    """

    requirement_key: str
    kind: str
    governing_rule_id: str
    superseded_rule_ids: tuple[str, ...]
    preserved_rule_ids: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class ResolvedRequirement:
    """A single applicable requirement after conflict resolution.

    The *governing* rule is the most-specific surviving rule for this permit; the
    *contributing* rules are every other fired rule that targets the same permit
    and is preserved (parent requirements). All are kept — nothing is deleted.
    """

    requirement_key: str
    governing: FiredRule
    contributing: tuple[FiredRule, ...]


@dataclass(frozen=True)
class ResolutionResult:
    """The deterministic output of conflict resolution.

    Attributes:
        requirements: Applicable requirements, ordered by the governing rule's
            ``(precedence_rank, rule_id)``. Each preserves its parent rules.
        conflicts: The conflict report — one :class:`ConflictRecord` per
            requirement where two or more fired rules contended (override or
            supersession). Ordered to match ``requirements``.
        superseded_rule_ids: Every fired rule removed from the governing set by
            an explicit ``supersedes`` reference, recorded so the deletion is
            never silent. Sorted by rule_id.
    """

    requirements: tuple[ResolvedRequirement, ...]
    conflicts: tuple[ConflictRecord, ...]
    superseded_rule_ids: tuple[str, ...] = field(default_factory=tuple)


def resolve_conflicts(
    fired_rules: Iterable[dict[str, Any]],
    evaluations: Iterable[RuleEvaluation] | None = None,
) -> ResolutionResult:
    """Resolve conflicts among the *fired_rules* deterministically.

    Args:
        fired_rules: The rule dicts (T00-01 shape) that fired for the project.
            Each must carry ``rule_id`` and ``jurisdiction_level``; ``outputs``,
            ``supersedes``, and ``superseded_by`` are read when present.
        evaluations: Optional matching :class:`RuleEvaluation`s (from T03-02),
            joined to each rule by ``rule_id`` so the report can reference the
            evaluated trigger tree. Order-independent; extra/missing entries are
            tolerated.

    Returns:
        A :class:`ResolutionResult` with applicable requirements (parents always
        preserved), a conflict report, and the list of explicitly superseded
        rules.
    """
    eval_by_id = _index_evaluations(evaluations)
    fired = [_to_fired_rule(rule, eval_by_id) for rule in fired_rules]
    surviving, superseded_ids = _apply_supersession(fired)
    groups = _group_by_requirement(surviving)
    requirements, conflicts = _resolve_groups(groups, fired)
    return ResolutionResult(
        requirements=tuple(requirements),
        conflicts=tuple(conflicts),
        superseded_rule_ids=tuple(sorted(superseded_ids)),
    )


def _index_evaluations(
    evaluations: Iterable[RuleEvaluation] | None,
) -> dict[str, RuleEvaluation]:
    """Index evaluations by ``rule_id`` (last write wins; order-independent)."""
    if evaluations is None:
        return {}
    return {evaluation.rule_id: evaluation for evaluation in evaluations}


def _to_fired_rule(
    rule: Mapping[str, Any], eval_by_id: Mapping[str, RuleEvaluation]
) -> FiredRule:
    """Extract the conflict-relevant fields from one fired rule dict."""
    rule_id = rule["rule_id"]
    supersedes = rule.get("supersedes") or ()
    return FiredRule(
        rule_id=rule_id,
        jurisdiction_level=rule.get("jurisdiction_level"),
        jurisdiction_id=rule.get("jurisdiction_id"),
        supersedes=tuple(supersedes),
        superseded_by=rule.get("superseded_by"),
        rule=dict(rule),
        evaluation=eval_by_id.get(rule_id),
    )


def _apply_supersession(
    fired: list[FiredRule],
) -> tuple[list[FiredRule], set[str]]:
    """Remove fired rules explicitly superseded by another *fired* rule.

    A ``supersedes`` reference is honoured only when its target also fired — a
    reference to a rule that did not fire is a no-op (it never appeared, so there
    is nothing to delete). The removed rule is still reported by the caller so
    the deletion is never silent (ontology §5.3).
    """
    by_id = {fr.rule_id: fr for fr in fired}
    by_ref = {fr.version_ref: fr for fr in fired}
    superseded: set[str] = set()
    for fr in fired:
        for ref in fr.supersedes:
            target = by_ref.get(ref) or by_id.get(_strip_version(ref))
            if target is not None:
                superseded.add(target.rule_id)
    surviving = [fr for fr in fired if fr.rule_id not in superseded]
    return surviving, superseded


def _strip_version(ref: str) -> str:
    """Return the ``rule_id`` portion of a ``rule_id@version`` reference."""
    return ref.split("@", 1)[0]


def _group_by_requirement(
    fired: list[FiredRule],
) -> dict[str, list[FiredRule]]:
    """Group fired rules by the requirement (permit identity) they target.

    A rule with no declared permit outputs is given a rule-unique key so it can
    never collide with another rule — distinct/unknown requirements are always
    preserved independently (ontology §7.2 overlap union).
    """
    groups: dict[str, list[FiredRule]] = {}
    for fr in fired:
        for key in _requirement_keys(fr):
            groups.setdefault(key, []).append(fr)
    return groups


def _requirement_keys(fired: FiredRule) -> list[str]:
    """Return the requirement key(s) a fired rule contributes to.

    One key per permit in ``outputs.permits``, built from normalised
    name/code/agency so the *same* permit issued by the *same* agency collides
    across jurisdiction levels (a candidate conflict) while distinct permits do
    not. Rules with no permit outputs get a unique per-rule key.
    """
    permits = (fired.rule.get("outputs") or {}).get("permits") or []
    keys = [_permit_key(permit) for permit in permits if isinstance(permit, Mapping)]
    return keys or [f"rule:{fired.rule_id}"]


def _permit_key(permit: Mapping[str, Any]) -> str:
    """Build a stable requirement key from a permit's identity fields."""
    parts = (
        _norm(permit.get("name")),
        _norm(permit.get("code")),
        _norm(permit.get("agency")),
    )
    return "permit:" + "|".join(parts)


def _norm(value: Any) -> str:
    """Normalise an identity token for keying (case/space-insensitive)."""
    return "" if value is None else " ".join(str(value).split()).casefold()


def _resolve_groups(
    groups: Mapping[str, list[FiredRule]],
    all_fired: list[FiredRule],
) -> tuple[list[ResolvedRequirement], list[ConflictRecord]]:
    """Resolve each requirement group into a requirement + optional conflict."""
    requirements: list[ResolvedRequirement] = []
    conflicts: list[ConflictRecord] = []
    superseded_present = _superseded_in(all_fired, groups)
    for key in sorted(groups, key=lambda k: _group_sort_key(groups[k])):
        members = _ordered(groups[key])
        governing = members[0]
        contributing = tuple(members[1:])
        requirements.append(ResolvedRequirement(key, governing, contributing))
        # A conflict exists if more than one fired rule contended for this
        # requirement — either as a surviving parent (override) or as a rule
        # removed by explicit supersession (so the deletion is documented).
        if len(members) > 1 or key in superseded_present:
            conflicts.append(
                _build_conflict(key, governing, contributing, superseded_present)
            )
    return requirements, conflicts


def _superseded_in(
    all_fired: list[FiredRule], groups: Mapping[str, list[FiredRule]]
) -> dict[str, list[FiredRule]]:
    """Map each requirement key to the fired-but-superseded rules in that group.

    Lets a conflict record name the parent rules that were formally replaced by a
    cross-level supersession (so the deletion is documented, not silent).
    """
    surviving_ids = {fr.rule_id for members in groups.values() for fr in members}
    removed = [fr for fr in all_fired if fr.rule_id not in surviving_ids]
    out: dict[str, list[FiredRule]] = {}
    for fr in removed:
        for key in _requirement_keys(fr):
            out.setdefault(key, []).append(fr)
    return out


def _ordered(members: Iterable[FiredRule]) -> list[FiredRule]:
    """Sort fired rules by precedence: most specific first, then rule_id.

    Most-specific (highest rank) governs, so we sort by ``-rank`` then rule_id.
    """
    return sorted(members, key=lambda fr: (-fr.rank, fr.rule_id))


def _group_sort_key(members: list[FiredRule]) -> tuple[int, str]:
    """Deterministic ordering key for a group, by its governing rule."""
    governing = _ordered(members)[0]
    return (governing.rank, governing.rule_id)


def _build_conflict(
    key: str,
    governing: FiredRule,
    contributing: tuple[FiredRule, ...],
    superseded_present: Mapping[str, list[FiredRule]],
) -> ConflictRecord:
    """Construct the :class:`ConflictRecord` for a contended requirement."""
    superseded = superseded_present.get(key, [])
    superseded_ids = tuple(sorted(fr.rule_id for fr in superseded))
    preserved_ids = tuple(fr.rule_id for fr in contributing)
    kind = "supersession" if superseded else "override"
    return ConflictRecord(
        requirement_key=key,
        kind=kind,
        governing_rule_id=governing.rule_id,
        superseded_rule_ids=superseded_ids,
        preserved_rule_ids=preserved_ids,
        rationale=_rationale(kind, governing, contributing, superseded),
    )


def _rationale(
    kind: str,
    governing: FiredRule,
    contributing: tuple[FiredRule, ...],
    superseded: list[FiredRule],
) -> str:
    """Build the plain-language precedence rationale for a conflict record."""
    gov = f"{governing.rule_id} ({governing.jurisdiction_level})"
    if kind == "supersession":
        gone = ", ".join(sorted(fr.rule_id for fr in superseded))
        note = f"{gov} explicitly supersedes {gone} via a supersedes reference"
    else:
        parents = ", ".join(
            f"{fr.rule_id} ({fr.jurisdiction_level})" for fr in contributing
        )
        note = (
            f"{gov} is the most specific jurisdiction and governs this "
            f"requirement; parent rule(s) {parents} are preserved (override, "
            f"not deletion)"
        )
    return note + " per ontology §5.2/§5.3 precedence."
