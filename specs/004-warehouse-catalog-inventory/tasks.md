# Tasks: Warehouse, Item Catalog & Inventory

**Input**: Design documents from `/specs/004-warehouse-catalog-inventory/`

**Prerequisites**: plan.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: REQUIRED per task (constitution: tests are part of each task; write
before implementation where practical; PG integration + concurrency per
research R14).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable · **[Story]**: US1–US5; FND = foundational
- FR/SC references map to spec.md; R# to research.md

---

## Phase 1: Setup

- [x] T001 [FND] Permission seed: append the 16 warehouse codes to `BASE_PERMISSIONS` in `backend/app/seeds/seed_dev.py` (`warehouse:item:create/read/update/retire`, `warehouse:warehouse:create/read/update/retire`, `warehouse:shelf:create/read/update/retire`, `warehouse:stock:receive/issue/adjust/read`, `warehouse:alert:read`, bilingual names); map roles — `WarehouseKeeper`: item create/read/update/retire, warehouse/shelf read, shelf create/update/retire, stock receive/issue/read, alert read; `WarehouseApprover`: read-only set; `tests/test_seed.py` additions: exact catalog growth, re-run idempotency, role mappings (FR-019, FR-022, research R10)
- [x] T002 [P] [FND] `backend/app/modules/warehouse/schemas.py`: `ItemCreateIn/ItemUpdateIn/ItemOut` (name, name_fa, code?, unit, min_quantity, description?, version), `WarehouseCreateIn/WarehouseUpdateIn/WarehouseOut`, `ShelfCreateIn/ShelfUpdateIn/ShelfOut`, `PlacementOut` (nested item/shelf/warehouse, `below_min_threshold`), `ReceiveIn/IssueIn/AdjustIn`, `MovementOut`, `AlertOut`, reuse `PageParams`; validators: quantities ≥ 0 with ≤3 decimals, quantity strings serialized with exactly 3 decimals, `version` required on updates/retire; `backend/tests/test_warehouse_schemas.py`: valid/invalid fixtures, decimal rounding/serialization, per-field errors (FR-001, FR-012, contracts/warehouse-endpoints.md shapes)

## Phase 2: Foundational — models & migration (blocking)

- [x] T003 [FND] `backend/app/modules/warehouse/models.py`: `ItemCatalog` (name/name_fa + maintained `name_norm`/`code_norm`, partial unique actives, unit, min_quantity Numeric(14,3)), `Warehouse` (workplace_id FK + org columns, partial unique code), `Shelf` (warehouse_id FK, partial unique `(warehouse_id, code)`), `InventoryPlacement` (shelf×item unique, quantity CHECK ≥ 0, no version/soft-delete), `StockMovement` (immutable ledger, movement_type check-enum, signed delta, resulting_quantity), `StockAlert` (partial unique `(placement_id) WHERE resolved_at IS NULL`) per data-model.md; alembic `backend/alembic/versions/0004_warehouse_catalog_inventory.py` (`down_revision="0003_org_user_module"`); verify `upgrade head → downgrade -1 → upgrade head` on local PG (data-model migration notes, research R1/R2/R4/R6/R7/R12)
- [x] T004 [P] [FND] `backend/app/modules/user/contracts.py`: add `get_workplace_with_parents(session, workplace_id)` returning workplace + parent complex/company ids (or None); `backend/tests/test_user_contracts.py`: found / unknown / deactivated-still-returned (contracts/warehouse-contract.md inbound dependency)

**Checkpoint**: migration reversible; permissions seeded idempotently; schemas validated.

## Phase 3: US1 — Item catalog with duplicate prevention and live search (P1) 🎯 MVP

**Goal**: items defined once, duplicates structurally impossible, debounced
paginated live search.

**Independent Test**: create item → appears in search → duplicate name/code
(case/whitespace variant) rejected → retire → name/code reusable.

- [x] T005 [US1] `repository.py` item queries: `search_items(session, params, search)` (ILIKE over `name_norm`/`name_fa`/`code_norm`, active only, ordered by `name_norm`), `get_item`, `get_item_by_name_norm`, `get_item_by_code_norm`; `backend/tests/test_warehouse_repository.py` (integration, PG): search modes, pagination envelope, active-only (FR-002, FR-003, research R3)
- [x] T006 [US1] `service.py` item_service: `create_item` (normalize name/code → `name_norm`/`code_norm`, IntegrityError → `DUPLICATE_RESOURCE` naming `name|code`, audit `ITEM_CREATED`), `update_item` (version guard → `STALE_VERSION`, renormalize, re-check duplicates, audit `ITEM_UPDATED`), `retire_item` (idempotent, audit `ITEM_RETIRED`); write ops require permission + ≥1 active warehouse scope (research R5); `backend/tests/test_warehouse_catalog.py`: case/whitespace duplicates on name and code, reuse after retire, stale version, audit snapshot shape, scope-any gate (FR-001, FR-002, FR-004, FR-005, SC-001)
- [x] T007 [US1] `router.py`: `GET/POST /warehouse/items`, `GET/PATCH /warehouse/items/{id}`, `POST /warehouse/items/{id}/retire` per contracts (require_operation per code; `ItemOut` with 3-decimal strings); `backend/tests/test_warehouse_catalog.py` endpoint additions: 201 shape, duplicates 409 field-specific, search query, STALE_VERSION 409, roleless 403 (FR-001..FR-005, FR-020)
- [x] T008 [P] [US1] BFF: `frontend/src/app/api/warehouse/items/route.ts` (GET, POST+CSRF), `items/[id]/route.ts` (GET, PATCH), `items/[id]/retire/route.ts` (POST) via `proxyToBackend`; `lib/client-api.ts` `warehouseApi.items.*` + types; `lib/schemas.ts` item Zod schemas (i18n message keys); `messages/{en,fa}.json` `warehouse.catalog.*` (FR-001..FR-003, constitution V)
- [x] T009 [US1] UI shell + catalog: `frontend/src/app/[locale]/(app)/warehouse/page.tsx` (Server Component, `setRequestLocale`, eyebrow/title/description) + `features/warehouse/WarehouseConsole.tsx` (tabs Catalog/Warehouses/Stock/Low stock — AdminViews pattern) + `features/warehouse/CatalogView.tsx` (server-paginated table, debounced search input 300ms, unit + threshold columns) + `features/warehouse/ItemForm.tsx` (create/edit dialog, Zod mirror, inline duplicate field errors naming name vs code, version hidden field, retire confirm); `nav-items.ts` + `nav.warehouse` label en/fa; skeletons + reduced-motion (FR-003, FR-004, SC-001, SC-002, constitution V)

**Checkpoint**: catalog CRUD + live search usable in the browser; duplicates
impossible (verified by tests and manually).

## Phase 4: US2 — Warehouses and shelves defined per site (P1)

**Goal**: physical structure exists, scope-anchored to workplaces, retirement
never orphans stock.

**Independent Test**: create warehouse + shelf → retire blocked while stock
remains → succeeds at zero; lower-scope actor sees none of it.

- [x] T010 [US2] `repository.py` warehouse/shelf queries: `list_warehouses(scope_ctx, params, workplace_id?)` (scope filter on `workplace_id` via `allowed_units` — `_employee_scope_filter` pattern), `get_warehouse_in_scope`, `list_shelves(scope_ctx, warehouse_id, params)`, `get_shelf_in_scope`; active-only everywhere; `backend/tests/test_warehouse_repository.py` additions: workplace/complex/global unions, cross-scope denial without existence leak, deactivated rows excluded (FR-006, FR-019, research R5)
- [x] T011 [US2] `service.py` warehouse_service: `create_warehouse` (validate workplace via user contract `get_workplace_with_parents`, fill org columns, code duplicate → `DUPLICATE_RESOURCE`, `WAREHOUSE_CREATED` audit), `update_warehouse` (version guard), `retire_warehouse`/`retire_shelf` (blocked with `BUSINESS_RULE_VIOLATION` naming blocking placements while non-zero stock — locking read; allowed at zero; resolves affected alerts), shelf create/update/retire (code unique per warehouse); `backend/tests/test_warehouse_catalog.py`/new `test_warehouse_structure.py`: anchoring correctness, duplicates, blocked retirement shelf+warehouse, retire at zero, stale version, audits (FR-006..FR-009, FR-008, SC-006, research R9)
- [x] T012 [US2] `router.py`: `GET/POST /warehouse/warehouses`, `PATCH/retire /warehouse/warehouses/{id}`, `GET/POST /warehouse/warehouses/{id}/shelves`, `PATCH/retire /warehouse/shelves/{id}` per contracts (scope target checks via `can(context, op, ScopeTarget)`); endpoint tests: 201, 409 duplicate code, 422 blocked retirement with placement details, 403 outside scope, roleless 403 (FR-006..FR-009, FR-019, FR-020)
- [x] T013 [P] [US2] BFF: `api/warehouse/warehouses/route.ts`, `warehouses/[id]/route.ts` (PATCH), `warehouses/[id]/retire/route.ts`, `warehouses/[id]/shelves/route.ts`, `shelves/[id]/route.ts` (PATCH), `shelves/[id]/retire/route.ts`; `warehouseApi.warehouses/shelves`; `messages` `warehouse.warehouses.*` (FR-006..FR-008)
- [x] T014 [US2] UI `features/warehouse/WarehouseView.tsx`: scope-filtered warehouse table (workplace column), create/edit dialogs (workplace picker from existing org endpoints, grouped by complex), shelves management per warehouse (inline list + add/edit/retire), blocked-retirement error surfaced with placement details, confirm dialogs; RTL/responsive per constitution V (FR-006..FR-008, SC-006)

**Checkpoint**: warehouses/shelves manageable in the browser; retirement
blocking observable; scope filtering verified with a second profile.

## Phase 5: US3 — Stock lives at shelf level and only moves through movements (P1)

**Goal**: placements as the only stock home; atomic movement ledger; row-locked
decrements; overdraw impossible; history per placement.

**Independent Test**: receive → issue → history consistent → overdraw rejected
unchanged → two concurrent overdrawing issues: exactly one wins.

- [x] T015 [US3] `repository.py` placement/movement queries: `list_placements(scope_ctx, params, warehouse_id?, item_id?, search?, include_empty?)` (joins item/shelf/warehouse, quantity > 0 unless `include_empty=true` — keeps emptied placements' history reachable per the retirement edge case, `below_min_threshold` computed), `get_placement_in_scope` (with `with_for_update()` variant `lock_placement`), `create_placement`, `record_movement` (append-only), `list_movements(placement_id, params)` newest first; `backend/tests/test_warehouse_repository.py` additions: scope filters, filters/search, include-empty toggle, envelope, ordering (FR-010, FR-014, research R4/R6)
- [x] T016 [US3] `service.py` stock_service.receive: validate item+shelf active, shelf's warehouse in scope (`can` with ScopeTarget), round to 3 decimals, lock-and-upsert placement, quantity += q, movement row, audit `STOCK_RECEIVED` (before/after snapshots, critical) — all in one transaction; `backend/tests/test_warehouse_stock.py`: happy path, implicit placement creation, retired item/shelf rejection, rollback leaves nothing (FR-010, FR-011, FR-012, FR-015)
- [x] T017 [US3] `service.py` stock_service.issue: lock placement (`FOR UPDATE`), authoritative quantity re-read, `quantity - q < 0` → `AppError(INSUFFICIENT_STOCK, 409, details.available)`; movement + `STOCK_ISSUED` audit in same transaction; tests: exact-quantity issue, overdraw rejected with quantity and ledger unchanged, failure injection mid-transaction (FR-011, FR-013, SC-004, research R4/R11)
- [x] T018 [US3] `service.py` stock_service.adjust: absolute corrected quantity (clarify Q3 of 004: one unit), target < 0 or delta == 0 → `VALIDATION_ERROR`, delta computed server-side, movement + `STOCK_ADJUSTED` audit; separate `warehouse:stock:adjust` permission enforced (receive/issue holders without it are denied); tests: recount semantics, zero-delta/negative rejections, permission split denial (FR-012, FR-022, research R8)
- [x] T019 [US3] `router.py`: `GET /warehouse/placements`, `POST /warehouse/placements/receive|issue|adjust`, `GET /warehouse/placements/{id}/movements` per contracts; endpoint tests: per-operation permission gates (keeper with receive+issue denied adjust 403), scope denial, envelope shapes, decimal serialization (FR-013, FR-014, FR-019, FR-022)
- [x] T020 [US3] `backend/tests/test_warehouse_concurrency.py` (PG, `requires_db`): N=8 threads × separate sessions racing issues of the same placement that together exceed stock — assert exactly the feasible number succeed, others get `INSUFFICIENT_STOCK`, final `quantity >= 0`, `sum(quantity_delta) == final quantity` (SC-004, research R14)
- [x] T021 [P] [US3] UI `features/warehouse/ItemSearchCombobox.tsx`: debounced 300ms live search against `warehouseApi.items.search`, paginated dropdown with keyboard navigation + aria-combobox semantics, loading state, clear selection; consumed later by Phase-5 request lines (FR-003, SC-002, requirements §6 "جستجوی زنده کالا هنگام ثبت")
- [x] T022 [P] [US3] BFF: `api/warehouse/placements/route.ts` (GET), `placements/receive|issue|adjust/route.ts` (POST+CSRF), `placements/[id]/movements/route.ts` (GET); `warehouseApi.stock.*`; `messages` `warehouse.stock.*` (FR-010..FR-014)
- [x] T023 [US3] UI `features/warehouse/StockView.tsx`: placement table (item, shelf, warehouse, quantity with unit, low-stock hint; desktop table → cards <768px), include-empty toggle (history reachability for emptied placements), Receive dialog (ItemSearchCombobox + shelf picker + quantity + reason), Issue dialog (placement picker + quantity + reason), Adjust dialog (absolute counted quantity + reason), `INSUFFICIENT_STOCK` error surfaced inline naming available quantity; skeletons (FR-010, FR-013, FR-014, SC-002, constitution V)
- [x] T024 [US3] UI `features/warehouse/MovementHistory.tsx`: per-placement history dialog (newest first, type chips, signed delta, resulting quantity, reason, actor, Jalali timestamp in `fa` with Farsi digits), paginated; entry point from StockView rows (FR-014, SC-003, constitution V)

**Checkpoint**: full receive→issue→adjust→history loop in the browser;
overdraw rejected; concurrent race decided by tests (SC-004).

## Phase 6: US4 — Low-stock alerts (P2)

**Goal**: alerts raised/resolved per placement episode, audited, visible.

**Independent Test**: drop below threshold → one alert; stay below → no
duplicate; recover → resolved; drop again → new alert; retirement resolves.

- [x] T025 [US4] `service.py` alert helpers: `evaluate_alert(session, placement, item, resulting_quantity)` (raise if `resulting < min_quantity` and no active alert — partial unique index as backstop; resolve on recovery with reason `recovered`) and `resolve_alerts_for_retirement(session, shelf_id | item_id, reason)`; audit `STOCK_ALERT_RAISED`/`STOCK_ALERT_RESOLVED` (critical) in the caller's transaction; `backend/tests/test_warehouse_alerts.py`: raise, no-duplicate-while-below, resolve+re-raise episode, retirement resolution reasons, race crossing threshold twice → single alert (FR-016, FR-017, SC-005, research R7)
- [x] T026 [US4] Wire evaluation into stock_service receive/issue/adjust (call `evaluate_alert` with resulting quantity before commit) and into warehouse_service shelf/item retirement (resolve with retirement reasons); `test_warehouse_stock.py` additions: alert state transitions following each movement type (FR-017, SC-005)
- [x] T027 [US4] `repository.py` alert queries + `router.py`: `GET /warehouse/alerts?active=true|false|all` (scope-filtered join to warehouse, item/shelf/warehouse embedded, current quantity); endpoint tests: active default, scope filtering, roleless 403 (FR-018, FR-019, SC-006)
- [x] T028 [P] [US4] BFF: `api/warehouse/alerts/route.ts` (GET); `warehouseApi.alerts`; `messages` `warehouse.alerts.*` (FR-018)
- [x] T029 [US4] UI `features/warehouse/AlertsView.tsx`: active-alerts table (item, shelf, warehouse, current quantity vs threshold, raised-at Jalali/`fa`), active/all filter, empty state with guidance; responsive + RTL (FR-018, SC-005, constitution V)

**Checkpoint**: alert lifecycle observable in the browser end to end.

## Phase 7: US5 — Bilingual UI completion pass (P2)

**Goal**: constitution V verified as acceptance criteria across all new
surfaces — not new features.

**Independent Test**: walk the four tabs in both locales at 375px and 1440px.

- [x] T030 [US5] i18n completeness audit: every user-facing warehouse string present in `messages/en.json` AND `fa.json` (`warehouse.*` + `nav.warehouse`); no hardcoded strings in `features/warehouse/**` (grep gate); backend error codes mapped to inline messages (`INSUFFICIENT_STOCK`, `BUSINESS_RULE_VIOLATION`, `DUPLICATE_RESOURCE`, `STALE_VERSION`); fix all findings (FR-021, SC-008)
- [x] T031 [US5] RTL/responsive/a11y pass over `features/warehouse/**`: logical CSS properties only (no physical left/right), tables collapse to cards <768px, touch targets ≥44px, Jalali dates + native Farsi digits in `fa`, skeletons + 150–300ms transitions with `prefers-reduced-motion` respected; verify at 375px and 1440px in both locales; fix all findings (FR-021, SC-008, constitution V)

## Phase 8: Polish & Convergence

- [x] T032 [P] [POL] `scripts/smoke-test.ps1`: warehouse section via BFF cookie flow — item create 201 → duplicate name 409 → warehouse+shelf create → receive 50 → issue 15 → overdraw 999 rejected (`INSUFFICIENT_STOCK`) → alert listed after dropping below threshold (SC-001, SC-003, SC-004, SC-005)
- [x] T033 [POL] CHANGELOG 0.4.0 entry (warehouse module) + VERSION bump + README warehouse section (module map, permissions, roles)
- [x] T034 [POL] Full gate: backend `ruff check`/`ruff format --check`/`mypy app`/`pytest` (incl. PG integration + concurrency), frontend `npm run lint`/`tsc --noEmit`/`build`, seed run twice idempotent, manual browser checklist per quickstart.md (10 steps), `scripts/smoke-ui.ps1` green, commit + push; CI green

---

## Dependencies & Execution Order

- T001–T002 (parallel) → T003 → T004 (parallel with T003 after schemas exist)
  → T005–T009 (US1; T006 needs T003+T004, T007 needs T006, T008/T009 need T007)
  → T010–T014 (US2; T011 needs T003+T004+T010, T012 needs T011, T014 needs
  T012+T013) → T015–T024 (US3; T016–T018 sequential on T015, T019 needs
  T016–T018, T020 needs T017, T023 needs T019+T021+T022) → T025–T029 (US4;
  T026 needs T016–T018 + T025, T027 needs T026) → T030–T031 (US5 pass) →
  T032–T034.
- US1 is the MVP increment and blocks nothing structurally except the UI
  shell (T009) that later tabs reuse; US2/US3 depend on Phase-2 foundations
  only — US2 could start after T004 in parallel with US1 if staffed (the
  combobox T021 and BFF T008/T013/T022/T028 are [P]-friendly).
- The US3 checkpoint (browser stock loop + concurrency test) is the phase's
  critical path; US4 wiring (T026) must land before the polish gate.

## Notes

- No physical deletes anywhere; catalog/warehouse/shelf retirement is soft
  delete with audit; placements/movements/alerts are never deleted (R6).
- Every repository method takes ScopeContext — a query without a scope filter
  is a bug (constitution II). Catalog reads are the documented exception
  (company-wide reference data, permission-gated — research R5).
- `FOR UPDATE` on every quantity change; `CHECK (quantity >= 0)` is the last
  line of defense; concurrency is proven by T020, not assumed (SC-004).
- Movement ledger is append-only: no update/delete code paths exist —
  reconciliation test `sum(deltas) == quantity` guards SC-003 forever.
- Quantities are `Numeric(14,3)` in one unit per item (clarified); no unit
  conversion, no transfers, no expiry/lot tracking in this phase.
- Commit after each phase checkpoint (Conventional Commits);
  `/speckit.analyze` runs before implementation starts.
