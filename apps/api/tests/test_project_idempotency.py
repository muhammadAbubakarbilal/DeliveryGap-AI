import pytest
from app.models import AuditEvent, Member, Project, ProjectCreationRequest, User
from sqlalchemy import func, select


def test_project_retry_returns_original_response_once(client, login, database):
    login()
    headers = {"Idempotency-Key": "create-project-1"}
    body = {"name": "ShopFlow", "description": "Checkout"}
    first = client.post("/api/v1/projects", json=body, headers=headers)
    replay = client.post("/api/v1/projects", json=body, headers=headers)
    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Project)) == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.event_type == "project.created")
            )
            == 1
        )


def test_conflicting_payload_and_new_key(client, login, database):
    login()
    headers = {"Idempotency-Key": "stable-key"}
    first = client.post("/api/v1/projects", json={"name": "Original"}, headers=headers)
    assert first.status_code == 201
    conflict = client.post("/api/v1/projects", json={"name": "Different"}, headers=headers)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "CONFLICT"
    second = client.post(
        "/api/v1/projects", json={"name": "Original"}, headers={"Idempotency-Key": "new-key"}
    )
    assert second.status_code == 201
    assert second.json()["id"] != first.json()["id"]
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Project)) == 2


def test_replay_is_frozen_and_uses_validated_fields(client, login):
    login()
    headers = {"Idempotency-Key": "frozen-key"}
    first = client.post("/api/v1/projects", json={"name": " Original "}, headers=headers)
    path = f"/api/v1/projects/{first.json()['id']}"
    assert client.patch(path, json={"name": "Renamed", "revision": 1}).status_code == 200
    replay = client.post(
        "/api/v1/projects", json={"name": "Original", "description": ""}, headers=headers
    )
    assert replay.status_code == 201
    assert replay.json() == first.json()
    assert client.get(path).json()["name"] == "Renamed"


@pytest.mark.parametrize("key", [None, "", " ", "bad key", "x" * 129])
def test_key_required_and_bounded(client, login, database, key):
    login()
    headers = {} if key is None else {"Idempotency-Key": key}
    response = client.post("/api/v1/projects", json={"name": "No write"}, headers=headers)
    assert response.status_code == 422
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Project)) == 0


def test_keys_are_actor_scoped_and_replay_rechecks_authorization(client, login, database):
    login()
    headers = {"Idempotency-Key": "shared-key"}
    body = {"name": "Private"}
    first = client.post("/api/v1/projects", json=body, headers=headers)
    assert first.status_code == 201
    login("outsider")
    assert client.post("/api/v1/projects", json=body, headers=headers).status_code == 403
    with database() as db:
        db.get(User, "outsider").is_admin = True
        db.commit()
    second = client.post("/api/v1/projects", json=body, headers=headers)
    assert second.status_code == 201
    assert second.json()["id"] != first.json()["id"]
    with database() as db:
        db.get(User, "outsider").is_admin = False
        db.commit()
    assert client.post("/api/v1/projects", json=body, headers=headers).status_code == 403
    login()
    client.headers.pop("x-csrf-token")
    assert client.post("/api/v1/projects", json=body, headers=headers).status_code == 403
    client.cookies.clear()
    assert client.post("/api/v1/projects", json=body, headers=headers).status_code == 401


def test_failed_transaction_does_not_consume_key(client, login, database, monkeypatch):
    from app import project_creation

    login()
    headers = {"Idempotency-Key": "retry-after-rollback"}
    body = {"name": "Recoverable"}
    original = project_creation.audit

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        args[0].flush()
        raise RuntimeError("simulated failure after project and audit writes")

    monkeypatch.setattr(project_creation, "audit", fail)
    assert client.post("/api/v1/projects", json=body, headers=headers).status_code == 500
    with database() as db:
        for model in [Project, Member, ProjectCreationRequest]:
            assert db.scalar(select(func.count()).select_from(model)) == 0
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.event_type == "project.created")
            )
            == 0
        )
    monkeypatch.setattr(project_creation, "audit", original)
    assert client.post("/api/v1/projects", json=body, headers=headers).status_code == 201


@pytest.mark.parametrize("different_payload", [False, True])
def test_concurrent_project_creation_postgresql(database, login, different_payload):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from app.models import LoginSession
    from app.project_creation import create_project
    from app.schemas import ProjectCreate
    from app.security import Principal
    from fastapi import HTTPException
    from sqlalchemy import event

    engine = database.kw["bind"]
    if engine.dialect.name != "postgresql":
        pytest.skip("Requires TEST_DATABASE_URL for real PostgreSQL concurrency")
    login()
    barrier = Barrier(2)

    def synchronize(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO projects "):
            barrier.wait(timeout=15)

    def create(index):
        with database() as db:
            principal = Principal(db.get(User, "admin"), db.scalar(select(LoginSession)))
            name = f"Concurrent {index}" if different_payload else "Concurrent"
            try:
                result = create_project(db, principal, ProjectCreate(name=name), "race-key")
                return 201, result.id
            except HTTPException as exc:
                return exc.status_code, None

    event.listen(engine, "before_cursor_execute", synchronize)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(create, [1, 2]))
    finally:
        event.remove(engine, "before_cursor_execute", synchronize)
    if different_payload:
        assert sorted(status for status, _ in results) == [201, 409]
    else:
        assert results[0] == results[1]
        assert results[0][0] == 201
    with database() as db:
        for model in [Project, Member, ProjectCreationRequest]:
            assert db.scalar(select(func.count()).select_from(model)) == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.event_type == "project.created")
            )
            == 1
        )
