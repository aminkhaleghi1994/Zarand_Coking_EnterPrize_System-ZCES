"""auth, rbac, scope and audit tables

Revision ID: 0002_auth_rbac_scope
Revises: 0001_baseline
Create Date: 2026-08-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_auth_rbac_scope"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACTIVE_WHERE = sa.text("deleted_at IS NULL")

scope_level_enum = sa.Enum(
    "global", "complex", "workplace", name="scope_level", native_enum=False,
    create_constraint=True, length=20,
)
refresh_status_enum = sa.Enum(
    "active", "rotated", "revoked", name="refresh_token_status", native_enum=False,
    create_constraint=True, length=20,
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("uq_users_email_active", "users", ["email"], unique=True, postgresql_where=ACTIVE_WHERE)
    op.create_index("uq_users_username_active", "users", ["username"], unique=True, postgresql_where=ACTIVE_WHERE)

    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("uq_roles_name_active", "roles", ["name"], unique=True, postgresql_where=ACTIVE_WHERE)

    op.create_table(
        "permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name_en", sa.String(length=200), nullable=False),
        sa.Column("name_fa", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("uq_permissions_code", "permissions", ["code"], unique=True)

    op.create_table(
        "role_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("uq_role_permissions_role_permission", "role_permissions", ["role_id", "permission_id"], unique=True)

    op.create_table(
        "user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("uq_user_roles_user_role", "user_roles", ["user_id", "role_id"], unique=True)

    op.create_table(
        "scope_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("level", scope_level_enum, nullable=False),
        sa.Column("module", sa.String(length=100), nullable=False),
        sa.Column("resource", sa.String(length=100), nullable=False),
        sa.Column("operation", sa.String(length=100), nullable=False),
        sa.Column("complex_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("workplace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("level IN ('global','complex','workplace')", name="ck_scope_assignments_level"),
    )
    op.create_index("ix_scope_assignments_user_id", "scope_assignments", ["user_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", refresh_status_enum, nullable=False),
        sa.Column("rotated_to_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('active','rotated','revoked')", name="ck_refresh_tokens_status"),
    )
    op.create_index("uq_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])
    op.create_index("ix_refresh_tokens_user_status", "refresh_tokens", ["user_id", "status"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("before_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("after_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("trace_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", [sa.text("created_at DESC")])
    op.create_index("ix_audit_logs_actor_created", "audit_logs", ["actor_user_id", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_actor_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_refresh_tokens_user_status", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
    op.drop_index("uq_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_scope_assignments_user_id", table_name="scope_assignments")
    op.drop_table("scope_assignments")
    op.drop_index("uq_user_roles_user_role", table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_index("uq_role_permissions_role_permission", table_name="role_permissions")
    op.drop_table("role_permissions")
    op.drop_index("uq_permissions_code", table_name="permissions")
    op.drop_table("permissions")
    op.drop_index("uq_roles_name_active", table_name="roles")
    op.drop_table("roles")
    op.drop_index("uq_users_username_active", table_name="users")
    op.drop_index("uq_users_email_active", table_name="users")
    op.drop_table("users")
    sa.Enum(name="refresh_token_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="scope_level").drop(op.get_bind(), checkfirst=True)
