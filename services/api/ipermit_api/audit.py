"""Append-only, hash-chained audit log writer (S01-05, ADR-0004).

Each evaluation (and, later, every rule-lifecycle and auth-significant event)
appends one :class:`~ipermit_tenancy.AuditRecord`. The record's ``hash`` is a
sha256 over its canonical content plus the previous record's ``hash``
(``prev_hash``), forming a tamper-evident chain: altering any past record breaks
every link after it. Records are never updated or deleted — corrections are new
compensating records (ADR-0004).
"""

from __future__ import annotations

import datetime
import hashlib
import json
from typing import Any

from ipermit_tenancy import AuditRecord
from sqlalchemy import select
from sqlalchemy.orm import Session


def _latest_hash(session: Session) -> str | None:
    """Return the most recent record's hash (chain tip), or None if empty."""
    return session.scalar(
        select(AuditRecord.hash).order_by(AuditRecord.id.desc()).limit(1)
    )


def compute_hash(
    *,
    occurred_at: str,
    actor: str,
    action: str,
    subject: str,
    payload: dict[str, Any],
    prev_hash: str | None,
) -> str:
    """Deterministic sha256 over the record content chained to *prev_hash*."""
    content = {
        "occurred_at": occurred_at,
        "actor": actor,
        "action": action,
        "subject": subject,
        "payload": payload,
        "prev_hash": prev_hash,
    }
    canonical = json.dumps(
        content, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def append_audit(
    session: Session,
    *,
    actor: str,
    action: str,
    subject: str,
    payload: dict[str, Any],
) -> AuditRecord:
    """Append one hash-chained audit record (flushed, not committed)."""
    occurred_at = datetime.datetime.now(tz=datetime.UTC)
    prev_hash = _latest_hash(session)
    record = AuditRecord(
        occurred_at=occurred_at,
        actor=actor,
        action=action,
        subject=subject,
        payload=payload,
        prev_hash=prev_hash,
        hash=compute_hash(
            occurred_at=occurred_at.isoformat(),
            actor=actor,
            action=action,
            subject=subject,
            payload=payload,
            prev_hash=prev_hash,
        ),
    )
    session.add(record)
    session.flush()
    return record
