"""Project mutation boundary and durable command replay."""

import hashlib
import json

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Member, Project
from app.security import Principal, project_access
from app.source_models import SourceCommand


def lock_write(db: Session, auth: Principal, project_id: str, lead: bool = False) -> None:
    project_access(db, auth, project_id)
    project = db.scalar(
        select(Project)
        .where(Project.id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    member = db.scalar(
        select(Member)
        .where(Member.project_id == project_id, Member.user_id == auth.user.id)
        .execution_options(populate_existing=True)
    )
    if member is None and not auth.user.is_admin:
        raise HTTPException(404, "Project not found")
    role = member.role if member else "admin"
    if lead and role != "lead" and not auth.user.is_admin:
        raise HTTPException(403, "Project lead required")
    if (
        project is None
        or project.status != "active"
        or (role == "reviewer" and not auth.user.is_admin)
    ):
        raise HTTPException(403, "An active project and contributor access are required")


def request_hash(payload: BaseModel) -> str:
    return hashlib.sha256(
        json.dumps(payload.model_dump(mode="json"), sort_keys=True, ensure_ascii=True).encode()
    ).hexdigest()


def replay(
    db: Session, auth: Principal, project: str, operation: str, key: str, payload: BaseModel
) -> dict[str, object] | None:
    row = db.get(SourceCommand, (auth.user.id, project, operation, key))
    if row is None:
        return None
    if row.request_hash != request_hash(payload):
        raise HTTPException(409, "Idempotency key was used with a different request")
    return row.response


def remember(
    db: Session,
    auth: Principal,
    project: str,
    operation: str,
    key: str,
    payload: BaseModel,
    result: BaseModel,
) -> None:
    db.add(
        SourceCommand(
            actor_id=auth.user.id,
            project_id=project,
            operation=operation,
            request_key=key,
            request_hash=request_hash(payload),
            response=result.model_dump(mode="json"),
        )
    )
