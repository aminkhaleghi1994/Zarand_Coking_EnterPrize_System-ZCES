import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column


class IDMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )


class VersionMixin:
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class CreatedByMixin:
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)


class UpdatedByMixin:
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)


class OrgScopeMixin:
    company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    complex_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    workplace_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)


class AuditableEntity(
    IDMixin,
    TimestampMixin,
    SoftDeleteMixin,
    VersionMixin,
    CreatedByMixin,
    UpdatedByMixin,
):
    """Composition for master-data entities (see data-model.md section 1)."""


class ScopedAuditableEntity(AuditableEntity, OrgScopeMixin):
    """Composition for master-data entities that carry hierarchical scope columns."""


__all__ = [
    "AuditableEntity",
    "CreatedByMixin",
    "IDMixin",
    "OrgScopeMixin",
    "ScopedAuditableEntity",
    "SoftDeleteMixin",
    "TimestampMixin",
    "UpdatedByMixin",
    "VersionMixin",
]
