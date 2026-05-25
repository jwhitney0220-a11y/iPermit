"""QA/QC aggregation layer for the analyst dashboard (T04-05).

Produces structured :class:`QAReport` objects that aggregate QA signals over a
set of fired rules and their evaluations. The report is the data contract
between the rules-engine backend and the future analyst dashboard UI (T08-02).

**UI boundary:** This module is pure data — no HTTP, no DB, no rendering.
A future frontend ticket (T08-02) will consume :class:`QAReport` to render the
analyst dashboard. Publication decisions are the analyst's responsibility and
are recorded by T08-04 tooling; this module only flags which gate items
pass or fail, NEVER makes the publish/reject decision.

**Inputs:** Plain rule dicts (T00-01 shape) and
:class:`~ipermit_engine.engine.RuleEvaluation` objects, keeping this module
DB-free and sibling-EPIC-04-module-free.

T00-09 SOP publication gate (§8.2) items checked per rule:

- ``provenance_present``  — ``provenance.source_citations`` non-empty and
  ``provenance.last_verified`` set.
- ``reviewer_present``    — ``provenance.reviewer`` is a non-empty string.
- ``confidence_tier_assigned`` — ``confidence_tier`` in {1, 2, 3}.
- ``advisory_language_present`` — at least one entry in ``advisories``.

Ordering: all collections in the report are sorted deterministically so
consumers can rely on stable ordering across runs (T00-05 §6).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .engine import RuleEvaluation
from .known_unknowns import KnownUnknownItem, collect_known_unknowns

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

# Statuses that indicate a rule is still awaiting analyst action.
_PENDING_REVIEW_STATUSES: frozenset[str] = frozenset({"draft", "published"})

# Valid confidence tier values per T00-01.
_VALID_TIERS: frozenset[int] = frozenset({1, 2, 3})


@dataclass(frozen=True)
class PublicationGate:
    """T00-09 §8.2 publication checklist result for a single rule.

    Each attribute is ``True`` when the corresponding gate item passes.
    The analyst (and T08-04 tooling) makes the final publish decision;
    this record only surfaces the pass/fail state for each item.

    Attributes:
        rule_id: The rule this gate result belongs to.
        provenance_present: ``provenance.source_citations`` is non-empty and
            ``provenance.last_verified`` is set.
        reviewer_present: ``provenance.reviewer`` is a non-empty string.
        confidence_tier_assigned: ``confidence_tier`` is one of 1, 2, 3.
        advisory_language_present: ``advisories`` list is non-empty.
    """

    rule_id: str
    provenance_present: bool
    reviewer_present: bool
    confidence_tier_assigned: bool
    advisory_language_present: bool

    @property
    def all_pass(self) -> bool:
        """``True`` when every gate item passes."""
        return (
            self.provenance_present
            and self.reviewer_present
            and self.confidence_tier_assigned
            and self.advisory_language_present
        )


@dataclass(frozen=True)
class TierCounts:
    """Counts of fired rules by confidence tier.

    Attributes:
        tier_1: Rules with ``confidence_tier == 1``.
        tier_2: Rules with ``confidence_tier == 2``.
        tier_3: Rules with ``confidence_tier == 3``.
        unassigned: Rules whose ``confidence_tier`` is absent or invalid.
    """

    tier_1: int
    tier_2: int
    tier_3: int
    unassigned: int


@dataclass(frozen=True)
class QAReport:
    """Aggregated QA signals for a set of fired rules.

    All list fields are sorted deterministically (by rule_id or natural
    ordering) so this report is reproducible across runs.

    Attributes:
        unresolved_unknowns: Deduplicated, sorted
            :class:`~ipermit_engine.known_unknowns.KnownUnknownItem` records
            collected from every fired rule via ``collect_known_unknowns``.
        tier_counts: Rule counts broken down by confidence tier.
        pending_review_rule_ids: Sorted rule ids whose status is ``draft`` or
            ``published`` (i.e. not yet ``effective`` or ``archived``).
        publication_gates: Sorted-by-rule_id
            :class:`PublicationGate` records, one per rule, indicating which
            T00-09 §8.2 checklist items pass or fail.
    """

    unresolved_unknowns: list[KnownUnknownItem]
    tier_counts: TierCounts
    pending_review_rule_ids: list[str]
    publication_gates: list[PublicationGate]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_qa_report(
    rules: list[dict[str, Any]],
    evaluations: list[RuleEvaluation],
) -> QAReport:
    """Aggregate QA signals over fired rules and their evaluations.

    Rules and evaluations are matched by ``rule_id``. Only rules that appear in
    *both* ``rules`` and ``evaluations`` (and whose evaluation fired) contribute
    to unresolved unknowns; all rules contribute to tier counts, pending-review
    detection, and publication gates.

    Args:
        rules: Canonical rule objects (T00-01 shape) as plain dicts.
        evaluations: :class:`~ipermit_engine.engine.RuleEvaluation` results
            for the same set of rules (may include non-fired results; only
            fired ones feed ``collect_known_unknowns``).

    Returns:
        A :class:`QAReport` with deterministically ordered collections.
    """
    eval_by_id = {ev.rule_id: ev for ev in evaluations}

    unknowns = _collect_all_unknowns(rules, eval_by_id)
    tier_counts = _count_tiers(rules)
    pending_ids = _pending_review_ids(rules)
    gates = _publication_gates(rules)

    return QAReport(
        unresolved_unknowns=unknowns,
        tier_counts=tier_counts,
        pending_review_rule_ids=pending_ids,
        publication_gates=gates,
    )


# ---------------------------------------------------------------------------
# Internal helpers — each stays well under 60 body lines
# ---------------------------------------------------------------------------


def _collect_all_unknowns(
    rules: list[dict[str, Any]],
    eval_by_id: dict[str, RuleEvaluation],
) -> list[KnownUnknownItem]:
    """Union of known-unknown items across all fired rules, deduplicated, sorted."""
    merged: set[KnownUnknownItem] = set()
    for rule in rules:
        rid = rule.get("rule_id", "")
        evaluation = eval_by_id.get(rid)
        if evaluation is None or not evaluation.fired:
            continue
        items = collect_known_unknowns(evaluation, rule)
        merged.update(items)
    return sorted(merged)


def _count_tiers(rules: list[dict[str, Any]]) -> TierCounts:
    """Count rules by confidence tier across the full rule list."""
    counts: dict[int | str, int] = {1: 0, 2: 0, 3: 0, "unassigned": 0}
    for rule in rules:
        tier = rule.get("confidence_tier")
        if tier in _VALID_TIERS:
            counts[tier] += 1
        else:
            counts["unassigned"] += 1
    return TierCounts(
        tier_1=counts[1],
        tier_2=counts[2],
        tier_3=counts[3],
        unassigned=counts["unassigned"],
    )


def _pending_review_ids(rules: list[dict[str, Any]]) -> list[str]:
    """Sorted rule ids whose status indicates they are pending analyst review."""
    ids = [
        rule["rule_id"]
        for rule in rules
        if rule.get("status") in _PENDING_REVIEW_STATUSES and "rule_id" in rule
    ]
    return sorted(ids)


def _publication_gates(rules: list[dict[str, Any]]) -> list[PublicationGate]:
    """Build a sorted-by-rule_id publication gate record for every rule."""
    gates = [_gate_for_rule(rule) for rule in rules if "rule_id" in rule]
    return sorted(gates, key=lambda g: g.rule_id)


def _gate_for_rule(rule: dict[str, Any]) -> PublicationGate:
    """Evaluate T00-09 §8.2 checklist items for a single rule dict."""
    return PublicationGate(
        rule_id=rule["rule_id"],
        provenance_present=_check_provenance(rule),
        reviewer_present=_check_reviewer(rule),
        confidence_tier_assigned=rule.get("confidence_tier") in _VALID_TIERS,
        advisory_language_present=bool(rule.get("advisories")),
    )


def _check_provenance(rule: dict[str, Any]) -> bool:
    """Pass when provenance has ≥1 source citation and last_verified is set."""
    prov = rule.get("provenance", {})
    citations = prov.get("source_citations", [])
    last_verified = prov.get("last_verified", "")
    return bool(citations) and bool(last_verified)


def _check_reviewer(rule: dict[str, Any]) -> bool:
    """Pass when provenance.reviewer is a non-empty string."""
    reviewer = rule.get("provenance", {}).get("reviewer", "")
    return isinstance(reviewer, str) and bool(reviewer.strip())
