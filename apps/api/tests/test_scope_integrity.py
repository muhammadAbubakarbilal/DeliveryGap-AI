from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.main import app
from app.source_jobs import run_parse
from app.source_storage import get_storage
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_foundation import create_project
from test_sources import MemoryStorage


def grounded(client, login, database):
    login()
    project = create_project(client)
    base = f"/api/v1/projects/{project['id']}"
    storage = MemoryStorage()
    app.dependency_overrides[get_storage] = lambda: storage
    uploaded = client.post(
        base + "/documents/manual",
        json={"title": "Scope", "text": "Checkout accepts USD payments only."},
        headers={"Idempotency-Key": str(uuid4())},
    ).json()
    run_parse(database, storage, uploaded["job_id"])
    span = client.get(base + f"/versions/{uploaded['version_id']}/spans").json()["items"][0]
    body = {
        "title": "Checkout",
        "content": span["text"],
        "source_version_id": uploaded["version_id"],
        "source_span_id": span["id"],
        "source_quote": span["text"],
    }
    return base, body


def test_scope_commands_replay_and_approved_version_cannot_be_rejected(client, login, database):
    base, body = grounded(client, login, database)
    headers = {"Idempotency-Key": str(uuid4())}
    first = client.post(base + "/requirements", json=body, headers=headers)
    replay = client.post(base + "/requirements", json=body, headers=headers)
    assert first.status_code == replay.status_code == 201
    assert replay.json() == first.json()
    req = first.json()
    assert (
        client.post(
            base + f"/requirements/{req['id']}/approve", json={"expected_version": 1}
        ).status_code
        == 200
    )
    assert (
        client.post(
            base + f"/requirements/{req['id']}/reject", json={"expected_version": 1}
        ).status_code
        == 409
    )


def test_member_can_create_grounded_draft_but_not_approve(client, login, database):
    base, body = grounded(client, login, database)
    client.post(base + "/members", json={"email": "member@example.com", "role": "member"})
    login("member")
    response = client.post(
        base + "/requirements", json=body, headers={"Idempotency-Key": str(uuid4())}
    )
    assert response.status_code == 201
    assert (
        client.post(
            base + f"/requirements/{response.json()['id']}/approve", json={"expected_version": 1}
        ).status_code
        == 403
    )


def test_revision_preserves_published_scope_and_replays_commands(client, login, database):
    base, body = grounded(client, login, database)
    req = client.post(
        base + "/requirements", json=body, headers={"Idempotency-Key": str(uuid4())}
    ).json()
    approved = client.post(
        base + f"/requirements/{req['id']}/approve", json={"expected_version": 1}
    ).json()["versions"][0]
    headers = {"Idempotency-Key": str(uuid4())}
    selection = {"requirement_version_ids": [approved["id"]]}
    baseline = client.post(base + "/baselines", json=selection, headers=headers)
    assert baseline.status_code == 201, baseline.text
    assert (
        client.post(base + "/baselines", json=selection, headers=headers).json() == baseline.json()
    )
    edit = {**body, "title": "Revised checkout", "expected_version": 1}
    headers = {"Idempotency-Key": str(uuid4())}
    path = base + f"/requirements/{req['id']}/versions"
    revised = client.post(path, json=edit, headers=headers)
    assert revised.status_code == 201, revised.text
    assert revised.json()["current_version"] == 2
    assert client.post(path, json=edit, headers=headers).json() == revised.json()
    assert client.post(path, json={**edit, "title": "Changed"}, headers=headers).status_code == 409
    assert (
        client.post(path, json=edit, headers={"Idempotency-Key": str(uuid4())}).status_code == 409
    )
    saved = client.get(base + f"/baselines/{baseline.json()['id']}").json()
    assert saved["items"] == baseline.json()["items"]
    assert saved["number"] == baseline.json()["number"]
    second = client.post(
        base + f"/requirements/{req['id']}/approve", json={"expected_version": 2}
    ).json()["versions"][0]
    assert (
        client.post(
            base + "/baselines",
            json={"requirement_version_ids": [approved["id"], second["id"]]},
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code
        == 422
    )


def test_migrated_database_rejects_history_mutation(client, login, database):
    # Install only the guard migration over this disposable metadata-created test DB.
    root = Path(__file__).resolve().parents[3]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "apps/api/alembic"))
    engine = database.kw["bind"]
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.stamp(config, "0006")
        command.upgrade(config, "0007")
    base, body = grounded(client, login, database)
    req = client.post(
        base + "/requirements", json=body, headers={"Idempotency-Key": str(uuid4())}
    ).json()
    approved = client.post(
        base + f"/requirements/{req['id']}/approve", json={"expected_version": 1}
    )
    assert approved.status_code == 200, approved.text
    version = approved.json()["versions"][0]["id"]
    baseline = client.post(
        base + "/baselines",
        json={"requirement_version_ids": [version]},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert baseline.status_code == 201, baseline.text
    for statement in (
        "UPDATE requirement_versions SET content = 'tampered'",
        "UPDATE requirement_versions SET status = 'rejected'",
        "DELETE FROM requirement_versions",
        "DELETE FROM baseline_items",
        "UPDATE baselines SET number = 99",
        "DELETE FROM requirement_review_events",
    ):
        with engine.connect() as connection:
            with pytest.raises(DBAPIError), connection.begin():
                connection.execute(text(statement))
