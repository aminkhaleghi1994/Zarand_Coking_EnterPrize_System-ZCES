import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.common.scope import ScopeLevel


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    username: str
    is_active: bool
    created_at: datetime


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None


class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name_en: str
    name_fa: str


class ScopeAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    level: ScopeLevel
    module: str
    resource: str
    operation: str
    complex_id: uuid.UUID | None = None
    workplace_id: uuid.UUID | None = None


class MeOut(BaseModel):
    user: UserOut
    roles: list[str]
    permissions: list[str]
    scopes: list[ScopeAssignmentOut]


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class TokenPairOut(BaseModel):
    user: UserOut
    roles: list[str]
    access_token: str
    access_expires_in: int
    refresh_token: str


class RefreshTokenIn(BaseModel):
    refresh_token: str = Field(min_length=16)


class SuccessOut(BaseModel):
    success: bool = True


class RoleCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = None


class AssignRoleIn(BaseModel):
    role_id: uuid.UUID


class ScopeCreateIn(BaseModel):
    level: ScopeLevel
    module: str = Field(min_length=1, max_length=100)
    resource: str = Field(min_length=1, max_length=100)
    operation: str = Field(min_length=1, max_length=100)
    complex_id: uuid.UUID | None = None
    workplace_id: uuid.UUID | None = None


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
