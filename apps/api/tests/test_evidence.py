from uuid import uuid4

from app.models import AuditEvent
from sqlalchemy import select
from test_foundation import create_project
from test_scope_integrity import grounded


def test_manual_artifact_upsert_is_project_scoped(client, login, database):
    login()
    project = create_project(client)
    path = f"/api/v1/projects/{project['id']}/artifacts"
    first = client.post(
        path,
        json={"kind": "test", "external_id": "T" * 120, "title": "USD checkout", "status": "pass"},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert first.status_code == 201, first.text
    second = client.post(
        path,
        json={
            "kind": "test",
            "external_id": "T" * 120,
            "title": "USD checkout updated",
            "status": "pass",
            "expected_revision": 1,
        },
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["title"] == "USD checkout updated"
    history = client.get(path + f"/{first.json()['id']}/history").json()
    assert [row["title"] for row in history] == ["USD checkout updated", "USD checkout"]
    with database() as db:
        events = list(
            db.scalars(
                select(AuditEvent).where(
                    AuditEvent.event_type == "artifact.recorded",
                    AuditEvent.project_id == project["id"],
                )
            )
        )
        assert len(events) == 2
        assert all(event.target_id == first.json()["id"] for event in events)
        assert all(event.details["external_id"] == "T" * 120 for event in events)


def test_test_artifact_metadata_is_timezone_normalized_and_versioned(client, login):
    login()
    project = create_project(client)
    path = f"/api/v1/projects/{project['id']}/artifacts"
    first = client.post(
        path,
        json={
            "kind": "test",
            "external_id": "TEST-META",
            "title": "Checkout",
            "status": "pass",
            "executed_at": "2026-10-19T15:30:00+05:30",
            "environment": "staging / Chrome",
        },
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert first.status_code == 201, first.text
    assert first.json()["executed_at"] == "2026-10-19T10:00:00Z"
    assert first.json()["environment"] == "staging / Chrome"
    updated = client.post(
        path,
        json={
            "kind": "test",
            "external_id": "TEST-META",
            "title": "Checkout",
            "status": "pass",
            "executed_at": "2026-10-20T12:00:00-04:00",
            "environment": "production / Firefox",
            "expected_revision": 1,
        },
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert updated.status_code == 201, updated.text
    assert updated.json()["executed_at"] == "2026-10-20T16:00:00Z"
    history = client.get(path + f"/{first.json()['id']}/history").json()
    assert [(row["executed_at"], row["environment"]) for row in history] == [
        ("2026-10-20T16:00:00Z", "production / Firefox"),
        ("2026-10-19T10:00:00Z", "staging / Chrome"),
    ]
    for metadata in [
        {"executed_at": "2026-10-19T10:00:00"},
        {"environment": "staging"},
    ]:
        invalid = client.post(
            path,
            json={
                "kind": "task",
                "external_id": f"INVALID-{uuid4()}",
                "title": "Task",
                **metadata,
            },
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert invalid.status_code == 422


def test_member_proposes_link_lead_reviews_with_revision(client, login, database):
    base, body = grounded(client, login, database)
    req = client.post(
        base + "/requirements", json=body, headers={"Idempotency-Key": str(uuid4())}
    ).json()
    client.post(base + f"/requirements/{req['id']}/approve", json={"expected_version": 1})
    version = req["versions"][0]["id"]
    baseline = client.post(
        base + "/baselines",
        json={"requirement_version_ids": [version]},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    client.post(base + "/members", json={"email": "member@example.com", "role": "member"})
    login("member")
    headers = {"Idempotency-Key": str(uuid4())}
    artifact_body = {"kind": "test", "external_id": "TEST-1", "title": "Checkout"}
    artifact = client.post(base + "/artifacts", json=artifact_body, headers=headers)
    assert artifact.status_code == 201, artifact.text
    assert (
        client.post(base + "/artifacts", json=artifact_body, headers=headers).json()
        == artifact.json()
    )
    link_body = {"requirement_version_id": version, "artifact_id": artifact.json()["id"]}
    assert (
        client.post(
            base + "/traceability/links",
            json={**link_body, "accept": True},
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code
        == 403
    )
    link = client.post(
        base + "/traceability/links", json=link_body, headers={"Idempotency-Key": str(uuid4())}
    )
    assert link.status_code == 201, link.text
    assert link.json()["review_status"] == "proposed"
    review_path = base + f"/traceability/links/{link.json()['id']}/review"
    decision = {
        "review_status": "accepted",
        "expected_revision": 1,
        "expected_artifact_revision": 1,
    }
    assert client.post(review_path, json=decision).status_code == 403
    login()
    accepted = client.post(review_path, json=decision)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["revision"] == 2
    assert client.post(review_path, json=decision).status_code == 409
    matrix = client.get(base + "/traceability", params={"baseline_id": baseline["id"]}).json()
    assert matrix[0]["links"][0]["review_status"] == "accepted"
    login("outsider")
    assert client.get(base + "/artifacts").status_code == 404
    assert (
        client.get(base + "/traceability", params={"baseline_id": baseline["id"]}).status_code
        == 404
    )


def test_bulk_link_review_is_atomic_idempotent_and_lead_only(client, login, database):
    base, body = grounded(client, login, database)
    req = client.post(
        base + "/requirements", json=body, headers={"Idempotency-Key": str(uuid4())}
    ).json()
    client.post(base + f"/requirements/{req['id']}/approve", json={"expected_version": 1})
    version_id = req["versions"][0]["id"]
    baseline = client.post(
        base + "/baselines",
        json={"requirement_version_ids": [version_id]},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert baseline.status_code == 201, baseline.text
    artifacts = []
    for index in range(1, 4):
        artifact_response = client.post(
            base + "/artifacts",
            json={"kind": "test", "external_id": f"BULK-{index}", "title": f"Test {index}"},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert artifact_response.status_code == 201, artifact_response.text
        artifacts.append(artifact_response.json())
    links = []
    for artifact in artifacts:
        link_response = client.post(
            base + "/traceability/links",
            json={"requirement_version_id": version_id, "artifact_id": artifact["id"]},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert link_response.status_code == 201, link_response.text
        links.append(link_response.json())
    path = base + "/traceability/links/bulk-review"
    decisions = [
        {
            "link_id": link["id"],
            "expected_revision": 1,
            "expected_artifact_revision": 1,
            "review_status": "accepted",
        }
        for link in links[:2]
    ]
    key = str(uuid4())
    accepted = client.post(path, json={"decisions": decisions}, headers={"Idempotency-Key": key})
    assert accepted.status_code == 200, accepted.text
    assert [row["review_status"] for row in accepted.json()["items"]] == ["accepted", "accepted"]
    replayed = client.post(path, json={"decisions": decisions}, headers={"Idempotency-Key": key})
    assert replayed.json() == accepted.json()

    client.post(base + "/members", json={"email": "member@example.com", "role": "member"})
    login("member")
    assert (
        client.post(
            path,
            json={"decisions": [dict(decisions[0], expected_revision=2)]},
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code
        == 403
    )
    login()
    stale_batch = [
        dict(decisions[0], expected_revision=2),
        {
            "link_id": links[2]["id"],
            "expected_revision": 1,
            "expected_artifact_revision": 2,
            "review_status": "accepted",
        },
    ]
    conflict = client.post(
        path, json={"decisions": stale_batch}, headers={"Idempotency-Key": str(uuid4())}
    )
    assert conflict.status_code == 409
    matrix = client.get(
        base + "/traceability", params={"baseline_id": baseline.json()["id"]}
    ).json()
    statuses = {link["id"]: link["review_status"] for row in matrix for link in row["links"]}
    assert statuses[links[2]["id"]] == "proposed"
    revisions = {link["id"]: link["revision"] for row in matrix for link in row["links"]}
    assert revisions[links[0]["id"]] == 2
