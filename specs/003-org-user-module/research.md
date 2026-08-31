# Research: Organizational Structure & Employee/User Management

**Date**: 2026-08-31 · Resolves all unknowns for [plan.md](./plan.md)

## R1 — How to model the org tree

**Decision**: Three flat tables with explicit parent FKs — `companies` (single
seeded row), `complexes.company_id`, `workplaces.complex_id`. No self-referencing
generic "org unit" table, no closure/adjacency materialized path.

**Why**: The hierarchy depth is fixed at 3 by requirements §5 (company is
constant in v1). Two FK columns give type-safe joins, trivial scope filtering
(`workplace_id IN (…)`, `complex_id = …`), and simple partial unique needs.
A generic tree buys nothing at fixed depth and complicates every scoped query.

**Consequences**: Adding deeper levels later means a migration; accepted for v1
simplicity (constitution VIII).

## R2 — Employee ↔ User linkage direction

**Decision**: `users.employee_id` (unique, nullable until Phase-3 backfill —
in practice every user created from Phase 3 on has an employee). Employee is
the aggregate root for people data; user exists for sign-in.

**Why**: requirements §3.1 make the 1:1 mandatory; anchoring the FK on users
keeps `employees` free of auth concerns and lets `is_active` deactivation
cascade naturally (employee → user in the same transaction). A unique FK gives
the 1:1 at the database level.

**Alternative rejected**: `employees.user_id` — puts auth identity inside the
people record; contract calls from other modules (`get_employee_workplace`)
would join through auth data.

## R3 — Uniqueness strategy for identity anchors

**Decision**: Partial unique indexes, exactly per requirements §11:
`uq_employee_national_id_active ON employees(national_id) WHERE deleted_at IS NULL`
and the same for `personnel_code`. Service also pre-checks and maps the
`IntegrityError` to `DUPLICATE_RESOURCE` with field details (better error
message than a raw constraint failure).

**Why**: soft delete means normal unique constraints would block identity reuse
forever; partial indexes are the documented project pattern (Phase 2 users
table already uses them).

## R4 — Create employee+user in one transaction

**Decision**: One service function opens the transaction: validate →
insert employee → insert user (bcrypt hash) → audit write (critical) → commit.
Any failure raises before commit; nothing persists. Uniqueness races are caught
by the partial indexes (IntegrityError → rollback → duplicate error).

**Why**: binding golden rule 7; audited as one `EMPLOYEE_CREATED` action with
masked after-snapshot (national_id masked, password material absent).

## R5 — Scope filtering for employees

**Decision**: Repository receives `ScopeContext` and builds the filter from the
union of assignments: Global ⇒ no filter; Complex ⇒ `complex_id IN (…)` via
join to workplace; Workplace ⇒ `workplace_id IN (…)`. Mutations re-check the
target's workplace against the same context before writing.

**Why**: constitution II (non-negotiable); reuses the Phase-2 resolver — no new
authorization logic, only the query-shape application of it.

## R6 — Search & pagination

**Decision**: Server-side pagination (`{items, page, page_size, total}`, bounded
page size ≤ 100, default 20). Search is an `ILIKE` prefix/infix on name,
exact-or-prefix on national_id/personnel_code, backed by plain B-tree indexes
(volume is thousands, trigram indexing is Phase-10 tuning if ever needed).
Status filter: `active` (default) / `deactivated` / `all`.

**Why**: constitution VII + AGENTS.md tables rule; avoids unbounded results;
indexes on `national_id`, `personnel_code`, `last_name` suffice at this scale.

## R7 — Deactivation cascade semantics

**Decision**: Deactivating an employee sets `deleted_at` on the employee AND
`is_active=false` on the linked user AND revokes all active refresh-token
families for that user — all inside one transaction with one audit action
(`EMPLOYEE_DEACTIVATED`) whose snapshot records both sides. Reactivation
reverses employee + user `is_active` (families stay dead; user signs in fresh).
Idempotent: re-deactivating succeeds with an audit entry.

**Why**: spec US4/FR-013; reuses Phase-2 `revoke_all_for_user` machinery;
"deactivation = sessions die now" was the verified Phase-2 behavior.

## R8 — Admin password reset (clarify Q1)

**Decision**: `POST /users/{id}/password` (BFF-passthrough) — admin supplies
the new password; service validates with the same rules as creation, hashes
with bcrypt, revokes all refresh families (so other sessions die), audits
`USER_PASSWORD_SET` with no credential material. Permission:
`user:password:set` (new). Target must be within the actor's scope.

**Why**: chosen in clarify; closes the "lost password = dead account" gap
without email infrastructure.

## R9 — Optimistic locking on employee edits

**Decision**: `Employee` carries `version` (existing VersionMixin). Update
requests must include the version they read; a mismatch returns
`STALE_VERSION`/`CONFLICT_CONCURRENT_UPDATE` per the standard code set.

**Why**: constitution III; two-admin concurrent edit edge case in spec.

## R10 — Frontend data surfaces

**Decision**: Employees page = server-paginated table (desktop) collapsing to
cards <768px, debounced search (300ms) hitting the backend (no client-side
filtering), status filter chips, row actions (edit, deactivate/reactivate, set
password). Create/edit = one form component (create includes the user-account
section; edit hides identity anchors, shows version-guarded fields).
Management UI = three views under the sidebar "System" group reusing the
Phase-2 admin endpoints (roles list+create, permissions catalog, per-user
role & scope manager with the level→unit picker rules of FR-019).

**Why**: AGENTS.md (tables, forms, i18n); reuses the redesigned console shell;
no new dependencies; skeleton loaders + `prefers-reduced-motion` per
constitution V.

## R11 — Seeding

**Decision**: Extend `seed_dev`/`seed_prod` with the org tree (idempotent by
natural keys: company code, complex code, workplace code — NOT by name alone).
Prod seed also creates the org tree (it is real operational data, not demo
data) but no demo employees. Codes: `ZCS`, `CTR`, `SM`, `KCM`, `CP1`, `CP2`,
`SP`.

**Why**: requirements §5 gives exact names; codes give stable idempotency and
friendly FK targets; spec US1 AC2 requires no-op re-runs.

## R12 — New permissions catalog

**Decision**: Add to the permission seed:
`user:employee:read`, `user:employee:create`, `user:employee:update`,
`user:employee:deactivate`, `user:password:set`, `user:org:read`,
`role:manage` (list/create), plus keep existing user:role:* / user:scope:*
codes for the management UI. SuperAdmin = ALL (existing rule).

**Why**: every FR maps to a permission; management UI (spec US5) reuses the
Phase-2 endpoint permission codes.
