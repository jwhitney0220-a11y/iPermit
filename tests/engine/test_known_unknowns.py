"""Tests for known-unknown detection (T03-06).

Covers:
- Authored known_unknowns are surfaced verbatim.
- Tier-3 rule → low_confidence item.
- Fired rule that matched via a MISSING/defaulted field → missing_input item.
- Deterministic ordering across repeated calls.
- Advisory-compliant wording (no prohibited certainty language).
"""

from __future__ import annotations

from typing import Any

from ipermit_engine import ProjectContext, evaluate_rule
from ipermit_engine.known_unknowns import KnownUnknownItem, collect_known_unknowns

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

_PROHIBITED_PHRASES = (
    "guaranteed",
    "complete permit certainty",
    "final regulatory determination",
    "legal compliance certification",
    "no further review required",
    "agency approval guaranteed",
)

_JX = "us-federal"
_TYPES = ["linear_general"]


def _base_rule(**overrides: Any) -> dict[str, Any]:
    """Minimal valid rule dict that fires when project.flag = True."""
    rule: dict[str, Any] = {
        "rule_id": "test-rule",
        "jurisdiction_id": _JX,
        "applicable_project_types": _TYPES,
        "confidence_tier": 1,
        "triggers": {
            "field": "project.flag",
            "operator": "=",
            "value": True,
        },
    }
    rule.update(overrides)
    return rule


def _fire(rule: dict[str, Any], ctx: ProjectContext) -> Any:
    """Evaluate the rule and assert it fired; return the RuleEvaluation."""
    result = evaluate_rule(rule, ctx, [_JX], _TYPES)
    assert result.fired, f"Expected rule to fire; detail: {result.detail!r}"
    return result


# ---------------------------------------------------------------------------
# Test: authored known_unknowns surfaced verbatim
# ---------------------------------------------------------------------------


def test_authored_known_unknowns_surfaced() -> None:
    rule = _base_rule(
        known_unknowns=[
            "Jurisdictional determination required.",
            "NWP eligibility depends on impact thresholds.",
        ]
    )
    ctx = ProjectContext({"project.flag": True})
    result = _fire(rule, ctx)
    items = collect_known_unknowns(result, rule)

    authored = [i for i in items if i.category == "authored"]
    assert len(authored) == 2
    texts = {i.text for i in authored}
    assert "Jurisdictional determination required." in texts
    assert "NWP eligibility depends on impact thresholds." in texts


def test_no_authored_known_unknowns_when_field_absent() -> None:
    rule = _base_rule()  # no known_unknowns key
    ctx = ProjectContext({"project.flag": True})
    result = _fire(rule, ctx)
    items = collect_known_unknowns(result, rule)
    authored = [i for i in items if i.category == "authored"]
    assert authored == []


def test_empty_authored_known_unknowns_produces_no_items() -> None:
    rule = _base_rule(known_unknowns=[])
    ctx = ProjectContext({"project.flag": True})
    result = _fire(rule, ctx)
    items = collect_known_unknowns(result, rule)
    authored = [i for i in items if i.category == "authored"]
    assert authored == []


# ---------------------------------------------------------------------------
# Test: Tier-3 rule → low_confidence item
# ---------------------------------------------------------------------------


def test_tier3_rule_produces_low_confidence_item() -> None:
    rule = _base_rule(confidence_tier=3)
    ctx = ProjectContext({"project.flag": True})
    result = _fire(rule, ctx)
    items = collect_known_unknowns(result, rule)

    low = [i for i in items if i.category == "low_confidence"]
    assert len(low) == 1
    assert "informational" in low[0].text.lower()
    assert "additional review recommended" in low[0].text.lower()


def test_tier1_rule_no_low_confidence_item() -> None:
    rule = _base_rule(confidence_tier=1)
    ctx = ProjectContext({"project.flag": True})
    result = _fire(rule, ctx)
    items = collect_known_unknowns(result, rule)
    low = [i for i in items if i.category == "low_confidence"]
    assert low == []


def test_tier2_rule_no_low_confidence_item() -> None:
    rule = _base_rule(confidence_tier=2)
    ctx = ProjectContext({"project.flag": True})
    result = _fire(rule, ctx)
    items = collect_known_unknowns(result, rule)
    low = [i for i in items if i.category == "low_confidence"]
    assert low == []


# ---------------------------------------------------------------------------
# Test: fired via MISSING field → missing_input item
# ---------------------------------------------------------------------------


def test_missing_field_produces_missing_input_item() -> None:
    """Rule fires on one branch; another branch evaluated against MISSING."""
    rule = _base_rule(
        triggers={
            "any": [
                {"field": "project.flag", "operator": "=", "value": True},
                {"field": "project.unset_field", "operator": "=", "value": 99},
            ]
        }
    )
    # Only project.flag is supplied; project.unset_field is MISSING.
    ctx = ProjectContext({"project.flag": True})
    result = _fire(rule, ctx)
    items = collect_known_unknowns(result, rule)

    missing = [i for i in items if i.category == "missing_input"]
    assert len(missing) == 1
    assert "project.unset_field" in missing[0].text
    assert "additional review recommended" in missing[0].text.lower()


def test_no_missing_input_when_all_fields_supplied() -> None:
    rule = _base_rule()
    ctx = ProjectContext({"project.flag": True})
    result = _fire(rule, ctx)
    items = collect_known_unknowns(result, rule)
    missing = [i for i in items if i.category == "missing_input"]
    assert missing == []


def test_nested_missing_field_detected() -> None:
    """MISSING field inside nested all/any is detected."""
    rule = _base_rule(
        triggers={
            "all": [
                {"field": "project.flag", "operator": "=", "value": True},
                {
                    "any": [
                        {
                            "field": "project.deep_missing",
                            "operator": "=",
                            "value": 1,
                        },
                        {"field": "project.flag", "operator": "=", "value": True},
                    ]
                },
            ]
        }
    )
    ctx = ProjectContext({"project.flag": True})
    result = _fire(rule, ctx)
    items = collect_known_unknowns(result, rule)
    missing_texts = {i.text for i in items if i.category == "missing_input"}
    assert any("project.deep_missing" in t for t in missing_texts)


# ---------------------------------------------------------------------------
# Test: discretionary advisory language → discretionary item
# ---------------------------------------------------------------------------


def test_discretionary_advisory_produces_discretionary_item() -> None:
    rule = _base_rule(
        advisories=["Implementation may vary by local district interpretation."]
    )
    ctx = ProjectContext({"project.flag": True})
    result = _fire(rule, ctx)
    items = collect_known_unknowns(result, rule)

    disc = [i for i in items if i.category == "discretionary"]
    assert len(disc) == 1
    assert "agency coordination recommended" in disc[0].text.lower()


def test_no_discretionary_item_for_plain_advisory() -> None:
    rule = _base_rule(advisories=["Submit to USACE district office."])
    ctx = ProjectContext({"project.flag": True})
    result = _fire(rule, ctx)
    items = collect_known_unknowns(result, rule)
    disc = [i for i in items if i.category == "discretionary"]
    assert disc == []


# ---------------------------------------------------------------------------
# Test: deterministic ordering
# ---------------------------------------------------------------------------


def test_output_is_deterministically_sorted() -> None:
    """Two identical calls return the same ordered list."""
    rule = _base_rule(
        confidence_tier=3,
        known_unknowns=["Beta uncertainty.", "Alpha uncertainty."],
        advisories=["Implementation may vary."],
        triggers={
            "any": [
                {"field": "project.flag", "operator": "=", "value": True},
                {"field": "project.missing_one", "operator": "=", "value": 1},
            ]
        },
    )
    ctx = ProjectContext({"project.flag": True})
    result = _fire(rule, ctx)

    items_a = collect_known_unknowns(result, rule)
    items_b = collect_known_unknowns(result, rule)
    assert items_a == items_b
    # Verify sorted by (category, text) — "authored" < "discretionary" < "low_confidence" < "missing_input"
    assert items_a == sorted(items_a)


def test_ordering_is_by_category_then_text() -> None:
    """Items sort authored < discretionary < low_confidence < missing_input."""
    rule = _base_rule(
        confidence_tier=3,
        known_unknowns=["Z-authored", "A-authored"],
        advisories=["Implementation may vary by local interpretation."],
        triggers={
            "any": [
                {"field": "project.flag", "operator": "=", "value": True},
                {"field": "project.zzz_missing", "operator": "=", "value": 1},
            ]
        },
    )
    ctx = ProjectContext({"project.flag": True})
    result = _fire(rule, ctx)
    items = collect_known_unknowns(result, rule)

    categories_seen = [i.category for i in items]
    # authored items (sorted by text: A before Z) come first
    assert categories_seen[0] == "authored"
    assert categories_seen[1] == "authored"
    assert items[0].text < items[1].text  # "A-authored" < "Z-authored"
    # discretionary before low_confidence
    disc_idx = next(i for i, it in enumerate(items) if it.category == "discretionary")
    low_idx = next(i for i, it in enumerate(items) if it.category == "low_confidence")
    assert disc_idx < low_idx


# ---------------------------------------------------------------------------
# Test: advisory-compliant wording (no prohibited phrases)
# ---------------------------------------------------------------------------


def test_all_detected_items_are_advisory_compliant() -> None:
    """No detected item text should contain prohibited certainty language."""
    rule = _base_rule(
        confidence_tier=3,
        advisories=["Implementation may vary by local interpretation."],
        triggers={
            "any": [
                {"field": "project.flag", "operator": "=", "value": True},
                {"field": "project.absent_field", "operator": "=", "value": 7},
            ]
        },
    )
    ctx = ProjectContext({"project.flag": True})
    result = _fire(rule, ctx)
    items = collect_known_unknowns(result, rule)

    for item in items:
        lower = item.text.lower()
        for phrase in _PROHIBITED_PHRASES:
            assert phrase not in lower, (
                f"Prohibited phrase {phrase!r} found in item text: {item.text!r}"
            )


def test_authored_items_use_verbatim_text() -> None:
    """Authored known_unknowns texts are not modified or filtered."""
    authored_text = "Coordinate with USACE before assuming NWP eligibility applies."
    rule = _base_rule(known_unknowns=[authored_text])
    ctx = ProjectContext({"project.flag": True})
    result = _fire(rule, ctx)
    items = collect_known_unknowns(result, rule)
    authored = [i for i in items if i.category == "authored"]
    assert authored[0].text == authored_text


# ---------------------------------------------------------------------------
# Test: KnownUnknownItem dataclass properties
# ---------------------------------------------------------------------------


def test_known_unknown_item_is_hashable_and_deduplicates() -> None:
    """KnownUnknownItem is frozen and hashable; sets deduplicate correctly."""
    a = KnownUnknownItem(category="authored", text="Same text.")
    b = KnownUnknownItem(category="authored", text="Same text.")
    assert a == b
    assert len({a, b}) == 1


def test_known_unknown_item_ordering() -> None:
    """Items sort by (category, text) via dataclass order=True."""
    x = KnownUnknownItem(category="authored", text="B")
    y = KnownUnknownItem(category="authored", text="A")
    z = KnownUnknownItem(category="low_confidence", text="A")
    assert y < x  # same category, text A < B
    assert x < z  # authored < low_confidence
