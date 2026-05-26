"""iPermit lightweight GIS engine (EPIC-05).

The spatial-intelligence layer that turns an uploaded project footprint into the
applicable jurisdictions and environmental overlays the rules engine consumes,
and runs the consultant review-and-confirm workflow over that detection.

Public surface:

- detection    — ``SpatialDetection`` / ``DetectedJurisdiction`` data model and
  the ``DetectionBackend`` seam (real spatial backend lands in T05-01..T05-04).
- confirmation — the auto-detection review & confirmation workflow (T05-06):
  apply overrides, log edits, and project the confirmed result into rules-engine
  inputs.
"""

from .confirmation import (
    ConfirmationResult,
    EngineInputs,
    JurisdictionOverride,
    OverlayOverride,
    OverrideLogEntry,
    confirm_detection,
    to_engine_inputs,
)
from .detection import (
    AUTO,
    MANUAL,
    DetectedJurisdiction,
    DetectionBackend,
    SpatialDetection,
)

__all__ = [
    "AUTO",
    "MANUAL",
    "ConfirmationResult",
    "DetectedJurisdiction",
    "DetectionBackend",
    "EngineInputs",
    "JurisdictionOverride",
    "OverlayOverride",
    "OverrideLogEntry",
    "SpatialDetection",
    "confirm_detection",
    "to_engine_inputs",
]
