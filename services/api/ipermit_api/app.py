"""FastAPI application factory for the iPermit public API (S01-03, ADR-0006).

A single composing service (BFF) over the deterministic engine, GIS, persistence,
and tenancy packages. The generated OpenAPI document is the published contract
(ADR-0003); routers expose ``/api/v1/...`` and all permit-bearing responses use
the standard envelope with mandatory advisories.
"""

from __future__ import annotations

from fastapi import FastAPI

from .envelope import register_exception_handlers
from .routers import (
    admin,
    auth,
    billing,
    feedback,
    projects,
    publications,
    qa,
    team,
    uploads,
    usage,
)
from .settings import get_settings, validate_security

API_DESCRIPTION = (
    "iPermit public API — wraps the deterministic rules engine, GIS confirmation,"
    " and permit-matrix builder behind a multi-tenant REST surface (ADR-0003)."
)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    validate_security(get_settings())
    app = FastAPI(
        title="iPermit API",
        version="0.1.0",
        description=API_DESCRIPTION,
    )
    register_exception_handlers(app)
    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(admin.router)
    app.include_router(feedback.router)
    app.include_router(billing.router)
    app.include_router(usage.router)
    app.include_router(team.router)
    app.include_router(uploads.router)
    app.include_router(publications.router)
    app.include_router(qa.router)

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok"}

    return app


app = create_app()
