"""Authorized, idempotent retries for failed provider operations."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commands import lock_write, remember, replay
from app.models import Project
from app.operation_models import Operation
from app.operation_schemas import OperationOut, RetryOperation
from app.security import Principal, audit


def retry_operation(
    db: Session,
    auth: Principal,
    project_id: str,
    operation_id: str,
    body: RetryOperation,
    key: str,
) -> OperationOut:
    lock_write(db, auth, project_id)
    command = "operation.retry:" + operation_id
    previous = replay(db, auth, project_id, command, key, body)
    if previous is not None:
        return OperationOut.model_validate(previous)

    operation = db.scalar(
        select(Operation)
        .where(Operation.id == operation_id, Operation.project_id == project_id)
        .with_for_update()
    )
    if operation is None:
        raise HTTPException(404, "Operation not found")
    if operation.kind not in {"analysis", "extraction"}:
        raise HTTPException(409, "This operation type does not support explicit retry")
    if operation.status != "failed":
        raise HTTPException(409, "Only failed operations can be retried")
    if operation.attempts >= 3:
        raise HTTPException(409, "Operation attempt limit reached; submit a new request")
    if not db.get_one(Project, project_id).external_ai_consent:
        raise HTTPException(409, "A project lead must enable external AI processing first")

    operation.actor_id = auth.user.id
    operation.status = "queued"
    operation.error = None
    operation.fence = None
    operation.lease_until = None
    operation.dispatched_at = None
    if operation.kind == "analysis":
        operation.result = None

    result = OperationOut.model_validate(operation)
    remember(db, auth, project_id, command, key, body, result)
    audit(db, auth.user, "operation.retry_queued", operation.id, project_id)
    db.commit()
    return result
