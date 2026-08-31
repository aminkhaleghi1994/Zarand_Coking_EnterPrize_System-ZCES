# Tasks: Organizational Structure & Employee/User Management

**Input**: Design documents from `/specs/003-org-user-module/`

**Prerequisites**: plan.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: REQUIRED per task (constitution: tests are part of each task; write before
implementation where practical).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable · **[Story]**: US1–US5; FND = foundational
- FR/SC references map to spec.md

---

## Phase 1: Setup

- [ ] T001 [FND] Add new permission codes to the permission seed: `user:employee:read`, `user:employee:read_full`, `user:employee:create`, `user:employee:update`, `user:employee:deactivate`, `user:password:set`, `user:org:read` (bilingual names; roles/scope management reuses existing `user:role:*`/`user:scope:*` codes); SuperAdmin=ALL rule keeps applying; `tests/test_seed.py` additions: exact catalog count/content, re-run idempotency (FR-018, research R12)
- [ ] T002 [P] [FND] `app/modules/user/schemas.py`: add `OrgOut`, `EmployeeSummaryOut`, `EmployeeOut`, `EmployeeCreateIn` (nested user account), `EmployeeUpdateIn` (+`version`), `PasswordSetIn`, `StatusFilter` enum; validators: national_id = exactly 10 digits (numeric string), personnel_code non-empty trimmed, password policy shared with creation (min 8); `tests/test_employee_schemas.py`: valid/invalid fixtures, per-field error paths (FR-006, FR-007, FR-010, FR-021)

## Phase 2: Foundational — org models & migration (blocking)

- [ ] T003 [FND] `models.py`: add `Company`, `Complex`, `Workplace`, `Employee` per data-model.md (mixins: full set; `users.employee_id` unique FK; scope_assignments FK conversion); alembic revision `0003_org_user_module` (hand-review partial unique indexes `uq_employee_national_id_active`, `uq_employee_personnel_code_active`, unique FK, FK conversions); verify `upgrade head → downgrade -1 → upgrade head` on local PG (FR-001, FR-003, FR-008, data-model migration notes)
- [ ] T004 [P] [FND] `org_repository.py`: `list_complexes(scope_ctx, page)`, `list_workplaces(scope_ctx, page, complex_id?)`, `get_workplace`, `get_complex` — every query applies the scope filter (Global→all, Complex→own, Workplace→own complex) AND active-rows-only (deactivated units never appear in lists/pickers); `tests/test_org_repository.py` (integration, PG): scope unions, cross-complex denial, empty-context denial, deactivated rows excluded (FR-004, FR-015, research R5)
- [ ] T005 [FND] Seed extension `seed_dev.py`/`seed_prod.py`: upsert org tree by natural keys (company `ZCS`; complexes `CTR`, `SM`; workplaces `KCM`→CTR, `CP1`→CTR, `CP2`→CTR, `SP`→SM — bilingual names per requirements §5); audit `ORG_SEEDED`; `tests/test_seed.py` additions: fresh seed exact tree, re-run no-op, prod includes tree without demo employees (SC-001, research R11)

**Checkpoint**: migration reversible; org tree seeds idempotently; org reads scope-filtered.

## Phase 3: US1 — Org structure visible (P1)

- [ ] T006 [US1] `router.py`: `GET /org/complexes`, `GET /org/workplaces` (`user:org:read`, paginated, `complex_id` narrowing) per contracts/employee-endpoints.md; `tests/test_org_endpoints.py`: admin 200 shape, workplace-scoped admin sees own complex only, roleless 403 (SC-001, FR-015)
- [ ] T007 [P] [US1] BFF passthrough: `frontend/src/app/api/org/{complexes,workplaces}/route.ts` (GET, cookie-forward, transparent refresh) mirroring existing auth routes; `lib/api.ts` fetchers + Zod schemas; `messages/{en,fa}.json` org keys (constitution V)

## Phase 4: US2 — Employee + user creation (P1) 🎯

- [ ] T008 [US2] `employee_repository.py`: `list_employees(scope_ctx, params)` (search ILIKE name / exact-or-prefix national_id / personnel_code; status filter default active; joins workplace+complex+user), `get_employee`, `get_by_national_id`, `get_by_personnel_code`, `get_user_by_email`; `tests/test_employee_repository.py` (integration, PG): scope unions, status filter semantics, search modes, pagination envelope (FR-015, FR-016, research R6)
- [ ] T009 [US2] `employee_service.create_employee_with_user(...)`: validate (incl. target workplace exists AND is active) → insert employee → insert user (bcrypt, `employee_id` set) → audit `EMPLOYEE_CREATED` (critical, masked: national_id via mask_identifier, NO password material) → commit; map IntegrityError → `DUPLICATE_RESOURCE` naming the field; rollback leaves nothing; `tests/test_employee_service.py` (integration): happy path, duplicate national_id/personnel_code/email/username, reuse after soft-delete, deactivated-workplace rejection, concurrency race on national_id (unique index catches), failure injection mid-transaction (FR-003, FR-005..FR-010, SC-003, research R3/R4)
- [ ] T010 [US2] `router.py`: `POST /employees` (`user:employee:create`; scope check on target workplace; 201 EmployeeOut) + `GET /employees` + `GET /employees/{id}` (`user:employee:read`; masked national_id without `read_full`); `tests/test_employee_endpoints.py`: admin create→201 shape; duplicates 409 field-specific; roleless 403; masked response field (FR-005..FR-011, FR-017)
- [ ] T011 [US2] BFF passthrough `app/api/employees/route.ts` (GET list, POST create with CSRF) + `app/api/employees/[id]/route.ts` (GET) · `features/employees/EmployeeTable.tsx` (server-paginated table, desktop table → cards <768px, debounced search 300ms, status filter chips) · `features/employees/EmployeeForm.tsx` (create mode: identity + user-account sections, workplace picker grouped by complex from `/api/org`, Zod mirror of backend rules, inline field errors, per-field duplicate errors) · `app/[locale]/(app)/employees/page.tsx` + sidebar link activation · `messages/{en,fa}.json` `employees.*` keys · skeleton loaders + reduced-motion (FR-006, FR-010, FR-016, SC-002, SC-007, research R10)

**Checkpoint**: end-to-end create in browser; new user signs in immediately.

## Phase 5: US3 — Directory editing & moves (P2)

- [ ] T012 [US3] `employee_service.update_employee(...)`: version guard (mismatch → `STALE_VERSION`/`CONFLICT_CONCURRENT_UPDATE`), reject identity-anchor changes (`VALIDATION_ERROR`), validate target workplace exists AND is active, workplace move requires BOTH current and target in scope; audited `EMPLOYEE_UPDATED` (+`EMPLOYEE_MOVED` on move) with before/after snapshots; `tests/test_employee_service.py` additions: stale version, anchor immutability, deactivated-target rejection, move in/out of scope, audit snapshot shape (FR-011, FR-012, research R9)
- [ ] T013 [P] [US3] `PATCH /employees/{id}` route + tests (409 envelope, field errors, 403 outside scope) + BFF passthrough `app/api/employees/[id]/route.ts` (PATCH with CSRF) per contracts (FR-012, FR-017)
- [ ] T014 [US3] `EmployeeForm` edit mode (identity anchors read-only, version hidden field, workplace picker restricted to in-scope workplaces, conflict-error refresh-and-retry affordance) + row Edit action wiring; FA/RTL responsive verification per constitution V (FR-011, FR-012, SC-004, SC-007)

## Phase 6: US4 — Deactivation cascade (P2)

- [ ] T015 [US4] `employee_service.deactivate(...)`/`reactivate(...)`: idempotent; same-txn cascade — employee soft-delete + user `is_active=false` + `revoke_all_for_user`; audited `EMPLOYEE_DEACTIVATED`/`EMPLOYEE_REACTIVATED` (masked before/after both sides); identity anchors become reusable (partial index semantics); `tests/test_employee_service.py` additions: cascade effect on user+sessions, idempotent re-deactivation, reactivation restores sign-in, identity reuse after deactivation (FR-013, FR-014, SC-005, research R7)
- [ ] T016 [US4] `POST /employees/{id}/deactivate` + `/reactivate` routes (+ `version` body) + tests + BFF passthrough `app/api/employees/[id]/{deactivate,reactivate}/route.ts`; UI: confirm dialog → action → status chip update; deactivated employees visible via status filter with Reactivate action (FR-013, FR-016, SC-005)

## Phase 7: US5 — Management surfaces (P3)

- [ ] T017 [US5] `POST /users/{user_id}/password` route (`user:password:set`; scope check; target user's employee in scope, Global required for bootstrap users without employee; bcrypt rehash + family revocation + `USER_PASSWORD_SET` audit without credential material) + tests (success, weak password 422, out-of-scope 403, audit masked, other sessions die) + BFF passthrough `app/api/users/[id]/password/route.ts` (FR-021, research R8)
- [ ] T018 [P] [US5] Scope-assignment service check: rejecting assignments that reference deactivated complexes/workplaces (extend Phase-2 assign-scope service; level→unit consistency per FR-019) + tests (FR-019, data-model note)
- [ ] T019 [US5] Frontend management views under System: `features/admin/RolesView.tsx` (list + create, duplicate error inline), `PermissionsView.tsx` (paginated catalog), `UserAccessManager.tsx` (per-user role assign/revoke + scope assign/remove with level→unit picker per FR-019, audited operations reflected immediately) wired to existing Phase-2 endpoints via new BFF passthrough routes; `messages/{en,fa}.json` `admin.*` keys; sidebar "System" group links activate (FR-018, SC-006, SC-007, research R10)

## Phase 8: Polish & Convergence

- [ ] T020 [P] [POL] `scripts/smoke-test.ps1`: add checks — create employee via BFF (cookies+CSRF) → 201; duplicate national_id → 409 field-specific; new-user sign-in works; deactivate → session dead; `zces_*` cookie flags still HttpOnly; audit trail accessible with masking (SC-002, SC-003, SC-005)
- [ ] T021 [POL] README org/employee section + CHANGELOG 0.3.0 entry; VERSION → 0.3.0
- [ ] T022 [POL] Full gate: backend ruff/mypy/pytest (incl. integration), frontend lint/tsc/build, seed twice idempotent, manual browser checklist per quickstart.md (10 steps), commit + push; CI green

---

## Dependencies & Execution Order

- T001–T002 → T003 → T004–T005 ([P] pair) → T006–T007 (US1) → T008–T011 (US2;
  T010 needs T009; T011 needs T007+T010) → T012–T014 (US3) → T015–T016 (US4;
  T015 needs T009+T003) → T017–T019 (US5; T017 needs T002+T009 machinery) →
  T018–T022.
- The US2 checkpoint (browser create + sign-in) is the phase's critical path;
  US5 can proceed in parallel with US3/US4 once T010 lands.

## Notes

- No physical deletes anywhere; org/employee deactivation is soft delete with
  audit; grant tables keep Phase-2 semantics.
- national_id/personnel_code immutable after creation (clarified with owner).
- Every repository method takes ScopeContext — a query without a scope filter
  is a bug (constitution II).
- Password material never appears in code paths beyond the bcrypt call site;
  masked audit verified by tests, not policy (SC-006).
- Commit after each phase checkpoint (Conventional Commits).
