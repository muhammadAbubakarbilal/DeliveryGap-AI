"""DB-only bounded jobs: a project transaction is the fence and queued rows are the outbox.

No network/provider calls run under these locks. A killed worker rolls back all output and
leaves the command queued; redelivery observes the terminal state and becomes a no-op.
"""

from datetime import timedelta

from fastapi import HTTPException
from redis import Redis
from rq import Queue
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db import SessionLocal
from app.import_service import apply_import
from app.models import Member, Project, User, now
from app.operation_models import Operation
from app.report_service import create_snapshot
from app.security import audit


def execute_with(factory: sessionmaker[Session], operation_id: str) -> None:
    with factory() as db:
        initial = db.get(Operation, operation_id)
        if initial is None:
            return
        if initial.kind == "analysis":
            db.close()
            from app.grounded_analysis import run_analysis

            run_analysis(factory, operation_id)
            return
        if initial.kind == "extraction":
            db.close()
            from app.extraction import run_extraction

            run_extraction(factory, operation_id)
            return
        db.scalar(select(Project).where(Project.id == initial.project_id).with_for_update())
        operation = db.scalar(
            select(Operation)
            .where(Operation.id == operation_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if operation is None or operation.status != "queued":
            return
        operation.attempts += 1
        user = db.get(User, operation.actor_id)
        project = db.get_one(Project, operation.project_id)
        member = db.get(Member, (operation.project_id, operation.actor_id))
        if (
            not user
            or not user.is_active
            or project.status != "active"
            or (not user.is_admin and (not member or member.role == "reviewer"))
        ):
            operation.status, operation.error = "failed", "Actor no longer has contributor access"
            db.commit()
            return
        try:
            with db.begin_nested():
                result = (
                    apply_import(db, operation)
                    if operation.kind == "import"
                    else create_snapshot(db, operation)
                )
            operation.result, operation.status = result, "succeeded"
            audit(db, user, operation.kind + ".completed", operation.id, operation.project_id)
        except HTTPException as exc:
            operation.status, operation.error = "failed", str(exc.detail)
        except Exception:
            # The nested transaction rolls back every output; never log CSV/provider contents.
            operation.status, operation.error = (
                "failed",
                "Processing failed; create a new preview or report",
            )
        db.commit()


def execute(operation_id: str) -> None:
    execute_with(SessionLocal, operation_id)


def dispatch_operations() -> None:
    connection = Redis.from_url(
        get_settings().redis_url, socket_connect_timeout=3, socket_timeout=3
    )
    queue = Queue("sources", connection=connection)
    with SessionLocal() as db:
        operations = list(
            db.scalars(
                select(Operation)
                .where(
                    or_(
                        and_(
                            Operation.status == "queued",
                            or_(
                                Operation.dispatched_at.is_(None),
                                Operation.dispatched_at <= now() - timedelta(seconds=180),
                            ),
                        ),
                        and_(
                            Operation.status == "running",
                            or_(Operation.lease_until.is_(None), Operation.lease_until <= now()),
                        ),
                    )
                )
                .order_by(Operation.created_at)
                .limit(25)
                .with_for_update(skip_locked=True)
            )
        )
        for operation in operations:
            from app.security import aware

            if operation.status == "running":
                if operation.lease_until and aware(operation.lease_until) > now():
                    continue
                operation.status = "queued" if operation.attempts < 3 else "failed"
                operation.fence, operation.lease_until, operation.dispatched_at = None, None, None
                operation.error = "Worker stopped before completing provider work"
                if operation.status == "failed":
                    continue

            if operation.dispatched_at and aware(operation.dispatched_at) > now() - timedelta(
                seconds=180
            ):
                continue
            timeout = 1500 if operation.kind == "analysis" else 120
            queue.enqueue(
                execute,
                operation.id,
                job_timeout=timeout,
                result_ttl=300,
                failure_ttl=3600,
            )
            operation.dispatched_at = now()
        db.commit()
