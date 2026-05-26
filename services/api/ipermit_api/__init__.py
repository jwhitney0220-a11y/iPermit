"""iPermit public API service (SAAS-01, ADR-0006).

A composing BFF over the deterministic engine, GIS confirmation, persistence, and
tenancy packages. See ``app.create_app`` for the FastAPI application factory.
"""

from .app import app, create_app

__all__ = ["app", "create_app"]
