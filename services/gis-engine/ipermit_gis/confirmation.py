"""Auto-detection review & confirmation workflow (T05-06).

After the spatial backend produces a :class:`~ipermit_gis.detection.SpatialDetection`,
the consultant reviews it, optionally edits it, and confirms it. The confirmed
values become the source of truth for the permit matrix (AGENTS.md *GIS Intake
Strategy*). This module:

- applies user overrides to detected jurisdictions and overlays,
- preserves the original auto-detection result,
- logs every override (the AGENTS.md requirement that user edits be logged),
- projects the confirmed result into the inputs the rules engine consumes
  (applicable jurisdiction ids, the explanation jurisdiction chain, and the
  ``geometry.*`` overlay context).

Manual entry remains a fallback: a detection with no auto-detected values is
valid, and everything can be supplied via ``add``/``set`` overrides.

Pure and DB-free. Depends on ``ipermit_engine`` only for the canonical
jurisdiction precedence order (single source of truth, ontology §4.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ipermit_engine.conflict import precedence_rank

from .detection import DetectedJurisdiction, SpatialDetection

# detection_source -> permit-explanation jurisdiction_chain detection_source.
_CHAIN_SOURCE = {
    "gis_auto_detect": "gis_auto_detect",
    "manual_entry": "user_input",
    "user_override": "user_override",
    "user_confirmed": "user_confirmed",
}
_OVERRIDE_SOURCE = "user_override"


@dataclass(frozen=True)
class JurisdictionOverride:
    """A consultant edit to the detected jurisdiction set (add or remove)."""

    action: str  # "add" | "remove"
    jurisdiction_id: str
    jurisdiction_level: str | None = None
    canonical_name: str | None = None


@dataclass(frozen=True)
class OverlayOverride:
    """A consultant edit to a detected overlay value (set or remove)."""

    action: str  # "set" | "remove"
    field: str
    value: Any = None


@dataclass(frozen=True)
class OverrideLogEntry:
    """One logged override applied during confirmation."""

    target: str  # "jurisdiction" | "overlay"
    action: str
    key: str  # jurisdiction_id or overlay field
    previous: Any
    confirmed: Any


@dataclass(frozen=True)
class ConfirmationResult:
    """The confirmed detection (source of truth) plus the audit log."""

    original: SpatialDetection
    jurisdictions: tuple[DetectedJurisdiction, ...]
    overlays: dict[str, Any]
    override_log: tuple[OverrideLogEntry, ...]


@dataclass(frozen=True)
class EngineInputs:
    """Confirmed GIS values projected into rules-engine inputs."""

    applicable_jurisdiction_ids: tuple[str, ...]
    jurisdiction_chain: list[dict[str, str]]
    geometry: dict[str, Any]


def _apply_jurisdiction_overrides(
    by_id: dict[str, DetectedJurisdiction],
    overrides: tuple[JurisdictionOverride, ...],
) -> list[OverrideLogEntry]:
    """Apply jurisdiction add/remove overrides in place; return log entries."""
    log: list[OverrideLogEntry] = []
    for ov in overrides:
        previous = by_id.get(ov.jurisdiction_id)
        if ov.action == "remove":
            by_id.pop(ov.jurisdiction_id, None)
            confirmed = None
        elif ov.action == "add":
            by_id[ov.jurisdiction_id] = DetectedJurisdiction(
                jurisdiction_id=ov.jurisdiction_id,
                jurisdiction_level=ov.jurisdiction_level or "",
                canonical_name=ov.canonical_name or ov.jurisdiction_id,
                detection_source=_OVERRIDE_SOURCE,
            )
            confirmed = by_id[ov.jurisdiction_id]
        else:
            raise ValueError(f"unknown jurisdiction override action {ov.action!r}")
        log.append(
            OverrideLogEntry(
                "jurisdiction", ov.action, ov.jurisdiction_id, previous, confirmed
            )
        )
    return log


def _apply_overlay_overrides(
    overlays: dict[str, Any], overrides: tuple[OverlayOverride, ...]
) -> list[OverrideLogEntry]:
    """Apply overlay set/remove overrides in place; return log entries."""
    log: list[OverrideLogEntry] = []
    for ov in overrides:
        previous = overlays.get(ov.field)
        if ov.action == "set":
            overlays[ov.field] = ov.value
            confirmed = ov.value
        elif ov.action == "remove":
            overlays.pop(ov.field, None)
            confirmed = None
        else:
            raise ValueError(f"unknown overlay override action {ov.action!r}")
        log.append(
            OverrideLogEntry("overlay", ov.action, ov.field, previous, confirmed)
        )
    return log


def confirm_detection(
    detection: SpatialDetection,
    *,
    jurisdiction_overrides: tuple[JurisdictionOverride, ...] = (),
    overlay_overrides: tuple[OverlayOverride, ...] = (),
) -> ConfirmationResult:
    """Apply consultant overrides to a detection and return the confirmed result.

    The original *detection* is preserved untouched; every override is recorded
    in ``override_log``. The returned jurisdictions/overlays are the source of
    truth for the permit matrix.
    """
    by_id = {j.jurisdiction_id: j for j in detection.jurisdictions}
    overlays = dict(detection.overlays)
    log = _apply_jurisdiction_overrides(by_id, jurisdiction_overrides)
    log += _apply_overlay_overrides(overlays, overlay_overrides)
    jurisdictions = tuple(
        by_id[key]
        for key in sorted(
            by_id, key=lambda k: (precedence_rank(by_id[k].jurisdiction_level), k)
        )
    )
    return ConfirmationResult(detection, jurisdictions, overlays, tuple(log))


def to_engine_inputs(confirmation: ConfirmationResult) -> EngineInputs:
    """Project a confirmed detection into rules-engine inputs.

    Returns the applicable jurisdiction ids, the ordered explanation
    jurisdiction chain (Federal -> local), and the ``geometry.*`` overlay context
    that ``simulate_project`` reads. The caller adds the ``project.*`` intake
    fields before evaluating.
    """
    chain = [
        {
            "jurisdiction_id": j.jurisdiction_id,
            "jurisdiction_level": j.jurisdiction_level,
            "canonical_name": j.canonical_name,
            "detection_source": _CHAIN_SOURCE.get(j.detection_source, "user_input"),
        }
        for j in confirmation.jurisdictions
    ]
    ids = tuple(j.jurisdiction_id for j in confirmation.jurisdictions)
    geometry = {
        f"geometry.{key}": value for key, value in confirmation.overlays.items()
    }
    return EngineInputs(ids, chain, geometry)
