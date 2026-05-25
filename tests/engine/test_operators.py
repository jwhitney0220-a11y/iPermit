"""Tests for the eleven trigger operators (T03-01).

Covers, for every operator: a match, a non-match, MISSING-field behaviour, and
(where relevant) a type mismatch raising OperatorError. ``exists`` is exercised
with and without a value and against present-but-null.
"""

from __future__ import annotations

import datetime

import pytest
from ipermit_engine import OPERATOR_KEYS, OperatorError, apply_operator
from ipermit_engine.context import MISSING
from ipermit_engine.operators import comparison_operators, is_known_operator

# ---------------------------------------------------------------------------
# Equality / inequality
# ---------------------------------------------------------------------------


def test_eq_match() -> None:
    assert apply_operator("=", 10, 10) is True


def test_eq_non_match() -> None:
    assert apply_operator("=", 10, 11) is False


def test_eq_match_string_and_bool() -> None:
    assert apply_operator("=", "linear", "linear") is True
    assert apply_operator("=", True, True) is True


def test_eq_missing_is_non_match() -> None:
    assert apply_operator("=", MISSING, 10) is False


def test_ne_match() -> None:
    assert apply_operator("!=", 10, 11) is True


def test_ne_non_match() -> None:
    assert apply_operator("!=", 10, 10) is False


def test_ne_missing_is_non_match() -> None:
    # MISSING short-circuits to False (non-match) for every value operator.
    assert apply_operator("!=", MISSING, 10) is False


# ---------------------------------------------------------------------------
# Ordered comparisons: > >= < <=
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("operator", "actual", "expected", "result"),
    [
        (">", 5, 0, True),
        (">", 0, 0, False),
        (">=", 5, 5, True),
        (">=", 4, 5, False),
        ("<", 1, 2, True),
        ("<", 2, 2, False),
        ("<=", 2, 2, True),
        ("<=", 3, 2, False),
    ],
)
def test_ordered_numeric(
    operator: str, actual: int, expected: int, result: bool
) -> None:
    assert apply_operator(operator, actual, expected) is result


def test_ordered_dates() -> None:
    earlier = datetime.date(2026, 1, 1)
    later = datetime.date(2026, 6, 1)
    assert apply_operator(">", later, earlier) is True
    assert apply_operator("<=", earlier, later) is True


def test_ordered_missing_is_non_match() -> None:
    assert apply_operator(">", MISSING, 0) is False


def test_ordered_rejects_bool_actual() -> None:
    # bool is an int subclass but ordering a bool is an authoring mistake.
    with pytest.raises(OperatorError):
        apply_operator(">", True, 0)


def test_ordered_rejects_string() -> None:
    with pytest.raises(OperatorError):
        apply_operator(">", "abc", 0)


def test_ordered_rejects_date_vs_number() -> None:
    with pytest.raises(OperatorError):
        apply_operator(">", datetime.date(2026, 1, 1), 5)


# ---------------------------------------------------------------------------
# contains
# ---------------------------------------------------------------------------


def test_contains_substring_match() -> None:
    assert apply_operator("contains", "nationwide permit", "permit") is True


def test_contains_substring_non_match() -> None:
    assert apply_operator("contains", "nationwide", "permit") is False


def test_contains_list_membership_match() -> None:
    assert apply_operator("contains", ["a", "b", "c"], "b") is True


def test_contains_list_membership_non_match() -> None:
    assert apply_operator("contains", ["a", "b"], "z") is False


def test_contains_missing_is_non_match() -> None:
    assert apply_operator("contains", MISSING, "x") is False


def test_contains_string_with_non_string_value_raises() -> None:
    with pytest.raises(OperatorError):
        apply_operator("contains", "abc", 1)


def test_contains_invalid_actual_type_raises() -> None:
    with pytest.raises(OperatorError):
        apply_operator("contains", 5, 5)


# ---------------------------------------------------------------------------
# intersects
# ---------------------------------------------------------------------------


def test_intersects_match() -> None:
    assert apply_operator("intersects", ["swg", "fwd"], ["fwd", "abq"]) is True


def test_intersects_non_match() -> None:
    assert apply_operator("intersects", ["swg"], ["abq"]) is False


def test_intersects_missing_is_non_match() -> None:
    assert apply_operator("intersects", MISSING, ["x"]) is False


def test_intersects_non_list_actual_raises() -> None:
    with pytest.raises(OperatorError):
        apply_operator("intersects", "swg", ["swg"])


def test_intersects_non_list_value_raises() -> None:
    with pytest.raises(OperatorError):
        apply_operator("intersects", ["swg"], "swg")


# ---------------------------------------------------------------------------
# exists  — the only operator that ignores value
# ---------------------------------------------------------------------------


def test_exists_present_value_true() -> None:
    assert apply_operator("exists", "anything", None) is True


def test_exists_present_falsy_value_true() -> None:
    # Falsy-but-present values (0, "", []) still exist.
    assert apply_operator("exists", 0, None) is True
    assert apply_operator("exists", "", None) is True
    assert apply_operator("exists", [], None) is True


def test_exists_missing_false() -> None:
    assert apply_operator("exists", MISSING, None) is False


def test_exists_present_but_null_false() -> None:
    # Present-but-None is not "present and non-null".
    assert apply_operator("exists", None, None) is False


def test_exists_ignores_provided_value() -> None:
    # exists never reads the rule's value; a value present or absent is the same.
    assert apply_operator("exists", "x", "ignored") is True


# ---------------------------------------------------------------------------
# in / not_in
# ---------------------------------------------------------------------------


def test_in_match() -> None:
    assert apply_operator("in", "county", ["state", "county"]) is True


def test_in_non_match() -> None:
    assert apply_operator("in", "federal", ["state", "county"]) is False


def test_in_missing_is_non_match() -> None:
    assert apply_operator("in", MISSING, ["state"]) is False


def test_in_non_list_value_raises() -> None:
    with pytest.raises(OperatorError):
        apply_operator("in", "x", "not-a-list")


def test_not_in_match() -> None:
    assert apply_operator("not_in", "federal", ["state", "county"]) is True


def test_not_in_non_match() -> None:
    assert apply_operator("not_in", "county", ["state", "county"]) is False


def test_not_in_missing_is_non_match() -> None:
    # Even not_in: a MISSING actual is a non-match (False), never True.
    assert apply_operator("not_in", MISSING, ["state"]) is False


def test_not_in_non_list_value_raises() -> None:
    with pytest.raises(OperatorError):
        apply_operator("not_in", "x", 5)


# ---------------------------------------------------------------------------
# Dispatch / introspection
# ---------------------------------------------------------------------------


def test_unknown_operator_raises() -> None:
    with pytest.raises(OperatorError):
        apply_operator("~=", 1, 1)


def test_operator_keys_are_the_eleven_spec_operators() -> None:
    assert set(OPERATOR_KEYS) == {
        "=",
        "!=",
        ">",
        ">=",
        "<",
        "<=",
        "contains",
        "intersects",
        "exists",
        "in",
        "not_in",
    }


def test_is_known_operator() -> None:
    assert is_known_operator("intersects") is True
    assert is_known_operator("nope") is False


def test_comparison_operators_are_numeric_and_equality_only() -> None:
    # These are the operators the explainer lifts into applicable_thresholds.
    assert set(comparison_operators()) == {">", ">=", "<", "<=", "=", "!="}
