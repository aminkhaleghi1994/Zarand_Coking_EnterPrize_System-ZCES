"""notifications + event outbox

Revision ID: 0008_notifications_outbox_sse
Revises: 0007_loan_module
Create Date: 2026-09-01

EventOutbox (in-transaction capture, claim index, bounded-retry statuses)
and per-recipient Notifications (exactly-once partial unique, unread and
list indexes). Fully reversible.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_notifications_outbox_sse"
down_revision: Union[str, None] = "0007_loan_module"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_EVENT_TYPES = (
    "UserCreated", "ItemCatalogCreated", "InventoryLowStock",
    "ItemRequestCreated", "ItemRequestApproved", "ItemRequestRejected",
    "ItemRequestFulfilled", "ItemReturned", "LoanRequestCreated",
    "LoanRequestActivated", "LoanRequestSettled", "AssetAssigned",
    "AssetReturned",
)
_EVENT_TYPE_SQL = ", ".join(f"'{value}'" for value in _EVENT_TYPES)
_STATUS_SQL = "'pending','processing','delivered','failed','skipped'"


def upgrade() -> None:
    op.create_table(
        "event_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            f"event_type IN ({_EVENT_TYPE_SQL})", name="ck_event_outbox_event_type"
        ),
        sa.CheckConstraint(f"status IN ({_STATUS_SQL})", name="ck_event_outbox_status"),
    )
    op.create_index(
        "ix_event_outbox_claim",
        "event_outbox",
        ["status", "created_at"],
        postgresql_where=sa.text("status IN ('pending','processing')"),
    )
    op.create_index("ix_event_outbox_type", "event_outbox", ["event_type"])

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "outbox_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("event_outbox.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            f"event_type IN ({_EVENT_TYPE_SQL})", name="ck_notifications_event_type"
        ),
    )
    op.create_index(
        "uq_notifications_event_recipient",
        "notifications",
        ["outbox_event_id", "user_id"],
        unique=True,
    )
    op.create_index(
        "ix_notifications_unread",
        "notifications",
        ["user_id"],
        postgresql_where=sa.text("read_at IS NULL"),
    )
    op.create_index(
        "ix_notifications_owner_created", "notifications", ["user_id", sa.text("created_at DESC")]
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_owner_created", table_name="notifications")
    op.drop_index("ix_notifications_unread", table_name="notifications")
    op.drop_index("uq_notifications_event_recipient", table_name="notifications")
    op.drop_table("notifications")

    op.drop_index("ix_event_outbox_type", table_name="event_outbox")
    op.drop_index("ix_event_outbox_claim", table_name="event_outbox")
    op.drop_table("event_outbox")
