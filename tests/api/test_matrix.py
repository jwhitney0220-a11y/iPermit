"""Unit test for the permit-matrix builder (S01-04).

Asserts that ``build_permit_matrix`` output conforms to permit-matrix.schema.json
and carries the mandatory liability fields (advisories, confidence) per permit.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml
from ipermit_api.matrix import build_permit_matrix
from ipermit_engine import ProjectContext, simulate_project
from ipermit_gis.confirmation import confirm_detection, to_engine_inputs
from ipermit_gis.detection import MANUAL, DetectedJurisdiction, SpatialDetection
from ipermit_rules import load_rules

ROOT = Path(__file__).resolve().parents[2]
_SCHEMA = json.loads(
    (ROOT / "docs/specs/schemas/permit-matrix.schema.json").read_text()
)
_BENCHMARK = (
    ROOT
    / "packages/benchmark-projects/benchmarks"
    / "federal-nexus-transmission-stream-crossing.yaml"
)
_LEVELS = {"us": ("federal", "United States"), "us-tx": ("state", "Texas")}


def _matrix() -> dict:
    bm = yaml.safe_load(_BENCHMARK.read_text())
    inp = bm["project_inputs"]
    ctx = inp["engine_context"]
    when = bm["evaluation_date"]
    detection = SpatialDetection(
        detected_at=when,
        jurisdictions=tuple(
            DetectedJurisdiction(jid, _LEVELS[jid][0], _LEVELS[jid][1], MANUAL)
            for jid in inp["applicable_jurisdiction_ids"]
        ),
        overlays=ctx.get("geometry", {}),
    )
    engine_inputs = to_engine_inputs(confirm_detection(detection))
    flat = {f"project.{k}": v for k, v in ctx.get("project", {}).items()}
    flat.update(engine_inputs.geometry)
    flat.update({f"derived.{k}": v for k, v in ctx.get("derived", {}).items()})
    sim = simulate_project(
        rules=[r.data for r in load_rules(statuses=("draft",))],
        context=ProjectContext(flat),
        applicable_jurisdiction_ids=engine_inputs.applicable_jurisdiction_ids,
        project_types=[inp["project_type"]],
        jurisdiction_chain=engine_inputs.jurisdiction_chain,
        evaluation_date=when,
    )
    return build_permit_matrix(sim, evaluation_id="e1", project_id="p1")


def test_matrix_conforms_to_schema() -> None:
    matrix = _matrix()
    jsonschema.Draft202012Validator(_SCHEMA).validate(matrix)


def test_every_permit_carries_liability_fields() -> None:
    matrix = _matrix()
    assert len(matrix["permits"]) == 5
    for permit in matrix["permits"]:
        assert permit["advisories"], "advisory is mandatory (T07-03)"
        assert permit["confidence"]["tier"] in (1, 2, 3)
        assert permit["citations"]


def test_matrix_is_deterministic() -> None:
    assert _matrix() == _matrix()
