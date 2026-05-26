"""Permit-matrix builder (S01-04, ADR-0003 contract 3, roadmap T07-01).

Aggregates a deterministic :class:`~ipermit_engine.simulation.SimulationResult`
into the consultant-facing permit matrix: an ordered set of likely permits, each
carrying — non-negotiably — its confidence tier, citations, advisories, and a
reference to its explanation record (ADR-0003). Sequencing data (T00-04) rides
alongside.

The liability framework (T07-03) is enforced structurally: every permit's
``advisories`` is copied from the explanation record, which always contains the
standing platform disclaimer (T00-05 §4.4). A permit with zero advisories is a
contract violation and fails permit-matrix.schema.json's ``minItems: 1``.

Pure and deterministic: no clocks, sorted output, byte-stable for identical input.
"""

from __future__ import annotations

from typing import Any

from ipermit_engine.conflict import precedence_rank
from ipermit_engine.simulation import SimulationResult

SCHEMA_VERSION = "1.0.0"


def _sequencing_index(sim: SimulationResult) -> dict[str, dict[str, Any]]:
    """Map each fired rule_id to its stage index and critical-path flag."""
    index: dict[str, dict[str, Any]] = {}
    for stage in sim.sequencing.stages:
        for permit in stage.permits:
            index[permit.rule_id] = {
                "stage_index": stage.stage_index,
                "on_critical_path": permit.on_critical_path,
            }
    return index


def _permit_entry(
    rule: dict[str, Any],
    explanation: dict[str, Any],
    permit: dict[str, Any],
    sequencing: dict[str, Any],
) -> dict[str, Any]:
    """Build one permit row from its rule, explanation, and sequencing."""
    return {
        "rule_id": rule["rule_id"],
        "permit_name": permit["name"],
        "agency": permit["agency"],
        "jurisdiction_level": rule.get("jurisdiction_level", "special"),
        "confidence": explanation["confidence"],
        "citations": explanation["citations"],
        "advisories": explanation["advisories"],
        "known_unknowns": explanation["known_unknowns"],
        "sequencing": sequencing.get(
            rule["rule_id"], {"stage_index": 0, "on_critical_path": False}
        ),
        "explanation_ref": {
            "rule_id": rule["rule_id"],
            "rule_version": rule["version"],
            "inputs_hash": explanation["reproducibility"]["inputs_hash"],
            "ruleset_content_hash": explanation["ruleset_version"]["content_hash"],
        },
    }


def _permits(sim: SimulationResult) -> list[dict[str, Any]]:
    """Build and deterministically order the permit rows."""
    sequencing = _sequencing_index(sim)
    rows: list[dict[str, Any]] = []
    for rule, explanation in zip(sim.fired_rules, sim.explanations, strict=True):
        for permit in rule.get("outputs", {}).get("permits", []):
            rows.append(_permit_entry(rule, explanation, permit, sequencing))
    rows.sort(
        key=lambda r: (
            r["sequencing"]["stage_index"],
            precedence_rank(r["jurisdiction_level"]),
            r["permit_name"],
        )
    )
    return rows


def _sequencing_summary(sim: SimulationResult) -> dict[str, Any]:
    """Summarise the dependency sequencing for the matrix."""
    return {
        "stages": [
            {
                "stage_index": stage.stage_index,
                "permits": [p.rule_id for p in stage.permits],
            }
            for stage in sim.sequencing.stages
        ],
        "critical_path": list(sim.sequencing.critical_path),
        "critical_path_total_days": sim.sequencing.critical_path_total_days,
    }


def build_permit_matrix(
    sim: SimulationResult, *, evaluation_id: str, project_id: str
) -> dict[str, Any]:
    """Aggregate a simulation result into the permit-matrix payload (T07-01)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluation_id": evaluation_id,
        "project_id": project_id,
        "evaluation_date": sim.evaluation_date,
        "ruleset_version": dict(sim.ruleset_version),
        "inputs_hash": sim.inputs_hash,
        "permits": _permits(sim),
        "sequencing": _sequencing_summary(sim),
    }
