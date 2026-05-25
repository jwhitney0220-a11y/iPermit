"""Permit dependency sequencer (T03-04).

Converts a set of fired rule objects into an ordered, parallelisable workflow:
an ordered list of stages (each containing rule_ids that can be pursued
concurrently), critical-path annotation, and bottleneck flagging.

Implements the algorithms described in docs/specs/dependency-sequencing.md
(T00-04) sections 7-9 using Kahn's layered topological sort and
longest-path-in-DAG for critical-path analysis.

Public API consumed by tests and downstream engines (T07-01, T06-02):

    sequence_rules(fired_rules, bottleneck_threshold_days) -> SequencerResult

Input shape: each element of ``fired_rules`` is a plain rule dict (T00-01 §5.7)
that carries an optional ``sequencing`` sub-object with ``prerequisites``,
``parallel_with``, and ``typical_lead_time_days``.

No hardcoded permit logic. No DB access. Pure Python.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

#: Default bottleneck threshold (spec §9.2).
DEFAULT_BOTTLENECK_DAYS: int = 120

# ---------------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StagePermit:
    """One permit within a stage, with critical-path annotation."""

    rule_id: str
    on_critical_path: bool


@dataclass(frozen=True)
class Stage:
    """One ordered stage of the workflow.  All permits in a stage are concurrent."""

    stage_index: int
    permits: tuple[StagePermit, ...]


@dataclass(frozen=True)
class Bottleneck:
    """A permit on the critical path that exceeds the bottleneck threshold.

    Per spec §9.4.
    """

    rule_id: str
    typical_lead_time_days: int
    cross_agency_response: bool
    predecessors: tuple[str, ...]
    successors: tuple[str, ...]


@dataclass
class DroppedEdge:
    """A prerequisite edge skipped because the predecessor did not fire (spec §8)."""

    predecessor_rule_id: str
    successor_rule_id: str
    reason: str = "prerequisite_not_triggered"


@dataclass
class SequencerResult:
    """Complete output of the sequencing algorithm (spec §11)."""

    stages: list[Stage]
    critical_path: list[str]
    critical_path_total_days: int
    bottlenecks: list[Bottleneck]
    parallel_with_hints: list[tuple[str, str]]
    dropped_edges: list[DroppedEdge]


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class CyclicDependencyError(ValueError):
    """Raised when the dependency graph contains a cycle (spec §6.1).

    A cycle is a publication-blocking error.  The message lists every cycle as a
    sequence of rule_ids so the analyst can identify the offending prerequisite.
    """


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def _build_graph(
    fired_rules: list[dict[str, Any]],
    fired_ids: set[str],
) -> tuple[
    dict[str, list[str]],  # adjacency: predecessor -> [successors]
    dict[str, int],  # in-degree for each node
    list[DroppedEdge],
    list[tuple[str, str]],  # parallel_with hint pairs
]:
    """Build the prerequisite_of directed graph from fired rules.

    Edges whose source did not fire are silently dropped (spec §8).
    Returns adjacency list, in-degree map, dropped edges, parallel hints.
    """
    adj: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = dict.fromkeys(fired_ids, 0)
    dropped: list[DroppedEdge] = []
    hints: list[tuple[str, str]] = []

    for rule in fired_rules:
        rule_id = rule["rule_id"]
        seq = rule.get("sequencing") or {}
        for prereq in seq.get("prerequisites") or []:
            if prereq not in fired_ids:
                dropped.append(DroppedEdge(prereq, rule_id))
                continue
            adj[prereq].append(rule_id)
            in_degree[rule_id] = in_degree.get(rule_id, 0) + 1

    # Collect parallel_with hints (deduplicated, canonical order).
    seen_hints: set[frozenset[str]] = set()
    for rule in fired_rules:
        rule_id = rule["rule_id"]
        seq = rule.get("sequencing") or {}
        for other in seq.get("parallel_with") or []:
            if other not in fired_ids:
                continue
            key = frozenset({rule_id, other})
            if key not in seen_hints:
                seen_hints.add(key)
                hints.append((min(rule_id, other), max(rule_id, other)))

    return dict(adj), in_degree, dropped, sorted(hints)


# ---------------------------------------------------------------------------
# Cycle detection (Kahn + remainder check)
# ---------------------------------------------------------------------------


def _detect_cycle(
    adj: dict[str, list[str]],
    in_degree: dict[str, int],
    fired_ids: set[str],
) -> None:
    """Raise CyclicDependencyError if the graph is not a DAG (spec §6.1).

    Uses Kahn's algorithm; any node not processed is part of a cycle.
    """
    remaining = dict(in_degree)
    queue = sorted(n for n, d in remaining.items() if d == 0)
    processed = 0

    while queue:
        node = queue.pop(0)
        processed += 1
        for successor in sorted(adj.get(node, [])):
            remaining[successor] -= 1
            if remaining[successor] == 0:
                queue.append(successor)
        queue.sort()

    if processed < len(fired_ids):
        cyclic = sorted(n for n, d in remaining.items() if d > 0)
        raise CyclicDependencyError(
            f"Dependency cycle detected among rules: {cyclic!r}. "
            "This is a publication-blocking error. Remove the circular "
            "prerequisite reference(s) from the rules listed above."
        )


# ---------------------------------------------------------------------------
# Topological sort into stages (Kahn's layered variant, spec §7)
# ---------------------------------------------------------------------------


def _topological_stages(
    adj: dict[str, list[str]],
    in_degree: dict[str, int],
) -> list[list[str]]:
    """Return an ordered list of stages via Kahn's layered topological sort.

    Each inner list is a stage; members within a stage are sorted by rule_id
    for deterministic output (spec §7 tie-breaking).
    """
    remaining = dict(in_degree)
    stages: list[list[str]] = []
    current = sorted(n for n, d in remaining.items() if d == 0)

    while current:
        stages.append(current)
        next_stage_candidates: set[str] = set()
        for node in current:
            for successor in adj.get(node, []):
                remaining[successor] -= 1
                if remaining[successor] == 0:
                    next_stage_candidates.add(successor)
        current = sorted(next_stage_candidates)

    return stages


# ---------------------------------------------------------------------------
# Critical-path analysis (longest path by lead-time weight, spec §9.1)
# ---------------------------------------------------------------------------


def _compute_critical_path(
    fired_rules: list[dict[str, Any]],
    adj: dict[str, list[str]],
    stages: list[list[str]],
    fired_ids: set[str],
) -> tuple[set[str], int, dict[str, int]]:
    """Compute the critical path using longest-path-in-DAG (spec §9).

    Returns:
        critical_ids: set of rule_ids on the (longest) critical path.
        total_days: sum of typical_lead_time_days along the path.
        dist: per-node longest-path distance from any stage-0 node.
    """
    lead_time: dict[str, int] = {}
    for rule in fired_rules:
        seq = rule.get("sequencing") or {}
        lead_time[rule["rule_id"]] = seq.get("typical_lead_time_days") or 0

    # Process nodes in topological order (stages are already in order).
    topo_order = [n for stage in stages for n in stage]

    # dist[n] = longest cumulative lead time from any start to END of n.
    dist: dict[str, int] = {n: lead_time[n] for n in topo_order}
    predecessor_on_path: dict[str, str | None] = dict.fromkeys(topo_order, None)

    for node in topo_order:
        for successor in adj.get(node, []):
            candidate = dist[node] + lead_time[successor]
            if candidate > dist[successor]:
                dist[successor] = candidate
                predecessor_on_path[successor] = node

    total_days = max(dist.values(), default=0)

    # Reconstruct all nodes on ANY critical path.
    critical_ids: set[str] = set()
    terminals = [n for n in topo_order if dist[n] == total_days]
    for terminal in terminals:
        node: str | None = terminal
        while node is not None:
            critical_ids.add(node)
            node = predecessor_on_path.get(node)

    return critical_ids, total_days, dist


# ---------------------------------------------------------------------------
# Bottleneck flagging (spec sections 9.2-9.3)
# ---------------------------------------------------------------------------


def _collect_bottlenecks(
    fired_rules: list[dict[str, Any]],
    adj: dict[str, list[str]],
    critical_ids: set[str],
    threshold: int,
) -> list[Bottleneck]:
    """Return bottleneck records for critical-path nodes above threshold.

    A node is a bottleneck when it is on the critical path AND its
    typical_lead_time_days >= threshold (spec §9.2).

    Cross-agency edges (different source_agency on predecessor vs. node) are
    classified as depends_on_response_from and tagged cross_agency_response
    (spec §5.3, §9.3).
    """
    agency: dict[str, str] = {
        r["rule_id"]: r.get("source_agency", "") for r in fired_rules
    }
    lead_time: dict[str, int] = {}
    for rule in fired_rules:
        seq = rule.get("sequencing") or {}
        lead_time[rule["rule_id"]] = seq.get("typical_lead_time_days") or 0

    # Build reverse adjacency for predecessor lookup.
    predecessors_map: dict[str, list[str]] = defaultdict(list)
    for pred, successors in adj.items():
        for succ in successors:
            predecessors_map[succ].append(pred)

    bottlenecks: list[Bottleneck] = []
    for rule_id in sorted(critical_ids):
        if lead_time.get(rule_id, 0) < threshold:
            continue
        preds = sorted(predecessors_map.get(rule_id, []))
        succs = sorted(adj.get(rule_id, []))
        cross = any(agency.get(p, "") != agency.get(rule_id, "") for p in preds)
        bottlenecks.append(
            Bottleneck(
                rule_id=rule_id,
                typical_lead_time_days=lead_time[rule_id],
                cross_agency_response=cross,
                predecessors=tuple(preds),
                successors=tuple(succs),
            )
        )
    return bottlenecks


# ---------------------------------------------------------------------------
# Main public entry point
# ---------------------------------------------------------------------------


def sequence_rules(
    fired_rules: list[dict[str, Any]],
    bottleneck_threshold_days: int = DEFAULT_BOTTLENECK_DAYS,
) -> SequencerResult:
    """Sequence fired rules into ordered, parallelisable workflow stages.

    Args:
        fired_rules: Rule dicts (T00-01 shape) for every rule that fired.
            Each may carry a ``sequencing`` sub-object (§5.7).
        bottleneck_threshold_days: A permit on the critical path with
            ``typical_lead_time_days >= threshold`` is flagged as a bottleneck
            (spec §9.2). Defaults to 120 days.

    Returns:
        A :class:`SequencerResult` containing stages, critical path,
        bottlenecks, parallel hints, and dropped edges.

    Raises:
        CyclicDependencyError: if the prerequisite graph contains a cycle
            (spec §6.1 — publication-blocking error).
    """
    fired_ids: set[str] = {r["rule_id"] for r in fired_rules}

    adj, in_degree, dropped, hints = _build_graph(fired_rules, fired_ids)
    _detect_cycle(adj, in_degree, fired_ids)

    raw_stages = _topological_stages(adj, in_degree)
    critical_ids, total_days, _ = _compute_critical_path(
        fired_rules, adj, raw_stages, fired_ids
    )
    bottlenecks = _collect_bottlenecks(
        fired_rules, adj, critical_ids, bottleneck_threshold_days
    )

    stages = [
        Stage(
            stage_index=idx,
            permits=tuple(
                StagePermit(rule_id=rid, on_critical_path=rid in critical_ids)
                for rid in stage_ids
            ),
        )
        for idx, stage_ids in enumerate(raw_stages)
    ]
    critical_path = _ordered_critical_path(raw_stages, critical_ids, adj)

    return SequencerResult(
        stages=stages,
        critical_path=critical_path,
        critical_path_total_days=total_days,
        bottlenecks=bottlenecks,
        parallel_with_hints=hints,
        dropped_edges=dropped,
    )


def _ordered_critical_path(
    stages: list[list[str]],
    critical_ids: set[str],
    adj: dict[str, list[str]],
) -> list[str]:
    """Return critical-path rule_ids in topological (stage) order."""
    return [rid for stage in stages for rid in stage if rid in critical_ids]
