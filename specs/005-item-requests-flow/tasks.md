# Tasks: Item Request Flow

**Input**: Design documents from `/specs/005-item-requests-flow/`

**Prerequisites**: plan.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: REQUIRED per task (constitution: tests are part of each task).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable · **[Story]**: US1–US5; FND = foundational
- FR/SC references map to spec.md; R# to research.md

---

## Phase 1: Setup

- [x] T001 [FND] Permission seed: append `warehouse:request:read`, `warehouse:request:decide`, `warehouse:request:fulfill` to `BASE_PERMISSIONS` in `backend/app/seeds/seed_dev.py`; map `WarehouseApprover` += read+decide, `WarehouseKeeper` += read+fulfill; `tests/test_seed.py` additions: request permission presence, role mappings, idempotency (FR-015, research R8)
- [x] T002 [P] [FND] `backend/app/modules/warehouse/schemas.py`: `RequestLineIn` (item_id, quantity > 0 ≤3 decimals, note ≤500), `RequestCreateIn` (purpose non-blank, lines min 1), `RequestLineOut`, `RequestOut`, `DecisionIn` (version, optional note), `FulfillLineIn`/`FulfillIn`; `backend/tests/test_item_request_schemas.py` fixtures (FR-001, FR-003)

## Phase 2: Foundational — models & migration (blocking)

- [x] T003 [FND] `backend/app/modules/warehouse/models.py`: `RequestStatus` enum + `ItemRequest` (requested_by FK, purpose_description, status default pending, decision fields, fulfilled_at, org anchor columns, version; no soft delete) + `ItemRequestLine` (request_id FK, item_id FK, quantity CHECK > 0, unique `(request_id, item_id)`, note) per data-model.md; alembic `backend/alembic/versions/0005_item_requests_flow.py`; verify reversible on local PG (data-model migration notes)

**Checkpoint**: migration reversible; permissions seeded idempotently.

## Phase 3: US1 — Requester submits an item request (P1) 🎯 MVP

**Goal**: valid requests composed and persisted pending; invalid refused with
field errors.

**Independent Test**: submit a 2-line request → pending + audited; empty
lines / blank purpose / zero quantity / retired item each refused.

- [x] T004 [US1] `backend/app/modules/warehouse/request_repository.py`: `create_request` (with lines), `get_request_with_lines`, `list_requests(session, context, params, *, status)` — ownership OR scope filter (`requested_by` = caller OR org anchor in `allowed_units` of `warehouse:request:read`), newest first; `backend/tests/test_item_request_flow.py` (integration, PG): repository shapes, ownership visibility, scope visibility, status filter (FR-002, FR-014, research R10)
- [x] T005 [US1] `backend/app/modules/warehouse/request_service.py`: `create_request` — validation matrix (purpose, ≥1 line, quantities, active items, no duplicate item across lines), anchor org columns via requester employee workplace (user contract; nullable for anchorless users), persist pending + audit `REQUEST_CREATED` with lines snapshot; test additions (FR-001..FR-003, SC-001, research R6)
- [x] T006 [US1] `backend/app/modules/warehouse/router.py`: `POST /warehouse/requests` (self-service, active user), `GET /warehouse/requests` (status filter), `GET /warehouse/requests/{id}` (ownership or `warehouse:request:read` + scope, no existence leak); endpoint tests incl. roleless user CAN create (FR-013, FR-014, research R5)
- [x] T007 [P] [US1] BFF: `frontend/src/app/api/warehouse/requests/route.ts` (GET, POST+CSRF), `requests/[id]/route.ts` (GET); `lib/client-api.ts` `requestApi` + types; `messages/{en,fa}.json` `requests.*` namespace; nav entry (FR-017, constitution V)
- [x] T008 [US1] UI: `frontend/src/app/[locale]/(app)/requests/page.tsx` + `features/requests/RequestsView.tsx` (status filter chips, list, status chips, page controls) + `features/requests/RequestForm.tsx` (purpose text area, line editor with `ItemSearchCombobox` + quantity + note + add/remove, `RequestInputSchema` Zod mirror, inline errors); skeletons + responsive cards (FR-001, FR-003, FR-017, SC-001, SC-006, research R11)

**Checkpoint**: employees compose requests in the browser; invalid
submissions refused with field errors.

## Phase 4: US2 — Approve / reject decisions (P1)

**Goal**: authorized approvers decide pending requests with version guards
and full audit.

**Independent Test**: approve → status approved + audited; decide non-pending
refused; two concurrent decisions → exactly one wins.

- [x] T009 [US2] `request_service.decide`: approve/reject from pending only (else `BUSINESS_RULE_VIOLATION`), version guard (`STALE_VERSION`), decision fields set, audit `REQUEST_APPROVED`/`REQUEST_REJECTED`; `tests/test_item_request_flow.py` additions: transitions, guards, concurrent-decision race via two sessions, out-of-scope denial (FR-004..FR-007, SC-002, research R3)
- [x] T010 [US2] `router.py`: `POST /warehouse/requests/{id}/approve|reject` (`warehouse:request:decide` + scope target check) + endpoint tests + BFF `requests/[id]/approve|reject/route.ts` + UI decision buttons (permission-gated via `/api/auth/me` payload, note input) (FR-004..FR-007, FR-015)

**Checkpoint**: decisions work in the browser with audit entries; races
resolved by the version guard.

## Phase 5: US3 — Fulfillment draws stock atomically (P1)

**Goal**: approved requests fulfilled through the Phase-4 contract; overdraws
refused atomically; double fulfillment impossible.

**Independent Test**: approve + fulfill with per-line placements → quantities
drop exactly, fulfillment movements exist; overdraw refused naming the line;
double fulfill refused; two requests racing one placement → exactly one
fulfills.

- [x] T011 [US3] `request_service.fulfill`: load approved request + version guard, validate per-line placement payload (placement exists, matches line item, shelf active, in caller scope), decrement each line via `contracts.apply_fulfillment_issue` in ONE transaction, set status fulfilled + `fulfilled_at`, audit `REQUEST_FULFILLED` with per-line before/after; `tests/test_item_request_fulfillment.py`: happy path, overdraw atomicity (nothing deducted), double fulfillment refusal, pending refusal (FR-008..FR-012, SC-003, research R4)
- [x] T012 [US3] `backend/tests/test_item_request_concurrency.py` (PG): two approved requests racing one placement — exactly one fulfills, the other receives `INSUFFICIENT_STOCK`, stock equals expected, ledger consistent (SC-003, research R12)
- [x] T013 [US3] `router.py`: `POST /warehouse/requests/{id}/fulfill` (`warehouse:request:fulfill` + scope) + endpoint tests + BFF `requests/[id]/fulfill/route.ts` + UI `FulfillDialog` (per-line placement picker fed by `warehouseApi.placements` filtered per item) (FR-008..FR-012, FR-015)

**Checkpoint**: full request → approve → fulfill loop moves stock in the
browser; contention decided by tests.

## Phase 6: US4 — Visibility rules (P2)

**Goal**: requester sees own requests always; warehouse actors see scoped
requests; denials never leak existence.

**Independent Test**: two users from different workplaces raise requests;
each sees own; a CP1-scoped keeper sees only CP1-anchored requests; direct
detail fetch of the other's request is denied without leak.

- [x] T014 [US4] Visibility test additions to `tests/test_item_request_flow.py`: ownership visibility across statuses, workplace-scoped keeper list purity (paginated full scan), cross-scope detail denial, global actor sees all (FR-014, FR-015, SC-005, research R6/R10)

## Phase 7: US5 — Bilingual UI completion pass (P2)

- [x] T015 [US5] i18n audit: every user-facing request string present in `messages/en.json` AND `fa.json` (`requests.*` + `nav.requests`); no hardcoded strings in `features/requests/**`; error codes mapped inline (`INSUFFICIENT_STOCK`, `BUSINESS_RULE_VIOLATION`, `STALE_VERSION`, `VALIDATION_ERROR`); fix findings (FR-017, SC-006)
- [x] T016 [US5] RTL/responsive/a11y pass over `features/requests/**`: logical CSS properties, line editor + tables collapse to cards <768px, touch targets ≥44px, Jalali timestamps in `fa`, skeletons + reduced motion; verify at 375px and 1440px both locales (FR-017, SC-006)

## Phase 8: Polish & Convergence

- [x] T017 [P] [POL] `scripts/smoke-test.ps1`: item-request E2E section — compose 2-line request → invalid variants 422 → approve → fulfill → Stock tab quantities decremented → overdraw request refused `INSUFFICIENT_STOCK` → audit trail contains all four transition actions (SC-001..SC-004)
- [x] T018 [POL] CHANGELOG 0.5.0 entry + VERSION bump + README requests module section (flow map, permissions, roles)
- [x] T019 [POL] Full gate: backend ruff/mypy/pytest (incl. PG + concurrency), frontend lint/tsc/build, seed twice idempotent, manual browser checklist per quickstart.md, `scripts/smoke-ui.ps1` green, commit + push; CI green

---

## Dependencies & Execution Order

- T001–T002 (parallel) → T003 → T004–T008 (US1; T005 needs T003+T004, T006
  needs T005, T007/T008 need T006) → T009–T010 (US2; needs US1 persistence +
  anchoring) → T011–T013 (US3; T011 needs T009 machinery, T012 needs T011,
  T013 needs T011) → T014 (US4 additions) → T015–T016 (US5 pass) →
  T017–T019.
- US1 is the MVP increment; US2 and US3 depend on the request persistence +
  anchoring but are independent of each other's stock behavior until
  fulfillment; BFF/UI tasks are [P]-friendly once their endpoints land.

## Notes

- Requests are immutable flow history — no edit/cancel/delete paths exist
  (research R2/R7).
- Self-service create/own-read is ownership-scoped (active authentication;
  `/auth/me` precedent) — the documented exception to permission-gated
  access (research R5, spec FR-013/FR-014).
- Fulfillment reuses `contracts.apply_fulfillment_issue` — no new stock
  machinery; contention is proven by T012, not assumed (SC-003).
- Every repository method that reads shared request data applies the
  ownership-OR-scope filter — a query without one is a bug (constitution II).
- Commit after each phase checkpoint (Conventional Commits).
