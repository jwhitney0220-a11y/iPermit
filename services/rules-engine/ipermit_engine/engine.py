"""Applicability pipeline and rule evaluation engine (T03-02).

Implements the rule-object spec §8 evaluation order for a single rule against a
:class:`~ipermit_engine.context.ProjectContext`, short-circuiting and recording
which step decided the outcome. The engine is **pure** and DB-free: every input
is passed in, and it contains NO hardcoded permit logic — everything flows from
the declarative rule object.

Evaluation order (spec §8):

1. ``jurisdiction``      — ``rule.jurisdiction_id`` must be one of the project's
   applicable jurisdiction ids (supplied by the caller from GIS/intake).
2. ``temporal_validity`` — **caller boundary.** The engine evaluates an
   *already-effective* ruleset; temporal selection is owned by T02-04
   (``ipermit_regulatory.temporal``) and is NOT re-implemented here. The engine
   assumes every rule it receives is temporally valid for the evaluation date.
3. ``project_type``      — ``rule.applicable_project_types`` must intersect the
   project's type(s).
4. ``trigger_conditions``— evaluate ``rule.triggers`` (T03-01 trigger evaluator).
5. ``spatial_overlays``  — ``geometry.*`` trigger fields are evaluated as
   ordinary context values inside step 4; real GIS overlay detection is
   EPIC-05. No extra handling here.
6. ``dependencies``      — **deferred to T03-04.** Sequencing / prerequisites are
   not resolved by this engine; this is a clean seam for that ticket.

Explicitly deferred (clean seams, not implemented here): conflict resolution
between overlapping rules (T03-03), dependency sequencing (T03-04), full
permit-explanation record generation (T03-05 — this engine produces only the
evaluated trigger tree it will consume), known-unknown detection (T03-06).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .context import ProjectContext
from .triggers import evaluate_trigger, matched


class DecisionStep(StrEnum):
    """The evaluation step that decided a rule's outcome (spec §8).

    A ``str`` enum so the value serialises directly and compares to the step
    names used by the explainability ``evaluation_trace`` (T00-05 §5.11).
    ``FIRED`` is the terminal value meaning the rule survived every step.
    """

    JURISDICTION = "jurisdiction"
    PROJECT_TYPE = "project_type"
    TRIGGERS = "triggers"
    FIRED = "fired"


@dataclass(frozen=True)
class RuleEvaluation:
    """The outcome of evaluating one rule against a project.

    Attributes:
        rule_id: The evaluated rule's id (for deterministic ordering / tracing).
        fired: True only when the rule survived every applicability step.
        decided_by: The :class:`DecisionStep` that determined the outcome —
            the step that eliminated the rule, or ``FIRED`` if it survived.
        evaluated_triggers: The evaluated-condition tree (T00-05 shape) when
            evaluation reached step 4; ``None`` when short-circuited earlier.
        detail: A short, human-readable note on the deciding step.
    """

    rule_id: str
    fired: bool
    decided_by: DecisionStep
    evaluated_triggers: dict[str, Any] | None
    detail: str


def evaluate_rule(
    rule: dict[str, Any],
    context: ProjectContext,
    applicable_jurisdiction_ids: Iterable[str],
    project_types: Iterable[str],
) -> RuleEvaluation:
    """Evaluate a single declarative *rule* against a project context.

    Runs the spec §8 pipeline in order, short-circuiting at the first failing
    step. Temporal validity (step 2) is the caller's responsibility (see module
    docstring); this function assumes *rule* is already effective.

    Args:
        rule: A canonical rule object (T00-01 shape) as a plain dict.
        context: The project's evaluation inputs.
        applicable_jurisdiction_ids: Jurisdiction ids that apply to the project
            (from GIS/intake). The rule fires past step 1 only if its
            ``jurisdiction_id`` is among these.
        project_types: The project's type token(s).

    Returns:
        A :class:`RuleEvaluation` recording fired/decided_by/evaluated tree.
    """
    rule_id = rule["rule_id"]

    jurisdiction_id = rule["jurisdiction_id"]
    if jurisdiction_id not in set(applicable_jurisdiction_ids):
        return RuleEvaluation(
            rule_id=rule_id,
            fired=False,
            decided_by=DecisionStep.JURISDICTION,
            evaluated_triggers=None,
            detail=f"jurisdiction {jurisdiction_id!r} not in project chain",
        )

    rule_types = set(rule.get("applicable_project_types", ()))
    if not rule_types & set(project_types):
        return RuleEvaluation(
            rule_id=rule_id,
            fired=False,
            decided_by=DecisionStep.PROJECT_TYPE,
            evaluated_triggers=None,
            detail="no project type in applicable_project_types",
        )

    return _evaluate_triggers_step(rule_id, rule["triggers"], context)


def _evaluate_triggers_step(
    rule_id: str, triggers: dict[str, Any], context: ProjectContext
) -> RuleEvaluation:
    """Run step 4 (trigger conditions) and build the resulting RuleEvaluation.

    Spatial overlays (step 5) require no special handling: ``geometry.*`` fields
    are read as ordinary context values by the trigger evaluator. Dependencies
    (step 6) are deferred to T03-04 and never block firing here.
    """
    evaluated = evaluate_trigger(triggers, context)
    fired = matched(evaluated)
    if not fired:
        return RuleEvaluation(
            rule_id=rule_id,
            fired=False,
            decided_by=DecisionStep.TRIGGERS,
            evaluated_triggers=evaluated,
            detail="trigger conditions not satisfied",
        )
    return RuleEvaluation(
        rule_id=rule_id,
        fired=True,
        decided_by=DecisionStep.FIRED,
        evaluated_triggers=evaluated,
        detail="all applicability steps passed",
    )


def evaluate_ruleset(
    rules: Iterable[dict[str, Any]],
    context: ProjectContext,
    applicable_jurisdiction_ids: Iterable[str],
    project_types: Iterable[str],
) -> list[RuleEvaluation]:
    """Evaluate every rule in *rules* and return the FIRED ones, sorted.

    Each rule is evaluated independently (conflict resolution between fired
    rules is deferred to T03-03). Only rules that fired are returned, ordered
    deterministically by ``rule_id`` so output is stable across runs (the
    explainability reproducibility contract, T00-05 §6).

    The jurisdiction/project-type criteria are materialised once and reused so
    the result does not depend on the iterables being re-iterable.
    """
    jurisdictions = set(applicable_jurisdiction_ids)
    types = set(project_types)
    fired = [
        result
        for rule in rules
        if (result := evaluate_rule(rule, context, jurisdictions, types)).fired
    ]
    return sorted(fired, key=lambda result: result.rule_id)
