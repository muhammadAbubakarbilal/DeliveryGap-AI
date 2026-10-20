from typing import Annotated

from fastapi import APIRouter, Header, Query

from app import requirement_service as service
from app.requirement_schemas import (
    BaselineCreate,
    BaselineOut,
    RequirementCreate,
    RequirementEdit,
    RequirementOut,
    RequirementPage,
    RequirementTransform,
    RequirementTransformOut,
    ReviewInput,
)
from app.security import DB, Auth

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["Requirements and baselines"])
Key = Annotated[str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")]


@router.get("/requirements", response_model=RequirementPage)
def requirements(
    project_id: str, auth: Auth, db: DB, page: Annotated[int, Query(ge=1)] = 1
) -> RequirementPage:
    return service.list_requirements(db, auth, project_id, page)


@router.get("/requirements/{requirement_id}", response_model=RequirementOut)
def detail(project_id: str, requirement_id: str, auth: Auth, db: DB) -> RequirementOut:
    return service.detail(db, auth, project_id, requirement_id)


@router.post("/requirements", response_model=RequirementOut, status_code=201)
def create_requirement(
    project_id: str, body: RequirementCreate, auth: Auth, db: DB, idempotency_key: Key
) -> RequirementOut:
    return service.create(db, auth, project_id, body, idempotency_key)


@router.post(
    "/requirements/{requirement_id}/versions", response_model=RequirementOut, status_code=201
)
def edit_requirement(
    project_id: str,
    requirement_id: str,
    body: RequirementEdit,
    auth: Auth,
    db: DB,
    idempotency_key: Key,
) -> RequirementOut:
    return service.edit(db, auth, project_id, requirement_id, body, idempotency_key)


@router.post("/requirements/transform", response_model=RequirementTransformOut, status_code=201)
def transform_requirements(
    project_id: str, body: RequirementTransform, auth: Auth, db: DB, idempotency_key: Key
) -> RequirementTransformOut:
    return service.transform(db, auth, project_id, body, idempotency_key)


@router.post("/requirements/{requirement_id}/approve", response_model=RequirementOut)
def approve(
    project_id: str, requirement_id: str, body: ReviewInput, auth: Auth, db: DB
) -> RequirementOut:
    return service.review(db, auth, project_id, requirement_id, body, "approved")


@router.post("/requirements/{requirement_id}/reject", response_model=RequirementOut)
def reject(
    project_id: str, requirement_id: str, body: ReviewInput, auth: Auth, db: DB
) -> RequirementOut:
    return service.review(db, auth, project_id, requirement_id, body, "rejected")


@router.post("/baselines", response_model=BaselineOut, status_code=201)
def publish_baseline(
    project_id: str, body: BaselineCreate, auth: Auth, db: DB, idempotency_key: Key
) -> BaselineOut:
    return service.publish(db, auth, project_id, body, idempotency_key)


@router.get("/baselines", response_model=list[BaselineOut])
def baselines(
    project_id: str, auth: Auth, db: DB, page: Annotated[int, Query(ge=1)] = 1
) -> list[BaselineOut]:
    return service.list_baselines(db, auth, project_id, page)


@router.get("/baselines/{baseline_id}", response_model=BaselineOut)
def baseline_detail(project_id: str, baseline_id: str, auth: Auth, db: DB) -> BaselineOut:
    return service.baseline_detail(db, auth, project_id, baseline_id)
