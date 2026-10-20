import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Project, new_id
from app.security import Principal, audit, project_access
from app.source_models import Document, DocumentVersion, OutboxEvent, ParseJob, SourceCommand
from app.source_parsers import InvalidSource, validate_original
from app.source_schemas import UploadOut
from app.source_storage import Storage


def source_access(db: Session, auth: Principal, project_id: str, write: bool = False) -> None:
    project, role = project_access(db, auth, project_id)
    if write and (project.status != "active" or (not auth.user.is_admin and role == "reviewer")):
        raise HTTPException(403, "An active project and lead or member access are required")


def get_version(db: Session, project_id: str, version_id: str) -> DocumentVersion:
    row = db.scalar(
        select(DocumentVersion).where(
            DocumentVersion.project_id == project_id, DocumentVersion.id == version_id
        )
    )
    if row is None:
        raise HTTPException(404, "Source version not found")
    return row


def save_source(
    db: Session,
    auth: Principal,
    project_id: str,
    title: str,
    kind: str,
    filename: str,
    mime: str,
    content: bytes,
    key: str,
    storage: Storage,
    document_id: str | None = None,
    manual: bool = False,
) -> UploadOut:
    source_access(db, auth, project_id, write=True)
    from app.config import get_settings

    if len(content) > get_settings().max_upload_bytes:
        raise HTTPException(413, "Files must be at most 10 MB")
    try:
        mime = validate_original(filename, mime, content)
    except InvalidSource as exc:
        raise HTTPException(422, str(exc)) from exc
    digest = hashlib.sha256(content).hexdigest()
    operation = "upload:" + (document_id or "new")
    payload_hash = hashlib.sha256(
        json.dumps([title, kind, filename, mime, digest, manual], ensure_ascii=True).encode()
    ).hexdigest()
    # Serialize revision allocation and same-project command retries. Membership
    # mutations use this same project lock; recheck permission after acquiring it.
    db.scalar(select(Project).where(Project.id == project_id).with_for_update())
    source_access(db, auth, project_id, write=True)
    identity = (auth.user.id, project_id, operation, key)
    previous = db.get(SourceCommand, identity)
    if previous:
        if previous.request_hash != payload_hash:
            raise HTTPException(409, "Idempotency key was used with different source content")
        return UploadOut.model_validate(previous.response)
    if document_id:
        document = db.scalar(
            select(Document).where(Document.project_id == project_id, Document.id == document_id)
        )
        if document is None:
            raise HTTPException(404, "Document not found")
    else:
        document = Document(project_id=project_id, title=title.strip(), kind=kind)
        db.add(document)
        db.flush()
    number = (
        db.scalar(
            select(func.max(DocumentVersion.version_number)).where(
                DocumentVersion.document_id == document.id
            )
        )
        or 0
    ) + 1
    duplicate = (
        db.scalar(
            select(DocumentVersion.id)
            .where(DocumentVersion.project_id == project_id, DocumentVersion.sha256 == digest)
            .limit(1)
        )
        is not None
    )
    version_id = new_id()
    storage_key = f"originals/{project_id}/{version_id}"
    try:
        storage.put(storage_key, content)
    except Exception as exc:
        raise HTTPException(
            503, "Private storage is unavailable. Retry with the same file."
        ) from exc
    version = DocumentVersion(
        id=version_id,
        project_id=project_id,
        document_id=document.id,
        version_number=number,
        filename=filename,
        mime_type=mime,
        sha256=digest,
        storage_key=storage_key,
        byte_size=len(content),
        uploaded_by=auth.user.id,
        is_manual=manual,
    )
    db.add(version)
    db.flush()
    job = ParseJob(project_id=project_id, version_id=version_id, actor_id=auth.user.id)
    db.add(job)
    db.flush()
    db.add(OutboxEvent(job_id=job.id))
    result = UploadOut(
        document_id=document.id, version_id=version.id, job_id=job.id, duplicate=duplicate
    )
    db.add(
        SourceCommand(
            actor_id=auth.user.id,
            project_id=project_id,
            operation=operation,
            request_key=key,
            request_hash=payload_hash,
            response=result.model_dump(),
        )
    )
    audit(db, auth.user, "document.uploaded", version.id, project_id, manual=manual)
    db.commit()
    return result
