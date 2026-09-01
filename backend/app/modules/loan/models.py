"""Loan module models: per-workplace Jalali-year policies and employee loan
or guarantee requests (requirements §19, data-model.md, migration 0007).

Integrity invariants (constitution III):
- one policy per workplace + year among active rows (partial unique index);
- request type/status are CHECK-guarded, amounts strictly positive;
- the request's Jalali `year` is an immutable creation snapshot;
- soft delete only — count/cap aggregates deliberately read all rows (§19,
  research R9) while listings read active rows.
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.common.mixins import (
    AuditableEntity,
    CreatedByMixin,
    IDMixin,
    SoftDeleteMixin,
    TimestampMixin,
    VersionMixin,
)
from app.core.database import Base


class LoanType(enum.StrEnum):
    LOAN = "loan"
    GUARANTEE = "guarantee"


class LoanStatus(enum.StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SETTLED = "settled"
    CANCELLED = "cancelled"


class LoanPolicy(
    AuditableEntity,
    Base,
):
    """Per-workplace, per-Jalali-year rule set (master data, soft-deletable)."""

    __tablename__ = "loan_policies"

    workplace_id: Mapped[uuid.UUID] = mapped_column(
        "workplace_id",
        ForeignKey("workplaces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    max_loan_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    max_guarantee_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    max_request_count_per_year: Mapped[int] = mapped_column(Integer, nullable=False)
    max_request_count_lifetime: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("year >= 1300 AND year <= 1500", name="ck_loan_policies_year_range"),
        CheckConstraint("max_loan_amount >= 0", name="ck_loan_policies_max_loan_amount"),
        CheckConstraint(
            "max_guarantee_amount >= 0", name="ck_loan_policies_max_guarantee_amount"
        ),
        CheckConstraint(
            "max_request_count_per_year >= 0", name="ck_loan_policies_count_per_year"
        ),
        CheckConstraint(
            "max_request_count_lifetime >= 0", name="ck_loan_policies_count_lifetime"
        ),
        Index(
            "uq_loan_policies_workplace_year_active",
            "workplace_id",
            "year",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_loan_policies_workplace_id", "workplace_id"),
        Index("ix_loan_policies_year", "year"),
    )


class LoanRequest(
    IDMixin,
    TimestampMixin,
    SoftDeleteMixin,
    VersionMixin,
    CreatedByMixin,
    Base,
):
    """An employee's loan or guarantee demand (immutable flow history)."""

    __tablename__ = "loan_requests"

    employee_id: Mapped[uuid.UUID] = mapped_column(
        "employee_id",
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    )
    workplace_id: Mapped[uuid.UUID] = mapped_column(
        "workplace_id",
        ForeignKey("workplaces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    complex_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    type: Mapped[LoanType] = mapped_column(
        Enum(
            LoanType,
            native_enum=False,
            length=20,
            create_constraint=False,
            values_callable=lambda obj: [member.value for member in obj],
        ),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[LoanStatus] = mapped_column(
        Enum(
            LoanStatus,
            native_enum=False,
            length=20,
            create_constraint=False,
            values_callable=lambda obj: [member.value for member in obj],
        ),
        nullable=False,
        default=LoanStatus.PENDING,
    )
    settled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    __table_args__ = (
        CheckConstraint("type IN ('loan','guarantee')", name="ck_loan_requests_type"),
        CheckConstraint(
            "status IN ('pending','active','settled','cancelled')",
            name="ck_loan_requests_status",
        ),
        CheckConstraint("amount > 0", name="ck_loan_requests_amount_positive"),
        CheckConstraint("year >= 1300 AND year <= 1500", name="ck_loan_requests_year_range"),
        Index("ix_loan_requests_employee_created", "employee_id", "created_at"),
        Index(
            "ix_loan_requests_workplace_status_year", "workplace_id", "year", "status"
        ),
        Index("ix_loan_requests_complex_id", "complex_id"),
        Index("ix_loan_requests_year", "year"),
    )
