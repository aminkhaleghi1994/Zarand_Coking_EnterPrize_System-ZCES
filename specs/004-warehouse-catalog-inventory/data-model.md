# Data Model: Warehouse, Item Catalog & Inventory

**Date**: 2026-08-31 · Companion to [plan.md](./plan.md) · 6 new tables,
migration `0004_warehouse_catalog_inventory`

All entities: UUID PK (`IDMixin`) + timestamps (`TimestampMixin`) + actor
columns (`CreatedByMixin`/`UpdatedByMixin`). Catalog/warehouse/shelf add
`SoftDeleteMixin` + `VersionMixin` (auditable, versioned documents);
placements/movements/alerts are integrity records (no version, no delete —
see per-table notes). Uniqueness on active rows via partial unique indexes
(`WHERE deleted_at IS NULL`). Quantity columns are `NUMERIC(14,3)`
(research R1).

## Entity catalog

### item_catalog
| Column | Type | Rules |
|---|---|---|
| name | text | NOT NULL (English display name) |
| name_fa | text | NOT NULL (Persian display name) |
| name_norm | text | NOT NULL; maintained = `lower(btrim(name))`; **partial unique** on active rows; also the search key |
| code | text | nullable (SKU/part number) |
| code_norm | text | nullable; maintained; **partial unique** on active rows when present |
| unit | text | NOT NULL (e.g. `kg`, `ad`) — one unit per item, no conversion |
| min_quantity | numeric(14,3) | NOT NULL default 0; low-stock threshold |
| description | text | nullable |
| mixins | — | ID, Timestamp, SoftDelete, Version, CreatedBy, UpdatedBy |

Indexes: partial unique (`name_norm`, `code_norm` active rows), `name_norm`
(search). Company-wide reference data — no org columns (research R5).

### warehouses
| Column | Type | Rules |
|---|---|---|
| workplace_id | FK workplaces | NOT NULL; the scope anchor (clarified in spec) |
| code | text | NOT NULL; **partial unique** on active rows |
| name / name_fa | text | NOT NULL |
| company_id / complex_id | uuid | NOT NULL; filled from the workplace's parents on create (OrgScopeMixin) — enables complex-level scope filters without joins to the org tree |
| mixins | — | ID, Timestamp, SoftDelete, Version, CreatedBy, UpdatedBy |

Indexes: partial unique (`code` active rows), `workplace_id` (scope filter).

### shelves
| Column | Type | Rules |
|---|---|---|
| warehouse_id | FK warehouses | NOT NULL; never re-parented |
| code | text | NOT NULL; **partial unique** `(warehouse_id, code)` on active rows |
| name / name_fa | text | nullable (display label) |
| mixins | — | ID, Timestamp, SoftDelete, Version, CreatedBy, UpdatedBy |

### inventory_placements
| Column | Type | Rules |
|---|---|---|
| shelf_id | FK shelves | NOT NULL |
| item_id | FK item_catalog | NOT NULL |
| quantity | numeric(14,3) | NOT NULL default 0; **CHECK (quantity >= 0)** — the DB-level negative guard |
| mixins | — | ID, Timestamp, CreatedBy, UpdatedBy — **no Version, no SoftDelete** (research R4/R6) |

Constraints: **unique `(shelf_id, item_id)`** (plain — placements are never
deleted; emptied placements remain as history anchors). Locking: rows are
`SELECT … FOR UPDATE`-locked for every quantity change (service).

### stock_movements — immutable ledger
| Column | Type | Rules |
|---|---|---|
| placement_id | FK inventory_placements | NOT NULL |
| item_id | FK item_catalog | NOT NULL (denormalized from the placement; invariant) |
| movement_type | text enum | NOT NULL; CHECK in (`receive`, `issue`, `adjust`); `fulfillment` joins in Phase 5 (R12) |
| quantity_delta | numeric(14,3) | NOT NULL; signed (+ receive / − issue / either adjust) |
| resulting_quantity | numeric(14,3) | NOT NULL; placement quantity after this movement |
| reason | text | nullable (free-text reason/reference) |
| mixins | — | ID, Timestamp, CreatedBy only — **no update, no delete, no version** (append-only) |

Indexes: `(placement_id, created_at DESC)` (history), `(item_id, created_at)`
(future item-centric views), `created_at` (audit correlation).

Invariant enforced by tests (SC-003): for every placement,
`quantity == sum(quantity_delta)` over its movements.

### stock_alerts — low-stock episodes
| Column | Type | Rules |
|---|---|---|
| placement_id | FK inventory_placements | NOT NULL |
| item_id | FK item_catalog | NOT NULL (denormalized, invariant) |
| quantity_at_alert | numeric(14,3) | NOT NULL |
| threshold_at_alert | numeric(14,3) | NOT NULL |
| resolved_at | timestamptz | nullable; NULL = active |
| resolve_reason | text | nullable (`recovered` · `placement_retired` · `item_retired`) |
| mixins | — | ID, Timestamp — episodes are immutable once resolved |

Constraint: **partial unique `(placement_id) WHERE resolved_at IS NULL`** —
at most one active alert per placement (FR-017, structural).

## Relationships

- workplaces 1—N warehouses 1—N shelves 1—N inventory_placements
- item_catalog 1—N inventory_placements (a placement is one shelf × one item)
- inventory_placements 1—N stock_movements (the ledger)
- inventory_placements 1—N stock_alerts (episodes)
- item_catalog / warehouses / shelves: soft-deletable documents; a retired
  item or shelf never breaks historical placements/movements (FKs persist)
- No changes to Phase 1–3 tables.

## State transitions

- **item / warehouse / shelf**: active ⇄ retired (`deleted_at`); retired
  rows leave pickers/search but remain FK-referenceable; name/code (and
  warehouse code, shelf code) become reusable; edits are version-guarded;
  retirement of warehouse/shelf blocked while non-zero stock remains (R9).
- **placement**: created implicitly on first receive (`quantity` 0 → q);
  quantity changes only via movements; never negative; never deleted.
- **stock_alert episode**: raised (below threshold, no active alert) →
  active → resolved on recovery (`recovered`) or on shelf/item retirement
  (`placement_retired` / `item_retired`); re-raise only after resolution.
- **movement**: written once, never mutated.

## Audit actions (new)

`ITEM_CREATED` · `ITEM_UPDATED` · `ITEM_RETIRED` ·
`WAREHOUSE_CREATED` · `WAREHOUSE_UPDATED` · `WAREHOUSE_RETIRED` ·
`SHELF_CREATED` · `SHELF_UPDATED` · `SHELF_RETIRED` ·
`STOCK_RECEIVED` · `STOCK_ISSUED` · `STOCK_ADJUSTED` (each with before/after
placement snapshots incl. resulting quantity) ·
`STOCK_ALERT_RAISED` · `STOCK_ALERT_RESOLVED` ·
(existing `EMPLOYEE_*`/`ROLE_*`/`SCOPE_*` actions unchanged)

Masking: no sensitive fields in warehouse snapshots (no masking rules
triggered); reason text stored verbatim (non-sensitive by definition).

## Migration notes (`0004_warehouse_catalog_inventory`)

1. Create `item_catalog`, `warehouses`, `shelves`, `inventory_placements`,
   `stock_movements`, `stock_alerts` (+ all partial unique indexes, CHECK
   constraints, search indexes) — hand-written `op.create_table` in the
   Phase-3 style (`revision = "0004_warehouse_catalog_inventory`,
   `down_revision = "0003_org_user_module"`).
2. Downgrade drops in reverse dependency order
   (stock_alerts → stock_movements → inventory_placements → shelves →
   warehouses → item_catalog); reversible, verified
   upgrade → downgrade → upgrade on local PG before commit.
3. No data backfill (greenfield module); seeds add permissions/roles only.
