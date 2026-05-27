"""Request/response DTOs for the API (S01-02 / S01-04).

These are the API-only shapes (auth, project create, evaluate input). Domain
payloads — the permit matrix and explanation records — follow their canonical
JSON Schemas (ADR-0003); this module does not redefine them.
"""

from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Email/password credentials for token issuance."""

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=72)


class TokenResponse(BaseModel):
    """An issued access token."""

    access_token: str
    token_type: str = "bearer"


class IdentityResponse(BaseModel):
    """The resolved caller (``GET /auth/me``)."""

    subject: str
    email: str
    platform_role: str
    tenant_ids: list[str]
    tenant_id: str | None


class CreateProjectRequest(BaseModel):
    """Create a tenant-scoped project."""

    name: str = Field(min_length=1, max_length=200)


class ProjectResponse(BaseModel):
    """A project summary."""

    project_id: str
    tenant_id: str
    name: str
    created_by: str


class JurisdictionEntry(BaseModel):
    """A manually entered (or confirmed) applicable jurisdiction (GIS fallback)."""

    jurisdiction_id: str = Field(min_length=1)
    jurisdiction_level: str = Field(min_length=1)
    canonical_name: str = Field(min_length=1)


class EvaluateRequest(BaseModel):
    """Confirmed evaluation inputs: intake (project.*) + GIS (jurisdictions, overlays).

    ``derived`` carries ``derived.*`` engine-context values that a later
    intake-derivation step will compute; for this slice the caller supplies them
    explicitly (documented loose end). ``evaluation_date`` is an explicit request
    parameter — the engine never reads wall-clock time (T00-03 §4.1).
    """

    project_type: str = Field(min_length=1)
    project: dict[str, Any] = Field(default_factory=dict)
    derived: dict[str, Any] = Field(default_factory=dict)
    jurisdictions: list[JurisdictionEntry] = Field(default_factory=list)
    overlays: dict[str, Any] = Field(default_factory=dict)
    evaluation_date: str | None = None


class EvaluationSummary(BaseModel):
    """One row in a project's evaluation history (newest first)."""

    evaluation_id: str
    evaluation_date: str
    inputs_hash: str
    ruleset_content_hash: str
    permit_count: int
    created_at: datetime.datetime


class AuditRecordResponse(BaseModel):
    """One append-only audit record (platform-admin read, ADR-0004)."""

    id: int
    occurred_at: datetime.datetime
    actor: str
    action: str
    subject: str
    payload: dict[str, Any]
    prev_hash: str | None
    hash: str
