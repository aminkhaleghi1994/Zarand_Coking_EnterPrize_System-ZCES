"""org user module

Revision ID: 0003_org_user_module
Revises: 0002_auth_rbac_scope
Create Date: 2026-08-31

Organization hierarchy (companies, complexes, workplaces) + employees with
partial unique identity indexes + users.employee_id 1:1 linkage + real FKs on
scope_assignments unit columns. Fully reversible.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_org_user_module"
down_revision: Union[str, None] = "0002_auth_rbac_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACTIVE_WHERE = sa.text("deleted_at IS NULL")


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_fa", sa.String(length=200), nullable=False),
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
    )
    op.create_index("uq_companies_code", "companies", ["code"], unique=True)

    op.create_table(
        "complexes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_fa", sa.String(length=200), nullable=False),
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
    )
    op.create_index("uq_complexes_code", "complexes", ["code"], unique=True)

    op.create_table(
        "workplaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "complex_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("complexes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_fa", sa.String(length=200), nullable=False),
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
    )
    op.create_index("uq_workplaces_code", "workplaces", ["code"], unique=True)

    op.create_table(
        "employees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "workplace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workplaces.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("national_id", sa.String(length=10), nullable=False),
        sa.Column("personnel_code", sa.String(length=50), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("first_name_fa", sa.String(length=100), nullable=True),
        sa.Column("last_name_fa", sa.String(length=100), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
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
    )
    op.create_index(
        "uq_employee_national_id_active",
        "employees",
        ["national_id"],
        unique=True,
        postgresql_where=ACTIVE_WHERE,
    )
    op.create_index(
        "uq_employee_personnel_code_active",
        "employees",
        ["personnel_code"],
        unique=True,
        postgresql_where=ACTIVE_WHERE,
    )
    op.create_index("ix_employees_workplace_id", "employees", ["workplace_id"])
    op.create_index("ix_employees_last_name", "employees", ["last_name"])

    op.add_column(
        "users",
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "uq_users_employee_id",
        "users",
        ["employee_id"],
        unique=True,
    )
    op.create_foreign_key(
        "fk_users_employee_id",
        "users",
        "employees",
        ["employee_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_foreign_key(
        "fk_scope_assignments_complex_id",
        "scope_assignments",
        "complexes",
        ["complex_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_scope_assignments_workplace_id",
        "scope_assignments",
        "workplaces",
        ["workplace_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_scope_assignments_workplace_id", "scope_assignments", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_scope_assignments_complex_id", "scope_assignments", type_="foreignkey"
    )
    op.drop_constraint("fk_users_employee_id", "users", type_="foreignkey")
    op.drop_index("uq_users_employee_id", table_name="users")
    op.drop_column("users", "employee_id")
    op.drop_index("ix_employees_last_name", table_name="employees")
    op.drop_index("ix_employees_workplace_id", table_name="employees")
    op.drop_index("uq_employee_personnel_code_active", table_name="employees")
    op.drop_index("uq_employee_national_id_active", table_name="employees")
    op.drop_table("employees")
    op.drop_index("uq_workplaces_code", table_name="workplaces")
    op.drop_table("workplaces")
    op.drop_index("uq_complexes_code", table_name="complexes")
    op.drop_table("complexes")
    op.drop_index("uq_companies_code", table_name="companies")
    op.drop_table("companies")
