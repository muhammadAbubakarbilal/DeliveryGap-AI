from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select

from app.analysis_models import AnalysisRun
from app.commands import lock_write, remember, replay
from app.evidence_routes import Key
from app.extraction import ExtractCreate, enqueue
from app.import_service import preview
from app.operation_models import Operation, ReportSnapshot
from app.operation_schemas import (
    CommitImport,
    ImportPreview,
    OperationOut,
    OverviewOut,
    PreviewOut,
    PreviewRow,
    ReportCreate,
    RetryOperation,
)
from app.operation_service import retry_operation
from app.report_service import freeze, overview, render
from app.security import DB, Auth, audit, project_access

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["Imports and reports"])


@router.post("/requirements/extract", response_model=OperationOut, status_code=202)
def extract_requirements(
    project_id: str, body: ExtractCreate, auth: Auth, db: DB, idempotency_key: Key
) -> OperationOut:
    return enqueue(db, auth, project_id, body, idempotency_key)


@router.post("/operations/{operation_id}/cancel", response_model=OperationOut)
def cancel_operation(project_id: str, operation_id: str, auth: Auth, db: DB) -> OperationOut:
    lock_write(db, auth, project_id, lead=True)
    operation = db.scalar(
        select(Operation)
        .where(Operation.id == operation_id, Operation.project_id == project_id)
        .with_for_update()
    )
    if operation is None:
        raise HTTPException(404, "Operation not found")
    if operation.status not in {"queued", "running", "cancelled"}:
        raise HTTPException(409, "Only queued or running operations can be cancelled")
    operation.status, operation.fence, operation.lease_until = "cancelled", None, None
    audit(db, auth.user, "operation.cancelled", operation.id, project_id)
    db.commit()
    return OperationOut.model_validate(operation)


@router.post("/operations/{operation_id}/retry", response_model=OperationOut, status_code=202)
def retry_failed_operation(
    project_id: str,
    operation_id: str,
    body: RetryOperation,
    auth: Auth,
    db: DB,
    idempotency_key: Key,
) -> OperationOut:
    return retry_operation(db, auth, project_id, operation_id, body, idempotency_key)


@router.post("/imports/preview", response_model=PreviewOut, status_code=201)
def import_preview(
    project_id: str, body: ImportPreview, auth: Auth, db: DB, idempotency_key: Key
) -> PreviewOut:
    return preview(db, auth, project_id, body, idempotency_key)


@router.get("/operations", response_model=list[OperationOut])
def operations(
    project_id: str,
    auth: Auth,
    db: DB,
    page: Annotated[int, Query(ge=1)] = 1,
    kind: Literal["import", "report", "extraction", "analysis"] | None = None,
) -> list[OperationOut]:
    project_access(db, auth, project_id)
    query = select(Operation).where(Operation.project_id == project_id)
    if kind is not None:
        query = query.where(Operation.kind == kind)
    return [
        OperationOut.model_validate(op)
        for op in db.scalars(
            query.order_by(Operation.created_at.desc()).offset((page - 1) * 25).limit(25)
        )
    ]


@router.get("/operations/{operation_id}", response_model=PreviewOut)
def operation_detail(project_id: str, operation_id: str, auth: Auth, db: DB) -> PreviewOut:
    project_access(db, auth, project_id)
    operation = db.scalar(
        select(Operation).where(Operation.project_id == project_id, Operation.id == operation_id)
    )
    if operation is None:
        raise HTTPException(404, "Operation not found")
    from pydantic import TypeAdapter

    rows = TypeAdapter(list[PreviewRow]).validate_python(operation.payload.get("rows", []))
    return PreviewOut(**OperationOut.model_validate(operation).model_dump(), rows=rows)


@router.post("/imports/{operation_id}/commit", response_model=OperationOut, status_code=202)
def commit_import(
    project_id: str, operation_id: str, body: CommitImport, auth: Auth, db: DB, idempotency_key: Key
) -> OperationOut:
    lock_write(db, auth, project_id)
    op_name = "import.commit:" + operation_id
    previous = replay(db, auth, project_id, op_name, idempotency_key, body)
    if previous is not None:
        return OperationOut.model_validate(previous)
    operation = db.scalar(
        select(Operation).where(
            Operation.id == operation_id,
            Operation.project_id == project_id,
            Operation.kind == "import",
        )
    )
    if operation is None:
        raise HTTPException(404, "Import not found")
    if operation.status != "preview":
        raise HTTPException(409, "This preview has already been committed")
    from pydantic import TypeAdapter

    rows = TypeAdapter(list[PreviewRow]).validate_python(operation.payload["rows"])
    if all(row.errors for row in rows):
        raise HTTPException(422, "No valid rows to import")
    if any(row.errors for row in rows) and not body.accept_partial:
        raise HTTPException(422, "Confirm partial import or correct the rejected rows")
    operation.actor_id, operation.status = auth.user.id, "queued"
    result = OperationOut.model_validate(operation)
    remember(db, auth, project_id, op_name, idempotency_key, body, result)
    audit(db, auth.user, "import.queued", operation.id, project_id)
    db.commit()
    return result


@router.post("/reports", response_model=OperationOut, status_code=202)
def request_report(
    project_id: str, body: ReportCreate, auth: Auth, db: DB, idempotency_key: Key
) -> OperationOut:
    lock_write(db, auth, project_id)
    previous = replay(db, auth, project_id, "report.create", idempotency_key, body)
    if previous is not None:
        return OperationOut.model_validate(previous)
    from app.requirement_models import Baseline

    if not db.scalar(
        select(Baseline.id).where(
            Baseline.id == body.baseline_id, Baseline.project_id == project_id
        )
    ):
        raise HTTPException(404, "Baseline not found")
    if body.run_ids is not None:
        matching_runs = set(
            db.scalars(
                select(AnalysisRun.id).where(
                    AnalysisRun.project_id == project_id,
                    AnalysisRun.baseline_id == body.baseline_id,
                    AnalysisRun.id.in_(body.run_ids),
                )
            )
        )
        if matching_runs != set(body.run_ids):
            raise HTTPException(422, "Selected runs must belong to this project and baseline")
    operation = Operation(
        project_id=project_id,
        actor_id=auth.user.id,
        kind="report",
        status="queued",
        payload=body.model_dump(),
    )
    db.add(operation)
    db.flush()
    result = OperationOut.model_validate(operation)
    remember(db, auth, project_id, "report.create", idempotency_key, body, result)
    audit(db, auth.user, "report.queued", operation.id, project_id)
    db.commit()
    return result


@router.get("/reports/{report_id}")
def report_preview(project_id: str, report_id: str, auth: Auth, db: DB) -> dict[str, object]:
    project_access(db, auth, project_id)
    report = db.scalar(
        select(ReportSnapshot).where(
            ReportSnapshot.project_id == project_id, ReportSnapshot.id == report_id
        )
    )
    if report is None:
        raise HTTPException(404, "Report not found")
    return report.payload


@router.get("/reports/{report_id}/download")
def report_download(
    project_id: str, report_id: str, auth: Auth, db: DB, format: Literal["md", "csv"] = "md"
) -> Response:
    payload = report_preview(project_id, report_id, auth, db)
    return Response(
        render(payload, format),
        media_type="text/markdown" if format == "md" else "text/csv",
        headers={"Content-Disposition": f'attachment; filename="deliverygap-{report_id}.{format}"'},
    )


@router.get("/overview", response_model=OverviewOut)
def project_overview(project_id: str, baseline_id: str, auth: Auth, db: DB) -> OverviewOut:
    project_access(db, auth, project_id)
    # All writers lock the project, so this snapshot sees one coherent set of decision states.
    from app.models import Project

    db.scalar(select(Project).where(Project.id == project_id).with_for_update())
    return overview(freeze(db, project_id, baseline_id))
