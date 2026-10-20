from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models import new_id, now


class DeliveryArtifact(Base):
    __tablename__ = "delivery_artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="manual")
    kind: Mapped[str] = mapped_column(String(16))
    external_id: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(32), default="recorded")
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    environment: Mapped[str | None] = mapped_column(String(200))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        Index("uq_artifact_project_id", "project_id", "id", unique=True),
        UniqueConstraint("project_id", "provider", "kind", "external_id"),
        CheckConstraint("kind IN ('task','test','pull_request')"),
    )


class ArtifactLink(Base):
    __tablename__ = "artifact_links"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    requirement_version_id: Mapped[str] = mapped_column(String(36))
    artifact_id: Mapped[str] = mapped_column(String(36))
    relation_type: Mapped[str] = mapped_column(String(24), default="evidence")
    origin: Mapped[str] = mapped_column(String(16), default="manual")
    review_status: Mapped[str] = mapped_column(String(16), default="proposed")
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    artifact_revision: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "requirement_version_id"],
            ["requirement_versions.project_id", "requirement_versions.id"],
        ),
        ForeignKeyConstraint(
            ["project_id", "artifact_id"],
            ["delivery_artifacts.project_id", "delivery_artifacts.id"],
        ),
        UniqueConstraint("project_id", "requirement_version_id", "artifact_id"),
        CheckConstraint("review_status IN ('proposed','accepted','rejected')"),
    )


class ArtifactRevision(Base):
    __tablename__ = "artifact_revisions"
    artifact_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36))
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    snapshot: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "artifact_id"],
            ["delivery_artifacts.project_id", "delivery_artifacts.id"],
        ),
    )


class LinkDecision(Base):
    __tablename__ = "link_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    link_id: Mapped[str] = mapped_column(ForeignKey("artifact_links.id"))
    revision: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(16))
    artifact_revision: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("link_id", "revision"),)
