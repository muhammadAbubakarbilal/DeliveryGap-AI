from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Member, Project, User
from app.schemas import ProjectOut


def project_output(db: Session, project: Project, role: str) -> ProjectOut:
    count = (
        db.scalar(select(func.count()).select_from(Member).where(Member.project_id == project.id))
        or 0
    )
    return ProjectOut(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        revision=project.revision,
        external_ai_consent=project.external_ai_consent,
        created_at=project.created_at,
        role=role,
        member_count=count,
    )


def lock_project(db: Session, project_id: str) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id).with_for_update())
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def protect_last_lead(db: Session, member: Member) -> None:
    if member.role != "lead":
        return
    active_leads = db.scalar(
        select(func.count())
        .select_from(Member)
        .join(User)
        .where(
            Member.project_id == member.project_id, Member.role == "lead", User.is_active.is_(True)
        )
    )
    user = db.get(User, member.user_id)
    if user and user.is_active and (active_leads or 0) <= 1:
        raise HTTPException(409, "Assign another active lead before removing this lead")
