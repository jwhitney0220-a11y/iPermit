"""iPermit tenancy & project persistence: the SaaS spine's data layer (S01-01).

Public API: the four ORM models, the enum/value tuples, the authoritative list
of tenant-owned models, and the tenant-aware data path (``TenantScope`` /
``tenant_session``) that is the only sanctioned way to read or write tenant data.
"""

from .models import (
    MEMBERSHIP_ROLES,
    TENANT_KINDS,
    TENANT_OWNED_MODELS,
    Project,
    ProjectEvaluation,
    Tenant,
    TenantMembership,
)
from .session import TenantScope, tenant_session

__all__ = [
    "MEMBERSHIP_ROLES",
    "TENANT_KINDS",
    "TENANT_OWNED_MODELS",
    "Project",
    "ProjectEvaluation",
    "Tenant",
    "TenantMembership",
    "TenantScope",
    "tenant_session",
]
