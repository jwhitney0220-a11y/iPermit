"""iPermit deterministic rules engine (EPIC-03) + validation/QA tooling (EPIC-04).

The pure, DB-free core of iPermit's declarative rules engine. Given a canonical
rule object (T00-01 shape) and a project context, it decides — deterministically
and explainably — whether each rule fires, resolves cross-jurisdiction conflicts,
sequences permit dependencies, assembles explanation records, and surfaces
uncertainty. EPIC-04 adds simulation, benchmark regression, edge-case analysis,
rule diffing, and QA/QC aggregation on top of the same core.

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
  hypothetical) bundling the full pipeline (T04-01). Benchmark regression
  (T04-02) lives in the ``ipermit_benchmarks`` package.
- edge_cases     — overlap / conflict / threshold / incomplete-data analysis (T04-03).
- rule_diff      — explainable diff between rule revisions (T04-04).
- qa             — QA/QC aggregation for analyst review (T04-05).
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
from .edge_cases import (
    ConflictingTriggerFinding,
    EdgeCaseReport,
    IncompleteDataFinding,
    OverlapFinding,
    ThresholdFinding,
    analyze_edge_cases,
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
from .qa import PublicationGate, QAReport, TierCounts, build_qa_report
from .rule_diff import (
    CitationChange,
    FieldChange,
    JurisdictionChange,
    OutputChange,
    RuleDiff,
    TriggerChange,
    diff_rules,
    summarize_diff,
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
    "CitationChange",
    "ConflictRecord",
    "ConflictingTriggerFinding",
    "CyclicDependencyError",
    "DecisionStep",
    "DroppedEdge",
    "EdgeCaseReport",
    "FieldChange",
    "FiredRule",
    "IncompleteDataFinding",
    "JurisdictionChange",
    "KnownUnknownItem",
    "OperatorError",
    "OutputChange",
    "OverlapFinding",
    "ProjectContext",
    "PublicationGate",
    "QAReport",
    "ResolutionResult",
    "ResolvedRequirement",
    "RuleDiff",
    "RuleEvaluation",
    "SequencerResult",
    "SimulationResult",
    "Stage",
    "StagePermit",
    "ThresholdFinding",
    "TierCounts",
    "TriggerChange",
    "TriggerError",
    "analyze_edge_cases",
    "apply_operator",
    "apply_overlay",
    "build_explanation",
    "build_qa_report",
    "collect_known_unknowns",
    "comparison_operators",
    "diff_rules",
    "evaluate_rule",
    "evaluate_ruleset",
    "evaluate_trigger",
    "hash_inputs",
    "is_known_operator",
    "is_more_specific",
    "matched",
    "precedence_rank",
    "resolve_conflicts",
    "ruleset_content_hash",
    "select_governing",
    "sequence_rules",
    "simulate_project",
    "summarize_diff",
    "validate_explanation",
]
