"""Fenced parsing attempts with a transactional outbox and DB reconciliation."""

import hashlib
import random
import time
from collections.abc import Callable
from datetime import timedelta

from fastapi import HTTPException
from redis import Redis
from rq import Queue
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db import SessionLocal
from app.models import Member, Project, User, new_id, now
from app.security import Principal, audit, aware
from app.source_models import (
    DocumentChunk,
    DocumentVersion,
    JobAttempt,
    OutboxEvent,
    ParseJob,
    SourceCommand,
    SourceSpan,
)
from app.source_parsers import InvalidSource, ParsedSpan, parse_original
from app.source_storage import Storage, get_storage


def authorized(db: Session, job: ParseJob) -> bool:
    user = db.get(User, job.actor_id)
    project = db.get(Project, job.project_id)
    membership = db.get(Member, (job.project_id, job.actor_id))
    return bool(
        user
        and user.is_active
        and project
        and project.status == "active"
        and (user.is_admin or (membership and membership.role in {"lead", "member"}))
    )


def fail_or_retry(db: Session, job: ParseJob, message: str, transient: bool) -> None:
    retry = transient and job.cycle_attempts < 3
    job.status = "queued" if retry else "failed"
    job.error = message
    job.lease_until = None
    version = db.get_one(DocumentVersion, job.version_id)
    version.status = "queued" if retry else "failed"
    if retry:
        event = db.get_one(OutboxEvent, job.id)
        event.available_at = now() + timedelta(seconds=2**job.cycle_attempts + random.random())
        event.dispatched_at = None


def run_parse(factory: sessionmaker[Session], storage: Storage, job_id: str) -> None:
    with factory() as db:
        initial = db.get(ParseJob, job_id)
        if initial is None:
            return
        db.scalar(select(Project).where(Project.id == initial.project_id).with_for_update())
        job = db.scalar(
            select(ParseJob)
            .where(ParseJob.id == job_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        assert job is not None
        event = db.get_one(OutboxEvent, job.id)
        if job.status != "queued" or aware(event.available_at) > now():
            return
        if not authorized(db, job):
            fail_or_retry(
                db, job, "Uploader no longer has permission to process this source.", False
            )
            db.commit()
            return
        job.attempts += 1
        job.cycle_attempts += 1
        job.fence = new_id()
        fence = job.fence
        job.status = "running"
        # RQ kills work after 120s; recovery waits 180s before fencing its results out.
        job.lease_until = now() + timedelta(seconds=180)
        job.error = None
        version = db.get_one(DocumentVersion, job.version_id)
        version.status = "processing"
        filename, key, digest = version.filename, version.storage_key, version.sha256
        db.add(JobAttempt(job_id=job.id, number=job.attempts, fence=fence, status="running"))
        db.commit()
    parsed: list[ParsedSpan] = []
    warning = None
    error = None
    transient = False
    try:
        content = storage.get(key)
        if hashlib.sha256(content).hexdigest() != digest:
            raise InvalidSource("Original checksum mismatch. Contact the workspace administrator.")
        parsed, warning = parse_original(filename, content)
    except InvalidSource as exc:
        error = str(exc)
    except Exception:
        error, transient = (
            "Source processing dependency unavailable. Retry is scheduled when eligible.",
            True,
        )
    with factory() as db:
        initial = db.get_one(ParseJob, job_id)
        db.scalar(select(Project).where(Project.id == initial.project_id).with_for_update())
        job = db.scalar(
            select(ParseJob)
            .where(ParseJob.id == job_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        assert job is not None
        if (
            job.fence != fence
            or job.status != "running"
            or not job.lease_until
            or aware(job.lease_until) <= now()
        ):
            return
        attempt = db.scalar(select(JobAttempt).where(JobAttempt.fence == fence))
        assert attempt is not None
        attempt.finished_at = now()
        if not authorized(db, job):
            error, transient = "Uploader no longer has permission to process this source.", False
        if error:
            attempt.status = "failed"
            fail_or_retry(db, job, error, transient)
        else:
            version = db.get_one(DocumentVersion, job.version_id)
            chunk_number = 0
            for number, source in enumerate(parsed, 1):
                span = SourceSpan(
                    project_id=job.project_id,
                    version_id=job.version_id,
                    ordinal=number,
                    locator=source.locator,
                    text=source.text,
                    char_end=len(source.text),
                )
                db.add(span)
                db.flush()
                for start in range(0, len(source.text), 1600):
                    chunk_number += 1
                    end = min(start + 2000, len(source.text))
                    db.add(
                        DocumentChunk(
                            project_id=job.project_id,
                            version_id=job.version_id,
                            span_id=span.id,
                            ordinal=chunk_number,
                            char_start=start,
                            char_end=end,
                            text=source.text[start:end],
                        )
                    )
            version.status = "ready" if parsed else "needs_manual_input"
            version.warning = warning
            job.status, job.lease_until = "succeeded", None
            attempt.status = "succeeded"
        db.commit()


def execute(job_id: str) -> None:
    run_parse(SessionLocal, get_storage(), job_id)


def dispatch(factory: sessionmaker[Session], enqueue: Callable[[str, str], None]) -> None:
    eligible_at = now()
    with factory() as db:
        jobs = list(
            db.scalars(
                select(ParseJob)
                .join(OutboxEvent, OutboxEvent.job_id == ParseJob.id)
                .where(
                    or_(
                        and_(
                            ParseJob.status == "queued",
                            OutboxEvent.available_at <= eligible_at,
                            or_(
                                OutboxEvent.dispatched_at.is_(None),
                                OutboxEvent.dispatched_at <= eligible_at - timedelta(seconds=30),
                            ),
                        ),
                        and_(
                            ParseJob.status == "running",
                            ParseJob.lease_until <= eligible_at,
                        ),
                    )
                )
                .order_by(ParseJob.id)
                .limit(100)
                .with_for_update(skip_locked=True)
            )
        )
        for job in jobs:
            event = db.get_one(OutboxEvent, job.id)
            if job.status == "running":
                if job.lease_until and aware(job.lease_until) <= now():
                    attempt = db.scalar(select(JobAttempt).where(JobAttempt.fence == job.fence))
                    if attempt:
                        attempt.status, attempt.finished_at = "lost", now()
                    fail_or_retry(db, job, "Worker stopped before completion.", True)
                else:
                    continue
            if job.status != "queued" or aware(event.available_at) > now():
                continue
            if event.dispatched_at and aware(event.dispatched_at) > now() - timedelta(seconds=30):
                continue
            try:
                enqueue(job.id, f"parse-{job.id}-{event.deliveries}")
            except Exception:
                # DB operation remains recoverable even when Redis is down.
                continue
            event.deliveries += 1
            event.dispatched_at = now()
        db.commit()


def retry_job(db: Session, auth: Principal, project_id: str, version_id: str, key: str) -> None:
    from app.source_service import source_access

    db.scalar(select(Project).where(Project.id == project_id).with_for_update())
    source_access(db, auth, project_id, write=True)
    operation = "retry:" + version_id
    identity = (auth.user.id, project_id, operation, key)
    if db.get(SourceCommand, identity):
        return
    job = db.scalar(
        select(ParseJob)
        .where(ParseJob.version_id == version_id, ParseJob.project_id == project_id)
        .with_for_update()
    )
    if job is None or job.status != "failed":
        raise HTTPException(409, "Only failed parsing jobs can be retried")
    job.actor_id, job.status, job.cycle_attempts = auth.user.id, "queued", 0
    job.fence, job.lease_until, job.error = None, None, None
    db.get_one(DocumentVersion, version_id).status = "queued"
    event = db.get_one(OutboxEvent, job.id)
    event.available_at, event.dispatched_at = now(), None
    db.add(
        SourceCommand(
            actor_id=auth.user.id,
            project_id=project_id,
            operation=operation,
            request_key=key,
            request_hash="retry",
            response={"job_id": job.id},
        )
    )
    audit(db, auth.user, "document.retry", version_id, project_id)
    db.commit()


def main() -> None:
    connection = Redis.from_url(
        get_settings().redis_url, socket_connect_timeout=5, socket_timeout=5
    )
    queue = Queue("sources", connection=connection)

    def enqueue(job_id: str, delivery_id: str) -> None:
        queue.enqueue(
            execute, job_id, job_id=delivery_id, job_timeout=120, result_ttl=300, failure_ttl=3600
        )

    while True:
        try:
            dispatch(SessionLocal, enqueue)
            from app.operation_jobs import dispatch_operations

            dispatch_operations()
        except Exception:
            # No exception text: DB messages can include source values.
            import logging

            logging.getLogger("deliverygap").error("source_dispatch_unavailable")
        time.sleep(3)


if __name__ == "__main__":
    main()
