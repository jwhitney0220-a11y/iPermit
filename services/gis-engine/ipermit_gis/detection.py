"""Spatial detection result model (EPIC-05).

A :class:`SpatialDetection` is the auto-detected set of applicable jurisdictions
and environmental overlays produced for an uploaded project footprint, before
consultant review. It conforms to
``docs/specs/schemas/spatial-detection.schema.json`` (AGENTS.md *GIS Strategy*).

This module is the data contract plus a :class:`DetectionBackend` seam. The
real backend — shapefile/KMZ parsing (T05-02), PostGIS overlay queries (T05-01),
and county/municipality/overlay detection (T05-03/T05-04) — plugs in here; this
ticket (T05-06) consumes its output and is DB-free and dependency-free.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

AUTO = "gis_auto_detect"
MANUAL = "manual_entry"


@dataclass(frozen=True)
class DetectedJurisdiction:
    """One detected applicable jurisdiction."""

    jurisdiction_id: str
    jurisdiction_level: str
    canonical_name: str
    detection_source: str = AUTO

    def to_dict(self) -> dict[str, Any]:
        """Serialise to the spatial-detection schema shape."""
        return {
            "jurisdiction_id": self.jurisdiction_id,
            "jurisdiction_level": self.jurisdiction_level,
            "canonical_name": self.canonical_name,
            "detection_source": self.detection_source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DetectedJurisdiction:
        """Build from a spatial-detection jurisdiction object."""
        return cls(
            jurisdiction_id=data["jurisdiction_id"],
            jurisdiction_level=data["jurisdiction_level"],
            canonical_name=data["canonical_name"],
            detection_source=data.get("detection_source", AUTO),
        )


@dataclass(frozen=True)
class SpatialDetection:
    """Auto-detected jurisdictions + environmental overlays for a footprint."""

    detected_at: str
    jurisdictions: tuple[DetectedJurisdiction, ...] = ()
    overlays: dict[str, Any] = field(default_factory=dict)
    footprint_ref: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to the spatial-detection schema shape."""
        out: dict[str, Any] = {
            "detected_at": self.detected_at,
            "jurisdictions": [j.to_dict() for j in self.jurisdictions],
            "overlays": dict(self.overlays),
        }
        if self.footprint_ref is not None:
            out["footprint_ref"] = self.footprint_ref
        if self.notes is not None:
            out["notes"] = self.notes
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpatialDetection:
        """Build from a parsed spatial-detection document."""
        return cls(
            detected_at=data["detected_at"],
            jurisdictions=tuple(
                DetectedJurisdiction.from_dict(j) for j in data.get("jurisdictions", [])
            ),
            overlays=dict(data.get("overlays", {})),
            footprint_ref=data.get("footprint_ref"),
            notes=data.get("notes"),
        )


@runtime_checkable
class DetectionBackend(Protocol):
    """The spatial detection seam implemented by T05-01/T05-02/T05-03/T05-04.

    A backend turns an uploaded footprint reference into a
    :class:`SpatialDetection`. The MVP is lightweight overlays only (AGENTS.md
    *GIS Strategy*); a real PostGIS-backed implementation lands in EPIC-05's
    later tickets. The confirmation workflow (T05-06) depends only on this
    protocol, never on a concrete backend.
    """

    def detect(self, footprint_ref: str) -> SpatialDetection:
        """Return the auto-detected jurisdictions and overlays for a footprint."""
        ...
