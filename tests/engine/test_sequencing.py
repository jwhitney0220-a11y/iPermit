"""Tests for the permit dependency sequencer (T03-04).

Exercises: linear prereq chain, parallel permits, not-fired prerequisite (skipped),
cycle detection, bottleneck flagging, and determinism.

Uses the Texas Transmission Wetland Crossing worked example from
docs/specs/dependency-sequencing.md §10 where applicable.
"""

from __future__ import annotations

from typing import Any

import pytest
from ipermit_engine.sequencing import (
    CyclicDependencyError,
    SequencerResult,
    sequence_rules,
)

# ---------------------------------------------------------------------------
# Helpers — rule dict builders (no hardcoded permit logic; params drive shape)
# ---------------------------------------------------------------------------


def _rule(
    rule_id: str,
    *,
    source_agency: str = "agency-a",
    lead_time: int | None = None,
    prerequisites: list[str] | None = None,
    parallel_with: list[str] | None = None,
) -> dict[str, Any]:
    """Build a minimal fired-rule dict with optional sequencing data."""
    seq: dict[str, Any] = {}
    if lead_time is not None:
        seq["typical_lead_time_days"] = lead_time
    if prerequisites:
        seq["prerequisites"] = prerequisites
    if parallel_with:
        seq["parallel_with"] = parallel_with
    rule: dict[str, Any] = {"rule_id": rule_id, "source_agency": source_agency}
    if seq:
        rule["sequencing"] = seq
    return rule


# ---------------------------------------------------------------------------
# Worked example from spec §10 — Texas Transmission Wetland Crossing
# ---------------------------------------------------------------------------

JD = "us-usace-jurisdictional-determination"
NWP = "us-usace-section-404-nationwide-permit"
WQC = "tx-tceq-401-water-quality-certification"
TPDES = "tx-tceq-tpdes-construction-stormwater"
COUNTY = "tx-county-floodplain-development-permit"


def _texas_example_rules() -> list[dict[str, Any]]:
    return [
        _rule(JD, source_agency="USACE", lead_time=90),
        _rule(
            NWP,
            source_agency="USACE",
            lead_time=60,
            prerequisites=[JD],
        ),
        _rule(
            WQC,
            source_agency="TCEQ",
            lead_time=60,
            prerequisites=[NWP],
        ),
        _rule(
            TPDES,
            source_agency="TCEQ",
            lead_time=14,
            parallel_with=[NWP, COUNTY],
        ),
        _rule(
            COUNTY,
            source_agency="County",
            lead_time=30,
            parallel_with=[TPDES],
        ),
    ]


def test_texas_example_stage_count() -> None:
    """Worked example produces exactly three stages (spec §10)."""
    result = sequence_rules(_texas_example_rules())
    assert len(result.stages) == 3


def test_texas_example_stage_0_permits() -> None:
    """Stage 0 contains JD, TPDES, and COUNTY — the three permits with no
    predecessors in the fired set (spec §10)."""
    result = sequence_rules(_texas_example_rules())
    stage0_ids = {p.rule_id for p in result.stages[0].permits}
    assert stage0_ids == {JD, TPDES, COUNTY}


def test_texas_example_stage_1_permits() -> None:
    """Stage 1 contains only the §404 NWP, which waits on the JD."""
    result = sequence_rules(_texas_example_rules())
    stage1_ids = {p.rule_id for p in result.stages[1].permits}
    assert stage1_ids == {NWP}


def test_texas_example_stage_2_permits() -> None:
    """Stage 2 contains only the §401 WQC, which waits on the §404."""
    result = sequence_rules(_texas_example_rules())
    stage2_ids = {p.rule_id for p in result.stages[2].permits}
    assert stage2_ids == {WQC}


def test_texas_example_critical_path() -> None:
    """Critical path is JD -> NWP -> WQC (210 days total, spec §10)."""
    result = sequence_rules(_texas_example_rules())
    assert result.critical_path_total_days == 210
    assert set(result.critical_path) == {JD, NWP, WQC}


def test_texas_example_critical_path_order() -> None:
    """Critical path is returned in topological order."""
    result = sequence_rules(_texas_example_rules())
    assert result.critical_path == [JD, NWP, WQC]


def test_texas_example_no_bottlenecks_at_default_threshold() -> None:
    """Under 120-day default threshold, no single permit exceeds it (spec §10)."""
    result = sequence_rules(_texas_example_rules())
    assert result.bottlenecks == []


def test_texas_example_bottleneck_when_threshold_lowered() -> None:
    """Lowering threshold to 60 flags WQC and NWP as bottlenecks."""
    result = sequence_rules(_texas_example_rules(), bottleneck_threshold_days=60)
    bottleneck_ids = {b.rule_id for b in result.bottlenecks}
    # NWP (60 days) and WQC (60 days) both meet >= 60
    assert NWP in bottleneck_ids
    assert WQC in bottleneck_ids


def test_texas_example_parallel_hints() -> None:
    """parallel_with hints are preserved for TPDES <-> NWP and TPDES <-> COUNTY."""
    result = sequence_rules(_texas_example_rules())
    hint_pairs = set(result.parallel_with_hints)
    assert (min(TPDES, NWP), max(TPDES, NWP)) in hint_pairs
    assert (min(TPDES, COUNTY), max(TPDES, COUNTY)) in hint_pairs


# ---------------------------------------------------------------------------
# Linear prerequisite chain
# ---------------------------------------------------------------------------


def test_linear_chain_stage_order() -> None:
    """A -> B -> C produces three stages in order."""
    rules = [
        _rule("a"),
        _rule("b", prerequisites=["a"]),
        _rule("c", prerequisites=["b"]),
    ]
    result = sequence_rules(rules)
    assert len(result.stages) == 3
    assert [p.rule_id for p in result.stages[0].permits] == ["a"]
    assert [p.rule_id for p in result.stages[1].permits] == ["b"]
    assert [p.rule_id for p in result.stages[2].permits] == ["c"]


def test_linear_chain_stage_indices() -> None:
    """Stage index matches position in output list."""
    rules = [_rule("a"), _rule("b", prerequisites=["a"])]
    result = sequence_rules(rules)
    for i, stage in enumerate(result.stages):
        assert stage.stage_index == i


def test_linear_chain_critical_path_accumulates() -> None:
    """Critical path total is sum of all lead times on the chain."""
    rules = [
        _rule("a", lead_time=10),
        _rule("b", lead_time=20, prerequisites=["a"]),
        _rule("c", lead_time=30, prerequisites=["b"]),
    ]
    result = sequence_rules(rules)
    assert result.critical_path_total_days == 60
    assert result.critical_path == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# Parallel permits end up in the same stage
# ---------------------------------------------------------------------------


def test_independent_permits_same_stage() -> None:
    """Three rules with no prerequisites form a single stage."""
    rules = [_rule("x"), _rule("y"), _rule("z")]
    result = sequence_rules(rules)
    assert len(result.stages) == 1
    ids = [p.rule_id for p in result.stages[0].permits]
    assert sorted(ids) == ["x", "y", "z"]


def test_parallel_permits_not_on_critical_path() -> None:
    """Off-critical-path permits in stage 0 are marked not on the critical path."""
    rules = [
        _rule("slow", lead_time=100),
        _rule("fast", lead_time=1),
        _rule("last", lead_time=10, prerequisites=["slow"]),
    ]
    result = sequence_rules(rules)
    # critical path: slow -> last = 110
    cp_map = {
        p.rule_id: p.on_critical_path for stage in result.stages for p in stage.permits
    }
    assert cp_map["slow"] is True
    assert cp_map["last"] is True
    assert cp_map["fast"] is False


# ---------------------------------------------------------------------------
# Not-fired prerequisite is silently dropped (spec §8)
# ---------------------------------------------------------------------------


def test_unfired_prerequisite_is_dropped() -> None:
    """Prerequisite not in the fired set is skipped; successor is not blocked."""
    rules = [
        # "b" references "a", but "a" did NOT fire (not in the list)
        _rule("b", prerequisites=["a"]),
        _rule("c"),
    ]
    result = sequence_rules(rules)
    # With "a" absent, "b" has in-degree 0 and lands in stage 0 with "c".
    assert len(result.stages) == 1
    stage0_ids = {p.rule_id for p in result.stages[0].permits}
    assert stage0_ids == {"b", "c"}


def test_unfired_prerequisite_recorded_in_dropped_edges() -> None:
    """Dropped edge is recorded with correct predecessor/successor."""
    rules = [_rule("b", prerequisites=["unfired-rule"])]
    result = sequence_rules(rules)
    assert len(result.dropped_edges) == 1
    edge = result.dropped_edges[0]
    assert edge.predecessor_rule_id == "unfired-rule"
    assert edge.successor_rule_id == "b"
    assert edge.reason == "prerequisite_not_triggered"


def test_unfired_prerequisite_not_blocking() -> None:
    """Permits remain in stage 0 even when their declared prerequisites didn't fire."""
    # "c" depends on "missing" which never fired; should still be in stage 0
    rules = [_rule("c", prerequisites=["missing"]), _rule("d")]
    result = sequence_rules(rules)
    stage0_ids = {p.rule_id for p in result.stages[0].permits}
    assert "c" in stage0_ids
    assert "d" in stage0_ids


# ---------------------------------------------------------------------------
# Cycle detection (spec §6.1 — publication-blocking error)
# ---------------------------------------------------------------------------


def test_simple_cycle_raises() -> None:
    """A -> B -> A cycle raises CyclicDependencyError."""
    rules = [
        _rule("a", prerequisites=["b"]),
        _rule("b", prerequisites=["a"]),
    ]
    with pytest.raises(CyclicDependencyError):
        sequence_rules(rules)


def test_three_node_cycle_raises() -> None:
    """A -> B -> C -> A raises CyclicDependencyError."""
    rules = [
        _rule("a", prerequisites=["c"]),
        _rule("b", prerequisites=["a"]),
        _rule("c", prerequisites=["b"]),
    ]
    with pytest.raises(CyclicDependencyError):
        sequence_rules(rules)


def test_cycle_error_message_names_participants() -> None:
    """CyclicDependencyError message includes the involved rule_ids."""
    rules = [
        _rule("permit-x", prerequisites=["permit-y"]),
        _rule("permit-y", prerequisites=["permit-x"]),
    ]
    with pytest.raises(CyclicDependencyError, match="permit-x"):
        sequence_rules(rules)


# ---------------------------------------------------------------------------
# Bottleneck flagging (spec §9.2 — threshold >= 120, on critical path)
# ---------------------------------------------------------------------------


def test_bottleneck_flagged_on_critical_path_above_threshold() -> None:
    """A long-lead permit on the critical path is flagged as a bottleneck."""
    rules = [
        _rule("fast-prereq", lead_time=10),
        _rule("slow-bottleneck", lead_time=365, prerequisites=["fast-prereq"]),
    ]
    result = sequence_rules(rules, bottleneck_threshold_days=120)
    assert len(result.bottlenecks) == 1
    b = result.bottlenecks[0]
    assert b.rule_id == "slow-bottleneck"
    assert b.typical_lead_time_days == 365


def test_bottleneck_below_threshold_not_flagged() -> None:
    """Permits on the critical path but below threshold are NOT bottlenecks."""
    rules = [
        _rule("a", lead_time=50),
        _rule("b", lead_time=119, prerequisites=["a"]),
    ]
    result = sequence_rules(rules, bottleneck_threshold_days=120)
    assert result.bottlenecks == []


def test_bottleneck_off_critical_path_not_flagged() -> None:
    """Long-lead permit off the critical path is never a bottleneck."""
    rules = [
        _rule("off-path", lead_time=365),  # not a prereq of anything
        _rule("critical-a", lead_time=500),
        _rule("critical-b", lead_time=200, prerequisites=["critical-a"]),
    ]
    result = sequence_rules(rules, bottleneck_threshold_days=120)
    bottleneck_ids = {b.rule_id for b in result.bottlenecks}
    # off-path has lead_time=365 but is not on the critical path
    assert "off-path" not in bottleneck_ids
    # critical-a and critical-b are on the path and above threshold
    assert "critical-a" in bottleneck_ids
    assert "critical-b" in bottleneck_ids


def test_cross_agency_bottleneck_tagged() -> None:
    """Bottleneck receiving a cross-agency prerequisite gets cross_agency_response=True."""
    rules = [
        _rule("usace-permit", source_agency="USACE", lead_time=150),
        _rule(
            "tceq-permit",
            source_agency="TCEQ",
            lead_time=130,
            prerequisites=["usace-permit"],
        ),
    ]
    result = sequence_rules(rules, bottleneck_threshold_days=120)
    # tceq-permit has a predecessor from a different agency -> cross_agency_response
    tceq_bottleneck = next(b for b in result.bottlenecks if b.rule_id == "tceq-permit")
    assert tceq_bottleneck.cross_agency_response is True


def test_same_agency_bottleneck_not_cross_agency() -> None:
    """Bottleneck with same-agency predecessor has cross_agency_response=False."""
    rules = [
        _rule("usace-jd", source_agency="USACE", lead_time=200),
        _rule(
            "usace-404",
            source_agency="USACE",
            lead_time=150,
            prerequisites=["usace-jd"],
        ),
    ]
    result = sequence_rules(rules, bottleneck_threshold_days=120)
    bottleneck_404 = next(b for b in result.bottlenecks if b.rule_id == "usace-404")
    assert bottleneck_404.cross_agency_response is False


def test_bottleneck_predecessors_successors_populated() -> None:
    """Bottleneck record lists correct predecessor and successor rule_ids."""
    rules = [
        _rule("pre", lead_time=10),
        _rule("mid", lead_time=300, prerequisites=["pre"]),
        _rule("post", lead_time=10, prerequisites=["mid"]),
    ]
    result = sequence_rules(rules, bottleneck_threshold_days=120)
    mid_bottleneck = next(b for b in result.bottlenecks if b.rule_id == "mid")
    assert "pre" in mid_bottleneck.predecessors
    assert "post" in mid_bottleneck.successors


# ---------------------------------------------------------------------------
# Determinism — same input always yields same output
# ---------------------------------------------------------------------------


def test_deterministic_stage_ordering_same_every_call() -> None:
    """Multiple calls with the same inputs produce identical stage ordering."""
    rules = [_rule("c"), _rule("a"), _rule("b", prerequisites=["a"])]
    result1 = sequence_rules(rules)
    result2 = sequence_rules(rules)
    ids1 = [[p.rule_id for p in s.permits] for s in result1.stages]
    ids2 = [[p.rule_id for p in s.permits] for s in result2.stages]
    assert ids1 == ids2


def test_deterministic_ordering_within_stage() -> None:
    """Within a stage, rule_ids are sorted alphabetically for stable diffable output."""
    rules = [_rule("zz-permit"), _rule("aa-permit"), _rule("mm-permit")]
    result = sequence_rules(rules)
    ids = [p.rule_id for p in result.stages[0].permits]
    assert ids == sorted(ids)


def test_deterministic_critical_path_ordering() -> None:
    """Critical path list is in topological (stage) order regardless of rule dict order."""
    # Supply rules in reverse topological order
    rules = [
        _rule("c", lead_time=10, prerequisites=["b"]),
        _rule("b", lead_time=10, prerequisites=["a"]),
        _rule("a", lead_time=10),
    ]
    result = sequence_rules(rules)
    assert result.critical_path == ["a", "b", "c"]


def test_deterministic_parallel_hints_sorted() -> None:
    """Parallel hints list is sorted canonically on repeated calls."""
    rules = [
        _rule("c", parallel_with=["a", "b"]),
        _rule("b", parallel_with=["c"]),
        _rule("a", parallel_with=["c"]),
    ]
    result1 = sequence_rules(rules)
    result2 = sequence_rules(rules)
    assert result1.parallel_with_hints == result2.parallel_with_hints


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_fired_rules() -> None:
    """An empty fired-rules list returns an empty SequencerResult."""
    result = sequence_rules([])
    assert isinstance(result, SequencerResult)
    assert result.stages == []
    assert result.critical_path == []
    assert result.critical_path_total_days == 0
    assert result.bottlenecks == []


def test_single_rule_no_sequencing() -> None:
    """A single rule with no sequencing data produces one stage with one permit."""
    result = sequence_rules([_rule("solo")])
    assert len(result.stages) == 1
    assert result.stages[0].permits[0].rule_id == "solo"
    assert result.stages[0].stage_index == 0


def test_no_lead_time_treated_as_zero() -> None:
    """Rules missing typical_lead_time_days contribute 0 to path weight."""
    rules = [
        _rule("a"),  # no lead time
        _rule("b", prerequisites=["a"]),  # no lead time
    ]
    result = sequence_rules(rules)
    assert result.critical_path_total_days == 0


def test_on_critical_path_flag_in_stage_permits() -> None:
    """StagePermit.on_critical_path reflects actual critical path membership."""
    rules = [
        _rule("cp", lead_time=100),
        _rule("off", lead_time=1),
        _rule("end", lead_time=50, prerequisites=["cp"]),
    ]
    result = sequence_rules(rules)
    # Flatten permits
    permit_map = {
        p.rule_id: p.on_critical_path for s in result.stages for p in s.permits
    }
    assert permit_map["cp"] is True
    assert permit_map["end"] is True
    assert permit_map["off"] is False
