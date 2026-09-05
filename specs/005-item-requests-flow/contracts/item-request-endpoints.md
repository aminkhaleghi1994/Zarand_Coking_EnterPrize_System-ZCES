# Contract: Item Request Endpoints (HTTP)

**Base**: `/api/v1/warehouse/requests` behind the BFF
(`/api/warehouse/requests/**` passthrough with cookies + CSRF on mutations).
All errors use the standard envelope `{code, message, details, trace_id}`;
lists paginate `{items, page, page_size, total}` (bounded, default 20).

## Authorization model (binding)

- **Self-service** (create, view own requests): active authentication only —
  ownership scope (`requested_by = caller`), the `/auth/me` precedent
  (research R5).
- **Warehouse actor surfaces** (scope-wide list/detail, decisions,
  fulfillment): permission + scope —
  - `warehouse:request:read` — scope-wide list/detail (union coverage over
    the request's workplace anchor)
  - `warehouse:request:decide` — approve/reject
  - `warehouse:request:fulfill` — fulfill
- Out-of-scope detail/decision/fulfillment attempts answer
  `AUTHORIZATION_DENIED` — indistinguishable from a missing request.

## Compose

### POST /warehouse/requests
- Auth: active user (self-service; requester = caller)
- Body:
```json
{
  "purpose_description": "Safety gloves for the night shift",
  "lines": [
    {"item_id": "uuid", "quantity": "4.000", "note": "size L"},
    {"item_id": "uuid", "quantity": "1.500"}
  ]
}
```
- 201: `RequestOut` · `REQUEST_CREATED` audited (with lines snapshot)
- Errors: `VALIDATION_ERROR` (blank purpose, zero lines, quantity ≤ 0 or
  > 3 decimals, duplicate item across lines, unknown/retired item — field
  errors carry the line index)

`RequestOut`:
```json
{
  "id": "uuid", "version": 1,
  "status": "pending",
  "requested_by": "uuid",
  "requested_by_email": "sara@zarandsteel.ir",
  "purpose_description": "Safety gloves for the night shift",
  "decision_note": null, "decided_by": null, "decided_at": null,
  "fulfilled_at": null,
  "lines": [
    {"id": "uuid", "item": {"id": "uuid", "name": "Gloves", "name_fa": "دستکش",
     "code": "GLV-L", "unit": "pair", "min_quantity": "5.000"},
     "quantity": "4.000", "note": "size L"}
  ],
  "created_at": "…"
}
```

## Visibility

### GET /warehouse/requests?status=&page=&page_size=
- Auth: active user — returns `requested_by = caller` **plus**, for holders
  of `warehouse:request:read`, requests anchored inside their scope union
  (research R10)
- Query: `status` = `pending` | `approved` | `rejected` | `fulfilled` | `all`
  (default `all`), pagination; ordered newest-first

### GET /warehouse/requests/{id}
- Auth: requester (own) or `warehouse:request:read` holder with scope coverage
- 200: `RequestOut` · `AUTHORIZATION_DENIED` outside scope (no existence
  leak) · `RESOURCE_NOT_FOUND` for global-coverage misses

## Decisions

### POST /warehouse/requests/{id}/approve · POST /warehouse/requests/{id}/reject
- Permission: `warehouse:request:decide`; scope must cover the request's
  workplace anchor
- Body: `{"version": n, "note": "optional decision note"}`
- 200: `RequestOut` (status `approved` / `rejected`, decision fields filled)
- Errors: `STALE_VERSION` (409, concurrent decision),
  `BUSINESS_RULE_VIOLATION` (422 — request is not pending),
  `AUTHORIZATION_DENIED`
- Audited: `REQUEST_APPROVED` / `REQUEST_REJECTED` (before/after status,
  note, actor)

## Fulfillment

### POST /warehouse/requests/{id}/fulfill
- Permission: `warehouse:request:fulfill`; scope must cover the request AND
  each selected placement
- Body: one placement per line, keyed by line:
```json
{
  "version": 2,
  "lines": [
    {"line_id": "uuid", "placement_id": "uuid"},
    {"line_id": "uuid", "placement_id": "uuid"}
  ]
}
```
- 200: `RequestOut` (status `fulfilled`, `fulfilled_at` set)
- Effect: for every line the selected placement is decremented atomically via
  the Phase-4 contract (`fulfillment` movements, alert evaluation) in one
  transaction with the status change; `REQUEST_FULFILLED` audited with
  per-line before/after quantities
- Errors:
  - `BUSINESS_RULE_VIOLATION` (not approved / already fulfilled; placement
    item mismatch or retired shelf)
  - `INSUFFICIENT_STOCK` (409 — details name the line id, requested and
    available quantities; nothing deducted)
  - `STALE_VERSION` (409), `AUTHORIZATION_DENIED`, `VALIDATION_ERROR`
    (missing/unknown line or placement in the payload)

## BFF passthrough pattern

Route handlers under `frontend/src/app/api/warehouse/requests/**` forward the
`zces_at` cookie + `X-Request-ID`, enforce the CSRF header on mutations,
return the backend body verbatim, and perform the transparent
refresh-and-retry on 401 (existing `proxyToBackend` wrapper).
