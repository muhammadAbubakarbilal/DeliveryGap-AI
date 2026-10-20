from uuid import uuid4

from app.main import app
from app.source_jobs import run_parse
from app.source_storage import get_storage
from test_foundation import create_project
from test_scope_integrity import grounded


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, content: bytes) -> None:
        self.objects[key] = content

    def get(self, key: str) -> bytes:
        return self.objects[key]


def test_grounded_requirement_approval_and_baseline_publication(client, login, database):
    storage = MemoryStorage()
    app.dependency_overrides[get_storage] = lambda: storage
    try:
        login()
        project = create_project(client)
        source = client.post(
            f"/api/v1/projects/{project['id']}/documents?filename=scope.md&title=Scope",
            content=b"The checkout accepts USD payments only.\n",
            headers={"Idempotency-Key": str(uuid4()), "content-type": "text/markdown"},
        )
        assert source.status_code == 201, source.text
        source_data = source.json()
        run_parse(database, storage, source_data["job_id"])
        spans = client.get(
            f"/api/v1/projects/{project['id']}/versions/{source_data['version_id']}/spans"
        ).json()["items"]
        requirement = client.post(
            f"/api/v1/projects/{project['id']}/requirements",
            json={
                "code": "REQ-003",
                "title": "USD-only checkout",
                "content": "Checkout accepts USD payments only.",
                "source_version_id": source_data["version_id"],
                "source_span_id": spans[0]["id"],
                "source_quote": "checkout accepts USD payments only",
            },
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert requirement.status_code == 201, requirement.text
        requirement_data = requirement.json()
        version_id = requirement_data["versions"][0]["id"]
        approved = client.post(
            f"/api/v1/projects/{project['id']}/requirements/{requirement_data['id']}/approve",
            json={"expected_version": 1},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["versions"][0]["status"] == "approved"
        baseline = client.post(
            f"/api/v1/projects/{project['id']}/baselines",
            json={"requirement_version_ids": [version_id]},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert baseline.status_code == 201, baseline.text
        assert baseline.json()["number"] == 1
        assert baseline.json()["items"][0]["requirement_code"] == "REQ-003"
        assert client.get(f"/api/v1/projects/{project['id']}/baselines").json()[0]["number"] == 1
    finally:
        app.dependency_overrides.pop(get_storage, None)


def test_ungrounded_requirement_cannot_be_approved(client, login):
    login()
    project = create_project(client)
    requirement = client.post(
        f"/api/v1/projects/{project['id']}/requirements",
        json={"title": "Refunds", "content": "Admins can refund orders."},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert requirement.status_code == 201
    body = requirement.json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/requirements/{body['id']}/approve",
        json={"expected_version": 1},
    )
    assert response.status_code == 422


def test_split_supersedes_parent_without_changing_published_baseline(client, login, database):
    base, source = grounded(client, login, database)
    parent = client.post(
        base + "/requirements", json=source, headers={"Idempotency-Key": str(uuid4())}
    ).json()
    approved = client.post(
        base + f"/requirements/{parent['id']}/approve", json={"expected_version": 1}
    )
    assert approved.status_code == 200, approved.text
    version_id = approved.json()["versions"][0]["id"]
    baseline = client.post(
        base + "/baselines",
        json={"requirement_version_ids": [version_id]},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    body = {
        "action": "split",
        "parents": [{"requirement_id": parent["id"], "expected_version": 1}],
        "children": [
            {
                "title": "Checkout payment currency",
                "content": "Checkout accepts USD payments only.",
                "source_version_id": source["source_version_id"],
                "source_span_id": source["source_span_id"],
                "source_quote": source["source_quote"],
            },
            {
                "title": "Checkout currency validation",
                "content": "Checkout rejects unsupported currencies.",
                "source_version_id": source["source_version_id"],
                "source_span_id": source["source_span_id"],
                "source_quote": source["source_quote"],
            },
        ],
    }
    client.post(base + "/members", json={"email": "member@example.com", "role": "member"})
    login("member")
    assert (
        client.post(
            base + "/requirements/transform",
            json=body,
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code
        == 403
    )

    login()
    key = str(uuid4())
    transformed = client.post(
        base + "/requirements/transform", json=body, headers={"Idempotency-Key": key}
    )
    assert transformed.status_code == 201, transformed.text
    assert (
        client.post(
            base + "/requirements/transform", json=body, headers={"Idempotency-Key": key}
        ).json()
        == transformed.json()
    )
    result = transformed.json()
    assert result["superseded_requirement_ids"] == [parent["id"]]
    assert len(result["children"]) == 2
    assert all(child["status"] == "active" for child in result["children"])
    assert all(child["versions"][0]["status"] == "draft" for child in result["children"])
    assert all(child["lineage"][0]["action"] == "split" for child in result["children"])
    assert all(
        child["lineage"][0]["parent_requirement_code"] == parent["code"]
        for child in result["children"]
    )
    assert client.get(base + f"/requirements/{parent['id']}").json()["status"] == "superseded"
    assert client.get(base + f"/baselines/{baseline['id']}").json()["items"] == baseline["items"]
    assert (
        client.post(
            base + "/baselines",
            json={"requirement_version_ids": [version_id]},
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code
        == 422
    )
    assert (
        client.post(
            base + f"/requirements/{parent['id']}/versions",
            json={**source, "expected_version": 1},
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code
        == 409
    )


def test_merge_records_each_parent_and_rejects_stale_parent_revision(client, login, database):
    base, source = grounded(client, login, database)
    parents = []
    for title in ("Checkout currencies", "Supported payment currencies"):
        draft = client.post(
            base + "/requirements",
            json={**source, "title": title},
            headers={"Idempotency-Key": str(uuid4())},
        ).json()
        approved = client.post(
            base + f"/requirements/{draft['id']}/approve", json={"expected_version": 1}
        )
        assert approved.status_code == 200, approved.text
        parents.append(draft)
    body = {
        "action": "merge",
        "parents": [{"requirement_id": parent["id"], "expected_version": 1} for parent in parents],
        "children": [
            {
                "title": "Checkout supported currencies",
                "content": "Checkout accepts supported payment currencies.",
                "source_version_id": source["source_version_id"],
                "source_span_id": source["source_span_id"],
                "source_quote": source["source_quote"],
            }
        ],
    }
    response = client.post(
        base + "/requirements/transform", json=body, headers={"Idempotency-Key": str(uuid4())}
    )
    assert response.status_code == 201, response.text
    child = response.json()["children"][0]
    assert child["lineage"][0]["action"] == "merge"
    assert {edge["parent_requirement_id"] for edge in child["lineage"]} == {
        parent["id"] for parent in parents
    }
    stale = client.post(
        base + "/requirements/transform",
        json=body,
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert stale.status_code == 409
