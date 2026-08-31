import enum
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.common.scope import ScopeLevel

NATIONAL_ID_PATTERN = r"^\d{10}$"


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


# --- Organization structure ---


class ComplexOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    name_fa: str
    company_id: uuid.UUID


class WorkplaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    name_fa: str
    complex_id: uuid.UUID


# --- Employees ---


class EmployeeUserIn(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)


class EmployeeCreateIn(BaseModel):
    national_id: str = Field(pattern=NATIONAL_ID_PATTERN)
    personnel_code: str = Field(min_length=1, max_length=50)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    first_name_fa: str | None = Field(default=None, max_length=100)
    last_name_fa: str | None = Field(default=None, max_length=100)
    birth_date: date | None = None
    phone: str | None = Field(default=None, max_length=20)
    workplace_id: uuid.UUID
    user: EmployeeUserIn


class EmployeeUpdateIn(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    first_name_fa: str | None = Field(default=None, max_length=100)
    last_name_fa: str | None = Field(default=None, max_length=100)
    birth_date: date | None = None
    phone: str | None = Field(default=None, max_length=20)
    workplace_id: uuid.UUID | None = None
    version: int = Field(ge=1)


class EmployeeUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    username: str
    is_active: bool


class EmployeeWorkplaceOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    name_fa: str
    complex_id: uuid.UUID


class EmployeeComplexOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    name_fa: str


class EmployeeOut(BaseModel):
    id: uuid.UUID
    version: int
    national_id: str
    personnel_code: str
    first_name: str
    last_name: str
    first_name_fa: str | None = None
    last_name_fa: str | None = None
    birth_date: date | None = None
    phone: str | None = None
    is_active: bool
    workplace: EmployeeWorkplaceOut
    complex: EmployeeComplexOut
    user: EmployeeUserOut
    created_at: datetime


class EmployeeSummaryOut(BaseModel):
    id: uuid.UUID
    national_id: str
    personnel_code: str
    first_name: str
    last_name: str
    is_active: bool
    workplace_id: uuid.UUID
    workplace_name: str


class PasswordSetIn(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class StatusFilterIn(enum.StrEnum):
    ACTIVE = "active"
    DEACTIVATED = "deactivated"
    ALL = "all"
