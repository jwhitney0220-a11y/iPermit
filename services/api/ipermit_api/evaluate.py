"""Evaluation orchestration (S01-04).

Wires the proven deterministic libraries into one tenant-scoped flow:

    intake (project.*) + confirmed GIS (jurisdictions, overlays -> geometry.*)
        -> simulate_project(...)              # rules engine (T04-01)
        -> build_permit_matrix(...)           # consultant deliverable (T07-01)
        -> persist Evaluation (reproducibility triple + matrix)

The GIS side reuses the T05-06 confirmation workflow: manual entries become a
``SpatialDetection`` with ``manual_entry`` source, ``confirm_detection`` orders
them by precedence, and ``to_engine_inputs`` projects them into the engine's
``geometry.*`` context, applicable jurisdiction ids, and the explanation chain.

Rules are loaded from the ``draft`` snapshot for now (promotion to ``effective``
is S05-02); the platform advisory caveat in every explanation reflects this.
"""

from __future__ import annotations

import datetime
import uuid

from ipermit_engine import ProjectContext, simulate_project
from ipermit_gis.confirmation import confirm_detection, to_engine_inputs
from ipermit_gis.detection import MANUAL, DetectedJurisdiction, SpatialDetection
from ipermit_rules import load_rules
from ipermit_tenancy import Evaluation
from sqlalchemy.orm import Session

from .matrix import build_permit_matrix
from .schemas import EvaluateRequest
from .usage import record_usage

# The seeded ruleset is still draft (promotion is S05-02); evaluate against it.
_RULE_STATUSES = ("draft",)


def _detection(request: EvaluateRequest, when: str) -> SpatialDetection:
    """Build a manual-entry spatial detection from the request's GIS inputs."""
    jurisdictions = tuple(
        DetectedJurisdiction(
            jurisdiction_id=j.jurisdiction_id,
            jurisdiction_level=j.jurisdiction_level,
            canonical_name=j.canonical_name,
            detection_source=MANUAL,
        )
        for j in request.jurisdictions
    )
    return SpatialDetection(
        detected_at=when, jurisdictions=jurisdictions, overlays=dict(request.overlays)
    )


def _context(request: EvaluateRequest, geometry: dict) -> ProjectContext:
    """Assemble the flat dotted-path engine context from intake + GIS + derived."""
    flat: dict[str, object] = {f"project.{k}": v for k, v in request.project.items()}
    flat.update(geometry)
    flat.update({f"derived.{k}": v for k, v in request.derived.items()})
    return ProjectContext(flat)


def evaluate_project(
    session: Session,
    *,
    project_id: str,
    tenant_id: str,
    actor: str,
    request: EvaluateRequest,
) -> Evaluation:
    """Run the deterministic pipeline and persist the resulting matrix.

    Returns the persisted (flushed, not committed) :class:`Evaluation`; the
    caller owns the transaction and the audit record (S01-05).
    """
    when = request.evaluation_date or datetime.date.today().isoformat()
    engine_inputs = to_engine_inputs(confirm_detection(_detection(request, when)))
    rules = [r.data for r in load_rules(statuses=_RULE_STATUSES)]
    sim = simulate_project(
        rules=rules,
        context=_context(request, engine_inputs.geometry),
        applicable_jurisdiction_ids=engine_inputs.applicable_jurisdiction_ids,
        project_types=[request.project_type],
        jurisdiction_chain=engine_inputs.jurisdiction_chain,
        evaluation_date=when,
    )
    evaluation_id = uuid.uuid4().hex
    matrix = build_permit_matrix(
        sim, evaluation_id=evaluation_id, project_id=project_id
    )
    evaluation = Evaluation(
        evaluation_id=evaluation_id,
        tenant_id=tenant_id,
        project_id=project_id,
        evaluation_date=when,
        inputs_hash=sim.inputs_hash,
        ruleset_content_hash=sim.ruleset_version["content_hash"],
        matrix=matrix,
        created_by=actor,
    )
    session.add(evaluation)
    session.flush()
    record_usage(session, tenant_id=tenant_id, metric="evaluation")
    return evaluation
