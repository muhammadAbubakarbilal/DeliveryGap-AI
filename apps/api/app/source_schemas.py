from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import Input

DocumentKind = Literal["scope", "change_request", "meeting_notes", "other"]


class ManualSource(Input):
    title: str = Field(min_length=1, max_length=200)
    kind: DocumentKind = "scope"
    text: str = Field(min_length=1, max_length=100_000)
    # Preserve authored text exactly; title is normalized separately.
    model_config = ConfigDict(extra="forbid")


class VersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    document_id: str
    version_number: int
    filename: str
    mime_type: str
    sha256: str
    byte_size: int
    is_manual: bool
    status: str
    warning: str | None
    created_at: datetime


class DocumentOut(BaseModel):
    id: str
    title: str
    kind: str
    versions: list[VersionOut]


class DocumentPage(BaseModel):
    items: list[DocumentOut]
    total: int


class UploadOut(BaseModel):
    document_id: str
    version_id: str
    job_id: str
    duplicate: bool


class SpanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    ordinal: int
    locator: str
    char_start: int
    char_end: int
    text: str


class SpanPage(BaseModel):
    items: list[SpanOut]
    total: int


class AttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    number: int
    status: str
    started_at: datetime
    finished_at: datetime | None


class JobOut(BaseModel):
    id: str
    version_id: str
    status: str
    error: str | None
    attempts: list[AttemptOut]
