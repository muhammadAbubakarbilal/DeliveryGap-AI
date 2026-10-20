import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditEvent, LoginSession, Member, Project, User

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))
COOKIE = "deliverygap_session"
DB = Annotated[Session, Depends(get_db)]


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_password(encoded: str, password: str) -> bool:
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


@dataclass
class Principal:
    user: User
    session: LoginSession


def authenticate(request: Request, db: DB) -> Principal:
    token = request.cookies.get(COOKIE, "")
    session = db.scalar(select(LoginSession).where(LoginSession.token_hash == token_hash(token)))
    if not session or session.revoked_at or aware(session.expires_at) <= datetime.now(UTC):
        raise HTTPException(401, "Authentication required")
    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Authentication required")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(csrf, session.csrf_token):
            raise HTTPException(403, "Invalid CSRF token")
    return Principal(user, session)


Auth = Annotated[Principal, Depends(authenticate)]


def require_admin(principal: Principal) -> None:
    if not principal.user.is_admin:
        raise HTTPException(403, "Workspace administrator required")


def audit(
    db: Session,
    user: User,
    event: str,
    target: str,
    project_id: str | None = None,
    **details: object,
) -> None:
    db.add(
        AuditEvent(
            actor_id=user.id,
            project_id=project_id,
            event_type=event,
            target_id=target,
            details=details,
        )
    )


def project_access(
    db: Session, principal: Principal, project_id: str, write: bool = False
) -> tuple[Project, str]:
    project = db.get(Project, project_id)
    member = db.get(Member, (project_id, principal.user.id))
    if not project or (not member and not principal.user.is_admin):
        raise HTTPException(404, "Project not found")
    if not member:
        audit(db, principal.user, "admin.project_access", project_id, project_id)
        db.commit()
    role = member.role if member else "admin"
    if write and role not in {"lead", "admin"} and not principal.user.is_admin:
        raise HTTPException(403, "Project lead required")
    return project, role
