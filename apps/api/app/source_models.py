"""Project-scoped originals, canonical source spans and durable parsing work."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models import new_id, now


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("project_id", "id"),
        CheckConstraint("kind IN ('scope','change_request','meeting_notes','other')"),
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    document_id: Mapped[str] = mapped_column(String(36))
    version_number: Mapped[int]
    filename: Mapped[str] = mapped_column(String(200))
    mime_type: Mapped[str] = mapped_column(String(100))
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(200), unique=True)
    byte_size: Mapped[int]
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    is_manual: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    warning: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "document_id"], ["documents.project_id", "documents.id"]
        ),
        UniqueConstraint("project_id", "id"),
        UniqueConstraint("document_id", "version_number"),
        CheckConstraint("version_number > 0 AND byte_size > 0"),
        CheckConstraint("status IN ('queued','processing','ready','needs_manual_input','failed')"),
    )


class SourceSpan(Base):
    __tablename__ = "source_spans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36))
    version_id: Mapped[str] = mapped_column(String(36))
    ordinal: Mapped[int]
    locator: Mapped[str] = mapped_column(String(60))
    char_start: Mapped[int] = mapped_column(default=0)
    char_end: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "version_id"], ["document_versions.project_id", "document_versions.id"]
        ),
        UniqueConstraint("version_id", "ordinal"),
        UniqueConstraint("project_id", "id"),
        UniqueConstraint("project_id", "version_id", "id"),
        CheckConstraint("ordinal > 0 AND char_start = 0 AND char_end >= char_start"),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36))
    version_id: Mapped[str] = mapped_column(String(36))
    span_id: Mapped[str] = mapped_column(String(36))
    ordinal: Mapped[int]
    char_start: Mapped[int]
    char_end: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "version_id", "span_id"],
            ["source_spans.project_id", "source_spans.version_id", "source_spans.id"],
        ),
        UniqueConstraint("version_id", "ordinal"),
        CheckConstraint("char_start >= 0 AND char_end > char_start"),
    )


class ParseJob(Base):
    __tablename__ = "processing_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36))
    version_id: Mapped[str] = mapped_column(String(36), unique=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    attempts: Mapped[int] = mapped_column(default=0)
    cycle_attempts: Mapped[int] = mapped_column(default=0)
    fence: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(String(300))
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "version_id"], ["document_versions.project_id", "document_versions.id"]
        ),
        CheckConstraint("status IN ('queued','running','succeeded','failed')"),
    )


class JobAttempt(Base):
    __tablename__ = "job_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("processing_jobs.id"))
    number: Mapped[int]
    fence: Mapped[str] = mapped_column(String(36), unique=True)
    status: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("job_id", "number"),)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    job_id: Mapped[str] = mapped_column(ForeignKey("processing_jobs.id"), primary_key=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deliveries: Mapped[int] = mapped_column(default=0)


class SourceCommand(Base):
    __tablename__ = "source_commands"
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    operation: Mapped[str] = mapped_column(String(80), primary_key=True)
    request_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict[str, object]] = mapped_column(JSON)
