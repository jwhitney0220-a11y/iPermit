"""Tests for the recursive trigger evaluator (T03-01).

Verifies the evaluated-condition tree shape (matching the permit-explanation
schema's evaluatedCondition $defs), the ``matched`` booleans at every node, and
that child order is preserved deterministically.
"""

from __future__ import annotations

import pytest
from ipermit_engine import ProjectContext, evaluate_trigger, matched
from ipermit_engine.triggers import TriggerError


def _ctx(**values: object) -> ProjectContext:
    return ProjectContext(dict(values))


# ---------------------------------------------------------------------------
# Leaf nodes
# ---------------------------------------------------------------------------


def test_leaf_match_shape() -> None:
    node = {"field": "project.acreage", "operator": ">=", "value": 10}
    result = evaluate_trigger(node, _ctx(**{"project.acreage": 12.5}))
    assert result == {
        "field": "project.acreage",
        "operator": ">=",
        "expected_value": 10,
        "actual_value": 12.5,
        "matched": True,
    }


def test_leaf_non_match() -> None:
    node = {"field": "project.acreage", "operator": ">=", "value": 10}
    result = evaluate_trigger(node, _ctx(**{"project.acreage": 3}))
    assert result["matched"] is False
    assert result["actual_value"] == 3


def test_leaf_missing_field_actual_is_null() -> None:
    node = {"field": "project.acreage", "operator": ">=", "value": 10}
    result = evaluate_trigger(node, _ctx())
    assert result["matched"] is False
    assert result["actual_value"] is None  # MISSING serialises to null


def test_leaf_exists_omits_expected_value() -> None:
    node = {"field": "geometry.intersects_usace_district", "operator": "exists"}
    result = evaluate_trigger(
        node, _ctx(**{"geometry.intersects_usace_district": ["swg"]})
    )
    assert "expected_value" not in result
    assert result["matched"] is True
    assert result["actual_value"] == ["swg"]


def test_leaf_exists_missing_is_false() -> None:
    node = {"field": "geometry.intersects_usace_district", "operator": "exists"}
    result = evaluate_trigger(node, _ctx())
    assert result["matched"] is False
    assert result["actual_value"] is None


def test_leaf_unknown_operator_raises() -> None:
    node = {"field": "project.x", "operator": "~=", "value": 1}
    with pytest.raises(TriggerError):
        evaluate_trigger(node, _ctx())


# ---------------------------------------------------------------------------
# all / any / not composites
# ---------------------------------------------------------------------------


def test_all_matched_is_and() -> None:
    node = {
        "all": [
            {"field": "project.a", "operator": "=", "value": 1},
            {"field": "project.b", "operator": "=", "value": 2},
        ]
    }
    matched_ctx = _ctx(**{"project.a": 1, "project.b": 2})
    failing_ctx = _ctx(**{"project.a": 1, "project.b": 99})
    assert matched(evaluate_trigger(node, matched_ctx)) is True
    assert matched(evaluate_trigger(node, failing_ctx)) is False


def test_any_matched_is_or() -> None:
    node = {
        "any": [
            {"field": "project.a", "operator": "=", "value": 1},
            {"field": "project.b", "operator": "=", "value": 2},
        ]
    }
    one_ctx = _ctx(**{"project.a": 1, "project.b": 99})
    none_ctx = _ctx(**{"project.a": 0, "project.b": 99})
    assert matched(evaluate_trigger(node, one_ctx)) is True
    assert matched(evaluate_trigger(node, none_ctx)) is False


def test_not_negates_child() -> None:
    node = {"not": {"field": "project.flag", "operator": "=", "value": True}}
    assert matched(evaluate_trigger(node, _ctx(**{"project.flag": True}))) is False
    assert matched(evaluate_trigger(node, _ctx(**{"project.flag": False}))) is True


def test_not_shape_uses_json_not_key() -> None:
    node = {"not": {"field": "project.flag", "operator": "=", "value": True}}
    result = evaluate_trigger(node, _ctx(**{"project.flag": False}))
    assert set(result) == {"not", "matched"}
    assert result["matched"] is True
    assert result["not"]["matched"] is False


def test_nested_composition_tree_shape() -> None:
    node = {
        "all": [
            {"field": "project.federal_nexus", "operator": "=", "value": True},
            {
                "any": [
                    {
                        "field": "project.stream_crossings_count",
                        "operator": ">",
                        "value": 0,
                    },
                    {"field": "project.has_wetlands", "operator": "=", "value": True},
                ]
            },
        ]
    }
    ctx = _ctx(
        **{
            "project.federal_nexus": True,
            "project.stream_crossings_count": 1,
            "project.has_wetlands": False,
        }
    )
    result = evaluate_trigger(node, ctx)
    assert result["matched"] is True
    assert list(result) == ["all", "matched"]
    inner_any = result["all"][1]
    assert list(inner_any) == ["any", "matched"]
    assert inner_any["matched"] is True
    # First any-branch matched, second did not — both still reported.
    assert inner_any["any"][0]["matched"] is True
    assert inner_any["any"][1]["matched"] is False


def test_child_order_preserved() -> None:
    node = {
        "all": [
            {"field": "project.z", "operator": "exists"},
            {"field": "project.a", "operator": "exists"},
            {"field": "project.m", "operator": "exists"},
        ]
    }
    ctx = _ctx(**{"project.z": 1, "project.a": 1, "project.m": 1})
    result = evaluate_trigger(node, ctx)
    fields = [child["field"] for child in result["all"]]
    assert fields == ["project.z", "project.a", "project.m"]


def test_all_branches_evaluated_no_short_circuit() -> None:
    # Even though the first all-child fails, every branch is still evaluated and
    # emitted so the explainer sees the full picture.
    node = {
        "all": [
            {"field": "project.a", "operator": "=", "value": 1},
            {"field": "project.b", "operator": "=", "value": 2},
        ]
    }
    result = evaluate_trigger(node, _ctx(**{"project.a": 0, "project.b": 2}))
    assert result["matched"] is False
    assert len(result["all"]) == 2
    assert result["all"][1]["matched"] is True


# ---------------------------------------------------------------------------
# Malformed nodes
# ---------------------------------------------------------------------------


def test_empty_node_raises() -> None:
    with pytest.raises(TriggerError):
        evaluate_trigger({}, _ctx())


def test_multiple_composite_keys_raises() -> None:
    node = {"all": [{"field": "project.a", "operator": "exists"}], "any": []}
    with pytest.raises(TriggerError):
        evaluate_trigger(node, _ctx())


def test_empty_all_list_raises() -> None:
    with pytest.raises(TriggerError):
        evaluate_trigger({"all": []}, _ctx())


def test_not_with_non_dict_child_raises() -> None:
    with pytest.raises(TriggerError):
        evaluate_trigger({"not": [1, 2]}, _ctx())
