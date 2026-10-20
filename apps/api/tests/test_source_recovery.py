from datetime import timedelta
from uuid import uuid4

import pytest
from app.main import app
from app.models import now
from app.source_jobs import dispatch, run_parse
from app.source_models import DocumentVersion, JobAttempt, OutboxEvent, ParseJob, SourceSpan
from app.source_storage import get_storage
from sqlalchemy import func, select
from test_foundation import create_project
from test_sources import MemoryStorage


@pytest.fixture
def storage():
    value = MemoryStorage()
    app.dependency_overrides[get_storage] = lambda: value
    yield value
    app.dependency_overrides.pop(get_storage, None)


def upload(client, login):
    login()
    project = create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/documents/manual",
        json={"title": "Recovery", "text": "Immutable original."},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 201
    return response.json()


def test_redis_failure_duplicate_delivery_and_revoked_actor(client, login, database, storage):
    source = upload(client, login)

    def unavailable(*args):
        raise ConnectionError("synthetic unavailable queue")

    dispatch(database, unavailable)
    with database() as db:
        assert db.get(OutboxEvent, source["job_id"]).dispatched_at is None
    run_parse(database, storage, source["job_id"])
    run_parse(database, storage, source["job_id"])
    with database() as db:
        assert db.scalar(select(func.count()).select_from(SourceSpan)) == 1
        assert db.get(ParseJob, source["job_id"]).attempts == 1


def test_expired_attempt_is_fenced_and_recovered(client, login, database, storage):
    source = upload(client, login)
    with database() as db:
        job = db.get(ParseJob, source["job_id"])
        job.status, job.fence, job.attempts, job.cycle_attempts = "running", "old-fence", 1, 1
        job.lease_until = now() - timedelta(seconds=1)
        db.add(JobAttempt(job_id=job.id, number=1, fence="old-fence", status="running"))
        db.commit()
    dispatch(database, lambda *_: None)
    with database() as db:
        assert db.scalar(select(JobAttempt)).status == "lost"
        event = db.get(OutboxEvent, source["job_id"])
        event.available_at = now() - timedelta(seconds=1)
        db.commit()
    run_parse(database, storage, source["job_id"])
    with database() as db:
        job = db.get(ParseJob, source["job_id"])
        assert job.status == "succeeded" and job.fence != "old-fence"
        assert db.scalar(select(func.count()).select_from(SourceSpan)) == 1


@pytest.mark.parametrize("blocked_state", ["running", "delayed", "dispatched"])
def test_ineligible_jobs_do_not_starve_ready_sources(
    client, login, database, storage, blocked_state
):
    source = upload(client, login)
    with database() as db:
        original = db.get_one(DocumentVersion, source["version_id"])
        ready = db.get_one(ParseJob, source["job_id"])
        # Deterministic IDs place the ready upload after a full dispatch window.
        for index in range(100):
            version = DocumentVersion(
                id=f"blocked-version-{index}",
                project_id=original.project_id,
                document_id=original.document_id,
                version_number=index + 2,
                filename=original.filename,
                mime_type=original.mime_type,
                sha256=original.sha256,
                storage_key=f"blocked/{index}",
                byte_size=original.byte_size,
                uploaded_by=original.uploaded_by,
            )
            db.add(version)
            db.flush()
            job = ParseJob(
                id=f"00000000-0000-0000-0000-{index:012}",
                project_id=ready.project_id,
                version_id=version.id,
                actor_id=ready.actor_id,
                status="running" if blocked_state == "running" else "queued",
                lease_until=now() + timedelta(hours=1) if blocked_state == "running" else None,
            )
            db.add(job)
            db.flush()
            db.add(
                OutboxEvent(
                    job_id=job.id,
                    available_at=now() + timedelta(hours=1)
                    if blocked_state == "delayed"
                    else now() - timedelta(seconds=1),
                    dispatched_at=now() if blocked_state == "dispatched" else None,
                )
            )
        db.commit()

    deliveries = []
    dispatch(database, lambda job_id, delivery_id: deliveries.append((job_id, delivery_id)))
    assert deliveries == [(source["job_id"], f"parse-{source['job_id']}-0")]
    dispatch(database, lambda *args: deliveries.append(args))
    assert len(deliveries) == 1
    run_parse(database, storage, source["job_id"])
    with database() as db:
        assert db.get_one(ParseJob, source["job_id"]).status == "succeeded"


def test_storage_retry_exhaustion_and_manual_recovery(client, login, database, storage):
    source = upload(client, login)

    class UnavailableStorage:
        def get(self, key):
            raise ConnectionError("synthetic dependency outage")

    for attempt in range(1, 4):
        with database() as db:
            db.get_one(OutboxEvent, source["job_id"]).available_at = now() - timedelta(seconds=1)
            db.commit()
        run_parse(database, UnavailableStorage(), source["job_id"])
        with database() as db:
            job = db.get_one(ParseJob, source["job_id"])
            assert job.attempts == attempt
            assert job.status == ("failed" if attempt == 3 else "queued")
            assert db.scalar(select(func.count()).select_from(SourceSpan)) == 0
    deliveries = []
    dispatch(database, lambda *args: deliveries.append(args))
    assert deliveries == []
    with database() as db:
        project_id = db.get_one(ParseJob, source["job_id"]).project_id
    path = f"/api/v1/projects/{project_id}/versions/{source['version_id']}/retry"
    headers = {"Idempotency-Key": str(uuid4())}
    assert client.post(path, headers=headers).status_code == 200
    assert client.post(path, headers=headers).status_code == 200
    run_parse(database, storage, source["job_id"])
    run_parse(database, storage, source["job_id"])
    with database() as db:
        job = db.get_one(ParseJob, source["job_id"])
        assert job.status == "succeeded" and job.attempts == 4 and job.cycle_attempts == 1
        assert db.scalar(select(func.count()).select_from(SourceSpan)) == 1
