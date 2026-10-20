"""Run persisted DeliveryGap jobs locally without Redis/RQ."""

from __future__ import annotations

import logging
import signal
import time
from collections.abc import Callable

from app.db import SessionLocal
from app.models import now
from app.operation_jobs import execute_with
from app.operation_models import Operation
from app.source_jobs import dispatch as dispatch_sources
from app.source_jobs import run_parse
from app.source_storage import Storage, get_storage
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

LOGGER = logging.getLogger("deliverygap.local_worker")
POLL_SECONDS = 0.5
Factory = sessionmaker[Session]


def recover_expired_operations(factory: Factory) -> list[str]:
    with factory() as db:
        operations = list(
            db.scalars(
                select(Operation)
                .where(
                    Operation.status == "running",
                    or_(Operation.lease_until.is_(None), Operation.lease_until <= now()),
                )
                .order_by(Operation.created_at)
                .limit(25)
            )
        )
        recovered: list[str] = []
        for operation in operations:
            operation.fence = None
            operation.lease_until = None
            operation.dispatched_at = None
            if operation.attempts >= 3:
                operation.status = "failed"
                operation.error = "Worker stopped before completing provider work"
            else:
                operation.status = "queued"
                operation.error = "Previous local worker lease expired; retrying"
                recovered.append(operation.id)
        db.commit()
        return recovered


def process_once(
    factory: Factory = SessionLocal,
    storage_factory: Callable[[], Storage] = get_storage,
) -> int:
    source_ids: list[str] = []
    dispatch_sources(factory, lambda job_id, _delivery_id: source_ids.append(job_id))
    storage = storage_factory()
    for job_id in dict.fromkeys(source_ids):
        run_parse(factory, storage, job_id)

    expired = recover_expired_operations(factory)
    with factory() as db:
        operation_ids = list(
            db.scalars(
                select(Operation.id)
                .where(Operation.status == "queued")
                .order_by(Operation.created_at)
                .limit(25)
            )
        )
    for operation_id in dict.fromkeys([*expired, *operation_ids]):
        execute_with(factory, operation_id)
    return len(source_ids) + len(operation_ids)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stopping = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    while not stopping:
        try:
            worked = process_once()
        except Exception:
            LOGGER.error("local_worker_iteration_failed")
            worked = 0
        time.sleep(0.05 if worked else POLL_SECONDS)


if __name__ == "__main__":
    main()
