"""Local shapely-backed :class:`DetectionBackend` (SAAS-06, T05-03/T05-04).

Implements the existing :class:`~ipermit_gis.detection.DetectionBackend` protocol
against the in-memory :class:`~ipermit_gis.store.GeometryStore`. Given a project
footprint registered by reference (e.g. the ``footprint_ref`` returned by the
upload endpoint), it returns the set of jurisdictions whose geometry intersects
the footprint as a :class:`SpatialDetection` ready for the consultant-confirm
workflow (T05-06) and the rules engine.

A factory bundles a small **seed of Texas boundary bbox polygons** (state + the
eight currently-modelled cities) so detection works end-to-end out of the box.
The Postgres/PostGIS-backed variant slots in behind the same Protocol when a
spatial store is provisioned (S06 deploy concern); the consultant flow does not
change.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterable

from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

from .detection import AUTO, DetectedJurisdiction, SpatialDetection
from .store import GeometryStore

# Bounding-box approximations (WGS84 lon/lat) sufficient for the consultant
# confirm workflow; real shapefiles slot into the same store at deploy time.
_TX_STATE_BBOX = (-106.65, 25.84, -93.51, 36.50)
_TX_CITY_BBOXES: dict[str, tuple[float, float, float, float]] = {
    "us-tx-municipality-houston": (-95.82, 29.52, -95.01, 30.11),
    "us-tx-municipality-dallas": (-96.99, 32.62, -96.46, 33.02),
    "us-tx-municipality-austin": (-98.00, 30.10, -97.56, 30.52),
    "us-tx-municipality-san-antonio": (-98.79, 29.18, -98.23, 29.71),
    "us-tx-municipality-fort-worth": (-97.55, 32.55, -97.07, 32.99),
    "us-tx-municipality-arlington": (-97.27, 32.61, -97.03, 32.81),
    "us-tx-municipality-waco": (-97.30, 31.45, -97.05, 31.65),
    "us-tx-municipality-el-paso": (-106.65, 31.55, -106.20, 31.95),
}
_LEVELS = {
    "us": ("federal", "United States"),
    "us-tx": ("state", "Texas"),
}


def _metadata(jurisdiction_id: str) -> tuple[str, str]:
    if jurisdiction_id in _LEVELS:
        return _LEVELS[jurisdiction_id]
    city = jurisdiction_id.removeprefix("us-tx-municipality-").replace("-", " ").title()
    return "municipality", f"City of {city}"


class LocalDetectionBackend:
    """In-process :class:`DetectionBackend` using a shapely :class:`GeometryStore`.

    Register footprints by reference with :meth:`register_footprint`; ``detect``
    intersects the registered geometry with the jurisdiction store. The
    federal entry (``us``) is always returned — every project is in the US.
    """

    def __init__(
        self,
        jurisdictions: GeometryStore,
        metadata: dict[str, tuple[str, str]] | None = None,
    ) -> None:
        self._jurisdictions = jurisdictions
        self._metadata = metadata or {}
        self._footprints: dict[str, BaseGeometry] = {}

    def register_footprint(self, ref: str, geometry: BaseGeometry) -> None:
        """Cache a parsed footprint geometry under *ref* for later detection."""
        self._footprints[ref] = geometry

    def detect(self, footprint_ref: str) -> SpatialDetection:
        """Return the auto-detected jurisdictions intersecting *footprint_ref*."""
        geometry = self._footprints.get(footprint_ref)
        if geometry is None:
            return _empty_detection(footprint_ref)
        ids = self._jurisdictions.intersecting(geometry)
        items = [self._detected(jid) for jid in ids]
        # Federal always applies to a US project; add ``us`` if absent.
        if not any(d.jurisdiction_id == "us" for d in items):
            items.append(self._detected("us"))
        return SpatialDetection(
            detected_at=datetime.date.today().isoformat(),
            jurisdictions=tuple(items),
            overlays={},
            footprint_ref=footprint_ref,
        )

    def _detected(self, jurisdiction_id: str) -> DetectedJurisdiction:
        level, name = self._metadata.get(jurisdiction_id) or _metadata(jurisdiction_id)
        return DetectedJurisdiction(
            jurisdiction_id=jurisdiction_id,
            jurisdiction_level=level,
            canonical_name=name,
            detection_source=AUTO,
        )


def _empty_detection(footprint_ref: str) -> SpatialDetection:
    return SpatialDetection(
        detected_at=datetime.date.today().isoformat(),
        jurisdictions=(),
        overlays={},
        footprint_ref=footprint_ref,
    )


def _seed_bboxes(
    store: GeometryStore,
    bboxes: Iterable[tuple[str, tuple[float, float, float, float]]],
) -> None:
    for jid, (minx, miny, maxx, maxy) in bboxes:
        store.add(jid, box(minx, miny, maxx, maxy))


def build_default_texas_backend() -> LocalDetectionBackend:
    """Backend seeded with Texas + the 8 modelled cities (bbox approximations)."""
    store = GeometryStore()
    # ``us`` is "everywhere" — wide bbox covering CONUS so any TX footprint hits.
    _seed_bboxes(
        store,
        [
            ("us", (-180.0, 15.0, -50.0, 73.0)),
            ("us-tx", _TX_STATE_BBOX),
            *_TX_CITY_BBOXES.items(),
        ],
    )
    metadata = {
        "us": _LEVELS["us"],
        "us-tx": _LEVELS["us-tx"],
        **{jid: ("municipality", _metadata(jid)[1]) for jid in _TX_CITY_BBOXES},
    }
    return LocalDetectionBackend(store, metadata)


# A module-level singleton: cheap to construct, holds state per process.
_DEFAULT_BACKEND: LocalDetectionBackend | None = None


def get_detection_backend() -> LocalDetectionBackend:
    """Return the process-wide :class:`DetectionBackend` (lazy, default Texas seed)."""
    global _DEFAULT_BACKEND  # noqa: PLW0603
    if _DEFAULT_BACKEND is None:
        _DEFAULT_BACKEND = build_default_texas_backend()
    return _DEFAULT_BACKEND


__all__ = [
    "LocalDetectionBackend",
    "build_default_texas_backend",
    "get_detection_backend",
]
