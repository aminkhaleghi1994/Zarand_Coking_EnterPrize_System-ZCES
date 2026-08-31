# Contract: Warehouse Endpoints (HTTP)

**Base**: `/api/v1/warehouse` behind the BFF (`/api/warehouse/...` passthrough
with cookies + CSRF on mutations). All errors use the standard envelope
`{code, message, details, trace_id}`. All lists paginate
`{items, page, page_size, total}` (bounded `page_size ≤ 100`, default 20).

Permission AND scope required on every endpoint (implicit deny). Scope filter
applies to returned rows, never just the endpoint. Quantities are decimals
with up to 3 fractional digits, always in the item's unit (R1/R5).

## Scope model (binding)

- **Physical domain** (warehouses, shelves, placements, movements, alerts):
  rows are filtered by the warehouse's `workplace_id` through
  `allowed_units(context, operation)` — Global → all; Complex → warehouses of
  the assigned complex's workplaces; Workplace → own warehouses only.
- **Catalog** (items): company-wide reference data — read requires only the
  permission; writes require the permission **and** ≥1 active scope
  assignment in the warehouse domain (research R5).
- Detail/mutation endpoints outside the caller's scope answer
  `AUTHORIZATION_DENIED` — indistinguishable from a missing resource (no
  existence leak, FR-020).

## Item catalog

### GET /warehouse/items?search=&page=&page_size=
- Permission: `warehouse:item:read` (no scope filter — company-wide)
- Query: `search` (matches `name_norm` / `name_fa` / `code_norm`, ILIKE),
  pagination
- 200: `{items: ItemOut[], page, page_size, total}` — active items only,
  ordered by `name_norm`

`ItemOut`:
```json
{
  "id": "uuid", "version": 3,
  "name": "Ball bearing 6204", "name_fa": "بلبرینگ ۶۲۰۴",
  "code": "BB-6204", "unit": "ad",
  "min_quantity": "10.000", "description": null,
  "is_active": true
}
```
(`min_quantity` serialized as a string with 3 decimals — decimal-safe JSON.)

### POST /warehouse/items
- Permission: `warehouse:item:create` + ≥1 active warehouse scope
- Body: `{name, name_fa, code?, unit, min_quantity, description?}`
- 201: `ItemOut` · `ITEM_CREATED` audited
- Errors: `VALIDATION_ERROR` (blank name/unit, min_quantity < 0),
  `DUPLICATE_RESOURCE` (details `field: "name" | "code"`), `AUTHORIZATION_DENIED`

### GET /warehouse/items/{id}
- Permission: `warehouse:item:read` · 200: `ItemOut` · `RESOURCE_NOT_FOUND`

### PATCH /warehouse/items/{id}
- Permission: `warehouse:item:update` + ≥1 active warehouse scope
- Body: editable fields (`name`, `name_fa`, `code`, `unit`, `min_quantity`,
  `description`) + `version` (required)
- 200: `ItemOut` · `STALE_VERSION` on version mismatch ·
  `DUPLICATE_RESOURCE` · `ITEM_UPDATED` audited

### POST /warehouse/items/{id}/retire
- Permission: `warehouse:item:retire` + ≥1 active warehouse scope
- Body: `{"version": n}`
- 200: `ItemOut` (`is_active: false`) · idempotent on retired items ·
  `ITEM_RETIRED` audited; active alerts on the item's placements resolved
  (`item_retired`, audited)

## Warehouses & shelves

### GET /warehouse/warehouses?workplace_id=&page=&page_size=
- Permission: `warehouse:warehouse:read`; scope-filtered
- 200: `{items: WarehouseOut[], ...}` — active only

`WarehouseOut`:
```json
{
  "id": "uuid", "version": 1,
  "workplace_id": "uuid",
  "workplace": {"id": "uuid", "code": "CP1", "name": "Coke Plant 1", "name_fa": "کوک‌سازی ۱"},
  "code": "WH-CP1-MAIN", "name": "Main warehouse", "name_fa": "انبار اصلی",
  "is_active": true
}
```

### POST /warehouse/warehouses
- Permission: `warehouse:warehouse:create`; scope must cover the target
  workplace (`can(context, op, ScopeTarget(...))`)
- Body: `{workplace_id, code, name, name_fa}`
- 201: `WarehouseOut` · `WAREHOUSE_CREATED` audited ·
  Errors: `VALIDATION_ERROR`, `DUPLICATE_RESOURCE` (code),
  `AUTHORIZATION_DENIED` (workplace out of scope), `RESOURCE_NOT_FOUND`
  (workplace)

### PATCH /warehouse/warehouses/{id} · POST /warehouse/warehouses/{id}/retire
- Permissions: `warehouse:warehouse:update` / `warehouse:warehouse:retire`;
  scope must cover the warehouse · `version` required
- Retire: `BUSINESS_RULE_VIOLATION` while any placement under it holds
  non-zero stock (details list blocking placements); audited

### GET/POST /warehouse/warehouses/{id}/shelves · PATCH/retire /warehouse/shelves/{id}
- Permissions: `warehouse:shelf:read` / `warehouse:shelf:create` /
  `warehouse:shelf:update` / `warehouse:shelf:retire`; scope must cover the
  parent warehouse
- `ShelfOut`: `{id, version, warehouse_id, code, name, name_fa, is_active}`
- Shelf retire: same blocking rule per shelf

## Placements & stock

### GET /warehouse/placements?warehouse_id=&item_id=&search=&page=&page_size=
- Permission: `warehouse:stock:read`; scope-filtered
- Query: optional `warehouse_id`, `item_id`, `search` (item name/code);
  **placements with quantity > 0 only** (empty placements are ledger
  anchors, not working stock)
- 200: `{items: PlacementOut[], ...}`

`PlacementOut`:
```json
{
  "id": "uuid",
  "item": {"id": "uuid", "name": "Ball bearing 6204", "name_fa": "بلبرینگ ۶۲۰۴",
           "code": "BB-6204", "unit": "ad", "min_quantity": "10.000"},
  "shelf": {"id": "uuid", "code": "A-01", "name": "Rack A"},
  "warehouse": {"id": "uuid", "code": "WH-CP1-MAIN", "name": "Main warehouse"},
  "quantity": "42.000",
  "below_min_threshold": false
}
```

### POST /warehouse/placements/receive
- Permission: `warehouse:stock:receive`; scope must cover the shelf's warehouse
- Body: `{item_id, shelf_id, quantity: "50.000", reason?}`
- Effect: placement created (first receive) or increased; exactly one
  `receive` movement in the same transaction; `STOCK_RECEIVED` audited
- 200: `PlacementOut` · Errors: `VALIDATION_ERROR` (quantity ≤ 0, >3
  decimals, retired item/shelf), `AUTHORIZATION_DENIED`, `RESOURCE_NOT_FOUND`

### POST /warehouse/placements/issue
- Permission: `warehouse:stock:issue`; scope must cover the placement's warehouse
- Body: `{placement_id, quantity, reason?}`
- Effect: `SELECT … FOR UPDATE` on the placement; quantity decreased;
  `issue` movement in the same transaction; `STOCK_ISSUED` audited
- 200: `PlacementOut` · Errors: `INSUFFICIENT_STOCK` (409, details carry
  `available`), `VALIDATION_ERROR`, `AUTHORIZATION_DENIED`

### POST /warehouse/placements/adjust
- Permission: `warehouse:stock:adjust` (separate from receive/issue — Q1);
  scope must cover the placement's warehouse
- Body: `{placement_id, quantity: "38.500", reason}` — the **corrected
  absolute** quantity (physical recount), not a delta
- Effect: delta computed server-side; `adjust` movement in the same
  transaction; `STOCK_ADJUSTED` audited
- 200: `PlacementOut` · Errors: `VALIDATION_ERROR` (target < 0, target ==
  current, quantity ≤ 0 input forms), `AUTHORIZATION_DENIED`

### GET /warehouse/placements/{id}/movements?page=&page_size=
- Permission: `warehouse:stock:read`; scope-filtered
- 200: `{items: MovementOut[], ...}` newest first

`MovementOut`:
```json
{
  "id": "uuid", "movement_type": "issue",
  "quantity_delta": "-5.000", "resulting_quantity": "37.000",
  "reason": "Work order 1404-221", "actor_user_id": "uuid",
  "created_at": "2026-08-31T10:15:00Z"
}
```

## Low-stock alerts

### GET /warehouse/alerts?active=true&page=&page_size=
- Permission: `warehouse:alert:read`; scope-filtered
- Query: `active` = `true` (default) | `false` | `all`
- 200: `{items: AlertOut[], ...}`

`AlertOut`:
```json
{
  "id": "uuid", "placement_id": "uuid",
  "item": {"id": "uuid", "name": "Ball bearing 6204", "unit": "ad"},
  "shelf": {"id": "uuid", "code": "A-01"},
  "warehouse": {"id": "uuid", "code": "WH-CP1-MAIN"},
  "quantity_at_alert": "8.000", "threshold_at_alert": "10.000",
  "current_quantity": "8.000", "raised_at": "…", "resolved_at": null
}
```

## BFF passthrough pattern

Each endpoint gets a route handler under `frontend/src/app/api/warehouse/**`
that forwards the `zces_at` cookie + `X-Request-ID`, enforces the CSRF header
on mutations, returns the backend body verbatim (envelope preserved) with the
backend status code, and performs the transparent-refresh-and-retry on 401
(existing `proxyToBackend` wrapper).
