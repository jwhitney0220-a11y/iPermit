"""Tests for the GIS auto-detection review & confirmation workflow (T05-06)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from ipermit_engine import ProjectContext, simulate_project
from ipermit_gis import (
    DetectedJurisdiction,
    JurisdictionOverride,
    OverlayOverride,
    SpatialDetection,
    confirm_detection,
    to_engine_inputs,
)
from ipermit_rules import load_rules


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "docs" / "specs" / "schemas").is_dir():
            return parent
    raise FileNotFoundError("repo root not found")


def _detection() -> SpatialDetection:
    return SpatialDetection(
        detected_at="2026-05-26",
        footprint_ref="upload/x.kmz",
        jurisdictions=(
            DetectedJurisdiction("us", "federal", "United States"),
            DetectedJurisdiction("us-tx", "state", "Texas"),
            DetectedJurisdiction(
                "us-tx-county-travis", "county", "Travis County, Texas"
            ),
        ),
        overlays={"fema_floodplain": True, "wetlands_present": True},
    )


# ---------------------------------------------------------------------------
# Schema conformance + round trip
# ---------------------------------------------------------------------------


def test_example_validates_against_schema() -> None:
    root = _repo_root()
    schema = json.loads(
        (root / "docs/specs/schemas/spatial-detection.schema.json").read_text()
    )
    example = json.loads(
        (root / "docs/specs/examples/spatial-detection-example.json").read_text()
    )
    jsonschema.Draft202012Validator(schema).validate(example)


def test_detection_round_trips_through_dict() -> None:
    detection = _detection()
    assert SpatialDetection.from_dict(detection.to_dict()) == detection


# ---------------------------------------------------------------------------
# Confirmation: overrides, logging, original preservation
# ---------------------------------------------------------------------------


def test_confirm_without_overrides_preserves_detection() -> None:
    result = confirm_detection(_detection())
    assert result.override_log == ()
    assert {j.jurisdiction_id for j in result.jurisdictions} == {
        "us",
        "us-tx",
        "us-tx-county-travis",
    }


def test_confirm_logs_and_applies_overrides() -> None:
    result = confirm_detection(
        _detection(),
        jurisdiction_overrides=(
            JurisdictionOverride("remove", "us-tx-county-travis"),
            JurisdictionOverride(
                "add",
                "us-tx-municipality-austin",
                "municipality",
                "City of Austin, Texas",
            ),
        ),
        overlay_overrides=(OverlayOverride("set", "fema_floodplain", False),),
    )
    ids = {j.jurisdiction_id for j in result.jurisdictions}
    assert "us-tx-county-travis" not in ids
    assert "us-tx-municipality-austin" in ids
    assert result.overlays["fema_floodplain"] is False
    # original detection is untouched
    assert any(
        j.jurisdiction_id == "us-tx-county-travis"
        for j in result.original.jurisdictions
    )
    assert {e.action for e in result.override_log} == {"remove", "add", "set"}


def test_added_jurisdiction_marked_user_override() -> None:
    result = confirm_detection(
        _detection(),
        jurisdiction_overrides=(
            JurisdictionOverride("add", "us-tx-etj-austin", "etj", "Austin ETJ"),
        ),
    )
    added = next(
        j for j in result.jurisdictions if j.jurisdiction_id == "us-tx-etj-austin"
    )
    assert added.detection_source == "user_override"


def test_unknown_override_action_raises() -> None:
    with pytest.raises(ValueError, match="unknown jurisdiction override action"):
        confirm_detection(
            _detection(),
            jurisdiction_overrides=(JurisdictionOverride("frobnicate", "us"),),
        )


def test_manual_entry_fallback_from_empty_detection() -> None:
    empty = SpatialDetection(detected_at="2026-05-26")
    result = confirm_detection(
        empty,
        jurisdiction_overrides=(
            JurisdictionOverride("add", "us-tx", "state", "Texas"),
        ),
        overlay_overrides=(OverlayOverride("set", "wetlands_present", True),),
    )
    assert [j.jurisdiction_id for j in result.jurisdictions] == ["us-tx"]
    assert result.overlays == {"wetlands_present": True}


# ---------------------------------------------------------------------------
# Projection into engine inputs (closing the loop)
# ---------------------------------------------------------------------------


def test_to_engine_inputs_orders_chain_and_namespaces_overlays() -> None:
    inputs = to_engine_inputs(confirm_detection(_detection()))
    assert inputs.applicable_jurisdiction_ids == ("us", "us-tx", "us-tx-county-travis")
    assert [c["jurisdiction_level"] for c in inputs.jurisdiction_chain] == [
        "federal",
        "state",
        "county",
    ]
    assert inputs.geometry == {
        "geometry.fema_floodplain": True,
        "geometry.wetlands_present": True,
    }
    # chain detection_source maps into the permit-explanation enum
    assert {c["detection_source"] for c in inputs.jurisdiction_chain} == {
        "gis_auto_detect"
    }


def test_engine_inputs_drive_a_simulation() -> None:
    """Confirmed GIS detection feeds simulate_project end to end."""
    detection = SpatialDetection(
        detected_at="2026-05-25",
        jurisdictions=(
            DetectedJurisdiction("us", "federal", "United States"),
            DetectedJurisdiction("us-tx", "state", "Texas"),
        ),
        overlays={"wetlands_present": True, "waters_of_us_present": True},
    )
    inputs = to_engine_inputs(confirm_detection(detection))
    rules = [r.data for r in load_rules()]
    project = {
        "federal_nexus": True,
        "dredge_or_fill_in_waters": True,
        "stream_crossings_count": 1,
    }
    sim = simulate_project(
        rules=rules,
        context=ProjectContext.from_namespaces(
            project=project,
            geometry={
                k.removeprefix("geometry."): v for k, v in inputs.geometry.items()
            },
            derived={"major_federal_action": True, "may_affect_listed_species": True},
        ),
        applicable_jurisdiction_ids=inputs.applicable_jurisdiction_ids,
        project_types=["transmission_line"],
        jurisdiction_chain=inputs.jurisdiction_chain,
        evaluation_date="2026-05-25",
    )
    fired = {e.rule_id for e in sim.fired}
    assert "us-tx-usace-section-404-da-permit" in fired
