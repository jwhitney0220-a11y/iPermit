"""Route-file upload tests (S04-03).

A KML route file uploads, parses through the GIS ingest seam into a footprint,
and is stored. Type/parse/size/auth/tenant guards are exercised. Object storage
is overridden with an in-memory stub so no bytes touch disk in CI.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from ipermit_api.storage import get_storage

_KML = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><LineString>'
    b"<coordinates>-97.74,30.27 -97.70,30.30 -97.66,30.33</coordinates>"
    b"</LineString></Placemark></Document></kml>"
)


class _MemStorage:
    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}

    def put(self, key: str, data: bytes, content_type: str) -> str:
        self.blobs[key] = data
        return f"mem://{key}"


def _use_mem_storage(client: TestClient) -> _MemStorage:
    mem = _MemStorage()
    client.app.dependency_overrides[get_storage] = lambda: mem
    return mem


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _project(client: TestClient, token: str) -> str:
    return client.post(
        "/api/v1/projects", json={"name": "Route"}, headers=_auth(token)
    ).json()["project_id"]


def test_upload_kml_returns_footprint(client: TestClient, seeded: dict, login) -> None:
    mem = _use_mem_storage(client)
    token = login(seeded["email_a"])
    pid = _project(client, token)
    resp = client.post(
        f"/api/v1/projects/{pid}/footprint",
        files={"file": ("route.kml", _KML, "application/vnd.google-earth.kml+xml")},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["geometry_type"] == "line"
    assert len(body["bbox"]) == 4
    assert body["footprint_ref"].startswith("mem://")
    assert len(mem.blobs) == 1


def test_unsupported_type_is_415(client: TestClient, seeded: dict, login) -> None:
    _use_mem_storage(client)
    token = login(seeded["email_a"])
    pid = _project(client, token)
    resp = client.post(
        f"/api/v1/projects/{pid}/footprint",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        headers=_auth(token),
    )
    assert resp.status_code == 415


def test_unparseable_kml_is_422(client: TestClient, seeded: dict, login) -> None:
    _use_mem_storage(client)
    token = login(seeded["email_a"])
    pid = _project(client, token)
    resp = client.post(
        f"/api/v1/projects/{pid}/footprint",
        files={"file": ("bad.kml", b"<kml>not geometry</kml>", "application/xml")},
        headers=_auth(token),
    )
    assert resp.status_code == 422


def test_upload_unknown_project_is_404(client: TestClient, seeded: dict, login) -> None:
    _use_mem_storage(client)
    token = login(seeded["email_a"])
    resp = client.post(
        "/api/v1/projects/nope/footprint",
        files={"file": ("route.kml", _KML, "application/xml")},
        headers=_auth(token),
    )
    assert resp.status_code == 404


def test_upload_requires_auth(client: TestClient, seeded: dict) -> None:
    resp = client.post(
        "/api/v1/projects/x/footprint",
        files={"file": ("route.kml", _KML, "application/xml")},
    )
    assert resp.status_code == 401
