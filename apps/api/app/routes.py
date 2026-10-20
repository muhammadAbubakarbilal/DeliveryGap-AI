import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from sqlalchemy import func, select, update

from app.config import get_settings
from app.models import LoginSession, LoginThrottle, Member, Project, User
from app.project_creation import create_project as create_project_command
from app.schemas import (
    ExternalAIConsentUpdate,
    LoginInput,
    MemberInput,
    MemberOut,
    MemberUpdate,
    ProjectCreate,
    ProjectOut,
    ProjectPage,
    ProjectUpdate,
    SessionOut,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.security import (
    COOKIE,
    DB,
    DUMMY_HASH,
    Auth,
    audit,
    aware,
    hasher,
    project_access,
    require_admin,
    token_hash,
    verify_password,
)
from app.services import lock_project, project_output, protect_last_lead

router = APIRouter(prefix="/api/v1")


@router.post("/auth/login", response_model=SessionOut)
def login(body: LoginInput, request: Request, response: Response, db: DB) -> SessionOut:
    # Per-account shared DB throttle. Unknown users follow the same password hash path.
    email = str(body.email).strip().lower()
    key = token_hash(email)
    current = datetime.now(UTC)
    # PostgreSQL ON CONFLICT makes first-attempt throttle creation safe under concurrency.
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert

        db.execute(
            insert(LoginThrottle)
            .values(key=key, attempts=0, window_start=current)
            .on_conflict_do_nothing(index_elements=["key"])
        )
    elif db.get(LoginThrottle, key) is None:
        db.add(LoginThrottle(key=key, attempts=0, window_start=current))
        db.flush()
    throttle = db.scalar(select(LoginThrottle).where(LoginThrottle.key == key).with_for_update())
    assert throttle is not None
    if current - aware(throttle.window_start) > timedelta(minutes=15):
        throttle.attempts = 0
        throttle.window_start = current
    if throttle.attempts >= 10:
        raise HTTPException(429, "Too many attempts. Try again in 15 minutes.")
    throttle.attempts += 1
    db.commit()
    user = db.scalar(select(User).where(User.email == email))
    valid = verify_password(user.password_hash if user else DUMMY_HASH, body.password)
    if not user or not valid or not user.is_active or user.neon_subject:
        raise HTTPException(401, "Incorrect email or password")
    old = request.cookies.get(COOKIE)
    if old:
        db.execute(
            update(LoginSession)
            .where(LoginSession.token_hash == token_hash(old))
            .values(revoked_at=current)
        )
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    settings = get_settings()
    db.add(
        LoginSession(
            user_id=user.id,
            token_hash=token_hash(token),
            csrf_token=csrf,
            expires_at=current + timedelta(hours=settings.session_hours),
        )
    )
    audit(db, user, "auth.login", user.id)
    db.commit()
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.session_hours * 3600,
    )
    return SessionOut(user=UserOut.model_validate(user), csrf_token=csrf)


@router.get("/auth/me", response_model=SessionOut)
def me(auth: Auth) -> SessionOut:
    return SessionOut(
        user=UserOut.model_validate(auth.user),
        csrf_token=auth.session.csrf_token,
        auth_provider="neon" if auth.user.neon_subject else "local",
    )


@router.get("/auth/options")
def auth_options() -> dict[str, bool]:
    settings = get_settings()
    return {"neon": bool(settings.neon_auth_base_url and settings.neon_auth_jwks_url)}


@router.post("/auth/neon", response_model=SessionOut)
def neon_login(
    request: Request,
    response: Response,
    db: DB,
    authorization: Annotated[str, Header(max_length=16384)],
) -> SessionOut:
    from app.neon_auth import exchange

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Neon sign-in token required")
    return exchange(db, request, response, token)


@router.post("/auth/logout", status_code=204)
def logout(auth: Auth, db: DB, response: Response) -> None:
    auth.session.revoked_at = datetime.now(UTC)
    audit(db, auth.user, "auth.logout", auth.user.id)
    db.commit()
    response.delete_cookie(
        COOKIE, path="/", secure=get_settings().cookie_secure, httponly=True, samesite="lax"
    )


@router.get("/admin/users", response_model=list[UserOut])
def users(auth: Auth, db: DB, page: Annotated[int, Query(ge=1)] = 1) -> list[User]:
    require_admin(auth)
    return list(db.scalars(select(User).order_by(User.email).offset((page - 1) * 25).limit(25)))


@router.post("/admin/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, auth: Auth, db: DB) -> User:
    require_admin(auth)
    if not body.display_name.strip():
        raise HTTPException(422, "Display name is required")
    user = User(
        email=str(body.email).strip().lower(),
        display_name=body.display_name.strip(),
        password_hash=hasher.hash(body.password),
    )
    db.add(user)
    db.flush()
    audit(db, auth.user, "user.created", user.id)
    db.commit()
    return user


@router.patch("/admin/users/{user_id}", response_model=UserOut)
def update_user(user_id: str, body: UserUpdate, auth: Auth, db: DB) -> User:
    require_admin(auth)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.is_admin:
        raise HTTPException(409, "Workspace administrator accounts cannot be disabled here")
    if not body.is_active:
        memberships = list(
            db.scalars(select(Member).where(Member.user_id == user_id).order_by(Member.project_id))
        )
        for member in memberships:
            lock_project(db, member.project_id)
            protect_last_lead(db, member)
        db.execute(
            update(LoginSession)
            .where(LoginSession.user_id == user_id)
            .values(revoked_at=datetime.now(UTC))
        )
    user.is_active = body.is_active
    audit(db, auth.user, "user.status_changed", user.id, is_active=body.is_active)
    db.commit()
    return user


@router.get("/projects", response_model=ProjectPage)
def projects(
    auth: Auth,
    db: DB,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    q: Annotated[str, Query(max_length=120)] = "",
) -> ProjectPage:
    query = select(Project)
    if not auth.user.is_admin:
        query = query.join(Member).where(Member.user_id == auth.user.id)
    if q.strip():
        query = query.where(Project.name.icontains(q.strip(), autoescape=True))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(Project.created_at.desc(), Project.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    for project in rows:
        membership = db.get(Member, (project.id, auth.user.id))
        role = membership.role if membership else "admin"
        items.append(project_output(db, project, role))
    if auth.user.is_admin:
        audit(db, auth.user, "admin.projects_list", auth.user.id)
        db.commit()
    return ProjectPage(items=items, total=total, page=page, page_size=page_size)


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(
    body: ProjectCreate,
    auth: Auth,
    db: DB,
    idempotency_key: Annotated[
        str,
        Header(
            min_length=1,
            max_length=128,
            pattern=r"^[A-Za-z0-9._:-]+$",
            description="Reuse for retries of project creation; changed fields return 409.",
        ),
    ],
) -> ProjectOut:
    return create_project_command(db, auth, body, idempotency_key)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, auth: Auth, db: DB) -> ProjectOut:
    project, role = project_access(db, auth, project_id)
    return project_output(db, project, role)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def edit_project(project_id: str, body: ProjectUpdate, auth: Auth, db: DB) -> ProjectOut:
    _, role = project_access(db, auth, project_id, write=True)
    result = db.execute(
        update(Project)
        .where(Project.id == project_id, Project.revision == body.revision)
        .values(
            name=body.name,
            description=body.description,
            status=body.status,
            revision=Project.revision + 1,
        )
    )
    if result.rowcount != 1:  # type: ignore[attr-defined]
        raise HTTPException(409, "Project changed. Refresh before saving again.")
    audit(db, auth.user, "project.updated", project_id, project_id)
    db.commit()
    db.expire_all()
    return project_output(db, db.get_one(Project, project_id), role)


@router.patch("/projects/{project_id}/ai-consent", response_model=ProjectOut)
def update_external_ai_consent(
    project_id: str, body: ExternalAIConsentUpdate, auth: Auth, db: DB
) -> ProjectOut:
    project, role = project_access(db, auth, project_id, write=True)
    project = lock_project(db, project_id)
    if body.enabled and project.status != "active":
        raise HTTPException(409, "External AI processing can only be enabled for an active project")
    if project.external_ai_consent != body.enabled:
        project.external_ai_consent = body.enabled
        audit(
            db,
            auth.user,
            "project.external_ai_consent.changed",
            project.id,
            project.id,
            enabled=body.enabled,
        )
        db.commit()
    return project_output(db, project, role)


@router.get("/projects/{project_id}/members", response_model=list[MemberOut])
def members(project_id: str, auth: Auth, db: DB) -> list[MemberOut]:
    project_access(db, auth, project_id)
    rows = db.execute(
        select(Member, User)
        .join(User)
        .where(Member.project_id == project_id)
        .order_by(User.display_name)
    )
    return [
        MemberOut(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=member.role,
            is_active=user.is_active,
        )
        for member, user in rows
    ]


@router.post("/projects/{project_id}/members", status_code=201, response_model=MemberOut)
def add_member(project_id: str, body: MemberInput, auth: Auth, db: DB) -> MemberOut:
    project_access(db, auth, project_id, write=True)
    lock_project(db, project_id)
    user = db.scalar(
        select(User).where(User.email == str(body.email).lower(), User.is_active.is_(True))
    )
    if not user:
        raise HTTPException(404, "No active workspace user with this email")
    if db.get(Member, (project_id, user.id)):
        raise HTTPException(409, "User already belongs to this project")
    db.add(Member(project_id=project_id, user_id=user.id, role=body.role))
    audit(db, auth.user, "member.added", user.id, project_id, role=body.role)
    db.commit()
    return MemberOut(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=body.role,
        is_active=user.is_active,
    )


@router.patch("/projects/{project_id}/members/{user_id}", status_code=204)
def change_member(project_id: str, user_id: str, body: MemberUpdate, auth: Auth, db: DB) -> None:
    project_access(db, auth, project_id, write=True)
    lock_project(db, project_id)
    member = db.get(Member, (project_id, user_id))
    if not member:
        raise HTTPException(404, "Member not found")
    if body.role != "lead":
        protect_last_lead(db, member)
    member.role = body.role
    audit(db, auth.user, "member.role_changed", user_id, project_id, role=body.role)
    db.commit()


@router.delete("/projects/{project_id}/members/{user_id}", status_code=204)
def remove_member(project_id: str, user_id: str, auth: Auth, db: DB) -> None:
    project_access(db, auth, project_id, write=True)
    lock_project(db, project_id)
    member = db.get(Member, (project_id, user_id))
    if not member:
        raise HTTPException(404, "Member not found")
    protect_last_lead(db, member)
    db.delete(member)
    audit(db, auth.user, "member.removed", user_id, project_id)
    db.commit()
