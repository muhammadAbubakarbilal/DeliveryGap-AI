from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Role = Literal["lead", "member", "reviewer"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginInput(Input):
    email: EmailStr
    # Do not normalize passwords; whitespace is meaningful.
    password: str = Field(min_length=1, max_length=256)
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    display_name: str
    is_admin: bool
    is_active: bool


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str
    auth_provider: str = "local"


class UserCreate(Input):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=12, max_length=256)
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class UserUpdate(Input):
    is_active: bool


class ProjectCreate(Input):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)


class ProjectUpdate(ProjectCreate):
    revision: int = Field(ge=1)
    status: Literal["active", "archived"] = "active"


class ExternalAIConsentUpdate(Input):
    enabled: bool


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str
    status: str
    revision: int
    external_ai_consent: bool = False
    created_at: datetime
    role: str
    member_count: int


class ProjectPage(BaseModel):
    items: list[ProjectOut]
    total: int
    page: int
    page_size: int


class MemberInput(Input):
    email: EmailStr
    role: Role


class MemberUpdate(Input):
    role: Role


class MemberOut(BaseModel):
    user_id: str
    email: str
    display_name: str
    role: Role
    is_active: bool
