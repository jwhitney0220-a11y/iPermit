"""Source-check recording and query functions (T02-05).

Records and queries ``SourceCheck`` rows — point-in-time verification events
that track whether a citation's URL is reachable and whether the underlying
source has changed.

Each function is under 60 lines and performs one clear task.
"""

from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import SourceCheck


def record_check(
    session: Session,
    rule_id: str,
    version: str,
    reference: str,
    checked_at: datetime.date,
    *,
    url_reachable: bool | None = None,
    http_status: int | None = None,
    form_changed: bool | None = None,
    notes: str | None = None,
) -> SourceCheck:
    """Create and persist a SourceCheck verification event.

    Args:
        session: Active SQLAlchemy session.
        rule_id: The rule this check belongs to.
        version: The rule version this check belongs to.
        reference: The citation reference string that was checked.
        checked_at: The date the verification was performed.
        url_reachable: True if the URL responded successfully; False if not;
            None if no HTTP check was attempted (e.g. manual offline review).
        http_status: The HTTP status code returned, if applicable.
        form_changed: True if the analyst observed the form or submission
            process has changed since the last check.
        notes: Free-text analyst notes about this check.

    Returns:
        The newly created and added ``SourceCheck`` instance.
    """
    check = SourceCheck(
        rule_id=rule_id,
        version=version,
        reference=reference,
        checked_at=checked_at,
        url_reachable=url_reachable,
        http_status=http_status,
        form_changed=form_changed,
        notes=notes,
    )
    session.add(check)
    return check


def latest_check(
    session: Session,
    rule_id: str,
    version: str,
    reference: str,
) -> SourceCheck | None:
    """Return the most recent SourceCheck for a (rule_id, version, reference).

    Returns None if no checks have been recorded.
    """
    stmt = (
        select(SourceCheck)
        .where(
            SourceCheck.rule_id == rule_id,
            SourceCheck.version == version,
            SourceCheck.reference == reference,
        )
        .order_by(SourceCheck.checked_at.desc(), SourceCheck.id.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def check_history(
    session: Session,
    rule_id: str,
    version: str,
    reference: str,
) -> list[SourceCheck]:
    """Return all SourceChecks for a (rule_id, version, reference) oldest-first."""
    stmt = (
        select(SourceCheck)
        .where(
            SourceCheck.rule_id == rule_id,
            SourceCheck.version == version,
            SourceCheck.reference == reference,
        )
        .order_by(SourceCheck.checked_at.asc(), SourceCheck.id.asc())
    )
    return list(session.execute(stmt).scalars().all())


def all_checks_for_rule(
    session: Session,
    rule_id: str,
    version: str,
) -> list[SourceCheck]:
    """Return all SourceChecks for a (rule_id, version) across all references."""
    stmt = (
        select(SourceCheck)
        .where(
            SourceCheck.rule_id == rule_id,
            SourceCheck.version == version,
        )
        .order_by(SourceCheck.checked_at.asc(), SourceCheck.id.asc())
    )
    return list(session.execute(stmt).scalars().all())


def is_currently_reachable(
    session: Session,
    rule_id: str,
    version: str,
    reference: str,
) -> bool | None:
    """Return the url_reachable value from the latest check, or None if none exist."""
    check = latest_check(session, rule_id, version, reference)
    if check is None:
        return None
    return check.url_reachable
