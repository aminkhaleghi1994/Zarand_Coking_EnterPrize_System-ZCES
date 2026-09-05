# Contract: Asset Endpoints (HTTP)

**Base**: `/api/v1/warehouse/assets` behind the BFF
(`/api/warehouse/assets/**` passthrough with cookies + CSRF on mutations).
Standard envelope `{code, message, details, trace_id}`; lists paginate
`{items, page, page_size, total}` (bounded, default 20).

## Authorization model (binding)

- Every endpoint requires the matching `warehouse:asset:*` permission AND
  scope coverage over the asset's workplace anchor (union: workplace →
  complex → global). Anchorless assets (creator without an employee record)
  require global coverage — the Phase-5 request pattern.
- Out-of-scope access answers `AUTHORIZATION_DENIED`, indistinguishable from
  a missing asset.

## Registration & listing

### GET /warehouse/assets?search=&status=&page=&page_size=
- Permission: `warehouse:asset:read`; scope-filtered
- Query: `search` (name/name_fa/serial ILIKE), `status` =
  `available` | `assigned` | `retired` | `all` (default `available`),
  pagination
- 200: `{items: AssetOut[], ...}`

`AssetOut`:
```json
{
  "id": "uuid", "version": 2,
  "name": "Torque wrench", "name_fa": "آچار گشتاور",
  "serial": "TW-2026-0042",
  "description": null,
  "status": "assigned",
  "holder": {
    "type": "employee",
    "employee": {"id": "uuid", "name": "Sara Ahmadi"},
    "location": null
  },
  "created_at": "…"
}
```
(`holder` is `{"type": "available"}`-shaped `null` holder for available
assets; `location` carries the free-text description for location targets.)

### POST /warehouse/assets
- Permission: `warehouse:asset:create`
- Body: `{name, name_fa, serial, description?}`
- 201: `AssetOut` · `ASSET_CREATED` audited (history entry `created`)
- Errors: `VALIDATION_ERROR`, `DUPLICATE_RESOURCE` (serial — details name
  the field)

### GET /warehouse/assets/{id}
- Permission: `warehouse:asset:read` + scope · 200 `AssetOut` ·
  `AUTHORIZATION_DENIED` (no existence leak) / `RESOURCE_NOT_FOUND` for
  global-coverage misses

### PATCH /warehouse/assets/{id}
- Permission: `warehouse:asset:update` + scope
- Body: `{name?, name_fa?, description?, version}` (serial immutable)
- 200: `AssetOut` · `STALE_VERSION` · `DUPLICATE_RESOURCE` impossible
  (serial immutable — service rejects attempts with `VALIDATION_ERROR`) ·
  `ASSET_UPDATED` audited (history entry `updated`)

### POST /warehouse/assets/{id}/retire
- Permission: `warehouse:asset:retire` + scope
- Body: `{"version": n}`
- 200: `AssetOut` (retired) · `BUSINESS_RULE_VIOLATION` while assigned ·
  idempotent on already-retired · `ASSET_RETIRED` audited

## Assignment & return

### POST /warehouse/assets/{id}/assign
- Permission: `warehouse:asset:assign` + scope
- Body: `{"version": n, "target_type": "employee" | "location",
  "employee_id": "uuid"?, "location": "text"?, "note": "optional"}`
- 200: `AssetOut` (assigned) · `ASSET_ASSIGNED` audited (history entry with
  from/to holder)
- Errors: `BUSINESS_RULE_VIOLATION` (already assigned; location text missing
  for a location target), `VALIDATION_ERROR` (unknown/deactivated employee
  for an employee target; employee_id set for a location target),
  `STALE_VERSION`, `AUTHORIZATION_DENIED`

### POST /warehouse/assets/{id}/return
- Permission: `warehouse:asset:return` + scope
- Body: `{"version": n, "note": "optional"}`
- 200: `AssetOut` (available) · `BUSINESS_RULE_VIOLATION` if the asset is
  not assigned · `ASSET_RETURNED` audited

## History

### GET /warehouse/assets/{id}/history?page=&page_size=
- Permission: `warehouse:asset:read` + scope
- 200: `{items: HistoryOut[], ...}` newest first

`HistoryOut`:
```json
{
  "id": "uuid", "action": "assigned",
  "from": {"type": "available"},
  "to": {"type": "employee", "employee": {"id": "uuid", "name": "Sara Ahmadi"}},
  "note": "night shift kit",
  "actor_user_id": "uuid",
  "created_at": "…"
}
```

## BFF passthrough pattern

Route handlers under `frontend/src/app/api/warehouse/assets/**` forward the
`zces_at` cookie + `X-Request-ID`, enforce CSRF on mutations, return the
backend body verbatim, and perform the transparent refresh-and-retry on 401
(existing `proxyToBackend` wrapper).
