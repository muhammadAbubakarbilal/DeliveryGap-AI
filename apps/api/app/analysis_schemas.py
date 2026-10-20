from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AnalysisCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(default="fixture", pattern="^fixture$")
    baseline_id: str
    input_text: str = Field(min_length=1, max_length=20_000)


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    classification: str
    summary: str
    requirement_version_id: str | None
    evidence_quote: str | None
    input_quote: str | None = None
    request_index: int | None = None
    input_span_start: int | None = None
    input_span_end: int | None = None
    review_status: str
    revision: int


class AnalysisOut(BaseModel):
    input_text: str = ""
    provider: str = "fixture"
    outcome: Literal["completed", "partial", "no_actionable_requests"] = "completed"
    warning: str = (
        "Synthetic fixture replay only; this is not live AI analysis or a quality evaluation."
    )
    id: str
    baseline_id: str
    status: str
    created_at: datetime
    findings: list[FindingOut]


class FindingDecisionIn(BaseModel):
    expected_revision: int = Field(ge=1)
    decision: str = Field(pattern="^(confirmed|dismissed|clarification_requested)$")
    expected_status: str = Field(pattern="^(pending|confirmed|dismissed|clarification_requested)$")


class ManualAnalysisCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    baseline_id: str
    input_text: str = Field(min_length=1, max_length=20000)
    classification: Literal[
        "IN_SCOPE", "CONFLICT", "POTENTIAL_SCOPE_ADDITION", "AMBIGUOUS", "INSUFFICIENT_EVIDENCE"
    ]
    summary: str = Field(min_length=1, max_length=4000)
    requirement_version_id: str | None = None
    evidence_quote: str | None = Field(default=None, min_length=1, max_length=20000)


class BaselineCitation(BaseModel):
    requirement_version_id: str
    requirement_code: str
    title: str
    content: str
    source_quote: str | None
