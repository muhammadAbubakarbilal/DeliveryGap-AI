from uuid import uuid4

from app.main import app
from app.source_jobs import run_parse
from app.source_storage import get_storage
from test_foundation import create_project


class Storage:
    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}

    def put(self, key: str, content: bytes) -> None:
        self.data[key] = content

    def get(self, key: str) -> bytes:
        return self.data[key]


def test_analysis_classifies_against_published_baseline_and_records_decision(
    client, login, database
):
    storage = Storage()
    app.dependency_overrides[get_storage] = lambda: storage
    try:
        login()
        project = create_project(client)
        source = client.post(
            f"/api/v1/projects/{project['id']}/documents?filename=scope.md&title=Scope",
            content=b"Checkout accepts USD payments only.",
            headers={"Idempotency-Key": str(uuid4()), "content-type": "text/markdown"},
        ).json()
        run_parse(database, storage, source["job_id"])
        span = client.get(
            f"/api/v1/projects/{project['id']}/versions/{source['version_id']}/spans"
        ).json()["items"][0]
        req = client.post(
            f"/api/v1/projects/{project['id']}/requirements",
            json={
                "code": "REQ-003",
                "title": "Currency",
                "content": "Checkout accepts USD payments only.",
                "source_version_id": source["version_id"],
                "source_span_id": span["id"],
                "source_quote": "Checkout accepts USD payments only.",
            },
            headers={"Idempotency-Key": str(uuid4())},
        ).json()
        client.post(
            f"/api/v1/projects/{project['id']}/requirements/{req['id']}/approve",
            json={"expected_version": 1},
        )
        baseline = client.post(
            f"/api/v1/projects/{project['id']}/baselines",
            json={"requirement_version_ids": [req["versions"][0]["id"]]},
            headers={"Idempotency-Key": str(uuid4())},
        ).json()
        analysis = client.post(
            f"/api/v1/projects/{project['id']}/analysis",
            json={"baseline_id": baseline["id"], "input_text": "Add EUR and GBP checkout."},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert analysis.status_code == 201, analysis.text
        finding = analysis.json()["findings"][0]
        assert finding["classification"] == "CONFLICT"
        decision = client.post(
            f"/api/v1/projects/{project['id']}/findings/{finding['id']}/decision",
            json={"decision": "confirmed", "expected_status": "pending", "expected_revision": 1},
        )
        assert decision.status_code == 200
        assert decision.json()["review_status"] == "confirmed"
        assert (
            client.post(
                f"/api/v1/projects/{project['id']}/findings/{finding['id']}/decision",
                json={
                    "decision": "dismissed",
                    "expected_status": "confirmed",
                    "expected_revision": 1,
                },
            ).status_code
            == 409
        )
        assert (
            client.post(
                f"/api/v1/projects/{project['id']}/analysis",
                json={"baseline_id": baseline["id"], "input_text": "Random text mentions checkout"},
                headers={"Idempotency-Key": str(uuid4())},
            ).status_code
            == 422
        )
    finally:
        app.dependency_overrides.pop(get_storage, None)
