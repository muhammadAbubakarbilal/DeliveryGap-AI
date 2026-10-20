from uuid import uuid4

from app.evidence_models import DeliveryArtifact
from app.operation_jobs import execute_with
from app.operation_models import Operation
from app.report_service import safe_cell
from sqlalchemy import select
from test_scope_integrity import grounded


def post(client, path, body, key=None):
    return client.post(path, json=body, headers={"Idempotency-Key": key or str(uuid4())})


def test_custom_headers_are_validated_frozen_and_committed(client, login, database):
    base, saved = baseline(client, login, database)
    body = {
        "kind": "task",
        "baseline_id": saved["id"],
        "csv_text": "Ticket,Summary,Details,State,Scope\nTASK-42,Checkout,USD,done,REQ-001\n",
        "column_mapping": {
            "external_id": "Ticket",
            "title": "Summary",
            "description": "Details",
            "status": "State",
            "requirement_id": "Scope",
        },
    }
    response = post(client, base + "/imports/preview", body)
    assert response.status_code == 201, response.text
    preview = response.json()
    assert not preview["rows"][0]["errors"]
    assert preview["rows"][0]["artifact"]["external_id"] == "TASK-42"
    with database() as db:
        assert db.get(Operation, preview["id"]).payload["column_mapping"] == body["column_mapping"]
    assert post(client, base + f"/imports/{preview['id']}/commit", {}).status_code == 202
    execute_with(database, preview["id"])
    assert client.get(base + "/artifacts").json()[0]["external_id"] == "TASK-42"
    for mapping in [
        {"title": "Absent"},
        {"title": "Ticket", "external_id": "Ticket"},
        {"unexpected": "Ticket"},
    ]:
        assert (
            post(client, base + "/imports/preview", {**body, "column_mapping": mapping}).status_code
            == 422
        )


def baseline(client, login, database):
    base, body = grounded(client, login, database)
    req = post(client, base + "/requirements", body).json()
    client.post(base + f"/requirements/{req['id']}/approve", json={"expected_version": 1})
    saved = post(
        client, base + "/baselines", {"requirement_version_ids": [req["versions"][0]["id"]]}
    ).json()
    return base, saved


def test_import_preview_partial_replay_and_revision_preservation(client, login, database):
    base, saved = baseline(client, login, database)
    csv_text = (
        "external_id,title,description,status,requirement_id\n"
        "T-1,Checkout,USD,done,REQ-001\nT-2,,bad,wat,REQ-001\n"
    )
    body = {"kind": "task", "baseline_id": saved["id"], "csv_text": csv_text}
    key = str(uuid4())
    response = post(client, base + "/imports/preview", body, key)
    assert response.status_code == 201, response.text
    preview = response.json()
    assert post(client, base + "/imports/preview", body, key).json() == preview
    assert not preview["rows"][0]["errors"] and preview["rows"][1]["errors"]
    commit = base + f"/imports/{preview['id']}/commit"
    assert post(client, commit, {}).status_code == 422
    queued = post(client, commit, {"accept_partial": True}, key)
    assert queued.status_code == 202, queued.text
    assert post(client, commit, {"accept_partial": True}, key).json() == queued.json()
    execute_with(database, preview["id"])
    execute_with(database, preview["id"])
    result = client.get(base + f"/operations/{preview['id']}").json()
    assert result["result"] == {"accepted": 1, "rejected": 1, "changed": 1, "unchanged": 0}
    again = post(client, base + "/imports/preview", body).json()
    assert (
        post(client, base + f"/imports/{again['id']}/commit", {"accept_partial": True}).status_code
        == 202
    )
    execute_with(database, again["id"])
    assert client.get(base + f"/operations/{again['id']}").json()["result"]["unchanged"] == 1
    matrix = client.get(base + "/traceability", params={"baseline_id": saved["id"]}).json()
    assert matrix[0]["links"][0]["review_status"] == "proposed"
    assert matrix[0]["links"][0]["artifact_revision"] == 1
    login("outsider")
    assert client.get(base + f"/operations/{preview['id']}").status_code == 404


def test_test_csv_metadata_persists_and_identical_reimport_is_unchanged(client, login, database):
    base, saved = baseline(client, login, database)
    csv_text = (
        "test_id,name,result,executed_at,environment,requirement_id\n"
        "TEST-META,Checkout,pass,2026-10-19T15:30:00+05:30,staging / Chrome,REQ-001\n"
    )
    body = {"kind": "test", "baseline_id": saved["id"], "csv_text": csv_text}
    preview = post(client, base + "/imports/preview", body)
    assert preview.status_code == 201, preview.text
    preview_row = preview.json()["rows"][0]
    assert not preview_row["errors"]
    assert preview_row["artifact"]["executed_at"] == "2026-10-19T10:00:00Z"
    assert preview_row["artifact"]["environment"] == "staging / Chrome"
    commit = base + f"/imports/{preview.json()['id']}/commit"
    assert post(client, commit, {}).status_code == 202
    execute_with(database, preview.json()["id"])
    artifacts = client.get(base + "/artifacts").json()
    artifact = next(row for row in artifacts if row["external_id"] == "TEST-META")
    assert artifact["executed_at"] == "2026-10-19T10:00:00Z"
    assert artifact["environment"] == "staging / Chrome"
    history = client.get(base + f"/artifacts/{artifact['id']}/history").json()
    assert history[0]["executed_at"] == artifact["executed_at"]
    assert history[0]["environment"] == artifact["environment"]

    repeat = post(client, base + "/imports/preview", body)
    assert repeat.status_code == 201, repeat.text
    assert post(client, base + f"/imports/{repeat.json()['id']}/commit", {}).status_code == 202
    execute_with(database, repeat.json()["id"])
    result = client.get(base + f"/operations/{repeat.json()['id']}").json()["result"]
    assert result == {"accepted": 1, "rejected": 0, "changed": 0, "unchanged": 1}


def test_csv_aliases_duplicates_timezone_and_unsafe_url(client, login, database):
    base, saved = baseline(client, login, database)
    csv_text = (
        "test_id,name,result,executed_at,requirement_id,related_requirement_id,url\n"
        "X,Test,PASSED,2026-10-19T10:00:00,REQ-001,REQ-002,javascript:alert(1)\n"
        "X,Test,pass,2026-10-19T10:00:00Z,REQ-001,REQ-001,https://example.com/test\n"
    )
    response = post(
        client,
        base + "/imports/preview",
        {"kind": "test", "baseline_id": saved["id"], "csv_text": csv_text},
    )
    assert response.status_code == 201, response.text
    rows = response.json()["rows"]
    assert len(rows[0]["errors"]) >= 4
    assert rows[1]["errors"] == ["Duplicate identifier in this CSV"]
    assert (
        post(
            client, base + f"/imports/{response.json()['id']}/commit", {"accept_partial": True}
        ).status_code
        == 422
    )
    assert safe_cell("  =SUM(A1)").startswith("'")
    assert safe_cell("@formula").startswith("'")


def test_report_is_frozen_and_updated_evidence_is_stale(client, login, database):
    base, saved = baseline(client, login, database)
    artifact_body = {
        "kind": "test",
        "external_id": "TEST-1",
        "title": "Original",
        "status": "pass",
        "executed_at": "2026-10-19T10:00:00Z",
        "environment": "staging / Chrome",
    }
    artifact = post(client, base + "/artifacts", artifact_body).json()
    link = post(
        client,
        base + "/traceability/links",
        {
            "artifact_id": artifact["id"],
            "requirement_version_id": saved["items"][0]["requirement_version_id"],
            "accept": True,
            "expected_artifact_revision": 1,
        },
    ).json()
    assert link["artifact_revision"] == 1
    queued = post(client, base + "/reports", {"baseline_id": saved["id"]})
    assert queued.status_code == 202, queued.text
    execute_with(database, queued.json()["id"])
    execute_with(database, queued.json()["id"])
    report_id = client.get(base + f"/operations/{queued.json()['id']}").json()["result"][
        "report_id"
    ]
    path = base + f"/reports/{report_id}"
    frozen = client.get(path).json()
    assert frozen["requirements"] and "links" in frozen["requirements"][0], list(
        frozen["requirements"][0]
    )
    frozen_artifact = frozen["requirements"][0]["links"][0]["artifact"]
    assert frozen_artifact["executed_at"] == "2026-10-19T10:00:00Z"
    assert frozen_artifact["environment"] == "staging / Chrome"
    download = client.get(path + "/download?format=csv").content
    assert (
        post(
            client,
            base + "/artifacts",
            {**artifact_body, "title": "Changed", "expected_revision": 1},
        ).status_code
        == 201
    )
    assert client.get(path).json() == frozen
    assert client.get(path + "/download?format=csv").content == download
    counts = client.get(base + "/overview", params={"baseline_id": saved["id"]}).json()
    assert counts["stale_links"] == 1 and counts["accepted_current_evidence"] == 0
    assert (
        client.get(
            base + "/traceability", params={"baseline_id": saved["id"], "coverage": "current"}
        ).json()
        == []
    )
    assert (
        len(
            client.get(
                base + "/traceability", params={"baseline_id": saved["id"], "coverage": "missing"}
            ).json()
        )
        == 1
    )
    assert (
        post(
            client,
            base + f"/traceability/links/{link['id']}/review",
            {
                "review_status": "accepted",
                "expected_revision": link["revision"],
                "expected_artifact_revision": 1,
            },
        ).status_code
        == 409
    )
    assert client.get(base + "/traceability", params={"baseline_id": saved["id"]}).json()[0][
        "links"
    ][0]["stale"]
    login("outsider")
    assert client.get(path + "/download").status_code == 404


def test_report_filters_are_project_and_baseline_scoped_and_frozen(client, login, database):
    base, saved = baseline(client, login, database)
    run = post(
        client,
        base + "/analysis",
        {"baseline_id": saved["id"], "input_text": "Add EUR and GBP checkout."},
    ).json()
    selected = {
        "baseline_id": saved["id"],
        "run_ids": [run["id"]],
        "classifications": ["CONFLICT"],
        "review_statuses": ["pending"],
    }
    queued = post(client, base + "/reports", selected)
    assert queued.status_code == 202, queued.text
    execute_with(database, queued.json()["id"])
    report_id = client.get(base + f"/operations/{queued.json()['id']}").json()["result"][
        "report_id"
    ]
    snapshot = client.get(base + f"/reports/{report_id}").json()
    assert snapshot["filters"] == {
        "run_ids": [run["id"]],
        "classifications": ["CONFLICT"],
        "review_statuses": ["pending"],
    }
    assert len(snapshot["findings"]) == 1
    assert snapshot["findings"][0]["run_id"] == run["id"]
    assert snapshot["findings"][0]["classification"] == "CONFLICT"
    assert (
        post(
            client,
            base + "/reports",
            {**selected, "run_ids": ["not-a-run"]},
        ).status_code
        == 422
    )
    assert "Filters:" in client.get(base + f"/reports/{report_id}/download?format=md").text


def test_queued_import_rechecks_access_and_stale_preview_rolls_back(client, login, database):
    base, saved = baseline(client, login, database)
    client.post(base + "/members", json={"email": "member@example.com", "role": "member"})
    login("member")
    body = {"kind": "task", "csv_text": "external_id,title,description,status\nT,Title,Body,done\n"}
    preview = post(client, base + "/imports/preview", body).json()
    post(client, base + f"/imports/{preview['id']}/commit", {})
    login()
    client.delete(base + "/members/member")
    execute_with(database, preview["id"])
    with database() as db:
        assert db.get(Operation, preview["id"]).status == "failed"
        assert db.scalar(select(DeliveryArtifact)) is None
    first = post(client, base + "/imports/preview", body).json()
    second = post(client, base + "/imports/preview", body).json()
    for item in [first, second]:
        post(client, base + f"/imports/{item['id']}/commit", {})
        execute_with(database, item["id"])
    assert client.get(base + f"/operations/{second['id']}").json()["status"] == "failed"
