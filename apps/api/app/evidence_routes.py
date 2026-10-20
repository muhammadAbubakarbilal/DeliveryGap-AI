from typing import Annotated, Literal

from fastapi import APIRouter, Header, Query

from app import evidence_service as service
from app.evidence_schemas import (
    ArtifactCreate,
    ArtifactOut,
    BulkLinkReview,
    BulkLinkReviewOut,
    LinkCreate,
    LinkOut,
    LinkReview,
    TraceabilityOut,
)
from app.security import DB, Auth

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["Delivery evidence"])
Key = Annotated[str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")]


@router.post("/artifacts", response_model=ArtifactOut, status_code=201)
def create_artifact(
    project_id: str, body: ArtifactCreate, auth: Auth, db: DB, idempotency_key: Key
) -> ArtifactOut:
    return service.create_artifact(project_id, body, auth, db, idempotency_key)


@router.get("/artifacts", response_model=list[ArtifactOut])
def artifacts(
    project_id: str, auth: Auth, db: DB, page: Annotated[int, Query(ge=1)] = 1
) -> list[ArtifactOut]:
    return service.artifacts(project_id, auth, db, page)


@router.post("/traceability/links", response_model=LinkOut, status_code=201)
def create_link(
    project_id: str, body: LinkCreate, auth: Auth, db: DB, idempotency_key: Key
) -> LinkOut:
    return service.create_link(project_id, body, auth, db, idempotency_key)


@router.post("/traceability/links/{link_id}/review", response_model=LinkOut)
def review_link(project_id: str, link_id: str, body: LinkReview, auth: Auth, db: DB) -> LinkOut:
    return service.review_link(project_id, link_id, body, auth, db)


@router.post("/traceability/links/bulk-review", response_model=BulkLinkReviewOut)
def review_links(
    project_id: str, body: BulkLinkReview, auth: Auth, db: DB, idempotency_key: Key
) -> BulkLinkReviewOut:
    return service.review_links(project_id, body, auth, db, idempotency_key)


@router.get("/traceability", response_model=list[TraceabilityOut])
def traceability(
    project_id: str,
    baseline_id: str,
    auth: Auth,
    db: DB,
    coverage: Literal["all", "current", "missing", "stale"] = "all",
) -> list[TraceabilityOut]:
    return service.traceability(project_id, baseline_id, auth, db, coverage)


@router.get("/artifacts/{artifact_id}/history", response_model=list[ArtifactOut])
def artifact_history(
    project_id: str, artifact_id: str, auth: Auth, db: DB, page: Annotated[int, Query(ge=1)] = 1
) -> list[ArtifactOut]:
    return service.artifact_history(project_id, artifact_id, auth, db, page)
