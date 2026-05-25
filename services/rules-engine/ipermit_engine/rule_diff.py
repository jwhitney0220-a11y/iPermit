"""Rule diff and change analysis for iPermit (T04-04).

Generates explainable, structured comparisons between two versions of the same
rule object (T00-01 shape).  Pure and DB-free — both inputs are plain dicts.

Covers:
- Field-level changes (title, permit_name/permit_code, confidence_tier, status,
  effective dates, applicable_project_types, jurisdiction fields, source_agency).
- Trigger-tree structural diff (added/removed/modified conditions, recursive).
- Output changes (permits, forms, agencies added or removed).
- Jurisdiction impact (jurisdiction_level / jurisdiction_id changes).
- Provenance changes (citation additions/removals).
Each change carries a plain-language ``description``.

Public API::

    diff = diff_rules(old_rule, new_rule)
    summary = summarize_diff(diff)

Determinism
-----------
All collection output is sorted by stable keys; equal inputs always produce an
identical :class:`RuleDiff` instance (T00-05 reproducibility contract).

Out of scope: simulation comparison (T04-01), benchmark regression (T04-02),
edge-case detection (T04-03), QA aggregation (T04-05).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldChange:
    """A single scalar-field change between two rule versions."""

    field_name: str
    old_value: Any
    new_value: Any
    description: str


@dataclass(frozen=True)
class TriggerChange:
    """A change detected within the trigger tree."""

    kind: str  # "added" | "removed" | "modified"
    path: str  # e.g. "all[0].any[1].field"
    old_node: dict[str, Any] | None
    new_node: dict[str, Any] | None
    description: str


@dataclass(frozen=True)
class OutputChange:
    """An item added to or removed from the rule's outputs."""

    kind: str  # "added" | "removed"
    output_type: str  # "permit" | "form" | "agency"
    item_key: str  # stable identifier for the item
    description: str


@dataclass(frozen=True)
class JurisdictionChange:
    """Change to jurisdiction_level or jurisdiction_id."""

    field_name: str
    old_value: str | None
    new_value: str | None
    description: str


@dataclass(frozen=True)
class CitationChange:
    """A citation added to or removed from provenance.source_citations."""

    kind: str  # "added" | "removed"
    reference: str
    description: str


@dataclass(frozen=True)
class RuleDiff:
    """Complete, structured, explainable diff between two versions of a rule."""

    rule_id: str
    old_version: str
    new_version: str
    field_changes: tuple[FieldChange, ...]
    trigger_changes: tuple[TriggerChange, ...]
    output_changes: tuple[OutputChange, ...]
    jurisdiction_changes: tuple[JurisdictionChange, ...]
    citation_changes: tuple[CitationChange, ...]

    @property
    def is_empty(self) -> bool:
        """True when no differences were found between the two rule versions."""
        return (
            not self.field_changes
            and not self.trigger_changes
            and not self.output_changes
            and not self.jurisdiction_changes
            and not self.citation_changes
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def diff_rules(old_rule: dict[str, Any], new_rule: dict[str, Any]) -> RuleDiff:
    """Compare two versions of the same rule and return a structured RuleDiff.

    Both arguments must be valid rule-object dicts (T00-01 shape) sharing the
    same ``rule_id``.  The comparison is purely structural — this function
    inspects rule definitions, not evaluation outputs.

    Args:
        old_rule: The earlier version of the rule dict.
        new_rule: The later version of the rule dict.

    Returns:
        A :class:`RuleDiff` summarising every detected difference with a
        plain-language description on each change.

    Raises:
        ValueError: if ``old_rule`` and ``new_rule`` have different ``rule_id``s.
    """
    old_id = old_rule.get("rule_id", "")
    new_id = new_rule.get("rule_id", "")
    if old_id != new_id:
        raise ValueError(
            f"diff_rules requires both rules to share the same rule_id; "
            f"got {old_id!r} vs {new_id!r}"
        )

    return RuleDiff(
        rule_id=old_id,
        old_version=old_rule.get("version", ""),
        new_version=new_rule.get("version", ""),
        field_changes=tuple(_diff_fields(old_rule, new_rule)),
        trigger_changes=tuple(_diff_triggers(old_rule, new_rule)),
        output_changes=tuple(_diff_outputs(old_rule, new_rule)),
        jurisdiction_changes=tuple(_diff_jurisdiction(old_rule, new_rule)),
        citation_changes=tuple(_diff_citations(old_rule, new_rule)),
    )


def summarize_diff(rule_diff: RuleDiff) -> str:
    """Return a short human-readable summary of a RuleDiff for analyst review.

    The summary is a multi-line string suitable for PR comments or analyst logs.
    It lists each category of changes with counts and highlights the first few
    items in each category.

    Args:
        rule_diff: A :class:`RuleDiff` produced by :func:`diff_rules`.

    Returns:
        A plain-text summary string.
    """
    if rule_diff.is_empty:
        return (
            f"Rule {rule_diff.rule_id!r}: no changes detected between "
            f"v{rule_diff.old_version} and v{rule_diff.new_version}."
        )

    lines: list[str] = [
        f"Rule diff: {rule_diff.rule_id!r}  "
        f"v{rule_diff.old_version} → v{rule_diff.new_version}",
        "-" * 60,
    ]

    _append_section(lines, "Field changes", rule_diff.field_changes)
    _append_section(lines, "Trigger changes", rule_diff.trigger_changes)
    _append_section(lines, "Output changes", rule_diff.output_changes)
    _append_section(lines, "Jurisdiction changes", rule_diff.jurisdiction_changes)
    _append_section(lines, "Citation changes", rule_diff.citation_changes)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal: field-level diff
# ---------------------------------------------------------------------------

# Scalar top-level fields covered by the field diff.
_SCALAR_FIELDS: tuple[str, ...] = (
    "title",
    "permit_name",
    "permit_code",
    "confidence_tier",
    "status",
    "effective_from",
    "effective_to",
    "source_agency",
)


def _diff_fields(old: dict[str, Any], new: dict[str, Any]) -> list[FieldChange]:
    """Compare scalar top-level fields and applicable_project_types."""
    changes: list[FieldChange] = []
    for fname in _SCALAR_FIELDS:
        ov, nv = old.get(fname), new.get(fname)
        if ov != nv:
            changes.append(
                FieldChange(
                    field_name=fname,
                    old_value=ov,
                    new_value=nv,
                    description=_scalar_description(fname, ov, nv),
                )
            )

    # applicable_project_types: treat as a set diff
    changes.extend(_diff_project_types(old, new))
    return sorted(changes, key=lambda c: c.field_name)


def _diff_project_types(old: dict[str, Any], new: dict[str, Any]) -> list[FieldChange]:
    """Detect changes in applicable_project_types as a set comparison."""
    old_set = sorted(set(old.get("applicable_project_types") or []))
    new_set = sorted(set(new.get("applicable_project_types") or []))
    if old_set == new_set:
        return []
    added = sorted(set(new_set) - set(old_set))
    removed = sorted(set(old_set) - set(new_set))
    parts: list[str] = []
    if added:
        parts.append(f"added project type(s): {', '.join(added)}")
    if removed:
        parts.append(f"removed project type(s): {', '.join(removed)}")
    return [
        FieldChange(
            field_name="applicable_project_types",
            old_value=old_set,
            new_value=new_set,
            description="; ".join(parts) + ".",
        )
    ]


def _scalar_description(fname: str, old_val: Any, new_val: Any) -> str:
    """Build a plain-language description for a scalar field change."""
    label = fname.replace("_", " ")
    if old_val is None:
        return f"{label} set to {new_val!r}."
    if new_val is None:
        return f"{label} removed (was {old_val!r})."
    return f"{label} changed from {old_val!r} to {new_val!r}."


# ---------------------------------------------------------------------------
# Internal: jurisdiction diff
# ---------------------------------------------------------------------------


def _diff_jurisdiction(
    old: dict[str, Any], new: dict[str, Any]
) -> list[JurisdictionChange]:
    """Compare jurisdiction_level and jurisdiction_id fields."""
    changes: list[JurisdictionChange] = []
    for fname in ("jurisdiction_level", "jurisdiction_id"):
        ov, nv = old.get(fname), new.get(fname)
        if ov != nv:
            label = fname.replace("_", " ")
            if ov is None:
                desc = f"{label} set to {nv!r}."
            elif nv is None:
                desc = f"{label} removed (was {ov!r})."
            else:
                desc = (
                    f"{label} changed from {ov!r} to {nv!r}; "
                    f"this may affect which projects are evaluated under this rule."
                )
            changes.append(
                JurisdictionChange(
                    field_name=fname,
                    old_value=ov,
                    new_value=nv,
                    description=desc,
                )
            )
    return sorted(changes, key=lambda c: c.field_name)


# ---------------------------------------------------------------------------
# Internal: output diff
# ---------------------------------------------------------------------------


def _diff_outputs(old: dict[str, Any], new: dict[str, Any]) -> list[OutputChange]:
    """Detect permits, forms, and agencies added or removed from outputs."""
    changes: list[OutputChange] = []
    old_out = old.get("outputs") or {}
    new_out = new.get("outputs") or {}

    changes.extend(_diff_permit_list(old_out, new_out))
    changes.extend(_diff_form_list(old_out, new_out))
    changes.extend(_diff_agency_list(old_out, new_out))
    return sorted(changes, key=lambda c: (c.output_type, c.kind, c.item_key))


def _permit_item_key(p: dict[str, Any]) -> str:
    """Stable identifier for a permit entry."""
    return "|".join(
        (p.get("agency", ""), p.get("code", ""), p.get("name", ""))
    ).casefold()


def _diff_permit_list(
    old_out: dict[str, Any], new_out: dict[str, Any]
) -> list[OutputChange]:
    """Compare outputs.permits between old and new."""
    old_permits = {_permit_item_key(p): p for p in (old_out.get("permits") or [])}
    new_permits = {_permit_item_key(p): p for p in (new_out.get("permits") or [])}
    changes: list[OutputChange] = []
    for key in sorted(set(new_permits) - set(old_permits)):
        p = new_permits[key]
        changes.append(
            OutputChange(
                kind="added",
                output_type="permit",
                item_key=key,
                description=f"Permit added: {p.get('name')!r} ({p.get('agency')}).",
            )
        )
    for key in sorted(set(old_permits) - set(new_permits)):
        p = old_permits[key]
        changes.append(
            OutputChange(
                kind="removed",
                output_type="permit",
                item_key=key,
                description=f"Permit removed: {p.get('name')!r} ({p.get('agency')}).",
            )
        )
    return changes


def _form_item_key(f: dict[str, Any]) -> str:
    """Stable identifier for a form entry."""
    return (f.get("form_number", "") or f.get("name", "")).casefold()


def _diff_form_list(
    old_out: dict[str, Any], new_out: dict[str, Any]
) -> list[OutputChange]:
    """Compare outputs.forms between old and new."""
    old_forms = {_form_item_key(f): f for f in (old_out.get("forms") or [])}
    new_forms = {_form_item_key(f): f for f in (new_out.get("forms") or [])}
    changes: list[OutputChange] = []
    for key in sorted(set(new_forms) - set(old_forms)):
        fm = new_forms[key]
        changes.append(
            OutputChange(
                kind="added",
                output_type="form",
                item_key=key,
                description=f"Form added: {fm.get('name')!r}.",
            )
        )
    for key in sorted(set(old_forms) - set(new_forms)):
        fm = old_forms[key]
        changes.append(
            OutputChange(
                kind="removed",
                output_type="form",
                item_key=key,
                description=f"Form removed: {fm.get('name')!r}.",
            )
        )
    return changes


def _diff_agency_list(
    old_out: dict[str, Any], new_out: dict[str, Any]
) -> list[OutputChange]:
    """Compare outputs.agencies between old and new."""
    old_agencies = sorted({a.strip() for a in (old_out.get("agencies") or [])})
    new_agencies = sorted({a.strip() for a in (new_out.get("agencies") or [])})
    old_set = {a.casefold(): a for a in old_agencies}
    new_set = {a.casefold(): a for a in new_agencies}
    changes: list[OutputChange] = []
    for key in sorted(set(new_set) - set(old_set)):
        changes.append(
            OutputChange(
                kind="added",
                output_type="agency",
                item_key=key,
                description=f"Agency added: {new_set[key]!r}.",
            )
        )
    for key in sorted(set(old_set) - set(new_set)):
        changes.append(
            OutputChange(
                kind="removed",
                output_type="agency",
                item_key=key,
                description=f"Agency removed: {old_set[key]!r}.",
            )
        )
    return changes


# ---------------------------------------------------------------------------
# Internal: trigger tree diff
# ---------------------------------------------------------------------------


def _diff_triggers(old: dict[str, Any], new: dict[str, Any]) -> list[TriggerChange]:
    """Diff the trigger trees of two rule versions structurally."""
    old_trig = old.get("triggers") or {}
    new_trig = new.get("triggers") or {}
    changes: list[TriggerChange] = []
    _diff_trigger_node(old_trig, new_trig, "triggers", changes)
    return sorted(changes, key=lambda c: (c.path, c.kind))


def _diff_trigger_node(
    old_node: dict[str, Any] | None,
    new_node: dict[str, Any] | None,
    path: str,
    out: list[TriggerChange],
) -> None:
    """Recursively compare two trigger nodes, appending changes to *out*."""
    if old_node is None and new_node is None:
        return
    if old_node is None:
        out.append(_trigger_added(path, new_node))
        return
    if new_node is None:
        out.append(_trigger_removed(path, old_node))
        return

    old_kind = _node_kind(old_node)
    new_kind = _node_kind(new_node)

    # Structure changed: treat as full replacement
    if old_kind != new_kind:
        out.append(
            _trigger_modified(path, old_node, new_node, "trigger structure changed")
        )
        return

    if old_kind == "leaf":
        _diff_leaf(old_node, new_node, path, out)
    elif old_kind in ("all", "any"):
        _diff_composition(old_node, new_node, old_kind, path, out)
    elif old_kind == "not":
        _diff_trigger_node(old_node.get("not"), new_node.get("not"), f"{path}.not", out)


def _node_kind(node: dict[str, Any]) -> str:
    """Identify the kind of a trigger node: leaf | all | any | not."""
    if "field" in node:
        return "leaf"
    if "all" in node:
        return "all"
    if "any" in node:
        return "any"
    if "not" in node:
        return "not"
    return "unknown"


def _diff_leaf(
    old_node: dict[str, Any],
    new_node: dict[str, Any],
    path: str,
    out: list[TriggerChange],
) -> None:
    """Compare two leaf trigger nodes and emit a change if anything differs."""
    if old_node == new_node:
        return
    parts: list[str] = []
    if old_node.get("field") != new_node.get("field"):
        parts.append(
            f"field changed from {old_node.get('field')!r} to {new_node.get('field')!r}"
        )
    if old_node.get("operator") != new_node.get("operator"):
        parts.append(
            f"operator changed from {old_node.get('operator')!r} "
            f"to {new_node.get('operator')!r}"
        )
    if old_node.get("value") != new_node.get("value"):
        parts.append(
            f"threshold changed from {old_node.get('value')!r} "
            f"to {new_node.get('value')!r}"
        )
    desc = "; ".join(parts) + "." if parts else "trigger condition modified."
    out.append(_trigger_modified(path, old_node, new_node, desc))


def _diff_composition(
    old_node: dict[str, Any],
    new_node: dict[str, Any],
    kind: str,
    path: str,
    out: list[TriggerChange],
) -> None:
    """Diff a list-based composition (all/any) child by child."""
    old_children: list[dict[str, Any]] = old_node.get(kind) or []
    new_children: list[dict[str, Any]] = new_node.get(kind) or []
    max_len = max(len(old_children), len(new_children))
    for i in range(max_len):
        child_path = f"{path}.{kind}[{i}]"
        old_child = old_children[i] if i < len(old_children) else None
        new_child = new_children[i] if i < len(new_children) else None
        _diff_trigger_node(old_child, new_child, child_path, out)


# ---------------------------------------------------------------------------
# Trigger change constructors
# ---------------------------------------------------------------------------


def _trigger_added(path: str, node: dict[str, Any] | None) -> TriggerChange:
    """Build a TriggerChange for a newly added trigger node."""
    return TriggerChange(
        kind="added",
        path=path,
        old_node=None,
        new_node=node,
        description=f"Trigger condition added at {path}: {_node_summary(node)}.",
    )


def _trigger_removed(path: str, node: dict[str, Any] | None) -> TriggerChange:
    """Build a TriggerChange for a removed trigger node."""
    return TriggerChange(
        kind="removed",
        path=path,
        old_node=node,
        new_node=None,
        description=f"Trigger condition removed at {path}: {_node_summary(node)}.",
    )


def _trigger_modified(
    path: str,
    old_node: dict[str, Any] | None,
    new_node: dict[str, Any] | None,
    detail: str,
) -> TriggerChange:
    """Build a TriggerChange for a modified trigger node."""
    return TriggerChange(
        kind="modified",
        path=path,
        old_node=old_node,
        new_node=new_node,
        description=f"Trigger modified at {path}: {detail}",
    )


def _node_summary(node: dict[str, Any] | None) -> str:
    """Produce a one-line plain-language description of a trigger node."""
    if node is None:
        return "(empty)"
    if "field" in node:
        op = node.get("operator", "")
        val = node.get("value")
        if val is None:
            return f"{node['field']} {op}"
        return f"{node['field']} {op} {val!r}"
    for key in ("all", "any", "not"):
        if key in node:
            children = node[key]
            n = len(children) if isinstance(children, list) else 1
            return f"{key.upper()} composition of {n} condition(s)"
    return "unknown trigger node"


# ---------------------------------------------------------------------------
# Internal: citation diff
# ---------------------------------------------------------------------------


def _diff_citations(old: dict[str, Any], new: dict[str, Any]) -> list[CitationChange]:
    """Detect citations added or removed in provenance.source_citations."""
    old_cites = {
        c["reference"]: c
        for c in (old.get("provenance") or {}).get("source_citations") or []
    }
    new_cites = {
        c["reference"]: c
        for c in (new.get("provenance") or {}).get("source_citations") or []
    }
    changes: list[CitationChange] = []
    for ref in sorted(set(new_cites) - set(old_cites)):
        ctype = new_cites[ref].get("citation_type", "")
        changes.append(
            CitationChange(
                kind="added",
                reference=ref,
                description=f"Citation added ({ctype}): {ref!r}.",
            )
        )
    for ref in sorted(set(old_cites) - set(new_cites)):
        ctype = old_cites[ref].get("citation_type", "")
        changes.append(
            CitationChange(
                kind="removed",
                reference=ref,
                description=f"Citation removed ({ctype}): {ref!r}.",
            )
        )
    return sorted(changes, key=lambda c: (c.kind, c.reference))


# ---------------------------------------------------------------------------
# Summary helper
# ---------------------------------------------------------------------------


def _append_section(
    lines: list[str],
    title: str,
    changes: tuple[Any, ...],
) -> None:
    """Append a labelled section to the summary line list."""
    if not changes:
        return
    lines.append(f"\n{title} ({len(changes)}):")
    for change in changes:
        lines.append(f"  - {change.description}")
