"""Versioned requirements and immutable published baselines."""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models import new_id, now


class Requirement(Base):
    __tablename__ = "requirements"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(32))
    current_version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("project_id", "id"),
        UniqueConstraint("project_id", "code"),
    )


class RequirementVersion(Base):
    __tablename__ = "requirement_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    requirement_id: Mapped[str] = mapped_column(String(36))
    version_number: Mapped[int]
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    source_version_id: Mapped[str | None] = mapped_column(String(36))
    source_span_id: Mapped[str | None] = mapped_column(String(36))
    source_quote: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "requirement_id"], ["requirements.project_id", "requirements.id"]
        ),
        ForeignKeyConstraint(
            ["project_id", "source_version_id"],
            ["document_versions.project_id", "document_versions.id"],
        ),
        ForeignKeyConstraint(
            ["project_id", "source_span_id"], ["source_spans.project_id", "source_spans.id"]
        ),
        UniqueConstraint("requirement_id", "version_number"),
        UniqueConstraint("project_id", "id"),
        CheckConstraint("version_number > 0"),
        CheckConstraint("status IN ('draft','approved','rejected')"),
    )


class RequirementEmbedding(Base):
    __tablename__ = "requirement_embeddings"
    project_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    requirement_version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    model: Mapped[str] = mapped_column(String(80), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024).with_variant(JSON(), "sqlite"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "requirement_version_id"],
            ["requirement_versions.project_id", "requirement_versions.id"],
        ),
        Index("ix_requirement_embeddings_project_model", "project_id", "model"),
    )


class RequirementLineage(Base):
    __tablename__ = "requirement_lineage"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(8))
    parent_requirement_id: Mapped[str] = mapped_column(String(36))
    parent_version_id: Mapped[str] = mapped_column(String(36))
    child_requirement_id: Mapped[str] = mapped_column(String(36))
    child_version_id: Mapped[str] = mapped_column(String(36))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "parent_requirement_id"], ["requirements.project_id", "requirements.id"]
        ),
        ForeignKeyConstraint(
            ["project_id", "child_requirement_id"], ["requirements.project_id", "requirements.id"]
        ),
        ForeignKeyConstraint(
            ["project_id", "parent_version_id"],
            ["requirement_versions.project_id", "requirement_versions.id"],
        ),
        ForeignKeyConstraint(
            ["project_id", "child_version_id"],
            ["requirement_versions.project_id", "requirement_versions.id"],
        ),
        UniqueConstraint("project_id", "action", "parent_requirement_id", "child_requirement_id"),
        CheckConstraint("action IN ('split','merge')"),
        CheckConstraint("parent_requirement_id <> child_requirement_id"),
    )


class RequirementReviewEvent(Base):
    __tablename__ = "requirement_review_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    requirement_version_id: Mapped[str] = mapped_column(String(36))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(16))
    expected_version: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "requirement_version_id"],
            ["requirement_versions.project_id", "requirement_versions.id"],
        ),
        CheckConstraint("action IN ('approved','rejected')"),
    )


class Baseline(Base):
    __tablename__ = "baselines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    number: Mapped[int]
    status: Mapped[str] = mapped_column(String(16), default="published")
    published_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("project_id", "number"),
        UniqueConstraint("project_id", "id"),
        CheckConstraint("number > 0"),
        CheckConstraint("status = 'published'"),
    )


class BaselineItem(Base):
    __tablename__ = "baseline_items"
    baseline_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36))
    requirement_version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    requirement_code: Mapped[str] = mapped_column(String(32))
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "baseline_id"], ["baselines.project_id", "baselines.id"]
        ),
        ForeignKeyConstraint(
            ["project_id", "requirement_version_id"],
            ["requirement_versions.project_id", "requirement_versions.id"],
        ),
    )
