"""loan module

Revision ID: 0007_loan_module
Revises: 0006_asset_tracking
Create Date: 2026-09-01

Loan policies (one per workplace + Jalali year among active rows) and loan
or guarantee requests (immutable year snapshot, positive amount, status
CHECKs). Fully reversible.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_loan_module"
down_revision: Union[str, None] = "0006_asset_tracking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACTIVE_WHERE = sa.text("deleted_at IS NULL")


def upgrade() -> None:
    op.create_table(
        "loan_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "workplace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workplaces.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("max_loan_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("max_guarantee_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("max_request_count_per_year", sa.Integer(), nullable=False),
        sa.Column("max_request_count_lifetime", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("year >= 1300 AND year <= 1500", name="ck_loan_policies_year_range"),
        sa.CheckConstraint("max_loan_amount >= 0", name="ck_loan_policies_max_loan_amount"),
        sa.CheckConstraint(
            "max_guarantee_amount >= 0", name="ck_loan_policies_max_guarantee_amount"
        ),
        sa.CheckConstraint(
            "max_request_count_per_year >= 0", name="ck_loan_policies_count_per_year"
        ),
        sa.CheckConstraint(
            "max_request_count_lifetime >= 0", name="ck_loan_policies_count_lifetime"
        ),
    )
    op.create_index(
        "uq_loan_policies_workplace_year_active",
        "loan_policies",
        ["workplace_id", "year"],
        unique=True,
        postgresql_where=ACTIVE_WHERE,
    )
    op.create_index("ix_loan_policies_workplace_id", "loan_policies", ["workplace_id"])
    op.create_index("ix_loan_policies_year", "loan_policies", ["year"])

    op.create_table(
        "loan_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "workplace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workplaces.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("complex_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint("type IN ('loan','guarantee')", name="ck_loan_requests_type"),
        sa.CheckConstraint(
            "status IN ('pending','active','settled','cancelled')",
            name="ck_loan_requests_status",
        ),
        sa.CheckConstraint("amount > 0", name="ck_loan_requests_amount_positive"),
        sa.CheckConstraint("year >= 1300 AND year <= 1500", name="ck_loan_requests_year_range"),
    )
    op.create_index(
        "ix_loan_requests_employee_created", "loan_requests", ["employee_id", "created_at"]
    )
    op.create_index(
        "ix_loan_requests_workplace_status_year", "loan_requests", ["workplace_id", "year", "status"]
    )
    op.create_index("ix_loan_requests_complex_id", "loan_requests", ["complex_id"])
    op.create_index("ix_loan_requests_year", "loan_requests", ["year"])


def downgrade() -> None:
    op.drop_index("ix_loan_requests_year", table_name="loan_requests")
    op.drop_index("ix_loan_requests_complex_id", table_name="loan_requests")
    op.drop_index(
        "ix_loan_requests_workplace_status_year", table_name="loan_requests"
    )
    op.drop_index("ix_loan_requests_employee_created", table_name="loan_requests")
    op.drop_table("loan_requests")

    op.drop_index("ix_loan_policies_year", table_name="loan_policies")
    op.drop_index("ix_loan_policies_workplace_id", table_name="loan_policies")
    op.drop_index("uq_loan_policies_workplace_year_active", table_name="loan_policies")
    op.drop_table("loan_policies")
