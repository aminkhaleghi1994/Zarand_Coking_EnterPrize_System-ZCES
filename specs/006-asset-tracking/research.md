# Research: Asset Tracking

**Date**: 2026-08-31 · Companion to [plan.md](./plan.md)

## R1 — Module placement and file layout

**Decision**: `AssetInstance`/`AssetHistory` live in `modules/warehouse`
(§9.2 owner), implemented as `asset_repository.py` + `asset_service.py`
beside the Phase-4/5 aggregates.
**Rationale**: §9.2 is explicit; assets interact with employees (user module)
only through the published user contract, and with nothing else.

## R2 — Holder representation

**Decision**: the placement of an asset is a single typed target:
`holder_type` (`employee` | `location` | NULL), `holder_employee_id`
(FK employees, nullable), `holder_location` (text, nullable). NULL type +
NULL both fields = **available**. A table CHECK enforces exactly the three
consistent states; the service validates semantics (active employee, in
scope).
**Rationale**: requirements §18 assign "به کارمند یا محل" (employee or
location); a single-holder model with a typed target keeps the state machine
trivial and the history unambiguous.
**Alternatives**: separate assignment rows with validity intervals
(rejected — the requirements describe current-holder semantics, not rental
contracts); many-to-many holders (rejected — an asset is physically in one
place).

## R3 — Serial uniqueness with normalization

**Decision**: `serial_norm = lower(btrim(serial))` maintained by the service;
partial unique index on `serial_norm` `WHERE deleted_at IS NULL`; retire →
serial reusable. Serial is required and immutable after creation
(traceability anchor, mirroring employee identity fields).
**Rationale**: identical mechanism proven by the Phase-4 item catalog
(research R2 there); the spec's edge case explicitly demands
case/whitespace-insensitive duplicates.

## R4 — Concurrency control

**Decision**: `version` on `asset_instances`; assign/return/update/retire
check the version first (→ `STALE_VERSION` 409) then mutate + audit in one
transaction. History rows are append-only.
**Rationale**: §25 names asset assignment/return as concurrency-sensitive
and mandates optimistic locking on editable entities; the version-first
ordering (before status checks) was validated in Phase 5's decision race
test.

## R5 — History table shape

**Decision**: `asset_histories` — `asset_id` FK, `action` (created /
assigned / returned / retired / updated; check-constrained text enum),
`from_type`/`from_employee_id`/`from_location`, `to_type`/
`to_employee_id`/`to_location`, `note`, actor + timestamp; append-only, no
update/delete paths. The timeline renders newest-first from this table.
**Rationale**: explicit from/to columns make the timeline self-contained and
auditable without joins; the `updated` action keeps edit history too (§18:
"تاریخچه دارایی را ثبت کند" — record the asset's history).
**Alternatives**: audit-log-only timeline (rejected — audit is global and
masked; the per-asset timeline needs first-class structured entries).

## R6 — Workplace anchoring and scope

**Decision**: nullable org columns (company/complex/workplace) snapshot from
the **creator's** employee anchor at creation (Phase-5 request pattern);
anchorless rows (creator without an employee record, e.g. the seeded admin)
are visible only to global scope and their creator. List/detail/mutations
filter or verify via `allowed_units` on `warehouse:asset:*` operations.
**Rationale**: the spec's visibility story needs an anchor; requiring one
would break admin-created assets (the smoke/gate flows) for no stated
requirement.
**Alternatives**: mandatory workplace binding like warehouses (rejected —
requirements never bind assets to workplaces, and the gate flows create
assets as the anchorless admin).

## R7 — Employee targets through the user contract

**Decision**: assignment validates the target employee via a new user-module
contract function `get_employee_holder(session, employee_id)` returning
`{id, display_name, company_id, complex_id, workplace_id, is_active}` or
None — the warehouse module never imports employee models directly.
**Rationale**: constitution VI; mirrors the Phase-4
`get_workplace_with_parents` seam. Deactivated employees are refused as
assignment targets (spec edge case) but remain valid historical from/to
references.

## R8 — Permissions

**Decision**: six codes — `warehouse:asset:create`, `warehouse:asset:read`,
`warehouse:asset:update`, `warehouse:asset:retire`, `warehouse:asset:assign`,
`warehouse:asset:return`. Role mapping: `WarehouseKeeper` += all six;
`WarehouseApprover` += read. `SuperAdmin` ensure-all.
**Rationale**: assets are keeper duties per §4; approvers get visibility
only (consistent with Phase 4/5 splits).

## R9 — Error mapping

**Decision**: assignment of an assigned asset / return of an available asset /
retirement while assigned → `BUSINESS_RULE_VIOLATION` (422); stale writes →
`STALE_VERSION` (409); duplicate serial → `DUPLICATE_RESOURCE` (409);
field/validation issues → `VALIDATION_ERROR` (422); out-of-scope →
`AUTHORIZATION_DENIED` (403, no existence leak).
**Rationale**: the established convention set; frontend dictionary already
covers every code.

## R10 — Endpoint shape

**Decision** (base `/api/v1/warehouse/assets`):
`GET /` (scope-filtered, `search`, `status` = available|assigned|retired|all,
paginated) · `POST /` · `GET /{id}` · `PATCH /{id}` (+version) ·
`POST /{id}/retire` (+version) · `GET /{id}/history` (paginated, newest
first) · `POST /{id}/assign` (+version, `{target_type, employee_id?,
location?, note?}`) · `POST /{id}/return` (+version, `{note?}`).
`AssetOut` embeds the resolved holder (`employee` brief with name, or
`location` text) so the UI never re-derives state.
**Rationale**: mirrors the Phase-4/5 endpoint conventions 1:1.

## R11 — Frontend surface

**Decision**: one `(app)/assets` page + `features/assets/`: `AssetsView`
(status filter chips, search, list/table → cards), `AssetForm`
(create/edit), `AssignDialog` (target toggle employee/location — employee
picker fed by the existing scoped employees API), `HistoryDrawer` (timeline
newest-first). Nav `assets` entry gains its href. Employee picker uses
`/api/employees` (already scope-filtered server-side).
**Rationale**: reuses the requests-console UX and existing APIs; no new
picker machinery needed (the employee dropdown is plain select over the
directory).

## R12 — Testing strategy

**Decision**: `backend/tests/test_asset_tracking.py` — registration matrix
(duplicates via normalization, reuse after retirement), assignment/return
happy paths, already-assigned/available refusals, retirement blocking,
version races (concurrent assign ×2 → one winner; assign-vs-return race),
scope purity (paginated full scan), history completeness and ordering, seed
idempotency. PG-gated integration; smoke-test gains an asset E2E section.
**Rationale**: the Phase-4/5 harness pattern; every SC gets an executable
assertion.

## R13 — i18n

**Decision**: `assets.*` namespace in both catalogs (list, form, assign
dialog, history drawer, errors) + reuse `nav.assets`; error codes map via
`assets.errors.*`.
**Rationale**: the established per-phase namespace pattern.

## Open items carried to tasks

None — the three clarify decisions are recorded in the spec; every design
choice above is binding for `/speckit.tasks`.
