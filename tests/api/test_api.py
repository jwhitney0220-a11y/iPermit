"""End-to-end tests for the API spine (S01-07).

Covers auth, application-layer tenant isolation, the evaluate→matrix flow over a
known federal-nexus scenario (reusing the T04-02 benchmark inputs), the mandatory
advisory contract (ADR-0003), and the hash-chained audit log (ADR-0004).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from ipermit_tenancy import AuditRecord
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[2]
_BENCHMARK = ROOT / "packages/benchmark-projects/benchmarks"
_FEDERAL_NEXUS = _BENCHMARK / "federal-nexus-transmission-stream-crossing.yaml"
_LEVELS = {"us": ("federal", "United States"), "us-tx": ("state", "Texas")}


def _evaluate_request() -> dict:
    """Translate the federal-nexus benchmark into an evaluate request body."""
    data = yaml.safe_load(_FEDERAL_NEXUS.read_text())
    inputs = data["project_inputs"]
    ctx = inputs["engine_context"]
    jurisdictions = [
        {
            "jurisdiction_id": jid,
            "jurisdiction_level": _LEVELS[jid][0],
            "canonical_name": _LEVELS[jid][1],
        }
        for jid in inputs["applicable_jurisdiction_ids"]
    ]
    return {
        "project_type": inputs["project_type"],
        "project": ctx.get("project", {}),
        "derived": ctx.get("derived", {}),
        "overlays": ctx.get("geometry", {}),
        "jurisdictions": jurisdictions,
        "evaluation_date": data["evaluation_date"],
    }


def _create_project(client: TestClient, token: str, name: str = "Line A") -> str:
    resp = client.post(
        "/api/v1/projects",
        json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["project_id"]


def test_login_and_me(client: TestClient, seeded: dict, login) -> None:
    token = login(seeded["email_a"])
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == seeded["email_a"]
    assert body["tenant_id"] == seeded["tenant_a"]
    assert body["platform_role"] == "consultant_user"


def test_bad_credentials_problem(client: TestClient, seeded: dict) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": seeded["email_a"], "password": "wrong"},
    )
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/problem+json")
    assert resp.json()["status"] == 401


def test_missing_token_problem(client: TestClient, seeded: dict) -> None:
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/problem+json")


def test_create_and_list_project(client: TestClient, seeded: dict, login) -> None:
    token = login(seeded["email_a"])
    project_id = _create_project(client, token)
    resp = client.get("/api/v1/projects", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert [p["project_id"] for p in resp.json()] == [project_id]


def test_cross_tenant_isolation(client: TestClient, seeded: dict, login) -> None:
    token_a = login(seeded["email_a"])
    project_id = _create_project(client, token_a, name="A secret")
    token_b = login(seeded["email_b"])
    # B cannot see A's project in its own list.
    listed = client.get(
        "/api/v1/projects", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert listed.json() == []
    # B cannot read A's project matrix — reported as 404, not 403.
    resp = client.get(
        f"/api/v1/projects/{project_id}/matrix",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404


def test_evaluate_federal_nexus_matrix(client: TestClient, seeded: dict, login) -> None:
    token = login(seeded["email_a"])
    project_id = _create_project(client, token)
    resp = client.post(
        f"/api/v1/projects/{project_id}/evaluate",
        json=_evaluate_request(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    permits = body["data"]["permits"]
    rule_ids = {p["rule_id"] for p in permits}
    assert rule_ids == {
        "us-tx-usace-section-404-da-permit",
        "us-tx-nepa-federal-environmental-review",
        "us-tx-usfws-esa-section-7-consultation",
        "us-tx-tceq-construction-stormwater-cgp",
        "us-tx-tceq-section-401-water-quality-certification",
    }
    assert all(p["confidence"]["tier"] == 1 for p in permits)
    # Liability contract (ADR-0003): every permit carries >= 1 advisory, and the
    # standing platform disclaimer is present at the envelope level.
    assert all(len(p["advisories"]) >= 1 for p in permits)
    assert any(a["origin"] == "platform" for a in body["advisories"])
    # Reproducibility triple in meta.
    assert body["meta"]["ruleset_version"]["content_hash"].startswith("sha256:")
    assert body["meta"]["evaluation_id"]


def test_get_matrix_after_evaluate(client: TestClient, seeded: dict, login) -> None:
    token = login(seeded["email_a"])
    project_id = _create_project(client, token)
    headers = {"Authorization": f"Bearer {token}"}
    client.post(
        f"/api/v1/projects/{project_id}/evaluate",
        json=_evaluate_request(),
        headers=headers,
    )
    resp = client.get(f"/api/v1/projects/{project_id}/matrix", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]["permits"]) == 5


@pytest.mark.parametrize(
    ("fmt", "media"),
    [
        ("json", "application/json"),
        (
            "xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        ("pdf", "application/pdf"),
    ],
)
def test_export_matrix(client: TestClient, seeded: dict, login, fmt, media) -> None:
    token = login(seeded["email_a"])
    project_id = _create_project(client, token)
    headers = {"Authorization": f"Bearer {token}"}
    client.post(
        f"/api/v1/projects/{project_id}/evaluate",
        json=_evaluate_request(),
        headers=headers,
    )
    resp = client.get(
        f"/api/v1/projects/{project_id}/matrix/export?format={fmt}", headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith(media)
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.content


def test_export_rejects_bad_format(client: TestClient, seeded: dict, login) -> None:
    token = login(seeded["email_a"])
    project_id = _create_project(client, token)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get(
        f"/api/v1/projects/{project_id}/matrix/export?format=docx", headers=headers
    )
    assert resp.status_code == 422


def test_export_requires_auth(client: TestClient, seeded: dict) -> None:
    resp = client.get("/api/v1/projects/whatever/matrix/export?format=json")
    assert resp.status_code == 401


def test_audit_chain_links(
    client: TestClient, seeded: dict, factory: sessionmaker[Session], login
) -> None:
    token = login(seeded["email_a"])
    project_id = _create_project(client, token)
    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(2):
        client.post(
            f"/api/v1/projects/{project_id}/evaluate",
            json=_evaluate_request(),
            headers=headers,
        )
    with factory() as s:
        records = list(s.scalars(select(AuditRecord).order_by(AuditRecord.id)))
    assert len(records) == 2
    assert all(r.action == "project.evaluated" for r in records)
    assert records[0].prev_hash is None
    assert records[1].prev_hash == records[0].hash
    assert records[1].hash != records[0].hash
