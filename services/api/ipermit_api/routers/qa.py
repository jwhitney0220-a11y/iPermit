"""Analyst QA dashboard endpoints (S05-02).

Surfaces existing rules-engine QA aggregation for the internal analyst portal.
This endpoint reports rule inventory and publication-gate signals only; it does
not publish, reject, or edit rules.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from ipermit_engine.qa import PublicationGate, build_qa_report
from ipermit_rules import load_rules

from ..auth import AuthenticatedIdentity, require_role
from ..schemas import (
    PublicationGateResponse,
    QASummaryResponse,
    QATierCountsResponse,
)

router = APIRouter(prefix="/api/v1/qa", tags=["qa"])


@router.get("/summary", response_model=QASummaryResponse)
def qa_summary(
    _identity: AuthenticatedIdentity = Depends(require_role("regulatory_analyst")),
) -> QASummaryResponse:
    """Return QA/QC dashboard summary for the current rule snapshot."""
    rules = [rule.data for rule in load_rules()]
    report = build_qa_report(rules, [])
    failing = [gate for gate in report.publication_gates if not gate.all_pass]
    return QASummaryResponse(
        tier_counts=QATierCountsResponse(**report.tier_counts.__dict__),
        pending_review_rule_ids=report.pending_review_rule_ids,
        publication_gate_count=len(report.publication_gates),
        failing_publication_gates=[_gate_response(gate) for gate in failing],
        unresolved_unknown_count=len(report.unresolved_unknowns),
    )


def _gate_response(gate: PublicationGate) -> PublicationGateResponse:
    """Convert engine dataclass to API response."""
    return PublicationGateResponse(
        rule_id=gate.rule_id,
        provenance_present=gate.provenance_present,
        reviewer_present=gate.reviewer_present,
        confidence_tier_assigned=gate.confidence_tier_assigned,
        advisory_language_present=gate.advisory_language_present,
        all_pass=gate.all_pass,
    )
