"""Tests for project evaluation history (S02-03).

Each evaluate persists an Evaluation; these endpoints expose the history (list,
newest first) and let a consultant fetch any prior revision's matrix. All
tenant-scoped: another tenant's evaluations are invisible (404).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
_FEDERAL_NEXUS = (
    ROOT
    / "packages/benchmark-projects/benchmarks"
    / "federal-nexus-transmission-stream-crossing.yaml"
)
_LEVELS = {"us": ("federal", "United States"), "us-tx": ("state", "Texas")}


def _evaluate_request(date: str) -> dict:
    bm = yaml.safe_load(_FEDERAL_NEXUS.read_text())
    inputs = bm["project_inputs"]
    ctx = inputs["engine_context"]
    return {
        "project_type": inputs["project_type"],
        "project": ctx.get("project", {}),
        "derived": ctx.get("derived", {}),
        "overlays": ctx.get("geometry", {}),
        "jurisdictions": [
            {
                "jurisdiction_id": jid,
                "jurisdiction_level": _LEVELS[jid][0],
                "canonical_name": _LEVELS[jid][1],
            }
            for jid in inputs["applicable_jurisdiction_ids"]
        ],
        "evaluation_date": date,
    }


def _project(client: TestClient, token: str) -> str:
    resp = client.post(
        "/api/v1/projects",
        json={"name": "History demo"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp.json()["project_id"]


def _evaluate(client: TestClient, token: str, project_id: str, date: str) -> str:
    resp = client.post(
        f"/api/v1/projects/{project_id}/evaluate",
        json=_evaluate_request(date),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["meta"]["evaluation_id"]


def test_history_lists_newest_first(client: TestClient, seeded: dict, login) -> None:
    token = login(seeded["email_a"])
    project_id = _project(client, token)
    headers = {"Authorization": f"Bearer {token}"}
    first = _evaluate(client, token, project_id, "2026-05-24")
    second = _evaluate(client, token, project_id, "2026-05-25")
    resp = client.get(f"/api/v1/projects/{project_id}/evaluations", headers=headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert [r["evaluation_id"] for r in rows] == [second, first]
    assert all(r["permit_count"] == 5 for r in rows)


def test_fetch_specific_evaluation(client: TestClient, seeded: dict, login) -> None:
    token = login(seeded["email_a"])
    project_id = _project(client, token)
    headers = {"Authorization": f"Bearer {token}"}
    eid = _evaluate(client, token, project_id, "2026-05-25")
    resp = client.get(
        f"/api/v1/projects/{project_id}/evaluations/{eid}", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["evaluation_id"] == eid


def test_unknown_evaluation_is_404(client: TestClient, seeded: dict, login) -> None:
    token = login(seeded["email_a"])
    project_id = _project(client, token)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get(
        f"/api/v1/projects/{project_id}/evaluations/nope", headers=headers
    )
    assert resp.status_code == 404


def test_history_is_tenant_scoped(client: TestClient, seeded: dict, login) -> None:
    token_a = login(seeded["email_a"])
    project_id = _project(client, token_a)
    eid = _evaluate(client, token_a, project_id, "2026-05-25")
    token_b = login(seeded["email_b"])
    headers_b = {"Authorization": f"Bearer {token_b}"}
    # B cannot list or fetch A's evaluations — the project itself 404s for B.
    assert (
        client.get(
            f"/api/v1/projects/{project_id}/evaluations", headers=headers_b
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/projects/{project_id}/evaluations/{eid}", headers=headers_b
        ).status_code
        == 404
    )
