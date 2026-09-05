# Tasks: Settings, Reports & Management Dashboard

**Input**: Design documents from `/specs/009-settings-reports-dashboard/`

**Prerequisites**: plan.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: REQUIRED per task (constitution: tests are part of each task).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable · **[Story]**: US1–US4; FND = foundational
- FR/SC references map to spec.md; R# to research.md

---

## Phase 1: Setup

- [x] T001 [FND] Add `openpyxl` to `backend/requirements-dev.txt`; install into the venv; smoke `Workbook(write_only=True)` import; no other dependency changes (research R4)

## Phase 2: Settings module — storage, service, API (US4)

- [x] T002 [FND] `backend/app/modules/settings/models.py`: `Setting` model per data-model.md (key unique, JSONB value, value_type CHECK, version, bilingual descriptions) + `backend/app/modules/settings/defaults.py`: fixed key set with typed defaults (8 keys, research R2); alembic `backend/alembic/versions/0009_settings.py` (reversible); verify upgrade/downgrade on local PG
- [x] T003 [P] [FND] `backend/app/modules/settings/schemas.py`: `SettingOut`, `SettingUpdateIn` (value + version) with per-key typed validation helper (`validate_setting_value(key, value)` → canonical value or VALIDATION_ERROR); schema contract tests for all 4 value types + unknown key + wrong type
- [x] T004 [US4] `backend/app/modules/settings/repository.py` + `service.py`: `list_settings` (scope-checked global op), `update_setting` — SELECT row, validate typed value, version guard (STALE_VERSION before any write), bump version, write audit row (`SETTING_UPDATED`, before/after snapshots via write_audit) in the SAME transaction, commit; `get_setting`/`get_setting_bool` typed reads with code-default fallback; tests: happy update, stale version, unknown key, wrong type, audit row present with masked snapshots, default fallback on missing row
- [x] T005 [US4] `backend/app/modules/settings/router.py`: `GET /settings` (`settings:setting:read`), `PATCH /settings/{key}` (`settings:setting:update`) returning `SettingOut`; endpoint tests: 200 flows, 401/403, VALIDATION_ERROR, STALE_VERSION envelope; wire router in `app/main.py`
- [x] T006 [P] [US4] `backend/app/modules/settings/contracts.py`: `get_setting(session, key)` / `get_setting_bool(session, key, default)` for other modules (constitution VI); contract tests incl. default fallback
- [x] T007 [P] [US4] `backend/app/seeds/seed_dev.py`: idempotent seeding of the 8 setting defaults + new permissions (`settings:setting:read`, `settings:setting:update`, `reports:dashboard:read`, `reports:inventory:read`, `reports:request:read`, `reports:loan:read`, `reports:export:excel`) + role maps (Manager: settings read + all report reads + export; Auditor: export; SuperAdmin: all — research R6); test: seed twice idempotent, permission rows exist

**Checkpoint**: settings CRUD + audit + seed proven; gate = pytest green.

## Phase 3: Dashboard backend (US3)

- [ ] T008 [FND] Cross-module count contracts: `user/contracts.py` `count_active_employees(scope_context)`, `warehouse/contracts.py` `count_catalog_items(scope_context)` + `count_open_item_requests` + `count_unresolved_alerts` + `item_requests_status_counts(scope_context)`, `loan/contracts.py` `count_active_loans(scope_context)` + `loans_status_counts`, notification total via existing repository; each applies the module's own scope filter; contract tests with global vs workplace scope
- [ ] T009 [US3] `backend/app/modules/reports/schemas.py` (DashboardOut + breakdown DTOs) + `service.py` `dashboard(context)` composing the contracts; `router.py` `GET /reports/dashboard` (`reports:dashboard:read`); tests: counters match seeded data, workplace-scoped context yields subset counts, 403 without permission, response shape per contracts

**Checkpoint**: dashboard endpoint proven scope-filtered.

## Phase 4: Operational reports backend (US2)

- [ ] T010 [P] [US2] `warehouse/contracts.py` filtered placement page (item/warehouse/shelf/quantity/threshold/below_min + warehouse_id + below_min_only filters, scope-filtered, paginated) + `reports/service.py` `inventory_report` + `GET /reports/inventory` (`reports:inventory:read`); tests: scope filter, below_min_only, pagination, 403
- [ ] T011 [P] [US2] `warehouse/contracts.py` filtered request summary page (status/date filters + status_counts over filtered set) + `reports/service.py` `requests_report` + `GET /reports/requests` (`reports:request:read`); requester-own fallback for users without management scope (mirror request module semantics); tests: filters, counts, own-only fallback, 403
- [ ] T012 [P] [US2] `loan/contracts.py` per-workplace/year aggregate rows (request counts by status, active loan/guarantee commitments, policy caps; scope-filtered) + `reports/service.py` `loans_report` + `GET /reports/loans` (`reports:loan:read`); tests: aggregate math vs seeded loans, scope filter, 403
- [ ] T013 [US1] `audit/contracts.py` filtered audit page (action/entity_type/actor/date filters, masked snapshots per existing semantics, `read_full` gate) + `reports/service.py` `audit_report` + `GET /reports/audit` (`audit:log:read`); tests: filters, masking on/off, foreign trace fields present, 403

**Checkpoint**: all four report endpoints green with scope+masking tests.

## Phase 5: Excel export backend (US1/US2)

- [ ] T014 [FND] `backend/app/modules/reports/excel.py`: `build_report_workbook(report, rows, locale)` — openpyxl write_only, bilingual headers per locale, `fa` RTL sheet view + Jalali date strings, masked values written as masked strings (never raw for non-read_full users); unit tests: header language, RTL flag, row fidelity, empty-page workbook valid, masking identical to endpoint output
- [ ] T015 [US1/US2] `reports/router.py` `GET /reports/export/excel` (`reports:export:excel` + the target report's read permission; masking per audit perms): reuses the report services with the same query params, streams workbook with Content-Type/Content-Disposition (filename per report+date); tests: 200 + magic bytes (PK zip header), rows equal filtered page, 403 without export permission, empty result → headers-only workbook, filename/locale handling

**Checkpoint**: exports byte-verified and permission-gated.

## Phase 6: Frontend (US1–US4)

- [ ] T016 [FND] BFF: `frontend/src/app/api/settings/route.ts` + `api/settings/[key]/route.ts` (PATCH via proxyToBackend) + `api/reports/{dashboard,inventory,requests,loans,audit}/route.ts`; `lib/bff-proxy.ts` `proxyFileToBackend(request, backendPath)` binary passthrough (cookie→Bearer, upstream Content-Type/Content-Disposition verbatim) + `api/reports/export/route.ts`; `lib/client-api.ts` `settingsApi` + `reportsApi` (typed DTOs incl. download helper); types match contracts
- [ ] T017 [P] [US4] `features/settings/SettingsConsole.tsx` + `app/[locale]/(app)/settings/page.tsx`: grouped typed controls (bool switch, integer input, json textarea with validation), stale-version surfacing (error + refetch), feature-flag group; `messages/{en,fa}.json` `settings.*` namespaces; permission-gated nav item
- [ ] T018 [P] [US3] Dashboard upgrade: `features/dashboard/DashboardView.tsx` for holders of `reports:dashboard:read` (counters + breakdown cards honoring `dashboard.show_*` settings flags; fallback to current module overview otherwise); `messages/{en,fa}.json` `dashboard.*` additions; Jalali dates in `fa`
- [ ] T019 [P] [US1/US2] `features/reports/ReportsConsole.tsx` + `app/[locale]/(app)/reports/page.tsx`: four tabs (inventory/requests/loans/audit), filter forms, paginated tables (card collapse on mobile), export button → `/api/reports/export` download link, skeletons, reduced motion; `messages/{en,fa}.json` `reports.*` namespaces incl. per-column headers and audit action labels
- [ ] T020 [P] [US4] Feature-flag gating in `nav-items.ts`: `flags.loan_module_enabled` / `flags.asset_module_enabled` hide/show Loans and Assets nav (read via `settingsApi` in the shell data path or server-side settings read); tests not applicable (visual) — verified via manual checklist

**Checkpoint**: app builds; manual browser checklist per quickstart.md.

## Phase 7: Polish & Convergence

- [ ] T021 [P] [POL] `scripts/smoke-test.ps1`: settings section (PATCH + version bump + audit row + stale rejection) + reports section (dashboard counters > 0 as admin, inventory/requests/loans/audit pages 200 + scoped, export returns xlsx magic bytes + filename, masked user export contains no raw national id); `scripts/smoke-ui.ps1`: dashboard + reports + settings render checks
- [ ] T022 [POL] CHANGELOG 0.9.0 entry + VERSION bump + README settings/reports section (module map, permissions, export model, feature flags)
- [ ] T023 [POL] Full gate: backend ruff/mypy/pytest (scratch DB), frontend lint/tsc/build, seed twice idempotent, manual browser checklist per quickstart.md, `scripts/smoke-test.ps1` + `scripts/smoke-ui.ps1` green, commit + push; CI green

---

## Dependencies & Execution Order

- T001 → T002–T003 (parallel) → T004 → T005 → T006/T007 (parallel) →
  T008 → T009 → T010–T013 (parallel after T008) → T014 → T015 →
  T016 → T017–T020 (parallel) → T021 → T022 → T023.
- Settings ships first (its flags feed the dashboard UI); reports and
  export follow; the frontend phase lands once all APIs exist.

## Notes

- The reports module owns NO models/repositories — all data access via
  contracts (constitution VI, research R3).
- Reuse `audit:log:read`/`read_full` for the audit report (research R6);
  export is one permission across report types.
- Setting changes do NOT emit outbox events (fixed 13-event set, R7).
- Exports are page-bounded (≤ page_size rows) — same data the screen
  shows; no unbounded dumps.
- Commit after each phase checkpoint (Conventional Commits).
