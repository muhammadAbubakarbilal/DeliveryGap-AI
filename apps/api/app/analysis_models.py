from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models import new_id, now


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    baseline_id: Mapped[str] = mapped_column(String(36))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    input_text: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(32), default="fixture")
    status: Mapped[str] = mapped_column(String(16), default="succeeded")
    outcome: Mapped[str] = mapped_column(String(32), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "baseline_id"], ["baselines.project_id", "baselines.id"]
        ),
        CheckConstraint("status = 'succeeded'"),
    )


class Finding(Base):
    __tablename__ = "findings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"))
    classification: Mapped[str] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(Text)
    requirement_version_id: Mapped[str | None] = mapped_column(String(36))
    evidence_quote: Mapped[str | None] = mapped_column(Text)
    input_quote: Mapped[str | None] = mapped_column(Text)
    request_index: Mapped[int | None] = mapped_column(Integer)
    input_span_start: Mapped[int | None] = mapped_column(Integer)
    input_span_end: Mapped[int | None] = mapped_column(Integer)
    review_status: Mapped[str] = mapped_column(String(24), default="pending")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "requirement_version_id"],
            ["requirement_versions.project_id", "requirement_versions.id"],
        ),
        UniqueConstraint("project_id", "id"),
        CheckConstraint(
            "classification IN ("
            "'IN_SCOPE','POTENTIAL_SCOPE_ADDITION','CONFLICT','AMBIGUOUS','INSUFFICIENT_EVIDENCE')"
        ),
        CheckConstraint(
            "review_status IN ('pending','confirmed','dismissed','clarification_requested')"
        ),
    )


class FindingDecision(Base):
    __tablename__ = "finding_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    finding_id: Mapped[str] = mapped_column(String(36))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(24))
    expected_status: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(["project_id", "finding_id"], ["findings.project_id", "findings.id"]),
        CheckConstraint("decision IN ('confirmed','dismissed','clarification_requested')"),
    )
