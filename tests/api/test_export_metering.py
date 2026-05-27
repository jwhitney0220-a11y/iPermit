"""S03-04 review fix: deliverable exports are metered, not just gated.

The usage meter advertises "evaluations/exports per tenant" (S03-03), but only
evaluations were recorded. This asserts an export now appears in the tenant's
usage summary alongside the evaluation. Export requires an active paid plan, so
the tenant is entitled first.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from ipermit_tenancy import TenantBilling
from sqlalchemy.orm import Session, sessionmaker


def _entitle(factory: sessionmaker[Session], tenant_id: str) -> None:
    with factory() as s:
        s.add(TenantBilling(tenant_id=tenant_id, plan="pro", status="active"))
        s.commit()


def test_export_is_metered(
    client: TestClient, seeded: dict, login, factory: sessionmaker[Session]
) -> None:
    _entitle(factory, seeded["tenant_a"])
    token = login(seeded["email_a"])
    headers = {"Authorization": f"Bearer {token}"}
    pid = client.post(
        "/api/v1/projects", json={"name": "Metered"}, headers=headers
    ).json()["project_id"]
    client.post(
        f"/api/v1/projects/{pid}/evaluate",
        json={"project_type": "transmission_line"},
        headers=headers,
    )
    export = client.get(
        f"/api/v1/projects/{pid}/matrix/export?format=json", headers=headers
    )
    assert export.status_code == 200, export.text
    metrics = client.get("/api/v1/usage", headers=headers).json()["metrics"]
    assert metrics.get("evaluation", 0) >= 1
    assert metrics.get("export", 0) >= 1
