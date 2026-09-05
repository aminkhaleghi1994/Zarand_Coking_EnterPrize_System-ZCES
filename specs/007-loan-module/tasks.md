# Tasks: Loan & Guarantee Management

**Input**: Design documents from `/specs/007-loan-module/`

**Prerequisites**: plan.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: REQUIRED per task (constitution: tests are part of each task).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable · **[Story]**: US1–US5; FND = foundational
- FR/SC references map to spec.md; R# to research.md

---

## Phase 1: Setup

- [x] T001 [FND] Permission seed: append the 9 loan codes (`loan:policy:create/read/update/retire`, `loan:request:create/read/activate/settle/cancel`) to `BASE_PERMISSIONS` in `backend/app/seeds/seed_dev.py`; map `LoanOfficer` += all nine; `tests/test_seed.py` additions: permission presence, role mapping, idempotency (research R5, contracts)
- [x] T002 [P] [FND] `backend/app/common/jalali.py`: Gregorian→Jalali conversion (jalaali algorithm: breaks/g2j) + `current_jalali_year(now)` helper; `backend/tests/test_jalali.py`: Nowruz boundary (2026-03-20→1404, 2026-03-21→1405), leap-year Esfand 30, round-trip spot checks across decades (research R4, SC-004)
- [x] T003 [P] [FND] `backend/app/common/masking.py`: add `"amount"` to `SENSITIVE_KEYS_FULL_MASK` so loan snapshots mask money (§21); masking test addition (research R7, FR-012)

## Phase 2: Foundational — models & migration (blocking)

- [x] T004 [FND] `backend/app/modules/loan/models.py`: `LoanType`/`LoanStatus` enums + `LoanPolicy` (workplace+year partial unique among active, year/amounts/counts CHECKs, anchors, version, soft delete) + `LoanRequest` (employee owner, workplace snapshot, type CHECK, amount CHECK > 0, year CHECK, status CHECK, settled_at, version, soft delete) per data-model.md; alembic `backend/alembic/versions/0007_loan_module.py`; verify reversible on local PG (data-model migration notes)

**Checkpoint**: migration reversible; permissions seeded idempotently; Jalali math proven at boundaries.

## Phase 3: US1 — Define and manage workplace loan policies (P1) 🎯 MVP

**Goal**: officers create/edit/retire per-workplace per-year policies that
every request validates against.

**Independent Test**: create policy → duplicate (workplace+year) refused →
edit stale refused → retire; scoped officers see only their units' policies.

- [x] T005 [P] [US1] `backend/app/modules/loan/schemas.py`: `LoanType`/`LoanStatus` payload enums, `LoanPolicyCreateIn/UpdateIn/RetireIn/LoanPolicyOut`, `LoanRequestCreateIn` (type + amount string 2dp), `LoanRequestOut` (employee/workplace briefs, status, settled_at), `WorkplaceBriefOut`; `backend/tests/test_loan_schemas.py` fixtures (contracts, research R8)
- [x] T006 [US1] `backend/app/modules/user/contracts.py`: `get_loan_requester(session, user_id)` → `{employee_id, display_name, company_id, complex_id, workplace_id, is_active}` or None; `tests/test_user_contracts.py` additions (research R6)
- [x] T007 [US1] `backend/app/modules/loan/repository.py`: `get_active_policy(session, workplace_id, year)`, `get_policy`, `get_policy_by_workplace_year`, `list_policies(scope_ctx, params, workplace_id?, year?, include_retired)` — scope filter via anchor columns; `backend/tests/test_loan_module.py` (integration, PG): repository shapes, scope purity (FR-001, FR-003, research R6)
- [x] T008 [US1] `backend/app/modules/loan/service.py`: `create_policy` (anchors via contract, duplicate workplace+year → `DUPLICATE_RESOURCE`, audit `LOAN_POLICY_CREATED`), `update_policy` (version guard, collision-safe year edits, audit `LOAN_POLICY_UPDATED`), `retire_policy` (soft delete, audit `LOAN_POLICY_RETIRED`); test additions: full policy matrix (FR-001, FR-002, SC-001 preconditions)
- [x] T009 [US1] `router.py`: `GET/POST /loan/policies`, `GET/PATCH /{id}`, `POST /{id}/retire` (require_operation per code + in-scope workplace target checks); endpoint tests: 201 shape, 409 duplicate, 409 stale, 403 out-of-scope (FR-001..FR-003)

**Checkpoint**: policies manageable in the browser; duplicates impossible.

## Phase 4: US2 — Submit with the exact validation cascade (P1) 🎯 core

**Goal**: every request validates in the exact §19 order with named-rule
refusals; settled/cancelled/soft-deleted keep counting; only active same-year
amounts bind caps; races resolve to one winner.

**Independent Test**: with known policy limits, trip each rule in turn and
verify the FIRST failing rule is named; a passing request is created pending.

- [x] T010 [US2] `repository.py` aggregates with §19 docstrings: `count_requests_lifetime(employee_id)` (all rows, ignoring status AND `deleted_at` — R9), `count_requests_year(employee_id, year)`, `sum_active_amount(employee_id, year, type)` (active + year-scoped only); test additions: settled/cancelled/soft-deleted inclusion, active-only sums, year scoping (FR-006, FR-007, SC-002, research R3/R9)
- [x] T011 [US2] `service.submit_request`: resolve requester via contract (active employee required), resolve policy under `SELECT … FOR UPDATE`, cascade 1→4 in exact order with `details.rule` ∈ {lifetime_count, yearly_count, loan_cap, guarantee_cap, no_policy} + current/limit values, year snapshot via `current_jalali_year`, persist pending, audit `LOAN_REQUEST_CREATED`; test additions: each rule refusal (order proven), happy path, no-policy, deactivated employee, two-session submission race (one winner) (FR-004, FR-005, FR-008, FR-009, SC-001, SC-003, research R2)
- [x] T012 [US2] `router.py`: `GET/POST /loan/requests`, `GET /{id}` (ownership self-view vs `loan:request:read` scoped view); endpoint tests: 201, 422 named rules, 404 out-of-scope without leak, self-service visibility (FR-004, FR-013)

**Checkpoint**: the four-rule cascade proven in order; submissions race-safe.

## Phase 5: US3 — Lifecycle transitions (P1)

**Goal**: pending → active → settled/cancelled with version-guarded
transitions; activation consumes, settlement/cancellation frees the amount
commitment.

**Independent Test**: activate → cap binds; settle → cap frees and
`settled_at` stamped; cancel → cap frees while counts stay consumed; two
concurrent activations → one winner.

- [x] T013 [US3] `service.py` transitions: `activate_request` (pending only + active employee → `BUSINESS_RULE_VIOLATION` otherwise), `settle_request` (active only, stamps `settled_at`), `cancel_request` (pending or active) — all version-guarded (`STALE_VERSION`), all audited (`LOAN_REQUEST_ACTIVATED/SETTLED/CANCELLED`); test additions: happy paths, invalid transitions, stale race (two sessions, one winner), deactivated-employee activation refusal, cap freed after settle, counts still consumed after settle (FR-010, FR-011, SC-002, SC-003)
- [x] T014 [US3] `router.py`: `POST /loan/requests/{id}/activate|settle|cancel` + endpoint tests + BFF routes for all loan endpoints (FR-010, FR-011, contracts)

**Checkpoint**: full lifecycle proven; commitments bind and free correctly.

## Phase 6: US4 — Scoped browsing of policies and requests (P2)

**Goal**: scope-pure listings with pagination and filters; ownership
self-service visibility.

**Independent Test**: two workplaces' data; scoped officer sees only theirs;
a plain employee sees only their own requests; filters (type/status/year)
and pagination verified.

- [x] T015 [US4] `repository.list_requests(scope_ctx, requester, params, type?, status?, year?, employee_id?, search?)` — union of ownership rows + `allowed_units` rows; filters by type/status/year, search by employee name; policy listing filters (`workplace_id`, `year`, `include_retired`); test additions: two-workplace scope purity, ownership-only for plain user, cross-scope detail denial, filter correctness (FR-013, SC-006)

## Phase 7: US5 — Bilingual loans console (P2)

- [x] T016 [US5] BFF: `frontend/src/app/api/loan/**` routes (policies list/create/detail/patch/retire; requests list/create/detail/activate/settle/cancel); `lib/client-api.ts` `loanApi` + types; `messages/{en,fa}.json` `loans.*` namespace; `nav-items.ts` loans href (FR-014, constitution V)
- [x] T017 [US5] UI: `frontend/src/app/[locale]/(app)/loans/page.tsx` + `features/loans/LoansConsole.tsx` (Policies/Requests tabs, filter chips type/status/year, tables→cards) + `PolicyForm.tsx` (create/edit, duplicate + stale errors) + `LoanForm.tsx` (type toggle + amount with 2dp validation) + per-card transitions (activate/settle/cancel confirmations, settled_at display); skeletons + reduced motion (FR-014, SC-006, research R11)

## Phase 8: Polish & Convergence

- [x] T018 [P] [POL] `scripts/smoke-test.ps1`: loan E2E section — policy create → duplicate 409 → cascade refusals in exact order (yearly_count, lifetime_count, loan_cap, guarantee_cap) → happy submit → activate binds cap → settle frees cap with settled_at → cancel keeps counts (SC-001..SC-005)
- [x] T019 [POL] CHANGELOG 0.7.0 entry + VERSION bump + README loans section (module map, permissions, validation cascade, Jalali semantics)
- [x] T020 [POL] Full gate: backend ruff/mypy/pytest (scratch DB), frontend lint/tsc/build, seed twice idempotent, manual browser checklist per quickstart.md, `scripts/smoke-ui.ps1` green, commit + push; CI green

---

## Dependencies & Execution Order

- T001–T003 (parallel) → T004 → T005–T009 (US1; T006 before T008) →
  T010–T012 (US2) → T013–T014 (US3) → T015 (US4) → T016–T017 (US5) →
  T018–T020.
- US1 is the MVP increment (policies are the validation substrate); US2 is
  the core business rule; US3/US4 sequential on the request persistence;
  BFF/UI tasks are [P]-friendly once endpoints land.

## Notes

- No physical deletes; policy/request retirement is soft delete with audit.
- The count/cap aggregates deliberately read ALL rows (including
  soft-deleted) per §19 — only the two named helpers in T010 (research R9).
- Submission serializes on the policy row (`SELECT … FOR UPDATE`) — the
  same locking discipline as stock decrements (research R2).
- `amount` is masked in every loan audit snapshot (T003, research R7).
- Commit after each phase checkpoint (Conventional Commits).

## Phase 9: Convergence

- [x] T021 Make all seven loan audit writes critical (in-transaction) per
  FR-012/Constitution III (partial): write_audit(..., critical=True) for
  LOAN_POLICY_CREATED/UPDATED/RETIRED and LOAN_REQUEST_CREATED/ACTIVATED/
  SETTLED/CANCELLED so audit rows can never outlive a rolled-back
  transition; test additions: audit row presence + masked amount for a
  transition
- [x] T022 Request listing `search` filter per FR-013/contracts (partial):
  list_requests + GET /loan/requests accept `search` matching employee
  first/last names (EN + FA, ilike); test additions: search narrows results
- [x] T023 Policy listing `workplace_id` filter per FR-003/contracts
  (partial): list_policies + GET /loan/policies accept `workplace_id`
  (scope-filtered union); test additions: filter narrows results
- [x] T024 PolicyForm `is_active` pause toggle per FR-002 (partial): edit
  mode exposes active/paused with save; messages updated; lint/build green
