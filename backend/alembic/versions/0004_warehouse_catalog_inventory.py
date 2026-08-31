"""warehouse catalog inventory

Revision ID: 0004_warehouse_catalog_inventory
Revises: 0003_org_user_module
Create Date: 2026-08-31

Item catalog (normalized-name partial uniques), warehouses (workplace-anchored
with org columns), shelves, inventory placements (quantity >= 0 CHECK), the
append-only stock-movement ledger and low-stock alerts (one active per
placement). Fully reversible.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_warehouse_catalog_inventory"
down_revision: Union[str, None] = "0003_org_user_module"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACTIVE_WHERE = sa.text("deleted_at IS NULL")


def _master_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    ]


def _ledger_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
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
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "item_catalog",
        *_master_columns(),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_fa", sa.String(length=200), nullable=False),
        sa.Column("name_norm", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("code_norm", sa.String(length=50), nullable=True),
        sa.Column("unit", sa.String(length=30), nullable=False),
        sa.Column("min_quantity", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index(
        "uq_item_catalog_name_norm_active",
        "item_catalog",
        ["name_norm"],
        unique=True,
        postgresql_where=ACTIVE_WHERE,
    )
    op.create_index(
        "uq_item_catalog_code_norm_active",
        "item_catalog",
        ["code_norm"],
        unique=True,
        postgresql_where=ACTIVE_WHERE,
    )
    op.create_index("ix_item_catalog_name_norm", "item_catalog", ["name_norm"])

    op.create_table(
        "warehouses",
        *_master_columns(),
        sa.Column(
            "workplace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workplaces.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_fa", sa.String(length=200), nullable=False),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "complex_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("complexes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
    )
    op.create_index(
        "uq_warehouses_code_active",
        "warehouses",
        ["code"],
        unique=True,
        postgresql_where=ACTIVE_WHERE,
    )
    op.create_index("ix_warehouses_workplace_id", "warehouses", ["workplace_id"])
    op.create_index("ix_warehouses_complex_id", "warehouses", ["complex_id"])

    op.create_table(
        "shelves",
        *_master_columns(),
        sa.Column(
            "warehouse_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("name_fa", sa.String(length=200), nullable=True),
    )
    op.create_index(
        "uq_shelves_warehouse_code_active",
        "shelves",
        ["warehouse_id", "code"],
        unique=True,
        postgresql_where=ACTIVE_WHERE,
    )
    op.create_index("ix_shelves_warehouse_id", "shelves", ["warehouse_id"])

    op.create_table(
        "inventory_placements",
        *_ledger_columns(),
        sa.Column(
            "shelf_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("shelves.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("item_catalog.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.CheckConstraint("quantity >= 0", name="ck_inventory_placements_quantity_non_negative"),
    )
    op.create_index(
        "uq_inventory_placements_shelf_item",
        "inventory_placements",
        ["shelf_id", "item_id"],
        unique=True,
    )
    op.create_index("ix_inventory_placements_item_id", "inventory_placements", ["item_id"])

    op.create_table(
        "stock_movements",
        *_ledger_columns(),
        sa.Column(
            "placement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inventory_placements.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("item_catalog.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("movement_type", sa.String(length=20), nullable=False),
        sa.Column("quantity_delta", sa.Numeric(14, 3), nullable=False),
        sa.Column("resulting_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "movement_type IN ('receive','issue','adjust')",
            name="ck_stock_movements_movement_type",
        ),
    )
    op.create_index(
        "ix_stock_movements_placement_created",
        "stock_movements",
        ["placement_id", "created_at"],
    )
    op.create_index("ix_stock_movements_item_created", "stock_movements", ["item_id", "created_at"])

    op.create_table(
        "stock_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
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
        sa.Column(
            "placement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inventory_placements.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("item_catalog.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("quantity_at_alert", sa.Numeric(14, 3), nullable=False),
        sa.Column("threshold_at_alert", sa.Numeric(14, 3), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolve_reason", sa.String(length=50), nullable=True),
    )
    op.create_index(
        "uq_stock_alerts_placement_active",
        "stock_alerts",
        ["placement_id"],
        unique=True,
        postgresql_where=sa.text("resolved_at IS NULL"),
    )
    op.create_index("ix_stock_alerts_item_id", "stock_alerts", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_stock_alerts_item_id", table_name="stock_alerts")
    op.drop_index("uq_stock_alerts_placement_active", table_name="stock_alerts")
    op.drop_table("stock_alerts")

    op.drop_index("ix_stock_movements_item_created", table_name="stock_movements")
    op.drop_index("ix_stock_movements_placement_created", table_name="stock_movements")
    op.drop_table("stock_movements")

    op.drop_index("ix_inventory_placements_item_id", table_name="inventory_placements")
    op.drop_index("uq_inventory_placements_shelf_item", table_name="inventory_placements")
    op.drop_table("inventory_placements")

    op.drop_index("ix_shelves_warehouse_id", table_name="shelves")
    op.drop_index("uq_shelves_warehouse_code_active", table_name="shelves")
    op.drop_table("shelves")

    op.drop_index("ix_warehouses_complex_id", table_name="warehouses")
    op.drop_index("ix_warehouses_workplace_id", table_name="warehouses")
    op.drop_index("uq_warehouses_code_active", table_name="warehouses")
    op.drop_table("warehouses")

    op.drop_index("ix_item_catalog_name_norm", table_name="item_catalog")
    op.drop_index("uq_item_catalog_code_norm_active", table_name="item_catalog")
    op.drop_index("uq_item_catalog_name_norm_active", table_name="item_catalog")
    op.drop_table("item_catalog")
