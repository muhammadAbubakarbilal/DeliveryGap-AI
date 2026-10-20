import re
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.security import DB, Auth
from app.source_models import Document, DocumentVersion, JobAttempt, ParseJob, SourceSpan
from app.source_schemas import (
    AttemptOut,
    DocumentKind,
    DocumentOut,
    DocumentPage,
    JobOut,
    ManualSource,
    SpanOut,
    SpanPage,
    UploadOut,
    VersionOut,
)
from app.source_service import get_version, save_source, source_access
from app.source_storage import Storage, get_storage

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["Document sources"])
Key = Annotated[str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")]
Store = Annotated[Storage, Depends(get_storage)]


def filename_checked(filename: str) -> str:
    if not filename.strip() or re.search(r"[\x00-\x1f\x7f/\\]", filename):
        raise HTTPException(422, "Use a plain filename without paths or control characters")
    return filename


@router.post("/documents", response_model=UploadOut, status_code=201)
async def upload(
    project_id: str,
    request: Request,
    auth: Auth,
    db: DB,
    storage: Store,
    idempotency_key: Key,
    filename: Annotated[str, Query(min_length=1, max_length=200)],
    title: Annotated[str, Query(min_length=1, max_length=200)],
    kind: DocumentKind = "scope",
    document_id: str | None = None,
) -> UploadOut:
    """Upload a bounded raw file body. document_id adds an immutable revision."""
    filename_checked(filename)
    if not title.strip():
        raise HTTPException(422, "A title is required")
    await run_in_threadpool(source_access, db, auth, project_id, True)
    maximum = get_settings().max_upload_bytes
    content = bytearray()
    async for part in request.stream():
        if len(content) + len(part) > maximum:
            raise HTTPException(413, "Files must be at most 10 MB")
        content.extend(part)
    return await run_in_threadpool(
        save_source,
        db,
        auth,
        project_id,
        title,
        kind,
        filename,
        request.headers.get("content-type", "application/octet-stream"),
        bytes(content),
        idempotency_key,
        storage,
        document_id,
    )


@router.post("/documents/manual", response_model=UploadOut, status_code=201)
def manual_source(
    project_id: str,
    body: ManualSource,
    auth: Auth,
    db: DB,
    storage: Store,
    idempotency_key: Key,
    document_id: str | None = None,
) -> UploadOut:
    if not body.title.strip() or not body.text.strip():
        raise HTTPException(422, "Title and manual text are required")
    return save_source(
        db,
        auth,
        project_id,
        body.title,
        body.kind,
        "manual-source.txt",
        "text/plain",
        body.text.encode("utf-8"),
        idempotency_key,
        storage,
        document_id,
        manual=True,
    )


def document_output(db: DB, row: Document) -> DocumentOut:
    versions = db.scalars(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == row.id)
        .order_by(DocumentVersion.version_number.desc())
    )
    return DocumentOut(
        id=row.id,
        title=row.title,
        kind=row.kind,
        versions=[VersionOut.model_validate(v) for v in versions],
    )


@router.get("/documents", response_model=DocumentPage)
def documents(
    project_id: str, auth: Auth, db: DB, page: Annotated[int, Query(ge=1)] = 1
) -> DocumentPage:
    source_access(db, auth, project_id)
    query = select(Document).where(Document.project_id == project_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(Document.created_at.desc(), Document.id).offset((page - 1) * 25).limit(25)
    )
    return DocumentPage(items=[document_output(db, row) for row in rows], total=total)


@router.get("/documents/{document_id}", response_model=DocumentOut)
def document_detail(project_id: str, document_id: str, auth: Auth, db: DB) -> DocumentOut:
    source_access(db, auth, project_id)
    row = db.scalar(
        select(Document).where(Document.project_id == project_id, Document.id == document_id)
    )
    if row is None:
        raise HTTPException(404, "Document not found")
    return document_output(db, row)


@router.get("/versions/{version_id}/spans", response_model=SpanPage)
def spans(
    project_id: str, version_id: str, auth: Auth, db: DB, page: Annotated[int, Query(ge=1)] = 1
) -> SpanPage:
    source_access(db, auth, project_id)
    get_version(db, project_id, version_id)
    query = select(SourceSpan).where(
        SourceSpan.project_id == project_id, SourceSpan.version_id == version_id
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(SourceSpan.ordinal).offset((page - 1) * 25).limit(25))
    return SpanPage(items=[SpanOut.model_validate(row) for row in rows], total=total)


@router.get("/versions/{version_id}/download")
def download(project_id: str, version_id: str, auth: Auth, db: DB, storage: Store) -> Response:
    source_access(db, auth, project_id)
    version = get_version(db, project_id, version_id)
    try:
        content = storage.get(version.storage_key)
    except Exception as exc:
        raise HTTPException(503, "The original is temporarily unavailable") from exc
    return Response(
        content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''"
            + quote(version.filename, safe="")
        },
    )


@router.get("/versions/{version_id}/job", response_model=JobOut)
def job_status(project_id: str, version_id: str, auth: Auth, db: DB) -> JobOut:
    source_access(db, auth, project_id)
    get_version(db, project_id, version_id)
    job = db.scalar(
        select(ParseJob).where(ParseJob.project_id == project_id, ParseJob.version_id == version_id)
    )
    assert job is not None
    attempts = db.scalars(
        select(JobAttempt)
        .where(JobAttempt.job_id == job.id)
        .order_by(JobAttempt.number.desc())
        .limit(25)
    )
    return JobOut(
        id=job.id,
        version_id=version_id,
        status=job.status,
        error=job.error,
        attempts=[AttemptOut.model_validate(a) for a in attempts],
    )


@router.post("/versions/{version_id}/retry", response_model=JobOut)
def retry(project_id: str, version_id: str, auth: Auth, db: DB, idempotency_key: Key) -> JobOut:
    from app.source_jobs import retry_job

    source_access(db, auth, project_id, write=True)
    get_version(db, project_id, version_id)
    retry_job(db, auth, project_id, version_id, idempotency_key)
    return job_status(project_id, version_id, auth, db)
