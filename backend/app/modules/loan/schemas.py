"""Loan module DTOs. Money amounts are strings with exactly two decimals
(research R8) mirroring the platform's quantity-string discipline."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

MONEY_PATTERN = r"^\d+(\.\d{1,2})?$"
MoneyAmount = Annotated[str, Field(pattern=MONEY_PATTERN)]

MIN_YEAR = 1300
MAX_YEAR = 1500


def format_money(value: Decimal) -> str:
    return f"{value:.2f}"


def parse_money(value: str) -> Decimal:
    return Decimal(value)


def format_year(value: int) -> str:
    """Locale-neutral Jalali year rendering (Farsi digits come from the
    Kalameh FaNum font in `fa` — no digit conversion in code)."""
    return str(value)


class WorkplaceBriefOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    name_fa: str


class EmployeeBriefOut(BaseModel):
    id: uuid.UUID
    name: str
    name_fa: str | None = None


# --- Policies ---


class LoanPolicyCreateIn(BaseModel):
    workplace_id: uuid.UUID
    year: int = Field(ge=MIN_YEAR, le=MAX_YEAR)
    max_loan_amount: MoneyAmount
    max_guarantee_amount: MoneyAmount
    max_request_count_per_year: int = Field(ge=0)
    max_request_count_lifetime: int = Field(ge=0)


class LoanPolicyUpdateIn(BaseModel):
    year: int | None = Field(default=None, ge=MIN_YEAR, le=MAX_YEAR)
    max_loan_amount: MoneyAmount | None = None
    max_guarantee_amount: MoneyAmount | None = None
    max_request_count_per_year: int | None = Field(default=None, ge=0)
    max_request_count_lifetime: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    version: int = Field(ge=1)


class LoanPolicyRetireIn(BaseModel):
    version: int = Field(ge=1)


class LoanPolicyOut(BaseModel):
    id: uuid.UUID
    version: int
    workplace: WorkplaceBriefOut
    year: int
    max_loan_amount: str
    max_guarantee_amount: str
    max_request_count_per_year: int
    max_request_count_lifetime: int
    is_active: bool
    created_at: datetime


# --- Requests ---


class LoanRequestCreateIn(BaseModel):
    type: Literal["loan", "guarantee"]
    amount: MoneyAmount

    @field_validator("amount")
    @classmethod
    def _amount_positive(cls, value: str) -> str:
        if Decimal(value) <= 0:
            raise ValueError("amount must be positive")
        return value


class LoanRequestOut(BaseModel):
    id: uuid.UUID
    version: int
    employee: EmployeeBriefOut
    workplace: WorkplaceBriefOut
    type: str
    amount: str
    year: int
    status: str
    settled_at: datetime | None
    created_at: datetime


class LoanRequestTransitionIn(BaseModel):
    version: int = Field(ge=1)
