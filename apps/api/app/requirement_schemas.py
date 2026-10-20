from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RequirementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str | None = Field(default=None, pattern=r"^REQ-[0-9]{3,}$")
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10_000)
    source_version_id: str | None = None
    source_span_id: str | None = None
    source_quote: str | None = Field(default=None, max_length=20_000)


class RequirementEdit(RequirementCreate):
    expected_version: int = Field(ge=1)


class RequirementVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    requirement_id: str
    version_number: int
    title: str
    content: str
    status: str = "active"
    source_version_id: str | None
    source_span_id: str | None
    source_quote: str | None
    created_at: datetime


class RequirementOut(BaseModel):
    id: str
    code: str
    current_version: int
    status: str
    versions: list[RequirementVersionOut]
    lineage: list["RequirementLineageOut"] = Field(default_factory=list)


class RequirementLineageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    action: Literal["split", "merge"]
    parent_requirement_id: str
    parent_requirement_code: str
    parent_version_id: str
    child_requirement_id: str
    child_requirement_code: str
    child_version_id: str
    created_at: datetime


class RequirementTransformParent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirement_id: str
    expected_version: int = Field(ge=1)


class RequirementTransform(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["split", "merge"]
    parents: list[RequirementTransformParent] = Field(min_length=1, max_length=10)
    children: list[RequirementCreate] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def validate_shape(self) -> "RequirementTransform":
        parent_ids = [parent.requirement_id for parent in self.parents]
        codes = [child.code for child in self.children if child.code]
        if len(parent_ids) != len(set(parent_ids)):
            raise ValueError("Parent requirements must be unique")
        if len(codes) != len(set(codes)):
            raise ValueError("Child requirement codes must be unique")
        if self.action == "split" and (len(self.parents) != 1 or len(self.children) < 2):
            raise ValueError("A split requires one parent and at least two child drafts")
        if self.action == "merge" and (len(self.parents) < 2 or len(self.children) != 1):
            raise ValueError("A merge requires at least two parents and one child draft")
        return self


class RequirementTransformOut(BaseModel):
    superseded_requirement_ids: list[str]
    children: list[RequirementOut]


class RequirementPage(BaseModel):
    items: list[RequirementOut]
    total: int


class ReviewInput(BaseModel):
    expected_version: int = Field(ge=1)


class BaselineCreate(BaseModel):
    requirement_version_ids: list[str] = Field(min_length=1, max_length=500)


class BaselineItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    requirement_version_id: str
    requirement_code: str


class BaselineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    number: int
    status: str
    published_by: str
    created_at: datetime
    items: list[BaselineItemOut]
