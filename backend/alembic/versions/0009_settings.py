"""settings

Revision ID: 0009_settings
Revises: 0008_notifications_outbox_sse
Create Date: 2026-09-05

Global typed key/value settings table (fixed code-defined key set; plain
unique on key — settings are never deleted). Fully reversible.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_settings"
down_revision: Union[str, None] = "0008_notifications_outbox_sse"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VALUE_TYPE_SQL = "'boolean','integer','string','json'"


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("value_type", sa.String(length=10), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("description_fa", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"value_type IN ({_VALUE_TYPE_SQL})", name="ck_settings_value_type"
        ),
        sa.UniqueConstraint("key", name="uq_settings_key"),
    )


def downgrade() -> None:
    op.drop_table("settings")
