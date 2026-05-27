"""Route-file upload → object storage → GIS footprint (S04-03, roadmap T05-02).

A consultant uploads a shapefile (.zip), KMZ, or KML for a tenant-scoped project.
The file is size/type validated, parsed through the GIS ingest seam
(``ipermit_gis``) into a single normalised :class:`ProjectFootprint`, and the raw
bytes are persisted to object storage. The returned ``footprint_ref`` + geometry
summary feed jurisdiction/overlay detection (real backends land in SAAS-06); the
manual-entry path remains the fallback.
"""

from __future__ import annotations

import uuid
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, UploadFile
from ipermit_gis import (
    GeometryError,
    normalize_footprint,
    parse_kml,
    parse_kmz,
    parse_shapefile,
)
from ipermit_tenancy import Project
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import append_audit
from ..auth import AuthenticatedIdentity, get_current_identity
from ..db import apply_tenant_scope, get_session
from ..envelope import ProblemException
from ..schemas import FootprintUploadResponse
from ..settings import Settings, get_settings
from ..storage import ObjectStorage, get_storage

router = APIRouter(prefix="/api/v1/projects", tags=["uploads"])

#: Accepted route-file extensions -> GIS ingest kind.
_ALLOWED = {".kml": "kml", ".kmz": "kmz", ".zip": "shapefile"}
_MB = 1024 * 1024


def _require_tenant(identity: AuthenticatedIdentity) -> str:
    if identity.tenant_id is None:
        raise ProblemException(403, "No tenant membership")
    return identity.tenant_id


def _load_project(session: Session, tenant_id: str, project_id: str) -> Project:
    project = session.scalar(
        select(Project).where(
            Project.project_id == project_id, Project.tenant_id == tenant_id
        )
    )
    if project is None:
        raise ProblemException(404, "Project not found")
    return project


def _footprint(kind: str, data: bytes):
    """Parse uploaded bytes via the GIS ingest seam into a normalised footprint."""
    try:
        if kind == "kml":
            geometries = parse_kml(data.decode("utf-8"))
        elif kind == "kmz":
            geometries = parse_kmz(data)
        else:
            geometries = parse_shapefile(data)
        return normalize_footprint(geometries)
    except (GeometryError, ValueError, UnicodeDecodeError) as exc:
        raise ProblemException(422, "Unparseable route file", str(exc)) from exc


@router.post("/{project_id}/footprint", response_model=FootprintUploadResponse)
async def upload_footprint(
    project_id: str,
    file: UploadFile,
    identity: AuthenticatedIdentity = Depends(get_current_identity),
    session: Session = Depends(get_session),
    storage: ObjectStorage = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> FootprintUploadResponse:
    """Upload + parse a route file; store it and return its footprint summary."""
    tenant_id = _require_tenant(identity)
    apply_tenant_scope(session, tenant_id)
    _load_project(session, tenant_id, project_id)
    ext = PurePosixPath(file.filename or "").suffix.lower()
    kind = _ALLOWED.get(ext)
    if kind is None:
        raise ProblemException(415, f"Unsupported file type {ext or '(none)'}")
    data = await file.read()
    if len(data) > settings.gis_max_upload_mb * _MB:
        raise ProblemException(413, "File exceeds the upload size limit")
    footprint = _footprint(kind, data)
    key = f"{tenant_id}/{project_id}/{uuid.uuid4().hex}{ext}"
    ref = storage.put(key, data, file.content_type or "application/octet-stream")
    append_audit(
        session,
        actor=identity.email,
        action="footprint.uploaded",
        subject=project_id,
        payload={
            "tenant_id": tenant_id,
            "ref": ref,
            "geometry_type": footprint.geometry_type,
        },
    )
    session.commit()
    return FootprintUploadResponse(
        footprint_ref=ref,
        geometry_type=footprint.geometry_type,
        bbox=list(footprint.bbox),
        byte_size=len(data),
    )
