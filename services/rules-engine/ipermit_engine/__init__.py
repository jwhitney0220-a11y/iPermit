"""iPermit deterministic rules engine (EPIC-03).

The pure, DB-free core of iPermit's declarative rules engine. Given a canonical
rule object (T00-01 shape) and a project context, it decides — deterministically
and explainably — whether each rule fires, resolves cross-jurisdiction conflicts,
sequences permit dependencies, assembles explanation records, and surfaces
uncertainty.

Public surface:

- context        — ``ProjectContext`` / ``MISSING`` (the dotted-path input namespace).
- operators      — the eleven trigger operators (T03-01 §7) and ``OperatorError``.
- triggers       — recursive trigger evaluation -> evaluated-condition tree.
- engine         — the spec §8 applicability pipeline (T03-02).
- conflict       — deterministic cross-jurisdiction conflict resolution (T03-03).
- sequencing     — permit dependency graph + staged sequencing (T03-04).
- explain        — permit-explanation record assembly (T03-05).
- known_unknowns — uncertainty / known-unknown detection (T03-06).
- simulation     — project simulation orchestration (active / historical /
  hypothetical) bundling the full pipeline (T04-01).
"""

from .conflict import (
    ConflictRecord,
    FiredRule,
    ResolutionResult,
    ResolvedRequirement,
    is_more_specific,
    precedence_rank,
    resolve_conflicts,
)
from .context import MISSING, ProjectContext
from .diff import (
    FieldChange,
    OutputImpact,
    RuleDiff,
    RulesetDiff,
    diff_rules,
    diff_rulesets,
    output_impact,
)
from .edge_cases import (
    OverlapRecord,
    ThresholdLeaf,
    boundary_probe_values,
    find_missing_inputs,
    numeric_threshold_leaves,
    overlapping_requirements,
)
from .engine import (
    DecisionStep,
    RuleEvaluation,
    evaluate_rule,
    evaluate_ruleset,
)
from .explain import build_explanation, hash_inputs
from .explain import validate as validate_explanation
from .known_unknowns import KnownUnknownItem, collect_known_unknowns
from .operators import (
    OPERATOR_KEYS,
    OperatorError,
    apply_operator,
    comparison_operators,
    is_known_operator,
)
from .sequencing import (
    Bottleneck,
    CyclicDependencyError,
    DroppedEdge,
    SequencerResult,
    Stage,
    StagePermit,
    sequence_rules,
)
from .simulation import (
    SimulationResult,
    apply_overlay,
    ruleset_content_hash,
    select_governing,
    simulate_project,
)
from .triggers import TriggerError, evaluate_trigger, matched

__all__ = [
    "MISSING",
    "OPERATOR_KEYS",
    "Bottleneck",
    "ConflictRecord",
    "CyclicDependencyError",
    "DecisionStep",
    "DroppedEdge",
    "FieldChange",
    "FiredRule",
    "KnownUnknownItem",
    "OperatorError",
    "OutputImpact",
    "OverlapRecord",
    "ProjectContext",
    "ResolutionResult",
    "ResolvedRequirement",
    "RuleDiff",
    "RuleEvaluation",
    "RulesetDiff",
    "SequencerResult",
    "SimulationResult",
    "Stage",
    "StagePermit",
    "ThresholdLeaf",
    "TriggerError",
    "apply_operator",
    "apply_overlay",
    "boundary_probe_values",
    "build_explanation",
    "collect_known_unknowns",
    "comparison_operators",
    "diff_rules",
    "diff_rulesets",
    "evaluate_rule",
    "evaluate_ruleset",
    "evaluate_trigger",
    "find_missing_inputs",
    "hash_inputs",
    "is_known_operator",
    "is_more_specific",
    "matched",
    "numeric_threshold_leaves",
    "output_impact",
    "overlapping_requirements",
    "precedence_rank",
    "resolve_conflicts",
    "ruleset_content_hash",
    "select_governing",
    "sequence_rules",
    "simulate_project",
    "validate_explanation",
]
