from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ImportPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["task", "test"]
    csv_text: str = Field(min_length=1, max_length=1_000_000)
    baseline_id: str | None = None
    column_mapping: dict[str, str] = Field(default_factory=dict, max_length=16)


class CommitImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accept_partial: bool = False


class RetryOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    baseline_id: str
    run_ids: list[str] | None = Field(default=None, max_length=100)
    classifications: list[
        Literal[
            "IN_SCOPE",
            "POTENTIAL_SCOPE_ADDITION",
            "CONFLICT",
            "AMBIGUOUS",
            "INSUFFICIENT_EVIDENCE",
        ]
    ] = Field(default_factory=list, max_length=5)
    review_statuses: list[
        Literal["pending", "confirmed", "dismissed", "clarification_requested"]
    ] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def unique_filters(self) -> "ReportCreate":
        if self.run_ids is not None and len(self.run_ids) != len(set(self.run_ids)):
            raise ValueError("Run IDs must be unique")
        if len(self.classifications) != len(set(self.classifications)):
            raise ValueError("Classifications must be unique")
        if len(self.review_statuses) != len(set(self.review_statuses)):
            raise ValueError("Review statuses must be unique")
        return self


class OperationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: str
    status: str
    result: dict[str, object] | None
    error: str | None
    attempts: int
    created_at: datetime


class PreviewRow(BaseModel):
    number: int
    artifact: dict[str, object] | None = None
    requirement_version_id: str | None = None
    expected_revision: int | None = None
    errors: list[str] = Field(default_factory=list)


class PreviewOut(OperationOut):
    rows: list[PreviewRow]


class OverviewOut(BaseModel):
    baseline_id: str
    requirements: int
    accepted_current_evidence: int
    missing_current_evidence: int
    stale_links: int
    pending_findings: int
