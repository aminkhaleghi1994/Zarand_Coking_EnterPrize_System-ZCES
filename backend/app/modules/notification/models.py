"""Notification module models: the append-only event outbox and per-recipient
in-app notifications (requirements §20, data-model.md, migration 0008).

Integrity invariants (constitution III):
- outbox rows are written inside the emitting transaction (atomic capture);
- one notification per (outbox event, recipient) — the exactly-once
  guarantee across relay replays (partial unique);
- no physical deletes — terminal failures are statuses, not deletions.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.mixins import IDMixin, TimestampMixin
from app.core.database import Base

# The §20 domain events (single source of truth for CHECKs and the relay).
EVENT_TYPES: tuple[str, ...] = (
    "UserCreated",
    "ItemCatalogCreated",
    "InventoryLowStock",
    "ItemRequestCreated",
    "ItemRequestApproved",
    "ItemRequestRejected",
    "ItemRequestFulfilled",
    "ItemReturned",
    "LoanRequestCreated",
    "LoanRequestActivated",
    "LoanRequestSettled",
    "AssetAssigned",
    "AssetReturned",
)

OUTBOX_STATUSES: tuple[str, ...] = (
    "pending",
    "processing",
    "delivered",
    "failed",
    "skipped",
)

_EVENT_TYPE_SQL = ", ".join(f"'{value}'" for value in EVENT_TYPES)
_OUTBOX_STATUS_SQL = ", ".join(f"'{value}'" for value in OUTBOX_STATUSES)


class EventOutbox(IDMixin, TimestampMixin, Base):
    """Append-only, in-transaction event record (never physically deleted)."""

    __tablename__ = "event_outbox"

    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            f"event_type IN ({_EVENT_TYPE_SQL})", name="ck_event_outbox_event_type"
        ),
        CheckConstraint(
            f"status IN ({_OUTBOX_STATUS_SQL})", name="ck_event_outbox_status"
        ),
        Index(
            "ix_event_outbox_claim",
            "status",
            "created_at",
            postgresql_where=text("status IN ('pending','processing')"),
        ),
        Index("ix_event_outbox_type", "event_type"),
    )


class Notification(IDMixin, TimestampMixin, Base):
    """Per-recipient in-app message; strictly owner-scoped reads."""

    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        "user_id",
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    outbox_event_id: Mapped[uuid.UUID] = mapped_column(
        "outbox_event_id",
        ForeignKey("event_outbox.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    __table_args__ = (
        CheckConstraint(
            f"event_type IN ({_EVENT_TYPE_SQL})", name="ck_notifications_event_type"
        ),
        Index(
            "uq_notifications_event_recipient",
            "outbox_event_id",
            "user_id",
            unique=True,
        ),
        Index(
            "ix_notifications_unread",
            "user_id",
            postgresql_where=text("read_at IS NULL"),
        ),
        Index("ix_notifications_owner_created", "user_id", text("created_at DESC")),
    )
