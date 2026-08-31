import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.common.mixins import (
    CreatedByMixin,
    IDMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UpdatedByMixin,
    VersionMixin,
)
from app.core.database import Base


class RefreshTokenStatus(enum.StrEnum):
    ACTIVE = "active"
    ROTATED = "rotated"
    REVOKED = "revoked"


class ScopeLevel(enum.StrEnum):
    GLOBAL = "global"
    COMPLEX = "complex"
    WORKPLACE = "workplace"


class User(
    IDMixin,
    TimestampMixin,
    SoftDeleteMixin,
    VersionMixin,
    CreatedByMixin,
    UpdatedByMixin,
    Base,
):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index(
            "uq_users_email_active",
            "email",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_users_username_active",
            "username",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )


class Role(
    IDMixin,
    TimestampMixin,
    SoftDeleteMixin,
    VersionMixin,
    CreatedByMixin,
    UpdatedByMixin,
    Base,
):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "uq_roles_name_active",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )


class Permission(IDMixin, TimestampMixin, CreatedByMixin, UpdatedByMixin, Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    name_fa: Mapped[str] = mapped_column(String(200), nullable=False)


class RolePermission(IDMixin, TimestampMixin, Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        Index(
            "uq_role_permissions_role_permission",
            "role_id",
            "permission_id",
            unique=True,
        ),
    )


class UserRole(IDMixin, TimestampMixin, Base):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (Index("uq_user_roles_user_role", "user_id", "role_id", unique=True),)


class ScopeAssignment(IDMixin, TimestampMixin, Base):
    __tablename__ = "scope_assignments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    level: Mapped[ScopeLevel] = mapped_column(
        Enum(
            ScopeLevel,
            native_enum=False,
            length=20,
            create_constraint=True,
            values_callable=lambda obj: [member.value for member in obj],
        ),
        nullable=False,
    )
    module: Mapped[str] = mapped_column(String(100), nullable=False)
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    complex_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    workplace_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    __table_args__ = (Index("ix_scope_assignments_user_id", "user_id"),)


class RefreshToken(IDMixin, TimestampMixin, Base):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[RefreshTokenStatus] = mapped_column(
        Enum(
            RefreshTokenStatus,
            native_enum=False,
            length=20,
            create_constraint=True,
            values_callable=lambda obj: [member.value for member in obj],
        ),
        nullable=False,
        default=RefreshTokenStatus.ACTIVE,
    )
    rotated_to_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(256), nullable=True)

    __table_args__ = (
        Index("ix_refresh_tokens_family_id", "family_id"),
        Index("ix_refresh_tokens_user_status", "user_id", "status"),
    )
