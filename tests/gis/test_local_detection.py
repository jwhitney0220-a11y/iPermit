"""LocalDetectionBackend tests (SAAS-06, T05-03/T05-04).

Detects Texas jurisdictions from a registered footprint via shapely intersection
against the seeded bbox set. Confirms Protocol compliance and the federal-
always-detected invariant.
"""

from __future__ import annotations

from ipermit_gis import (
    DetectionBackend,
    LocalDetectionBackend,
    build_default_texas_backend,
    get_detection_backend,
)
from shapely.geometry import Point, box


def test_protocol_compliance() -> None:
    backend = build_default_texas_backend()
    assert isinstance(backend, DetectionBackend)
    assert isinstance(backend, LocalDetectionBackend)


def test_austin_point_detects_us_tx_and_austin() -> None:
    backend = build_default_texas_backend()
    # Downtown Austin coordinates.
    backend.register_footprint("ref-austin", Point(-97.74, 30.27))
    detection = backend.detect("ref-austin")
    ids = {j.jurisdiction_id for j in detection.jurisdictions}
    assert {"us", "us-tx", "us-tx-municipality-austin"} <= ids
    # No other Texas city should match a downtown-Austin point.
    cities = [
        j for j in detection.jurisdictions if j.jurisdiction_level == "municipality"
    ]
    assert {c.jurisdiction_id for c in cities} == {"us-tx-municipality-austin"}
    assert detection.footprint_ref == "ref-austin"


def test_houston_polygon_detects_houston() -> None:
    backend = build_default_texas_backend()
    backend.register_footprint("ref-h", box(-95.40, 29.70, -95.30, 29.80))
    detection = backend.detect("ref-h")
    ids = {j.jurisdiction_id for j in detection.jurisdictions}
    assert "us-tx-municipality-houston" in ids
    assert "us" in ids


def test_unregistered_ref_returns_empty_with_us_absent() -> None:
    backend = LocalDetectionBackend(
        jurisdictions=__import__("ipermit_gis").GeometryStore()
    )
    detection = backend.detect("does-not-exist")
    assert detection.jurisdictions == ()


def test_federal_always_added_when_intersecting_jurisdiction_only() -> None:
    backend = build_default_texas_backend()
    # A point in the Gulf of Mexico — outside any modelled jurisdiction (no
    # us-tx, no city) but well inside the wide ``us`` bbox.
    backend.register_footprint("ref-gulf", Point(-94.0, 27.0))
    detection = backend.detect("ref-gulf")
    ids = {j.jurisdiction_id for j in detection.jurisdictions}
    assert "us" in ids


def test_detection_source_is_auto() -> None:
    backend = build_default_texas_backend()
    backend.register_footprint("r", Point(-97.74, 30.27))
    for j in backend.detect("r").jurisdictions:
        assert j.detection_source == "gis_auto_detect"


def test_get_detection_backend_is_singleton() -> None:
    assert get_detection_backend() is get_detection_backend()
