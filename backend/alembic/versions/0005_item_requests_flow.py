"""item requests flow

Revision ID: 0005_item_requests_flow
Revises: 0004_warehouse_catalog_inventory
Create Date: 2026-08-31

Item requests + lines: immutable flow history (no soft delete), status CHECK,
per-line quantity > 0 CHECK, unique (request, item) lines, workplace-anchored
org columns for scope-filtered visibility. Fully reversible.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_item_requests_flow"
down_revision: Union[str, None] = "0004_warehouse_catalog_inventory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "item_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "requested_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("purpose_description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("complex_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("workplace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected','fulfilled')",
            name="ck_item_requests_status",
        ),
    )
    op.create_index("ix_item_requests_requested_by", "item_requests", ["requested_by"])
    op.create_index("ix_item_requests_workplace_id", "item_requests", ["workplace_id"])
    op.create_index("ix_item_requests_complex_id", "item_requests", ["complex_id"])
    op.create_index("ix_item_requests_status", "item_requests", ["status"])

    op.create_table(
        "item_request_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("item_requests.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("item_catalog.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("quantity > 0", name="ck_item_request_lines_quantity_positive"),
    )
    op.create_index(
        "uq_item_request_lines_request_item",
        "item_request_lines",
        ["request_id", "item_id"],
        unique=True,
    )
    op.create_index("ix_item_request_lines_request_id", "item_request_lines", ["request_id"])


def downgrade() -> None:
    op.drop_index("ix_item_request_lines_request_id", table_name="item_request_lines")
    op.drop_index("uq_item_request_lines_request_item", table_name="item_request_lines")
    op.drop_table("item_request_lines")

    op.drop_index("ix_item_requests_status", table_name="item_requests")
    op.drop_index("ix_item_requests_complex_id", table_name="item_requests")
    op.drop_index("ix_item_requests_workplace_id", table_name="item_requests")
    op.drop_index("ix_item_requests_requested_by", table_name="item_requests")
    op.drop_table("item_requests")
