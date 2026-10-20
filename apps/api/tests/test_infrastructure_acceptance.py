"""Opt-in Linux acceptance; requires the dedicated disposable Compose stack."""

import os
import signal
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import boto3
import pytest
from app.config import get_settings
from app.evidence_models import DeliveryArtifact
from app.models import now
from app.operation_jobs import execute as execute_operation
from app.operation_models import Operation, ReportSnapshot
from app.source_jobs import dispatch, execute
from app.source_models import DocumentVersion, JobAttempt, OutboxEvent, ParseJob, SourceSpan
from app.source_storage import S3Storage
from app.storage_admin import initialize
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError
from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry
from rq import Queue
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from test_source_recovery import upload

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INFRASTRUCTURE_ACCEPTANCE") != "1",
    reason="Requires the disposable Linux PostgreSQL/Redis/MinIO acceptance stack",
)


def wait_until(predicate, description, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    pytest.fail(f"Timed out waiting for {description}")


@pytest.fixture
def infrastructure(database):
    assert sys.platform == "linux", "Run acceptance inside the Linux Compose stack"
    assert database.kw["bind"].dialect.name == "postgresql"
    # The opt-in stack has dedicated services: CLIENT PAUSE must never target shared Redis.
    settings = get_settings()
    assert settings.redis_url == "redis://redis:6379/0"
    assert settings.s3_endpoint == "http://minio:9000"
    for attempt in range(30):
        try:
            initialize()
            break
        except Exception:
            if attempt == 29:
                pytest.fail("Private object storage did not become ready")
            time.sleep(1)
    connection = Redis.from_url(settings.redis_url, socket_timeout=0.2, retry=Retry(NoBackoff(), 0))
    assert connection.ping()
    queue = Queue("acceptance-" + uuid4().hex, connection=connection)
    yield queue, S3Storage()
    # No FLUSHDB: delete only this test's queue. The enclosing stack owns service teardown.
    queue.delete(delete_jobs=True)
    connection.close()


def worker(queue, database, marker=None):
    with database() as db:
        schema = db.scalar(text("SELECT current_schema()"))
    environment = {
        **os.environ,
        "DATABASE_URL": make_url(os.environ["TEST_DATABASE_URL"])
        .update_query_dict({"options": f"-csearch_path={schema},deliverygap_test_extensions"})
        .render_as_string(hide_password=False),
        "ACCEPTANCE_QUEUE": queue.name,
    }
    environment.pop("ACCEPTANCE_PAUSE_MARKER", None)
    if marker:
        environment["ACCEPTANCE_PAUSE_MARKER"] = str(marker)
    return subprocess.Popen(
        [sys.executable, str(Path(__file__).with_name("infrastructure_worker.py"))],
        env=environment,
        start_new_session=True,
    )


def stop(process):
    # RQ puts its work horse in a separate process group.
    children = Path(f"/proc/{process.pid}/task/{process.pid}/children")
    child_pids = children.read_text().split() if children.exists() else []
    for pid in [process.pid, *(int(child) for child in child_pids)]:
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=10)


def finish(process):
    try:
        assert process.wait(timeout=30) == 0
    finally:
        stop(process)


def test_private_original_and_redis_outage_recover(client, login, database, infrastructure):
    queue, storage = infrastructure
    source = upload(client, login)
    with database() as db:
        version = db.get_one(DocumentVersion, source["version_id"])
        key = version.storage_key
    assert storage.get(key) == b"Immutable original."
    with pytest.raises(ClientError) as overwrite:
        storage.put(key, b"replacement")
    assert overwrite.value.response["ResponseMetadata"]["HTTPStatusCode"] == 412
    assert storage.get(key) == b"Immutable original."
    anonymous = boto3.client(
        "s3",
        endpoint_url=get_settings().s3_endpoint,
        region_name="us-east-1",
        config=Config(signature_version=UNSIGNED),
    )
    with pytest.raises(ClientError) as denied:
        anonymous.get_object(Bucket=storage.bucket, Key=key)
    assert denied.value.response["ResponseMetadata"]["HTTPStatusCode"] == 403

    def enqueue(job_id, delivery_id):
        queue.enqueue(execute, job_id, job_id=delivery_id, job_timeout=120)

    # Real Redis stops serving commands after the source/outbox transaction committed.
    queue.connection.execute_command("CLIENT", "PAUSE", 2000, "ALL")
    dispatch(database, enqueue)
    with database() as db:
        event = db.get_one(OutboxEvent, source["job_id"])
        assert event.dispatched_at is None and event.deliveries == 0
    time.sleep(2)
    dispatch(database, enqueue)
    finish(worker(queue, database))
    # A separate real queue delivery must not create another parse attempt/output.
    queue.enqueue(execute, source["job_id"], job_timeout=120)
    finish(worker(queue, database))
    with database() as db:
        assert db.get_one(ParseJob, source["job_id"]).status == "succeeded"
        assert db.get_one(ParseJob, source["job_id"]).attempts == 1
        assert db.scalar(select(func.count()).select_from(SourceSpan)) == 1


def test_killed_rq_worker_recovers_without_duplicate_output(
    client, login, database, infrastructure, tmp_path
):
    queue, _ = infrastructure
    source = upload(client, login)

    def enqueue(job_id, delivery_id):
        queue.enqueue(execute, job_id, job_id=delivery_id, job_timeout=120)

    dispatch(database, enqueue)
    marker = tmp_path / "original-read"
    process = worker(queue, database, marker)
    try:
        wait_until(marker.exists, "worker to read the real S3 original")
        with database() as db:
            job = db.get_one(ParseJob, source["job_id"])
            assert job.status == "running" and job.attempts == 1
            old_fence = job.fence
    finally:
        stop(process)
    with database() as db:
        assert db.scalar(select(func.count()).select_from(SourceSpan)) == 0
        # Advance persisted deadlines instead of waiting the production 180-second lease.
        db.get_one(ParseJob, source["job_id"]).lease_until = now() - timedelta(seconds=1)
        db.commit()
    dispatch(database, enqueue)
    with database() as db:
        assert db.scalar(select(JobAttempt).where(JobAttempt.fence == old_fence)).status == "lost"
        db.get_one(OutboxEvent, source["job_id"]).available_at = now() - timedelta(seconds=1)
        db.commit()
    dispatch(database, enqueue)
    finish(worker(queue, database))
    queue.enqueue(execute, source["job_id"], job_timeout=120)
    finish(worker(queue, database))
    with database() as db:
        job = db.get_one(ParseJob, source["job_id"])
        assert job.status == "succeeded" and job.attempts == 2 and job.fence != old_fence
        assert db.scalar(select(func.count()).select_from(SourceSpan)) == 1
        assert list(db.scalars(select(JobAttempt.status).order_by(JobAttempt.number))) == [
            "lost",
            "succeeded",
        ]


def test_missing_object_exhausts_retries_then_explicit_retry_recovers(
    client, login, database, infrastructure
):
    queue, storage = infrastructure
    source = upload(client, login)
    with database() as db:
        version = db.get_one(DocumentVersion, source["version_id"])
        key, project_id = version.storage_key, version.project_id
    original = storage.get(key)
    # Fault injection removes only this disposable test's synthetic object.
    storage.client.delete_object(Bucket=storage.bucket, Key=key)

    def enqueue(job_id, delivery_id):
        queue.enqueue(execute, job_id, job_id=delivery_id, job_timeout=120)

    for attempt in range(1, 4):
        with database() as db:
            db.get_one(OutboxEvent, source["job_id"]).available_at = now() - timedelta(seconds=1)
            db.commit()
        dispatch(database, enqueue)
        finish(worker(queue, database))
        with database() as db:
            job = db.get_one(ParseJob, source["job_id"])
            assert job.attempts == attempt
            assert job.status == ("failed" if attempt == 3 else "queued")
            assert db.scalar(select(func.count()).select_from(SourceSpan)) == 0
    dispatch(database, enqueue)
    assert queue.count == 0
    storage.put(key, original)
    response = client.post(
        f"/api/v1/projects/{project_id}/versions/{source['version_id']}/retry",
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 200, response.text
    dispatch(database, enqueue)
    finish(worker(queue, database))
    with database() as db:
        job = db.get_one(ParseJob, source["job_id"])
        assert job.status == "succeeded" and job.attempts == 4 and job.cycle_attempts == 1
        assert db.scalar(select(func.count()).select_from(SourceSpan)) == 1


@pytest.mark.parametrize("kind", ["import", "report"])
def test_killed_operation_rolls_back_and_redelivery_commits_once(
    client, login, database, infrastructure, tmp_path, kind
):
    from test_operations import post

    queue, _ = infrastructure
    source = upload(client, login)
    queue.enqueue(execute, source["job_id"], job_timeout=120)
    finish(worker(queue, database))
    with database() as db:
        project_id = db.get_one(ParseJob, source["job_id"]).project_id
    base = f"/api/v1/projects/{project_id}"
    spans = client.get(base + f"/versions/{source['version_id']}/spans").json()["items"]
    draft = post(
        client,
        base + "/requirements",
        {
            "title": "Original",
            "content": spans[0]["text"],
            "source_version_id": source["version_id"],
            "source_span_id": spans[0]["id"],
            "source_quote": spans[0]["text"],
        },
    )
    assert draft.status_code == 201, draft.text
    requirement = draft.json()
    approved = client.post(
        base + f"/requirements/{requirement['id']}/approve", json={"expected_version": 1}
    )
    assert approved.status_code == 200, approved.text
    published = post(
        client,
        base + "/baselines",
        {"requirement_version_ids": [requirement["versions"][0]["id"]]},
    )
    assert published.status_code == 201, published.text
    baseline_id = published.json()["id"]
    if kind == "import":
        preview = post(
            client,
            base + "/imports/preview",
            {
                "kind": "task",
                "baseline_id": baseline_id,
                "csv_text": "external_id,title,status\nTASK-1,Original,done\n",
            },
        )
        assert preview.status_code == 201, preview.text
        queued = post(client, base + f"/imports/{preview.json()['id']}/commit", {})
        output_model = DeliveryArtifact
    else:
        queued = post(client, base + "/reports", {"baseline_id": baseline_id})
        output_model = ReportSnapshot
    assert queued.status_code == 202, queued.text
    operation_id = queued.json()["id"]
    queue.enqueue(execute_operation, operation_id, job_timeout=120)
    marker = tmp_path / "output-flushed"
    process = worker(queue, database, marker)
    try:
        wait_until(marker.exists, "operation output flushed but not committed")
    finally:
        stop(process)
    with database() as db:
        assert db.get_one(Operation, operation_id).status == "queued"
        assert db.scalar(select(func.count()).select_from(output_model)) == 0
    # The durable operation survived; a replacement RQ delivery commits it once.
    queue.enqueue(execute_operation, operation_id, job_timeout=120)
    finish(worker(queue, database))
    queue.enqueue(execute_operation, operation_id, job_timeout=120)
    finish(worker(queue, database))
    with database() as db:
        operation = db.get_one(Operation, operation_id)
        assert operation.status == "succeeded" and operation.attempts == 1
        assert db.scalar(select(func.count()).select_from(output_model)) == 1
