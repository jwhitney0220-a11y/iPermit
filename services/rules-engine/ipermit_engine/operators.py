"""The eleven trigger operators of the rules engine (T03-01).

Each operator is a deterministic, type-aware predicate over a single context
value (the *actual* value at a field path) and the rule's *expected* ``value``.
Operators come from the rule-object spec §7; the symbol strings are the public
keys, matching the JSON Schema's operator enum verbatim.

Two cross-cutting contracts apply to every operator:

1. **MISSING is never a crash.** When the context did not supply the field,
   the actual value is :data:`~ipermit_engine.context.MISSING`. Every operator
   returns ``False`` for a MISSING actual (a non-match), including ``exists``.
   Operators never raise on absent input.

2. **Type mismatches on a *present* value raise** :class:`OperatorError`.
   A genuinely incompatible operand — e.g. ``>`` applied to a boolean, or
   ``in`` whose ``value`` is not a list — is a rule-authoring or data error the
   engine should surface, not silently swallow. The distinction matters: a
   missing input is an expected runtime condition; a type mismatch on a value
   that *is* present is a defect.

``exists`` is the sole operator that ignores ``value`` and inspects only
whether the field is present and non-null.

Booleans are deliberately rejected by the ordered comparison operators
(``>``, ``>=``, ``<``, ``<=``) even though Python treats ``bool`` as ``int``:
the spec scopes those operators to numbers and dates, and ordering booleans is
almost always an authoring mistake.
"""

from __future__ import annotations

import datetime
from collections.abc import Callable, Sequence
from typing import Any

from .context import MISSING

#: Public operator symbols, in spec §7 order. Used to validate rule operators.
OPERATOR_KEYS: tuple[str, ...] = (
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
)


class OperatorError(ValueError):
    """Raised when an operator is applied to a genuinely incompatible operand.

    This is distinct from a non-match. A non-match (including a MISSING field)
    returns ``False``; an OperatorError signals a rule/data defect — e.g.
    ordering a boolean, or an ``in`` whose ``value`` is not a list.
    """


# Types the ordered comparison operators accept. ``bool`` is excluded on
# purpose (see module docstring) even though it subclasses ``int``.
_ORDERED_TYPES = (int, float, datetime.date)


def _is_ordered(value: Any) -> bool:
    """Return True if *value* is a number or date the engine can order."""
    return isinstance(value, _ORDERED_TYPES) and not isinstance(value, bool)


def _check_ordered(operator: str, actual: Any, expected: Any) -> None:
    """Raise OperatorError unless both operands are orderable and comparable."""
    if not _is_ordered(actual):
        raise OperatorError(
            f"operator {operator!r} requires a number or date on the left; "
            f"got {type(actual).__name__}"
        )
    if not _is_ordered(expected):
        raise OperatorError(
            f"operator {operator!r} requires a number or date value; "
            f"got {type(expected).__name__}"
        )
    # A date compared against a number (or vice versa) is incomparable.
    actual_is_date = isinstance(actual, datetime.date)
    expected_is_date = isinstance(expected, datetime.date)
    if actual_is_date != expected_is_date:
        raise OperatorError(
            f"operator {operator!r} cannot compare "
            f"{type(actual).__name__} with {type(expected).__name__}"
        )


def op_eq(actual: Any, expected: Any) -> bool:
    """``=`` — scalar equality. Exact value match (no coercion)."""
    return actual == expected


def op_ne(actual: Any, expected: Any) -> bool:
    """``!=`` — scalar inequality. True when values differ."""
    return actual != expected


def op_gt(actual: Any, expected: Any) -> bool:
    """``>`` — strictly greater than (numbers or dates only)."""
    _check_ordered(">", actual, expected)
    return actual > expected


def op_ge(actual: Any, expected: Any) -> bool:
    """``>=`` — greater than or equal (numbers or dates only)."""
    _check_ordered(">=", actual, expected)
    return actual >= expected


def op_lt(actual: Any, expected: Any) -> bool:
    """``<`` — strictly less than (numbers or dates only)."""
    _check_ordered("<", actual, expected)
    return actual < expected


def op_le(actual: Any, expected: Any) -> bool:
    """``<=`` — less than or equal (numbers or dates only)."""
    _check_ordered("<=", actual, expected)
    return actual <= expected


def op_contains(actual: Any, expected: Any) -> bool:
    """``contains`` — substring (string actual) or membership (list actual).

    For a string field, ``expected`` must be a string and is matched as a
    substring. For a list/tuple field, ``expected`` is matched as an element.
    Any other actual type raises :class:`OperatorError`.
    """
    if isinstance(actual, str):
        if not isinstance(expected, str):
            raise OperatorError(
                "operator 'contains' on a string requires a string value; "
                f"got {type(expected).__name__}"
            )
        return expected in actual
    if isinstance(actual, (list, tuple)):
        return expected in actual
    raise OperatorError(
        "operator 'contains' requires a string or list on the left; "
        f"got {type(actual).__name__}"
    )


def op_intersects(actual: Any, expected: Any) -> bool:
    """``intersects`` — non-empty overlap between two lists.

    Both operands must be sequences (list/tuple); returns True when they share
    at least one element. Used for spatial overlay checks against detected
    jurisdiction/geometry IDs. A non-sequence operand raises
    :class:`OperatorError`.
    """
    if not _is_seq(actual):
        raise OperatorError(
            "operator 'intersects' requires a list on the left; "
            f"got {type(actual).__name__}"
        )
    if not _is_seq(expected):
        raise OperatorError(
            "operator 'intersects' requires a list value; "
            f"got {type(expected).__name__}"
        )
    return bool(set(actual) & set(expected))


def op_exists(actual: Any, _expected: Any = None) -> bool:
    """``exists`` — field is present and non-null. Ignores ``value`` entirely.

    Returns False for both a MISSING field and a present-but-``None`` field;
    True for any other present value (including falsy values like ``0``,
    ``""``, ``[]``).
    """
    return actual is not MISSING and actual is not None


def op_in(actual: Any, expected: Any) -> bool:
    """``in`` — actual is one of the elements in the ``value`` list."""
    if not _is_seq(expected):
        raise OperatorError(
            f"operator 'in' requires a list value; got {type(expected).__name__}"
        )
    return actual in expected


def op_not_in(actual: Any, expected: Any) -> bool:
    """``not_in`` — actual is none of the elements in the ``value`` list."""
    if not _is_seq(expected):
        raise OperatorError(
            f"operator 'not_in' requires a list value; got {type(expected).__name__}"
        )
    return actual not in expected


def _is_seq(value: Any) -> bool:
    """Return True for list/tuple sequences (strings are not treated as lists)."""
    return isinstance(value, (list, tuple))


# Operator symbol -> implementation. The single source of truth the trigger
# evaluator dispatches through; kept in spec §7 order for readability.
_OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    "=": op_eq,
    "!=": op_ne,
    ">": op_gt,
    ">=": op_ge,
    "<": op_lt,
    "<=": op_le,
    "contains": op_contains,
    "intersects": op_intersects,
    "exists": op_exists,
    "in": op_in,
    "not_in": op_not_in,
}

#: Operators that do not read the rule's ``value`` field.
VALUELESS_OPERATORS: frozenset[str] = frozenset({"exists"})


def apply_operator(operator: str, actual: Any, expected: Any) -> bool:
    """Evaluate one operator against an actual and expected value.

    Enforces the cross-cutting contracts: a MISSING actual is a non-match for
    every operator (False); a present but type-incompatible operand raises
    :class:`OperatorError`.

    Args:
        operator: One of :data:`OPERATOR_KEYS`.
        actual: The context value (or :data:`MISSING` when the field is absent).
        expected: The rule's ``value`` (ignored for ``exists``).

    Returns:
        The boolean match result.

    Raises:
        OperatorError: if *operator* is unknown, or the operands are present but
            incompatible with the operator.
    """
    func = _OPERATORS.get(operator)
    if func is None:
        raise OperatorError(f"unknown operator {operator!r}")
    if operator == "exists":
        return op_exists(actual)
    if actual is MISSING:
        # Absent inputs never match (and never crash) for value operators.
        return False
    return func(actual, expected)


def is_known_operator(operator: str) -> bool:
    """Return True if *operator* is one of the eleven supported symbols."""
    return operator in _OPERATORS


def comparison_operators() -> Sequence[str]:
    """Return the numeric/date comparison operators (for threshold lifting)."""
    return (">", ">=", "<", "<=", "=", "!=")
