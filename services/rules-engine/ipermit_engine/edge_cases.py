"""Edge-case testing framework for the rules engine (T04-03).

Detects and exercises four categories of edge-case engine behaviour for a
given ruleset and project context, without any DB access or hardcoded permit
logic. All analysis is driven by the rule data and the context supplied by the
caller.

Four edge categories:
  - ``overlapping_jurisdictions`` — multiple rules from different jurisdiction
    levels that fired for the same requirement; reports how conflict resolution
    settled each overlap.
  - ``conflicting_triggers``     — two rules whose triggers reference the same
    field with logically contradictory conditions (only one can fire for any
    single value); reported as a structural finding even before evaluation.
  - ``ambiguous_thresholds``     — a project context value is exactly on a
    numeric threshold boundary in a ``>`` or ``<`` comparison (exclusive
    boundary), making the result sensitive to tiny data changes.
  - ``incomplete_data``          — trigger fields that were MISSING from the
    context; reports which rules were affected and which fields were absent.

Usage::

    report = analyze_edge_cases(rules, context, jurisdiction_ids, project_types)
    for finding in report.overlapping_jurisdictions:
        print(finding.requirement_key, finding.resolution_summary)
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .conflict import resolve_conflicts
from .context import MISSING, ProjectContext
from .engine import RuleEvaluation, evaluate_rule

# ---------------------------------------------------------------------------
# Finding dataclasses — one per edge-case category
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OverlapFinding:
    """A requirement served by rules from two or more jurisdiction levels.

    Attributes:
        requirement_key: The permit-identity key the conflict resolver used.
        governing_rule_id: The rule that governs after resolution.
        preserved_rule_ids: Parent rules preserved alongside the governing one.
        resolution_summary: Plain-language summary from the conflict record.
    """

    requirement_key: str
    governing_rule_id: str
    preserved_rule_ids: tuple[str, ...]
    resolution_summary: str


@dataclass(frozen=True)
class ConflictingTriggerFinding:
    """Two rules whose triggers are structurally contradictory on one field.

    Both rules reference *field* with comparison operators whose value ranges
    cannot both be satisfied simultaneously: e.g. rule A uses ``>= 10`` and
    rule B uses ``< 10`` — no single project value satisfies both at once.

    Attributes:
        rule_id_a: First rule in the pair (lexicographically earlier).
        rule_id_b: Second rule in the pair.
        field: The shared trigger field.
        operator_a: Operator used by rule_id_a.
        value_a: Threshold value in rule_id_a's trigger.
        operator_b: Operator used by rule_id_b.
        value_b: Threshold value in rule_id_b's trigger.
    """

    rule_id_a: str
    rule_id_b: str
    field: str
    operator_a: str
    value_a: Any
    operator_b: str
    value_b: Any


@dataclass(frozen=True)
class ThresholdFinding:
    """A context value sitting exactly on an exclusive (``>`` / ``<``) boundary.

    When the project value equals the rule's threshold in a strict comparison,
    the outcome flips with the smallest possible data change — a boundary
    case worth flagging for analyst review.

    Attributes:
        rule_id: The rule whose trigger contains the boundary.
        field: The trigger field whose value is on the boundary.
        operator: The strict comparison operator (``>`` or ``<``).
        threshold: The rule's threshold value.
        actual_value: The context value that equals the threshold.
    """

    rule_id: str
    field: str
    operator: str
    threshold: Any
    actual_value: Any


@dataclass(frozen=True)
class IncompleteDataFinding:
    """A rule whose evaluation was affected by one or more MISSING fields.

    Attributes:
        rule_id: The rule with missing trigger inputs.
        missing_fields: Fields referenced in triggers but absent from context.
    """

    rule_id: str
    missing_fields: tuple[str, ...]


# ---------------------------------------------------------------------------
# Top-level report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EdgeCaseReport:
    """The structured output of :func:`analyze_edge_cases`.

    Each list is deterministically ordered (by rule_id / requirement_key).
    An empty list in a category means no findings in that category.

    Attributes:
        overlapping_jurisdictions: Requirements with multi-jurisdiction overlap.
        conflicting_triggers: Structurally contradictory trigger pairs.
        ambiguous_thresholds: Context values on exclusive threshold boundaries.
        incomplete_data: Rules with MISSING trigger inputs.
    """

    overlapping_jurisdictions: tuple[OverlapFinding, ...]
    conflicting_triggers: tuple[ConflictingTriggerFinding, ...]
    ambiguous_thresholds: tuple[ThresholdFinding, ...]
    incomplete_data: tuple[IncompleteDataFinding, ...]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def analyze_edge_cases(
    rules: Iterable[dict[str, Any]],
    context: ProjectContext,
    applicable_jurisdiction_ids: Iterable[str],
    project_types: Iterable[str],
) -> EdgeCaseReport:
    """Run all four edge-case analyses and return a structured report.

    Args:
        rules: Candidate rule dicts (T00-01 shape). Consumed once; need not
            be re-iterable — the function materialises the list internally.
        context: The project's evaluation inputs.
        applicable_jurisdiction_ids: Jurisdiction ids that apply to the project.
        project_types: The project's type token(s).

    Returns:
        An :class:`EdgeCaseReport` with findings per category, each ordered
        deterministically so results are stable across runs.
    """
    rules_list = list(rules)
    jids = list(applicable_jurisdiction_ids)
    ptypes = list(project_types)

    evaluations = _evaluate_all(rules_list, context, jids, ptypes)
    fired_rules = [r for r in rules_list if _eval_fired(evaluations, r["rule_id"])]

    return EdgeCaseReport(
        overlapping_jurisdictions=_find_overlaps(fired_rules, evaluations),
        conflicting_triggers=_find_conflicting_triggers(rules_list),
        ambiguous_thresholds=_find_ambiguous_thresholds(rules_list, context),
        incomplete_data=_find_incomplete_data(rules_list, context, jids, ptypes),
    )


# ---------------------------------------------------------------------------
# Category 1: overlapping jurisdictions
# ---------------------------------------------------------------------------

# An overlap needs at least two fired rules to compare.
_MIN_RULES_FOR_OVERLAP = 2


def _find_overlaps(
    fired_rules: list[dict[str, Any]],
    evaluations: dict[str, RuleEvaluation],
) -> tuple[OverlapFinding, ...]:
    """Detect requirements served by more than one jurisdiction level."""
    if len(fired_rules) < _MIN_RULES_FOR_OVERLAP:
        return ()
    evals = list(evaluations.values())
    result = resolve_conflicts(fired_rules, evals)
    findings: list[OverlapFinding] = []
    for conflict in result.conflicts:
        findings.append(
            OverlapFinding(
                requirement_key=conflict.requirement_key,
                governing_rule_id=conflict.governing_rule_id,
                preserved_rule_ids=conflict.preserved_rule_ids,
                resolution_summary=conflict.rationale,
            )
        )
    return tuple(sorted(findings, key=lambda f: f.requirement_key))


# ---------------------------------------------------------------------------
# Category 2: conflicting triggers
# ---------------------------------------------------------------------------

# Operators that are mutually exclusive on the same field when value ranges do
# not overlap. We check numeric/ordered operators in pairs.
_ORDERED_OPS = frozenset({">", ">=", "<", "<=", "="})


def _find_conflicting_triggers(
    rules: list[dict[str, Any]],
) -> tuple[ConflictingTriggerFinding, ...]:
    """Detect rule pairs whose triggers are structurally contradictory."""
    # Collect (rule_id, field, op, value) for every leaf with an ordered op.
    leaves = _collect_ordered_leaves(rules)
    findings: list[ConflictingTriggerFinding] = []
    # Compare every pair of leaves that share the same field.
    seen: set[tuple[str, str]] = set()
    for i, (rid_a, fld_a, op_a, val_a) in enumerate(leaves):
        for rid_b, fld_b, op_b, val_b in leaves[i + 1 :]:
            if fld_a != fld_b or rid_a == rid_b:
                continue
            pair_key = (min(rid_a, rid_b), max(rid_a, rid_b), fld_a, op_a, op_b)
            if pair_key in seen:
                continue
            if _are_contradictory(op_a, val_a, op_b, val_b):
                seen.add(pair_key)
                a, b = (rid_a, op_a, val_a), (rid_b, op_b, val_b)
                if rid_a > rid_b:
                    a, b = b, a
                findings.append(
                    ConflictingTriggerFinding(
                        rule_id_a=a[0],
                        rule_id_b=b[0],
                        field=fld_a,
                        operator_a=a[1],
                        value_a=a[2],
                        operator_b=b[1],
                        value_b=b[2],
                    )
                )
    return tuple(sorted(findings, key=lambda f: (f.rule_id_a, f.rule_id_b, f.field)))


def _collect_ordered_leaves(
    rules: list[dict[str, Any]],
) -> list[tuple[str, str, str, Any]]:
    """Return (rule_id, field, operator, value) for ordered-op trigger leaves."""
    result: list[tuple[str, str, str, Any]] = []
    for rule in rules:
        rid = rule.get("rule_id", "")
        _walk_trigger_leaves(rule.get("triggers", {}), rid, result)
    return result


def _walk_trigger_leaves(
    node: Any,
    rule_id: str,
    out: list[tuple[str, str, str, Any]],
) -> None:
    """Recursively collect ordered-op leaves from a trigger node."""
    if not isinstance(node, dict):
        return
    if "field" in node:
        op = node.get("operator", "")
        if op in _ORDERED_OPS:
            out.append((rule_id, node["field"], op, node.get("value")))
        return
    for key in ("all", "any"):
        if key in node:
            for child in node[key]:
                _walk_trigger_leaves(child, rule_id, out)
    if "not" in node:
        _walk_trigger_leaves(node["not"], rule_id, out)


def _are_contradictory(op_a: str, val_a: Any, op_b: str, val_b: Any) -> bool:
    """Return True when the two conditions cannot both be True simultaneously."""
    try:
        return _ranges_incompatible(op_a, val_a, op_b, val_b)
    except (TypeError, ValueError):
        return False


def _ranges_incompatible(op_a: str, val_a: Any, op_b: str, val_b: Any) -> bool:
    """Check logical incompatibility of two ordered-op conditions on one field."""
    # Build interval-style bounds: (low, low_inclusive, high, high_inclusive)
    # where None means unbounded.
    lo_a, li_a, hi_a, hi_ia = _op_bounds(op_a, val_a)
    lo_b, li_b, hi_b, hi_ib = _op_bounds(op_b, val_b)
    # Intersection is empty when high of one < low of other (or == with exclusion).
    effective_lo = _max_bound(lo_a, li_a, lo_b, li_b)
    effective_hi = _min_bound(hi_a, hi_ia, hi_b, hi_ib)
    return _interval_empty(effective_lo, effective_hi)


def _op_bounds(op: str, val: Any) -> tuple[Any, bool, Any, bool]:
    """Return (lo, lo_incl, hi, hi_incl) for a single ordered comparison."""
    if op == ">":
        return (val, False, None, True)
    if op == ">=":
        return (val, True, None, True)
    if op == "<":
        return (None, True, val, False)
    if op == "<=":
        return (None, True, val, True)
    # "=" — exact point
    return (val, True, val, True)


def _max_bound(lo_a: Any, li_a: bool, lo_b: Any, li_b: bool) -> tuple[Any, bool]:
    """Return the tighter lower bound of two lower bounds."""
    if lo_a is None:
        return (lo_b, li_b)
    if lo_b is None:
        return (lo_a, li_a)
    if lo_a > lo_b:
        return (lo_a, li_a)
    if lo_b > lo_a:
        return (lo_b, li_b)
    # Equal values — inclusive only if BOTH are inclusive.
    return (lo_a, li_a and li_b)


def _min_bound(hi_a: Any, hi_ia: bool, hi_b: Any, hi_ib: bool) -> tuple[Any, bool]:
    """Return the tighter upper bound of two upper bounds."""
    if hi_a is None:
        return (hi_b, hi_ib)
    if hi_b is None:
        return (hi_a, hi_ia)
    if hi_a < hi_b:
        return (hi_a, hi_ia)
    if hi_b < hi_a:
        return (hi_b, hi_ib)
    return (hi_a, hi_ia and hi_ib)


def _interval_empty(lo: tuple[Any, bool], hi: tuple[Any, bool]) -> bool:
    """Return True when the interval [lo, hi] is empty."""
    lo_val, lo_incl = lo
    hi_val, hi_incl = hi
    if lo_val is None or hi_val is None:
        return False
    if lo_val > hi_val:
        return True
    return lo_val == hi_val and not (lo_incl and hi_incl)


# ---------------------------------------------------------------------------
# Category 3: ambiguous thresholds
# ---------------------------------------------------------------------------

_STRICT_OPS = frozenset({">", "<"})


def _find_ambiguous_thresholds(
    rules: list[dict[str, Any]],
    context: ProjectContext,
) -> tuple[ThresholdFinding, ...]:
    """Flag fields where the context value exactly equals a strict boundary."""
    findings: list[ThresholdFinding] = []
    for rule in rules:
        rid = rule.get("rule_id", "")
        _check_threshold_leaves(rule.get("triggers", {}), rid, context, findings)
    findings.sort(key=lambda f: (f.rule_id, f.field, f.operator))
    return tuple(findings)


def _check_threshold_leaves(
    node: Any,
    rule_id: str,
    context: ProjectContext,
    out: list[ThresholdFinding],
) -> None:
    """Recursively find strict-op leaves where context value == threshold."""
    if not isinstance(node, dict):
        return
    if "field" in node:
        op = node.get("operator", "")
        if op in _STRICT_OPS:
            actual = context.get(node["field"])
            threshold = node.get("value")
            if actual is not MISSING and actual is not None:
                try:
                    if actual == threshold:
                        out.append(
                            ThresholdFinding(
                                rule_id=rule_id,
                                field=node["field"],
                                operator=op,
                                threshold=threshold,
                                actual_value=actual,
                            )
                        )
                except (TypeError, ValueError):
                    pass
        return
    for key in ("all", "any"):
        if key in node:
            for child in node[key]:
                _check_threshold_leaves(child, rule_id, context, out)
    if "not" in node:
        _check_threshold_leaves(node["not"], rule_id, context, out)


# ---------------------------------------------------------------------------
# Category 4: incomplete project data
# ---------------------------------------------------------------------------


def _find_incomplete_data(
    rules: list[dict[str, Any]],
    context: ProjectContext,
    jids: list[str],
    ptypes: list[str],
) -> tuple[IncompleteDataFinding, ...]:
    """Report rules that referenced MISSING context fields during evaluation."""
    findings: list[IncompleteDataFinding] = []
    for rule in rules:
        rid = rule.get("rule_id", "")
        missing = _collect_missing_fields(rule.get("triggers", {}), context)
        if missing:
            findings.append(
                IncompleteDataFinding(
                    rule_id=rid,
                    missing_fields=tuple(sorted(missing)),
                )
            )
    findings.sort(key=lambda f: f.rule_id)
    return tuple(findings)


def _collect_missing_fields(node: Any, context: ProjectContext) -> list[str]:
    """Return field paths referenced in *node* whose context value is MISSING."""
    missing: list[str] = []
    _walk_missing(node, context, missing)
    return missing


def _walk_missing(node: Any, context: ProjectContext, out: list[str]) -> None:
    """Recursively walk trigger nodes collecting MISSING field references."""
    if not isinstance(node, dict):
        return
    if "field" in node:
        path = node["field"]
        if context.get(path) is MISSING:
            out.append(path)
        return
    for key in ("all", "any"):
        if key in node:
            for child in node[key]:
                _walk_missing(child, context, out)
    if "not" in node:
        _walk_missing(node["not"], context, out)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _evaluate_all(
    rules: list[dict[str, Any]],
    context: ProjectContext,
    jids: list[str],
    ptypes: list[str],
) -> dict[str, RuleEvaluation]:
    """Evaluate every rule and index the results by rule_id."""
    out: dict[str, RuleEvaluation] = {}
    for rule in rules:
        ev = evaluate_rule(rule, context, jids, ptypes)
        out[ev.rule_id] = ev
    return out


def _eval_fired(evaluations: dict[str, RuleEvaluation], rule_id: str) -> bool:
    """Return True if the rule with *rule_id* fired in the evaluation map."""
    ev = evaluations.get(rule_id)
    return ev is not None and ev.fired
