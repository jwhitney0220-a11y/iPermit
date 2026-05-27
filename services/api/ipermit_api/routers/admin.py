"""Admin / analyst endpoints (S02-01).

Role-gated platform-internal surfaces. The audit log is platform-global (ADR-0004)
and readable only by ``platform_admin`` (ADR-0002), so this router is not
tenant-scoped — it is the first internal surface the analyst portal (SAAS-05)
will build on.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from ipermit_tenancy import AuditRecord
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import AuthenticatedIdentity, require_role
from ..db import get_session
from ..schemas import AuditRecordResponse

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])

_MAX_PAGE = 500


@router.get("", response_model=list[AuditRecordResponse])
def list_audit(
    limit: int = Query(50, ge=1, le=_MAX_PAGE),
    _identity: AuthenticatedIdentity = Depends(require_role("platform_admin")),
    session: Session = Depends(get_session),
) -> list[AuditRecordResponse]:
    """Return the most recent audit records (newest first; platform_admin only)."""
    rows = session.scalars(
        select(AuditRecord).order_by(AuditRecord.id.desc()).limit(limit)
    )
    return [
        AuditRecordResponse(
            id=r.id,
            occurred_at=r.occurred_at,
            actor=r.actor,
            action=r.action,
            subject=r.subject,
            payload=r.payload,
            prev_hash=r.prev_hash,
            hash=r.hash,
        )
        for r in rows
    ]
