import uuid
from typing import Any

from sqlalchemy import String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.mixins import IDMixin, TimestampMixin
from app.core.database import Base


class AuditLog(IDMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    before_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
