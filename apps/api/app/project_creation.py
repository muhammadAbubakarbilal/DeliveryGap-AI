"""Project creation and its replay result commit in one transaction."""

import hashlib
import json

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Member, Project, ProjectCreationRequest
from app.schemas import ProjectCreate, ProjectOut
from app.security import Principal, audit, require_admin
from app.services import project_output


def replay(record: ProjectCreationRequest, request_hash: str) -> ProjectOut:
    if record.request_hash != request_hash:
        raise HTTPException(409, "Idempotency key was already used with different project fields")
    return ProjectOut.model_validate(record.response)


def create_project(
    db: Session, principal: Principal, body: ProjectCreate, request_key: str
) -> ProjectOut:
    require_admin(principal)
    actor_id = principal.user.id
    request_hash = hashlib.sha256(
        json.dumps(body.model_dump(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    identity = (actor_id, request_key)
    existing = db.get(ProjectCreationRequest, identity)
    if existing:
        return replay(existing, request_hash)

    try:
        project = Project(name=body.name, description=body.description, owner_id=actor_id)
        db.add(project)
        db.flush()
        db.add(Member(project_id=project.id, user_id=actor_id, role="lead"))
        audit(db, principal.user, "project.created", project.id, project.id)
        result = project_output(db, project, "lead")
        db.add(
            ProjectCreationRequest(
                actor_id=actor_id,
                request_key=request_key,
                request_hash=request_hash,
                project_id=project.id,
                response=result.model_dump(mode="json"),
            )
        )
        db.commit()
        return result
    except IntegrityError:
        # A concurrent request may win the actor/key constraint. Roll back ALL
        # losing writes (including project, membership and audit) before replay.
        db.rollback()
        existing = db.get(ProjectCreationRequest, identity)
        if existing is None:
            raise
        return replay(existing, request_hash)
