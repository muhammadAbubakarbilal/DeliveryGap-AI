from uuid import uuid4

import pytest
from app.main import app
from app.source_jobs import run_parse
from app.source_storage import get_storage
from test_foundation import create_project


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, content: bytes) -> None:
        if key in self.objects:
            raise RuntimeError("immutable object already exists")
        self.objects[key] = content

    def get(self, key: str) -> bytes:
        return self.objects[key]


@pytest.fixture
def storage():
    value = MemoryStorage()
    app.dependency_overrides[get_storage] = lambda: value
    yield value
    app.dependency_overrides.pop(get_storage, None)


def source_path(project_id: str) -> str:
    return f"/api/v1/projects/{project_id}/documents"


def test_text_upload_parses_spans_and_is_idempotent(client, login, database, storage):
    login()
    project = create_project(client)
    path = source_path(project["id"])
    key = str(uuid4())
    response = client.post(
        path + "?filename=scope.md&title=Scope&kind=scope",
        content=b"REQ-001: Sign in.\nREQ-002: Checkout in USD.\n",
        headers={"Idempotency-Key": key, "content-type": "text/markdown"},
    )
    assert response.status_code == 201, response.text
    uploaded = response.json()
    assert uploaded["duplicate"] is False
    duplicate = client.post(
        path + "?filename=scope.md&title=Scope&kind=scope",
        content=b"REQ-001: Sign in.\nREQ-002: Checkout in USD.\n",
        headers={"Idempotency-Key": key, "content-type": "text/markdown"},
    )
    assert duplicate.status_code == 201
    assert duplicate.json() == uploaded
    run_parse(database, storage, uploaded["job_id"])
    job = client.get(f"{path}/{uploaded['document_id']}")
    assert job.status_code == 200
    assert job.json()["versions"][0]["status"] == "ready"
    spans = client.get(f"/api/v1/projects/{project['id']}/versions/{uploaded['version_id']}/spans")
    assert spans.status_code == 200
    assert [item["locator"] for item in spans.json()["items"]] == ["Line 1", "Line 2"]
    assert spans.json()["items"][0]["char_start"] == 0
    assert spans.json()["items"][0]["char_end"] == len("REQ-001: Sign in.\n")
    original = client.get(
        f"/api/v1/projects/{project['id']}/versions/{uploaded['version_id']}/download"
    )
    assert original.status_code == 200
    assert original.content.startswith(b"REQ-001")


def test_manual_text_with_no_selectable_source_is_explicitly_supported(
    client, login, database, storage
):
    login()
    project = create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/documents/manual",
        json={"title": "Authored scope", "kind": "scope", "text": "REQ-001: Sign in."},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 201, response.text
    run_parse(database, storage, response.json()["job_id"])
    version = client.get(
        f"/api/v1/projects/{project['id']}/documents/{response.json()['document_id']}"
    ).json()["versions"][0]
    assert version["is_manual"] is True
    assert version["status"] == "ready"


def test_rejects_oversize_and_malformed_sources_without_storage_write(client, login, storage):
    login()
    project = create_project(client)
    path = source_path(project["id"])
    oversized = client.post(
        path + "?filename=scope.txt&title=Too%20large",
        content=b"x" * (10 * 1024 * 1024 + 1),
        headers={"Idempotency-Key": str(uuid4()), "content-type": "text/plain"},
    )
    assert oversized.status_code == 413
    malformed = client.post(
        path + "?filename=scope.txt&title=Bad",
        content=b"\xff\xfe\x00",
        headers={"Idempotency-Key": str(uuid4()), "content-type": "text/plain"},
    )
    assert malformed.status_code == 422
    assert storage.objects == {}


def test_project_membership_is_required_for_source_reads(client, login, database, storage):
    login()
    project = create_project(client)
    response = client.post(
        source_path(project["id"]) + "?filename=scope.txt&title=Scope",
        content=b"private source",
        headers={"Idempotency-Key": str(uuid4()), "content-type": "text/plain"},
    )
    assert response.status_code == 201
    login("outsider")
    assert client.get(source_path(project["id"])).status_code == 404
    assert (
        client.get(
            f"/api/v1/projects/{project['id']}/versions/{response.json()['version_id']}/download"
        ).status_code
        == 404
    )
