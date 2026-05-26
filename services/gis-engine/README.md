# services/gis-engine

Lightweight spatial intelligence for iPermit (AGENTS.md *GIS Strategy* — overlays
only, no enterprise GIS). Turns an uploaded project footprint into the applicable
jurisdictions and environmental overlays the rules engine consumes, and runs the
consultant review-and-confirm intake workflow over that detection.

## `ipermit_gis` package

| Module | Ticket | Purpose |
|--------|--------|---------|
| `detection.py` | EPIC-05 | `SpatialDetection` / `DetectedJurisdiction` data model (conforms to `docs/specs/schemas/spatial-detection.schema.json`) and the `DetectionBackend` seam. |
| `confirmation.py` | T05-06 | Auto-detection review & confirmation: apply consultant overrides, log every edit, preserve the original detection, and project the confirmed result into rules-engine inputs. |

## Workflow (AGENTS.md GIS Intake Strategy)

1. A `DetectionBackend` produces a `SpatialDetection` from a footprint.
2. The consultant reviews it and supplies `JurisdictionOverride` / `OverlayOverride` edits.
3. `confirm_detection(...)` applies them, returning a `ConfirmationResult` whose
   confirmed values are the **source of truth**, with the original preserved and
   every edit recorded in `override_log`.
4. `to_engine_inputs(...)` projects the confirmed result into
   `applicable_jurisdiction_ids`, the ordered explanation `jurisdiction_chain`,
   and the `geometry.*` overlay context that `simulate_project` reads.

Manual entry is a first-class fallback: an empty detection plus `add`/`set`
overrides covers early-stage projects with no route file.

## Status

`ipermit_gis` is pure and dependency-free (only `ipermit_engine` for the
canonical jurisdiction precedence order). Still to come in EPIC-05:

- **T05-01** spatial DB (PostGIS) — follows the `docs/operations/postgis-planning.md` decisions.
- **T05-02** shapefile/KMZ ingestion — needs geospatial libraries and is not yet wired.
- **T05-03 / T05-04** county/municipality/ETJ and FEMA/watershed/USACE detection — the real `DetectionBackend` implementations; they require Texas boundary datasets.
- **T05-05** GIS-driven intake modifiers.

These deferred pieces need spatial infrastructure and real boundary data; the
detection contract and confirmation workflow here are the parts that are pure,
testable, and unblock the rules-engine integration today.
