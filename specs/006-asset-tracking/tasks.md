# Tasks: Asset Tracking

**Input**: Design documents from `/specs/006-asset-tracking/`

**Prerequisites**: plan.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: REQUIRED per task (constitution: tests are part of each task).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable · **[Story]**: US1–US5; FND = foundational
- FR/SC references map to spec.md; R# to research.md

---

## Phase 1: Setup

- [x] T001 [FND] Permission seed: append the 6 asset codes (`warehouse:asset:create/read/update/retire/assign/return`) to `BASE_PERMISSIONS` in `backend/app/seeds/seed_dev.py`; map `WarehouseKeeper` += all six, `WarehouseApprover` += read; `tests/test_seed.py` additions: permission presence, role mappings, idempotency (FR-015, research R8)
- [x] T002 [P] [FND] `backend/app/modules/warehouse/schemas.py`: `HolderType` enum, `AssetCreateIn/AssetUpdateIn/AssetOut/HolderOut`, `AssetAssignIn` (target_type + employee_id/location + note), `AssetReturnIn`, `AssetHistoryOut`; `backend/tests/test_asset_schemas.py` fixtures (FR-001, FR-005, contracts)

## Phase 2: Foundational — models & migration (blocking)

- [x] T003 [FND] `backend/app/modules/warehouse/models.py`: `HolderType`/`AssetAction` enums + `AssetInstance` (serial/serial_norm partial unique, holder-type CHECK, org anchor columns, version; soft delete) + `AssetHistory` (action CHECK, from/to holder columns, append-only) per data-model.md; alembic `backend/alembic/versions/0006_asset_tracking.py`; verify reversible on local PG (data-model migration notes)

**Checkpoint**: migration reversible; permissions seeded idempotently.

## Phase 3: US1 — Register an asset instance (P1) 🎯 MVP

**Goal**: assets registered with duplicate-proof serials; retirement blocked
while assigned.

**Independent Test**: register → duplicate serial variant refused → retire →
serial reusable; retire while assigned blocked.

- [x] T004 [US1] `backend/app/modules/warehouse/asset_repository.py`: `create_asset`, `get_asset`, `get_asset_by_serial_norm`, `list_assets(scope_ctx, params, search?, status?)` — scope filter via org anchor columns, status computed from holder/retired, newest/serial ordering; `backend/tests/test_asset_tracking.py` (integration, PG): repository shapes, scope purity, search, status filter (FR-002, FR-011, research R3/R6)
- [x] T005 [US1] `backend/app/modules/warehouse/asset_service.py`: `create_asset` (normalize serial, duplicate check, anchor via user contract, audit `ASSET_CREATED` + history entry), `update_asset` (version guard, serial immutable, audit `ASSET_UPDATED`), `retire_asset` (blocked while assigned → `BUSINESS_RULE_VIOLATION`; idempotent; audit `ASSET_RETIRED` + history); test additions: full matrix (FR-001..FR-004, SC-001, research R3)
- [x] T006 [US1] `router.py`: `GET/POST /warehouse/assets`, `GET/PATCH /{id}`, `POST /{id}/retire` (require_operation per code + scope target checks); endpoint tests: 201 shape, 409 duplicate, 422 blocked retirement, 403 out-of-scope (FR-001..FR-004, FR-011)

**Checkpoint**: assets registrable in the browser; duplicates impossible.

## Phase 4: US2 — Assign to employee or location (P1)

**Goal**: typed assignment targets with version-guarded races and history.

**Independent Test**: assign to employee → holder set + history + audit;
second assignment refused; concurrent assignments → one winner; deactivated
employee refused.

- [x] T007 [US2] `backend/app/modules/user/contracts.py`: add `get_employee_holder(session, employee_id)` returning `{id, display_name, company_id, complex_id, workplace_id, is_active}` or None; `tests/test_user_contracts.py` additions (FR-005, research R7)
- [x] T008 [US2] `asset_service.assign_asset`: validate target (employee active+in-scope via contract, or location text present), version guard, holder-state CHECK-safe update, history entry (`assigned` with from/to), audit `ASSET_ASSIGNED`; test additions: employee + location targets, already-assigned refusal, deactivated-employee refusal, concurrent assignment race (two sessions, one winner) (FR-005, FR-006, SC-002, research R2/R4)
- [x] T009 [US2] `router.py`: `POST /warehouse/assets/{id}/assign` + endpoint tests + BFF route (FR-005, FR-006, FR-015)

## Phase 5: US3 — Return an assigned asset (P1)

**Goal**: returns clear the holder with history + audit; available-asset
returns refused.

**Independent Test**: assign → return (holder cleared, 2 history entries);
return of available asset refused; concurrent returns → one winner.

- [x] T010 [US3] `asset_service.return_asset`: only from assigned (else `BUSINESS_RULE_VIOLATION`), version guard, holder cleared, history entry (`returned` with from/to), audit `ASSET_RETURNED`; test additions: happy path, available-asset refusal, concurrent return race (FR-007, SC-003, research R4)
- [x] T011 [US3] `router.py`: `POST /warehouse/assets/{id}/return` + endpoint tests + BFF route (FR-007, FR-015)

## Phase 6: US4 — Scoped list and history timeline (P2)

**Goal**: scope-pure listings and complete newest-first timelines.

**Independent Test**: two workplaces' assets; CP1-scoped keeper sees only
CP1; timelines show all lifecycle entries in order.

- [x] T012 [US4] `asset_repository.get_history` (paginated newest first) + `GET /warehouse/assets/{id}/history` route; visibility test additions: paginated full-scan scope purity, cross-scope detail denial, retired-asset history queryable (FR-009, FR-010, FR-011, SC-004)

## Phase 7: US5 — Bilingual assets console (P2)

- [x] T013 [US5] BFF: `frontend/src/app/api/warehouse/assets/**` routes (list/create/detail/patch/retire/assign/return/history); `lib/client-api.ts` `assetApi` + types; `messages/{en,fa}.json` `assets.*` namespace; `nav-items.ts` assets href (FR-012, constitution V)
- [x] T014 [US5] UI: `frontend/src/app/[locale]/(app)/assets/page.tsx` + `features/assets/AssetsView.tsx` (filter chips, search, table→cards) + `AssetForm.tsx` (create/edit, serial immutable in edit) + `AssignDialog.tsx` (employee/location toggle, employee picker from the scoped directory API) + `HistoryDrawer.tsx` (timeline newest-first, Jalali in `fa`); return/retire confirmations; skeletons + reduced motion (FR-012, SC-006, research R11)

## Phase 8: Polish & Convergence

- [x] T015 [P] [POL] `scripts/smoke-test.ps1`: asset E2E section — register → duplicate 409 → assign employee → history 2 entries → return → retire blocked→allowed after return → serial reuse (SC-001..SC-004)
- [x] T016 [POL] CHANGELOG 0.6.0 entry + VERSION bump + README assets section (module map, permissions, holder model)
- [ ] T017 [POL] Full gate: backend ruff/mypy/pytest, frontend lint/tsc/build, seed twice idempotent, manual browser checklist per quickstart.md, `scripts/smoke-ui.ps1` green, commit + push; CI green

---

## Dependencies & Execution Order

- T001–T002 (parallel) → T003 → T004–T006 (US1) → T007–T009 (US2; T007
  before T008) → T010–T011 (US3) → T012 (US4) → T013–T014 (US5) →
  T015–T017.
- US1 is the MVP increment; US2/US3 sequential on the asset persistence;
  BFF/UI tasks are [P]-friendly once endpoints land.

## Notes

- No physical deletes; asset retirement is soft delete with audit; history
  is append-only (research R5).
- Every repository method that reads shared asset data applies the scope
  filter — a query without one is a bug (constitution II).
- Holder-state consistency is enforced by a DB CHECK plus the service
  state machine (research R2).
- Commit after each phase checkpoint (Conventional Commits).
