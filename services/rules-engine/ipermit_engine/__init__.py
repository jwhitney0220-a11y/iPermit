"""iPermit deterministic rules engine (EPIC-03 core).

The pure, DB-free core of iPermit's declarative rules engine. Given a canonical
rule object (T00-01 shape) and a project context, it decides — deterministically
and explainably — whether the rule fires, and emits an evaluated-condition tree
the explainability engine (T03-05) consumes directly.

Public surface:

- context     — ``ProjectContext`` / ``MISSING`` (the dotted-path input namespace).
- operators   — the eleven trigger operators (T03-01 §7) and ``OperatorError``.
- triggers    — recursive trigger evaluation -> evaluated-condition tree.
- engine      — the spec §8 applicability pipeline (T03-02).

Deferred to later EPIC-03 tickets (clean seams here, not implemented): conflict
resolution (T03-03), dependency sequencing (T03-04), full permit-explanation
records (T03-05), known-unknown detection (T03-06).
"""

from .context import MISSING, ProjectContext
from .engine import (
    DecisionStep,
    RuleEvaluation,
    evaluate_rule,
    evaluate_ruleset,
)
from .operators import (
    OPERATOR_KEYS,
    OperatorError,
    apply_operator,
    comparison_operators,
    is_known_operator,
)
from .triggers import TriggerError, evaluate_trigger, matched

__all__ = [
    "MISSING",
    "OPERATOR_KEYS",
    "DecisionStep",
    "OperatorError",
    "ProjectContext",
    "RuleEvaluation",
    "TriggerError",
    "apply_operator",
    "comparison_operators",
    "evaluate_rule",
    "evaluate_ruleset",
    "evaluate_trigger",
    "is_known_operator",
    "matched",
]
