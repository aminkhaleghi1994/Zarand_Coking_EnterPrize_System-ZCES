"""Warehouse module models: item catalog, warehouses, shelves, placements,
stock-movement ledger and low-stock alerts (data-model.md, migration 0004).

Integrity invariants (constitution III):
- placements can never go negative (CHECK + service-level FOR UPDATE);
- movements are an append-only ledger — no update/delete paths exist;
- at most one active alert per placement (partial unique index).
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.common.mixins import (
    AuditableEntity,
    CreatedByMixin,
    IDMixin,
    TimestampMixin,
    UpdatedByMixin,
)
from app.core.database import Base


class MovementType(enum.StrEnum):
    RECEIVE = "receive"
    ISSUE = "issue"
    ADJUST = "adjust"
    FULFILLMENT = "fulfillment"


class ItemCatalog(AuditableEntity, Base):
    __tablename__ = "item_catalog"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_fa: Mapped[str] = mapped_column(String(200), nullable=False)
    name_norm: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    code_norm: Mapped[str | None] = mapped_column(String(50), nullable=True)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    min_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=Decimal("0")
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "uq_item_catalog_name_norm_active",
            "name_norm",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_item_catalog_code_norm_active",
            "code_norm",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_item_catalog_name_norm", "name_norm"),
    )


class Warehouse(AuditableEntity, Base):
    __tablename__ = "warehouses"

    workplace_id: Mapped[uuid.UUID] = mapped_column(
        "workplace_id",
        ForeignKey("workplaces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_fa: Mapped[str] = mapped_column(String(200), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(
        "company_id", ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    complex_id: Mapped[uuid.UUID] = mapped_column(
        "complex_id", ForeignKey("complexes.id", ondelete="RESTRICT"), nullable=False
    )

    __table_args__ = (
        Index(
            "uq_warehouses_code_active",
            "code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_warehouses_workplace_id", "workplace_id"),
        Index("ix_warehouses_complex_id", "complex_id"),
    )


class Shelf(AuditableEntity, Base):
    __tablename__ = "shelves"

    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        "warehouse_id",
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name_fa: Mapped[str | None] = mapped_column(String(200), nullable=True)

    __table_args__ = (
        Index(
            "uq_shelves_warehouse_code_active",
            "warehouse_id",
            "code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_shelves_warehouse_id", "warehouse_id"),
    )


class InventoryPlacement(IDMixin, TimestampMixin, CreatedByMixin, UpdatedByMixin, Base):
    __tablename__ = "inventory_placements"

    shelf_id: Mapped[uuid.UUID] = mapped_column(
        "shelf_id",
        ForeignKey("shelves.id", ondelete="RESTRICT"),
        nullable=False,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        "item_id",
        ForeignKey("item_catalog.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=Decimal("0"))

    __table_args__ = (
        CheckConstraint(
            "quantity >= 0",
            name="ck_inventory_placements_quantity_non_negative",
        ),
        Index(
            "uq_inventory_placements_shelf_item",
            "shelf_id",
            "item_id",
            unique=True,
        ),
        Index("ix_inventory_placements_item_id", "item_id"),
    )


class StockMovement(IDMixin, TimestampMixin, CreatedByMixin, Base):
    __tablename__ = "stock_movements"

    placement_id: Mapped[uuid.UUID] = mapped_column(
        "placement_id",
        ForeignKey("inventory_placements.id", ondelete="RESTRICT"),
        nullable=False,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        "item_id",
        ForeignKey("item_catalog.id", ondelete="RESTRICT"),
        nullable=False,
    )
    movement_type: Mapped[MovementType] = mapped_column(
        Enum(
            MovementType,
            native_enum=False,
            length=20,
            create_constraint=False,
            values_callable=lambda obj: [member.value for member in obj],
        ),
        nullable=False,
    )
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    resulting_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('receive','issue','adjust','fulfillment')",
            name="ck_stock_movements_movement_type",
        ),
        Index("ix_stock_movements_placement_created", "placement_id", "created_at"),
        Index("ix_stock_movements_item_created", "item_id", "created_at"),
    )


class StockAlert(IDMixin, TimestampMixin, Base):
    __tablename__ = "stock_alerts"

    placement_id: Mapped[uuid.UUID] = mapped_column(
        "placement_id",
        ForeignKey("inventory_placements.id", ondelete="RESTRICT"),
        nullable=False,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        "item_id",
        ForeignKey("item_catalog.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity_at_alert: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    threshold_at_alert: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    resolve_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)

    __table_args__ = (
        Index(
            "uq_stock_alerts_placement_active",
            "placement_id",
            unique=True,
            postgresql_where=text("resolved_at IS NULL"),
        ),
        Index("ix_stock_alerts_item_id", "item_id"),
    )


# --- Item requests (Phase 5, requirements §9.2/§17) ---


class RequestStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FULFILLED = "fulfilled"


class ItemRequest(
    IDMixin,
    TimestampMixin,
    CreatedByMixin,
    UpdatedByMixin,
    Base,
):
    """Immutable flow history — no edit/cancel/delete paths (research R2/R7)."""

    __tablename__ = "item_requests"

    requested_by: Mapped[uuid.UUID] = mapped_column(
        "requested_by",
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    purpose_description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RequestStatus] = mapped_column(
        Enum(
            RequestStatus,
            native_enum=False,
            length=20,
            create_constraint=False,
            values_callable=lambda obj: [member.value for member in obj],
        ),
        nullable=False,
        default=RequestStatus.PENDING,
    )
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    fulfilled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    complex_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    workplace_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected','fulfilled')",
            name="ck_item_requests_status",
        ),
        Index("ix_item_requests_requested_by", "requested_by"),
        Index("ix_item_requests_workplace_id", "workplace_id"),
        Index("ix_item_requests_complex_id", "complex_id"),
        Index("ix_item_requests_status", "status"),
    )


class ItemRequestLine(IDMixin, TimestampMixin, CreatedByMixin, Base):
    __tablename__ = "item_request_lines"

    request_id: Mapped[uuid.UUID] = mapped_column(
        "request_id",
        ForeignKey("item_requests.id", ondelete="RESTRICT"),
        nullable=False,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        "item_id",
        ForeignKey("item_catalog.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_item_request_lines_quantity_positive"),
        Index("uq_item_request_lines_request_item", "request_id", "item_id", unique=True),
        Index("ix_item_request_lines_request_id", "request_id"),
    )


# --- Assets (Phase 6, requirements §9.2/§18) ---


class HolderType(enum.StrEnum):
    EMPLOYEE = "employee"
    LOCATION = "location"


class AssetAction(enum.StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    ASSIGNED = "assigned"
    RETURNED = "returned"
    RETIRED = "retired"


class AssetInstance(
    AuditableEntity,
    Base,
):
    """Master data with a typed current holder; soft-deletable, versioned."""

    __tablename__ = "asset_instances"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_fa: Mapped[str] = mapped_column(String(200), nullable=False)
    serial: Mapped[str] = mapped_column(String(100), nullable=False)
    serial_norm: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    holder_type: Mapped[HolderType | None] = mapped_column(
        Enum(
            HolderType,
            native_enum=False,
            length=20,
            create_constraint=False,
            values_callable=lambda obj: [member.value for member in obj],
        ),
        nullable=True,
    )
    holder_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        "holder_employee_id",
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=True,
    )
    holder_location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    complex_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    workplace_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "(holder_type IS NULL AND holder_employee_id IS NULL"
            " AND holder_location IS NULL)"
            " OR (holder_type = 'employee' AND holder_employee_id IS NOT NULL"
            " AND holder_location IS NULL)"
            " OR (holder_type = 'location' AND holder_employee_id IS NULL"
            " AND holder_location IS NOT NULL)",
            name="ck_asset_instances_holder_state",
        ),
        Index(
            "uq_asset_instances_serial_norm_active",
            "serial_norm",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_asset_instances_workplace_id", "workplace_id"),
        Index("ix_asset_instances_complex_id", "complex_id"),
        Index("ix_asset_instances_serial_norm", "serial_norm"),
        Index("ix_asset_instances_holder_employee_id", "holder_employee_id"),
    )


class AssetHistory(IDMixin, TimestampMixin, CreatedByMixin, Base):
    """Append-only per-asset lifecycle timeline (research R5)."""

    __tablename__ = "asset_histories"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        "asset_id",
        ForeignKey("asset_instances.id", ondelete="RESTRICT"),
        nullable=False,
    )
    action: Mapped[AssetAction] = mapped_column(
        Enum(
            AssetAction,
            native_enum=False,
            length=20,
            create_constraint=False,
            values_callable=lambda obj: [member.value for member in obj],
        ),
        nullable=False,
    )
    from_type: Mapped[HolderType | None] = mapped_column(
        Enum(
            HolderType,
            native_enum=False,
            length=20,
            create_constraint=False,
            values_callable=lambda obj: [member.value for member in obj],
        ),
        nullable=True,
    )
    from_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        "from_employee_id",
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=True,
    )
    from_location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    to_type: Mapped[HolderType | None] = mapped_column(
        Enum(
            HolderType,
            native_enum=False,
            length=20,
            create_constraint=False,
            values_callable=lambda obj: [member.value for member in obj],
        ),
        nullable=True,
    )
    to_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        "to_employee_id",
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=True,
    )
    to_location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "action IN ('created','updated','assigned','returned','retired')",
            name="ck_asset_histories_action",
        ),
        Index("ix_asset_histories_asset_created", "asset_id", "created_at"),
    )
