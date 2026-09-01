"""asset tracking

Revision ID: 0006_asset_tracking
Revises: 0005_item_requests_flow
Create Date: 2026-08-31

Asset instances (typed holder with a state CHECK, normalized serial partial
unique among active rows, workplace anchor for scope) + append-only per-asset
history. Fully reversible.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_asset_tracking"
down_revision: Union[str, None] = "0005_item_requests_flow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACTIVE_WHERE = sa.text("deleted_at IS NULL")

_HOLDER_STATE_CHECK = (
    "(holder_type IS NULL AND holder_employee_id IS NULL AND holder_location IS NULL)"
    " OR (holder_type = 'employee' AND holder_employee_id IS NOT NULL AND holder_location IS NULL)"
    " OR (holder_type = 'location' AND holder_employee_id IS NULL AND holder_location IS NOT NULL)"
)


def upgrade() -> None:
    op.create_table(
        "asset_instances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_fa", sa.String(length=200), nullable=False),
        sa.Column("serial", sa.String(length=100), nullable=False),
        sa.Column("serial_norm", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("holder_type", sa.String(length=20), nullable=True),
        sa.Column(
            "holder_employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("holder_location", sa.String(length=200), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("complex_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("workplace_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.CheckConstraint(_HOLDER_STATE_CHECK, name="ck_asset_instances_holder_state"),
    )
    op.create_index(
        "uq_asset_instances_serial_norm_active",
        "asset_instances",
        ["serial_norm"],
        unique=True,
        postgresql_where=ACTIVE_WHERE,
    )
    op.create_index("ix_asset_instances_workplace_id", "asset_instances", ["workplace_id"])
    op.create_index("ix_asset_instances_complex_id", "asset_instances", ["complex_id"])
    op.create_index("ix_asset_instances_serial_norm", "asset_instances", ["serial_norm"])
    op.create_index(
        "ix_asset_instances_holder_employee_id", "asset_instances", ["holder_employee_id"]
    )

    op.create_table(
        "asset_histories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("asset_instances.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("from_type", sa.String(length=20), nullable=True),
        sa.Column(
            "from_employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("from_location", sa.String(length=200), nullable=True),
        sa.Column("to_type", sa.String(length=20), nullable=True),
        sa.Column(
            "to_employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("to_location", sa.String(length=200), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "action IN ('created','updated','assigned','returned','retired')",
            name="ck_asset_histories_action",
        ),
    )
    op.create_index("ix_asset_histories_asset_created", "asset_histories", ["asset_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_asset_histories_asset_created", table_name="asset_histories")
    op.drop_table("asset_histories")

    op.drop_index("ix_asset_instances_holder_employee_id", table_name="asset_instances")
    op.drop_index("ix_asset_instances_serial_norm", table_name="asset_instances")
    op.drop_index("ix_asset_instances_complex_id", table_name="asset_instances")
    op.drop_index("ix_asset_instances_workplace_id", table_name="asset_instances")
    op.drop_index("uq_asset_instances_serial_norm_active", table_name="asset_instances")
    op.drop_table("asset_instances")
