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
    Numeric,
    String,
    Text,
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


class MovementType(str, enum.Enum):
    RECEIVE = "receive"
    ISSUE = "issue"
    ADJUST = "adjust"


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
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=Decimal("0")
    )

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
            create_constraint=True,
            values_callable=lambda obj: [member.value for member in obj],
        ),
        nullable=False,
    )
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    resulting_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
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
