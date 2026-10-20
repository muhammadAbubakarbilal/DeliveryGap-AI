from typing import Annotated

from fastapi import APIRouter, Header, Query

from app import analysis_service as service
from app.analysis_schemas import (
    AnalysisCreate,
    AnalysisOut,
    BaselineCitation,
    FindingDecisionIn,
    FindingOut,
    ManualAnalysisCreate,
)
from app.grounded_analysis import GroundedCreate, enqueue
from app.operation_schemas import OperationOut
from app.security import DB, Auth

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["Analysis"])
Key = Annotated[str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")]


@router.get("/baselines/{baseline_id}/citations", response_model=list[BaselineCitation])
def citations(project_id: str, baseline_id: str, auth: Auth, db: DB) -> list[BaselineCitation]:
    return service.baseline_citations(project_id, baseline_id, auth, db)


@router.post("/manual-analysis", response_model=AnalysisOut, status_code=201)
def manual_analysis(
    project_id: str, body: ManualAnalysisCreate, auth: Auth, db: DB, idempotency_key: Key
) -> AnalysisOut:
    return service.create_manual(project_id, body, auth, db, idempotency_key)


@router.post("/analysis-jobs", response_model=OperationOut, status_code=202)
def queue_analysis(
    project_id: str, body: GroundedCreate, auth: Auth, db: DB, idempotency_key: Key
) -> OperationOut:
    return enqueue(db, auth, project_id, body, idempotency_key)


@router.post("/analysis", response_model=AnalysisOut, status_code=201)
def create_analysis(
    project_id: str, body: AnalysisCreate, auth: Auth, db: DB, idempotency_key: Key
) -> AnalysisOut:
    return service.create_analysis(project_id, body, auth, db, idempotency_key)


@router.post("/findings/{finding_id}/decision", response_model=FindingOut)
def decide(
    project_id: str, finding_id: str, body: FindingDecisionIn, auth: Auth, db: DB
) -> FindingOut:
    return service.decide(project_id, finding_id, body, auth, db)


@router.get("/analysis", response_model=list[AnalysisOut])
def analyses(
    project_id: str,
    auth: Auth,
    db: DB,
    page: Annotated[int, Query(ge=1)] = 1,
    baseline_id: str | None = None,
) -> list[AnalysisOut]:
    return service.analyses(project_id, auth, db, page, baseline_id)


@router.get("/analysis/{run_id}", response_model=AnalysisOut)
def analysis_detail(project_id: str, run_id: str, auth: Auth, db: DB) -> AnalysisOut:
    return service.analysis_detail(project_id, run_id, auth, db)
