"""Recursive trigger evaluation for the rules engine (T03-01).

A ``triggers`` node (rule-object spec §5.5) is either a single *leaf* condition
or a logical composition (``all`` / ``any`` / ``not``). This module evaluates a
node against a :class:`~ipermit_engine.context.ProjectContext` and returns BOTH:

1. the boolean match, and
2. an *evaluated-condition tree* — a plain dict tree that mirrors the
   ``$defs/evaluatedCondition`` shapes of
   ``docs/specs/schemas/permit-explanation.schema.json`` (T00-05) so the
   explainability engine (T03-05) can drop it straight under
   ``trigger_path.root``.

Evaluated-tree shapes (canonical schema field names):

- leaf -> ``{field, operator, expected_value?, actual_value, matched}``
  (``expected_value`` is omitted for the ``exists`` operator; ``actual_value``
  is ``None`` when the field is absent — the schema permits null there).
- all  -> ``{"all": [children...], "matched": <AND of children>}``
- any  -> ``{"any": [children...], "matched": <OR of children>}``
- not  -> ``{"not": child, "matched": <NOT child.matched>}``  (JSON key is
  literally ``not``; mirrors the ``not_`` alias in packages/shared-schemas.)

Determinism:
    Children are evaluated and emitted in the exact order written in the rule.
    ``all`` / ``any`` evaluate every child (no short-circuit) so the evaluated
    tree always reports the match state of every branch — the explainer needs
    the full picture, and the engine short-circuits at the *step* level, not
    inside the trigger tree.
"""

from __future__ import annotations

from typing import Any

from .context import MISSING, ProjectContext
from .operators import VALUELESS_OPERATORS, apply_operator, is_known_operator


class TriggerError(ValueError):
    """Raised when a trigger node is malformed (unknown shape or operator)."""


# Composite keys, in the order the schema/spec lists them.
_COMPOSITE_KEYS = ("all", "any", "not")


def evaluate_trigger(node: dict[str, Any], context: ProjectContext) -> dict[str, Any]:
    """Evaluate a trigger *node* against *context*, returning its evaluated tree.

    Dispatches on node shape: a node with a ``field`` key is a leaf; a node with
    exactly one of ``all`` / ``any`` / ``not`` is that composite. The returned
    dict always carries a top-level ``matched`` boolean and matches the
    permit-explanation ``evaluatedCondition`` schema.

    Raises:
        TriggerError: if the node has neither a recognised composite key nor a
            ``field`` key, or mixes composite keys.
    """
    if "field" in node:
        return _evaluate_leaf(node, context)
    present = [key for key in _COMPOSITE_KEYS if key in node]
    if len(present) != 1:
        raise TriggerError(
            f"trigger node must be a leaf (with 'field') or exactly one of "
            f"{_COMPOSITE_KEYS}; got keys {sorted(node)}"
        )
    return _evaluate_composite(present[0], node, context)


def matched(evaluated: dict[str, Any]) -> bool:
    """Return the top-level ``matched`` flag of an evaluated-condition tree."""
    return bool(evaluated["matched"])


def _evaluate_leaf(node: dict[str, Any], context: ProjectContext) -> dict[str, Any]:
    """Evaluate a leaf condition and build its EvaluatedLeaf dict."""
    operator = node["operator"]
    if not is_known_operator(operator):
        raise TriggerError(f"unknown operator {operator!r} in leaf {node['field']!r}")

    field = node["field"]
    raw = context.get(field)
    expected = node.get("value")
    is_match = apply_operator(operator, raw, expected)

    leaf: dict[str, Any] = {
        "field": field,
        "operator": operator,
        # MISSING is serialised as null per the schema's actual_value contract.
        "actual_value": None if raw is MISSING else raw,
        "matched": is_match,
    }
    if operator not in VALUELESS_OPERATORS:
        leaf["expected_value"] = expected
    return leaf


def _evaluate_composite(
    kind: str, node: dict[str, Any], context: ProjectContext
) -> dict[str, Any]:
    """Dispatch an ``all`` / ``any`` / ``not`` composite to its builder."""
    if kind == "not":
        return _evaluate_not(node["not"], context)
    return _evaluate_all_any(kind, node[kind], context)


def _evaluate_all_any(
    kind: str, children: Any, context: ProjectContext
) -> dict[str, Any]:
    """Evaluate an ``all`` (AND) or ``any`` (OR) composite, preserving order."""
    if not isinstance(children, list) or not children:
        raise TriggerError(f"composite {kind!r} requires a non-empty list of children")
    evaluated = [evaluate_trigger(child, context) for child in children]
    flags = [matched(child) for child in evaluated]
    is_match = all(flags) if kind == "all" else any(flags)
    return {kind: evaluated, "matched": is_match}


def _evaluate_not(child: Any, context: ProjectContext) -> dict[str, Any]:
    """Evaluate a ``not`` composite (negation of a single child)."""
    if not isinstance(child, dict):
        raise TriggerError("composite 'not' requires a single child condition")
    evaluated = evaluate_trigger(child, context)
    return {"not": evaluated, "matched": not matched(evaluated)}
