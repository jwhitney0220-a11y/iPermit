"""Conflict-resolution tests for the rules engine (T03-03).

Exercises the deterministic resolution of fired rules against the T00-02
ontology precedence ladder: overlap union (distinct permits never conflict),
lower-jurisdiction override with parent preservation, explicit supersession,
deterministic ordering, and the conflict-report contents.

These are pure-Python tests over synthetic rule dicts — no DB, no GIS, no
temporal selection (all owned by other tickets).
"""

from __future__ import annotations

from typing import Any

from ipermit_engine.conflict import (
    JURISDICTION_PRECEDENCE,
    ConflictRecord,
    ResolutionResult,
    is_more_specific,
    precedence_rank,
    resolve_conflicts,
)
from ipermit_engine.engine import DecisionStep, RuleEvaluation


def _rule(
    rule_id: str,
    level: str,
    *,
    permit: tuple[str, str, str] = ("Permit A", "PA", "Agency A"),
    jurisdiction_id: str | None = None,
    version: str = "1.0.0",
    supersedes: list[str] | None = None,
    superseded_by: str | None = None,
) -> dict[str, Any]:
    """Build a minimal fired-rule dict with one declared permit output."""
    name, code, agency = permit
    rule: dict[str, Any] = {
        "rule_id": rule_id,
        "version": version,
        "jurisdiction_level": level,
        "jurisdiction_id": jurisdiction_id or f"{level}-jx",
        "outputs": {"permits": [{"name": name, "code": code, "agency": agency}]},
    }
    if supersedes is not None:
        rule["supersedes"] = supersedes
    if superseded_by is not None:
        rule["superseded_by"] = superseded_by
    return rule


# ---------------------------------------------------------------------------
# Precedence ladder helpers
# ---------------------------------------------------------------------------


def test_precedence_ladder_matches_ontology_order() -> None:
    assert JURISDICTION_PRECEDENCE == (
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


def test_precedence_rank_federal_is_least_specific() -> None:
    assert precedence_rank("federal") < precedence_rank("state")
    assert precedence_rank("state") < precedence_rank("county")
    assert precedence_rank("county") < precedence_rank("special")


def test_unknown_level_ranks_after_every_known_level() -> None:
    assert precedence_rank("not-a-level") > precedence_rank("special")
    assert precedence_rank(None) > precedence_rank("special")


def test_is_more_specific() -> None:
    assert is_more_specific("county", "state") is True
    assert is_more_specific("state", "county") is False
    assert is_more_specific("special", "federal") is True


# ---------------------------------------------------------------------------
# Overlap union: distinct permits are NOT a conflict
# ---------------------------------------------------------------------------


def test_distinct_permits_are_both_preserved_no_conflict() -> None:
    # A federal rule and a county rule requiring DIFFERENT permits both apply;
    # ontology §7.2 overlap union — neither suppresses the other.
    rules = [
        _rule("us-cwa-404", "federal", permit=("CWA 404", "404", "USACE")),
        _rule(
            "tx-travis-flood", "county", permit=("Floodplain Permit", "FP", "Travis")
        ),
    ]
    result = resolve_conflicts(rules)
    assert isinstance(result, ResolutionResult)
    assert len(result.requirements) == 2
    # No conflict was reported — they are distinct requirements.
    assert result.conflicts == ()
    governing_ids = {req.governing.rule_id for req in result.requirements}
    assert governing_ids == {"us-cwa-404", "tx-travis-flood"}
    # Neither has any contributing (parent) rule folded in.
    assert all(req.contributing == () for req in result.requirements)


def test_two_jurisdictions_same_permit_is_a_conflict() -> None:
    # Same permit identity from two levels IS a conflict (same requirement).
    rules = [
        _rule("federal-rule", "federal"),
        _rule("county-rule", "county"),
    ]
    result = resolve_conflicts(rules)
    assert len(result.requirements) == 1
    assert len(result.conflicts) == 1


# ---------------------------------------------------------------------------
# Lower-jurisdiction override preserves the parent requirement
# ---------------------------------------------------------------------------


def test_lower_jurisdiction_governs_parent_preserved() -> None:
    parent = _rule("state-threshold", "state")
    child = _rule("county-threshold", "county")
    result = resolve_conflicts([parent, child])

    assert len(result.requirements) == 1
    req = result.requirements[0]
    # The more specific (county) rule governs...
    assert req.governing.rule_id == "county-threshold"
    # ...and the parent (state) rule is PRESERVED as a contributing rule.
    assert [fr.rule_id for fr in req.contributing] == ["state-threshold"]


def test_override_conflict_report_records_preservation() -> None:
    result = resolve_conflicts(
        [_rule("state-threshold", "state"), _rule("county-threshold", "county")]
    )
    assert len(result.conflicts) == 1
    conflict = result.conflicts[0]
    assert isinstance(conflict, ConflictRecord)
    assert conflict.kind == "override"
    assert conflict.governing_rule_id == "county-threshold"
    # Parent kept, nothing deleted.
    assert conflict.preserved_rule_ids == ("state-threshold",)
    assert conflict.superseded_rule_ids == ()
    assert "preserved" in conflict.rationale
    assert "§5.2" in conflict.rationale


def test_three_levels_most_specific_governs_all_parents_preserved() -> None:
    rules = [
        _rule("federal-r", "federal"),
        _rule("state-r", "state"),
        _rule("muni-r", "municipality"),
    ]
    result = resolve_conflicts(rules)
    req = result.requirements[0]
    assert req.governing.rule_id == "muni-r"
    # Both parents preserved, ordered most-specific-first then rule_id.
    assert [fr.rule_id for fr in req.contributing] == ["state-r", "federal-r"]


# ---------------------------------------------------------------------------
# Explicit supersession (ontology §5.3 — the only legitimate deletion)
# ---------------------------------------------------------------------------


def test_supersession_removes_target_from_governing_set() -> None:
    parent = _rule("state-old", "state", version="1.0.0")
    child = _rule(
        "county-new", "county", version="2.0.0", supersedes=["state-old@1.0.0"]
    )
    result = resolve_conflicts([parent, child])

    # The superseded parent is no longer a contributing rule in the requirement.
    req = result.requirements[0]
    assert req.governing.rule_id == "county-new"
    assert req.contributing == ()
    # But it is RECORDED so the deletion is never silent.
    assert result.superseded_rule_ids == ("state-old",)


def test_supersession_conflict_report_documents_deletion() -> None:
    child = _rule(
        "county-new", "county", version="2.0.0", supersedes=["state-old@1.0.0"]
    )
    parent = _rule("state-old", "state", version="1.0.0")
    result = resolve_conflicts([child, parent])
    assert len(result.conflicts) == 1
    conflict = result.conflicts[0]
    assert conflict.kind == "supersession"
    assert conflict.governing_rule_id == "county-new"
    assert conflict.superseded_rule_ids == ("state-old",)
    assert "supersedes" in conflict.rationale


def test_supersedes_reference_to_unfired_rule_is_noop() -> None:
    # The target of supersedes did NOT fire -> nothing to delete, no conflict.
    child = _rule(
        "county-new", "county", supersedes=["some-rule-that-did-not-fire@1.0.0"]
    )
    result = resolve_conflicts([child])
    assert result.superseded_rule_ids == ()
    assert result.conflicts == ()
    assert result.requirements[0].governing.rule_id == "county-new"


def test_supersedes_matches_on_bare_rule_id() -> None:
    # A supersedes ref without @version still matches the fired rule_id.
    parent = _rule("state-old", "state")
    child = _rule("county-new", "county", supersedes=["state-old"])
    result = resolve_conflicts([parent, child])
    assert result.superseded_rule_ids == ("state-old",)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_requirements_ordered_by_precedence_then_rule_id() -> None:
    # Distinct permits so each is its own requirement; governing-rule ordering
    # is (precedence_rank, rule_id) ascending: federal before county; within a
    # level, rule_id lexicographic.
    rules = [
        _rule("z-county", "county", permit=("P3", "P3", "Ag")),
        _rule("a-county", "county", permit=("P2", "P2", "Ag")),
        _rule("fed", "federal", permit=("P1", "P1", "Ag")),
    ]
    result = resolve_conflicts(rules)
    ordered = [req.governing.rule_id for req in result.requirements]
    assert ordered == ["fed", "a-county", "z-county"]


def test_output_is_stable_across_runs_and_input_order() -> None:
    rules = [
        _rule("muni-r", "municipality"),
        _rule("federal-r", "federal"),
        _rule("state-r", "state"),
    ]
    first = resolve_conflicts(rules)
    second = resolve_conflicts(list(reversed(rules)))
    assert first == second
    # Contributing order is deterministic regardless of input order.
    assert [fr.rule_id for fr in first.requirements[0].contributing] == [
        "state-r",
        "federal-r",
    ]


# ---------------------------------------------------------------------------
# Evaluation join + edge cases
# ---------------------------------------------------------------------------


def test_evaluations_are_joined_by_rule_id() -> None:
    rule = _rule("county-r", "county")
    evaluation = RuleEvaluation(
        rule_id="county-r",
        fired=True,
        decided_by=DecisionStep.FIRED,
        evaluated_triggers={"matched": True},
        detail="fired",
    )
    result = resolve_conflicts([rule], [evaluation])
    governing = result.requirements[0].governing
    assert governing.evaluation is evaluation
    assert governing.evaluation.evaluated_triggers == {"matched": True}


def test_rule_without_permit_outputs_gets_unique_key() -> None:
    # Two output-less rules never collide into a false conflict.
    rules = [
        {"rule_id": "a", "jurisdiction_level": "state"},
        {"rule_id": "b", "jurisdiction_level": "county"},
    ]
    result = resolve_conflicts(rules)
    assert len(result.requirements) == 2
    assert result.conflicts == ()


def test_empty_input_yields_empty_result() -> None:
    result = resolve_conflicts([])
    assert result.requirements == ()
    assert result.conflicts == ()
    assert result.superseded_rule_ids == ()


def test_same_level_same_permit_distinct_jurisdictions_both_kept() -> None:
    # Two counties (overlap, §7.4): same permit identity, same level. The engine
    # keeps both — most-specific-first then rule_id — and does not merge them.
    rules = [
        _rule("travis-fp", "county", jurisdiction_id="travis"),
        _rule("hays-fp", "county", jurisdiction_id="hays"),
    ]
    result = resolve_conflicts(rules)
    req = result.requirements[0]
    assert req.governing.rule_id == "hays-fp"  # rule_id tiebreak within level
    assert [fr.rule_id for fr in req.contributing] == ["travis-fp"]
