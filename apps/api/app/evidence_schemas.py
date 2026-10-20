from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class ArtifactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_revision: int | None = Field(default=None, ge=1)
    kind: str = Field(pattern="^(task|test|pull_request)$")
    external_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=20_000)
    status: str = Field(default="recorded", max_length=32)
    url: HttpUrl | None = None
    executed_at: datetime | None = None
    environment: str | None = Field(default=None, max_length=200)

    @field_validator("executed_at")
    @classmethod
    def timezone_aware_execution(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Execution time must include a timezone")
        return value.astimezone(UTC) if value is not None else None

    @model_validator(mode="after")
    def test_metadata(self) -> "ArtifactCreate":
        if self.kind != "test" and (self.executed_at is not None or self.environment is not None):
            raise ValueError("Execution time and environment apply only to test artifacts")
        return self


class ArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    provider: str
    kind: str
    external_id: str
    title: str
    description: str
    url: str | None
    status: str
    executed_at: datetime | None
    environment: str | None
    updated_at: datetime
    revision: int

    @field_validator("executed_at", mode="before")
    @classmethod
    def normalize_stored_execution_time(cls, value: datetime | str | None) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class LinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accept: bool = False
    expected_artifact_revision: int | None = Field(default=None, ge=1)
    requirement_version_id: str
    artifact_id: str
    relation_type: str = Field(default="evidence", max_length=24)


class LinkReview(BaseModel):
    expected_artifact_revision: int | None = Field(default=None, ge=1)
    expected_revision: int = Field(ge=1)
    review_status: str = Field(pattern="^(accepted|rejected)$")


class BulkLinkDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    link_id: str
    expected_revision: int = Field(ge=1)
    expected_artifact_revision: int = Field(ge=1)
    review_status: str = Field(pattern="^(accepted|rejected)$")


class BulkLinkReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decisions: list[BulkLinkDecision] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_links(self) -> "BulkLinkReview":
        ids = [decision.link_id for decision in self.decisions]
        if len(ids) != len(set(ids)):
            raise ValueError("A link may appear only once in a bulk review")
        return self


class LinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    requirement_version_id: str
    artifact_id: str
    relation_type: str
    origin: str
    review_status: str
    reviewed_by: str | None
    revision: int
    artifact_revision: int | None = None
    stale: bool = False
    artifact_title: str | None = None
    artifact_kind: str | None = None
    current_artifact_revision: int | None = None


class BulkLinkReviewOut(BaseModel):
    items: list[LinkOut]


class TraceabilityOut(BaseModel):
    requirement_version_id: str
    links: list[LinkOut]
