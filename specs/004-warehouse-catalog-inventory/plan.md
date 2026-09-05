# Implementation Plan: Warehouse, Item Catalog & Inventory

**Branch**: `feature/004-warehouse-catalog-inventory` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-warehouse-catalog-inventory/spec.md`

## Summary

Deliver the warehouse domain as a new `modules/warehouse` backend module plus
warehouse UI: an item catalog (bilingual name, optional unique SKU code, unit
of measure, minimum threshold) with case/whitespace-normalized duplicate
prevention and a debounced, paginated live search; warehouses anchored to a
workplace with shelves under them (retirement blocked while stock remains);
stock recorded only as placements (shelf × item) whose quantity changes
exclusively through an atomic stock-movement ledger — decrements serialized
with `SELECT … FOR UPDATE`, negative quantities impossible (DB CHECK +
service guard + concurrency tests); low-stock alerts raised/resolved per
placement episode and audited; all queries scope-filtered (warehouse →
workplace anchor), every mutation audited with snapshots, standard envelope +
pagination everywhere, and a tabbed bilingual RTL warehouse console
(catalog / warehouses / stock / low stock). Gate: browser-verified
receive→issue→overdraw flow, duplicate items blocked, alert observed, both
locales RTL-correct, all Phase 1–3 gates stay green.

## Technical Context

**Language/Version**: Python 3.12 (backend venv) · Node 24 / npm 11 (frontend)

**Primary Dependencies**: existing stack only — SQLAlchemy 2.0, Alembic,
Pydantic v2; frontend: TanStack Query + React Hook Form + Zod; **no new
runtime dependencies** (search = plain ILIKE over indexed columns; no pg_trgm,
no Redis, no Celery)

**Storage**: PostgreSQL — 6 new tables (`item_catalog`, `warehouses`, `shelves`,
`inventory_placements`, `stock_movements`, `stock_alerts`) + partial unique
indexes + `quantity >= 0` CHECK; migration
`0004_warehouse_catalog_inventory` (reversible, `down_revision =
0003_org_user_module`)

**Testing**: pytest (unit: normalization, movement math, alert episode logic;
integration on PG: partial indexes, retirement blocking, movement atomicity,
scope filters, seed idempotency; **concurrency test: two sessions racing an
overdraw — exactly one wins**) · eslint/tsc/build · extended smoke test

**Target Platform**: Local Windows dev → single Ubuntu VM; GitHub Actions CI

**Performance Goals**: P95 < 200ms for list/search endpoints at the clarified
scale (~500 active items, thousands of movements); indexed search columns;
server-side pagination only

**Constraints**: browser never touches FastAPI (BFF only); every repository
query carries the scope filter (constitution II); no physical deletes; stock
change + movement + alert evaluation in ONE transaction (constitution III);
`FOR UPDATE` on decrements; no Redis/Celery (alerting is transactional, not
queued — delivery arrives with the notifications phase)

**Scale/Scope**: 6 new tables · ~15 backend endpoints · 5 warehouse
permissions groups (16 permission codes) added to seed · 1 tabbed UI surface
(4 tabs) + live-search combobox · ~55 tasks

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence / Plan |
|---|---|---|
| I. Spec-driven sequential delivery | ✅ Pass | This cycle; gate = browser-verified stock flow, duplicate blocking, alert observed, locales RTL-correct |
| II. Scoped access on every query | ✅ Enabled | Warehouse/shelf/placement/movement/alert repositories take `ScopeContext` and filter via `allowed_units` on `warehouses.workplace_id`; denials never leak existence; catalog is company-wide reference data (read: permission-only; write: permission + ≥1 active warehouse scope) — decision R5 |
| III. Auditability & data integrity | ✅ Pass | UUIDs; soft delete on catalog/warehouses/shelves; partial unique indexes on active rows; placement quantity guarded by `CHECK (quantity >= 0)`; movements + quantity change + alert evaluation in one transaction; `FOR UPDATE` on issues/adjustments; audit with snapshots on all mutations; movements are an immutable ledger (no update/delete paths) |
| IV. Security & secrets discipline | ✅ Pass | No secrets involved; env-only config; validation backend-side; standard masking on audit snapshots |
| V. Bilingual RTL responsive UX | ✅ Pass | New `warehouse.*` namespace in EN/FA; RTL-correct tabbed console; Jalali timestamps for `fa`; Farsi digits via font; skeletons; touch targets ≥44px; reduced-motion respected |
| VI. Modular monolith boundaries | ✅ Pass | New `modules/warehouse` owns its models/repos/services; workplace anchoring resolved via the user module's contracts (workplace lookup by id); warehouse exposes `contracts.py` for Phase 5 fulfillment |
| VII. Standard API contracts | ✅ Pass | Envelope `{code, message, details, trace_id}`; `INSUFFICIENT_STOCK`, `DUPLICATE_RESOURCE`, `BUSINESS_RULE_VIOLATION`, `STALE_VERSION`, `VALIDATION_ERROR`; lists `{items, page, page_size, total}` |
| VIII. Simplicity over speculation | ✅ Pass | No Redis/Celery/queues; no pg_trgm/full-text; no unit conversion; no transfers; single tabbed page; alerts stored, not pushed (notifications later) |

**Post-design re-check**: ✅ Passes — see Complexity Tracking (empty).

## Project Structure

### Documentation (this feature)

```text
specs/004-warehouse-catalog-inventory/
├── plan.md / research.md / data-model.md / quickstart.md / tasks.md
└── contracts/ (warehouse-endpoints.md, warehouse-contract.md)
```

### Source Code (repository root)

```text
backend/app/
├── modules/warehouse/
│   ├── models.py           # ItemCatalog, Warehouse, Shelf, InventoryPlacement,
│   │                       # StockMovement, StockAlert (+ partial unique indexes, CHECK)
│   ├── schemas.py          # ItemIn/Out, WarehouseIn/Out, ShelfIn/Out, PlacementOut,
│   │                       # MovementOut, AlertOut, ReceiveIn, IssueIn, AdjustIn, PageParams reuse
│   ├── repository.py       # scope-filtered queries: items search, warehouses, shelves,
│   │                       # placements, movements, alerts (allowed_units-based filter)
│   ├── service.py          # item_service / warehouse_service / stock_service:
│   │                       # normalization, duplicate + retirement rules, FOR UPDATE
│   │                       # ledger writes, alert episode evaluation, audit writes
│   ├── router.py           # /warehouse/* endpoints (require_operation per op)
│   ├── contracts.py        # get_item, get_placement, apply_movement (Phase 5 fulfillment)
│   └── tests/              # backend/tests/test_warehouse_*.py (flat convention)
├── seeds/seed_dev.py       # + 16 warehouse permission codes, role mapping
└── alembic/versions/0004_warehouse_catalog_inventory.py

frontend/src/
├── app/api/warehouse/**    # BFF passthrough routes (cookie + CSRF on mutations)
├── app/[locale]/(app)/warehouse/page.tsx   # tabbed console (Server Component)
├── features/warehouse/     # WarehouseConsole (tabs), CatalogView, ItemForm,
│                           # ItemSearchCombobox (debounced), WarehouseView, StockView,
│                           # MovementDialogs (receive/issue/adjust), MovementHistory,
│                           # AlertsView
├── lib/client-api.ts       # + warehouseApi + types
├── lib/schemas.ts          # + warehouse Zod schemas
└── messages/{en,fa}.json   # + warehouse.* namespace, nav entry
```

**Structure Decision**: One backend module (requirements §9 module list names
`warehouse` as the owner of catalog/inventory), mirroring the user module's
repository/service/router split with separate service files per aggregate.
Frontend is one route with tabs (the AdminViews pattern) because the four
surfaces share one scope context and one item picker; the live-search combobox
is built once here and reused by Phase 5's request lines.

## Complexity Tracking

> Empty — no constitution violations to justify.
