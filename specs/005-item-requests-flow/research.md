# Research: Item Request Flow

**Date**: 2026-08-31 · Companion to [plan.md](./plan.md) · Resolves every
design question surfaced by the spec.

## R1 — Module placement

**Decision**: ItemRequest/ItemRequestLine live in `modules/warehouse`
(requirements §9.2 names the warehouse module as their owner), implemented as
dedicated `request_repository.py` + `request_service.py` files beside the
Phase-4 code.
**Rationale**: §9.2 is explicit; the fulfillment path consumes the module's
own published contract (`apply_fulfillment_issue`), so a separate module
would create a circular dependency for zero benefit.
**Alternatives**: a new `requests` module (rejected — contradicts §9.2 and
would need a cross-module stock dependency); user module (rejected — requests
are warehouse-domain data).

## R2 — Status model and transitions

**Decision**: `RequestStatus` enum (`pending`, `approved`, `rejected`,
`fulfilled`; check-constrained text enum per the module's convention) with
allowed transitions: `pending → approved`, `pending → rejected`,
`approved → fulfilled`. Everything else is refused with
`BUSINESS_RULE_VIOLATION`. Requests are immutable flow history: no edit, no
cancel, no delete paths exist in code.
**Rationale**: the requirements define exactly created → approved/rejected →
fulfilled (§20 events, §27.3 E2E) and clarify Q1 fixed whole-request
fulfillment; per-line states would add a tracking dimension the requirements
never ask for.
**Alternatives**: per-line fulfillment states (rejected — clarify Q1);
a cancel/withdraw transition (rejected — not in the requirements; assumption
recorded in the spec).

## R3 — Concurrency control

**Decision**: decisions and fulfillment are guarded by the request's
`version` column (optimistic locking → `STALE_VERSION` 409 on stale writes,
per §25); the stock side of fulfillment locks placements
(`SELECT … FOR UPDATE` via the Phase-4 contract) so two concurrent
fulfillments drawing from the same placement serialize exactly like issues.
**Rationale**: §25 names ItemRequest fulfillment as a sensitive entity and
mandates optimistic locking on editable entities plus pessimistic locking for
stock; the version guard also makes concurrent approve-vs-reject produce
exactly one winner (spec US2/AC4).
**Alternatives**: state-machine DB locks (rejected — overkill); no version on
requests (rejected — double decisions would be possible).

## R4 — Fulfillment mechanics

**Decision**: the fulfill payload carries one placement per line
(`lines: [{line_id, placement_id}]`). The service: loads the request
(approved, in scope), locks it and checks the version, then for each line
validates the placement (same item, active shelf, within the caller's scope)
and calls the Phase-4 contract `apply_fulfillment_issue` — all inside one
transaction the service commits; any refusal (insufficient stock naming the
line, retired shelf) rolls the whole request back.
**Rationale**: clarify Q2 (keeper picks per line — stock decisions stay
visible) and clarify Q1 (whole-request atomicity); reusing the contract means
zero new stock machinery and identical ledger semantics to Phase 4.
**Alternatives**: auto-deduction heuristics (rejected — clarify Q2); partial
per-line fulfillment (rejected — clarify Q1); direct ledger writes bypassing
the contract (rejected — duplicates the integrity logic the contract exists
to own).

## R5 — Self-service creation and visibility split

**Decision**: request creation and "my requests" access are
**ownership-scoped** (active authentication; `requested_by = caller`), the
same authorization model as `/auth/me` — no permission code is required for
self-service. Warehouse actor surfaces (scope-wide listing, decisions,
fulfillment) require the corresponding permission AND scope. The three new
permission codes are `warehouse:request:read` (scope-wide list/detail),
`warehouse:request:decide` (approve/reject), `warehouse:request:fulfill`.
**Rationale**: clarify Q3 fixed self-service creation; constitution II
governs shared-data access, while own-request access is ownership-based
(the `/auth/me` precedent from Phase 2). The spec's FR-013/FR-014 encode
exactly this split.
**Alternatives**: requiring `warehouse:request:create` for self-service
(rejected — employees hold no roles; gating self-service behind role
assignment would break the requirement's intent); one merged "manage"
permission (rejected — least privilege).

## R6 — Workplace anchoring of requests

**Decision**: `item_requests` carries nullable org columns
(`company_id`, `complex_id`, `workplace_id`) snapshot from the requester's
employee record at creation (via the user-module contract
`get_workplace_with_parents`-style lookup); `requested_by` is always set.
Scope-wide visibility filters on these columns with `allowed_units`; users
without an employee record (bootstrap admin) have unanchored requests visible
only to global scope and to themselves.
**Rationale**: the spec's visibility story (US4) needs an organizational
anchor, and snapshotting at creation keeps the request's scope stable even if
the requester later moves workplaces (history integrity).
**Alternatives**: joining requester → employee → workplace at query time
(rejected — breaks if the employee moves; the request's originating workplace
is historical fact).

## R7 — Request lines immutability

**Decision**: lines are written once at creation and never updated or
deleted (a change means submitting a new request); the table carries
`request_id` FK with `ON DELETE RESTRICT` semantics through immutability (no
delete paths), `quantity NUMERIC(14,3) CHECK (quantity > 0)`, optional note.
**Rationale**: clarify Q1 + the spec's "requests are immutable flow history"
assumption; line-level edits would corrupt decided/fulfilled history.
**Alternatives**: editable lines pre-decision (rejected — requirements never
ask; adds versioning complexity for zero stated value).

## R8 — Permissions and role mapping

**Decision**: three new codes — `warehouse:request:read`,
`warehouse:request:decide`, `warehouse:request:fulfill`. Role mapping:
`WarehouseApprover` += read + decide; `WarehouseKeeper` += read + fulfill;
`SuperAdmin` += all (ensure-all behavior). Self-service needs no code (R5).
**Rationale**: §4 role table assigns review/approval to WarehouseApprover and
stock management to WarehouseKeeper; the split keeps decision and fulfillment
authorities separate (mirroring the Phase-4 receive/issue/adjust split).
**Alternatives**: one `warehouse:request:manage` code (rejected — least
privilege); granting decide to keepers (rejected — separation of duties).

## R9 — Error mapping

**Decision**: invalid state transitions → `BUSINESS_RULE_VIOLATION` (422);
stale version → `STALE_VERSION` (409); stock shortfalls during fulfillment →
`INSUFFICIENT_STOCK` (409, details carry line id + available); field
validation → `VALIDATION_ERROR` (422, field_errors); out-of-scope →
`AUTHORIZATION_DENIED` (403, no existence leak).
**Rationale**: identical to the Phase-4 conventions; the frontend error-code
dictionary already maps every one of these codes.

## R10 — List query shape

**Decision**: `GET /warehouse/requests` merges ownership and scope: rows
where `requested_by = caller` **or** the request's org anchor falls inside the
caller's `warehouse:request:read` units (global → all). A `status` filter
(default `all`) and bounded pagination apply; ordered newest-first.
**Rationale**: FR-014's visibility rule in one query; the OR semantics match
"requesters see their own; warehouse actors see their scope" without two
endpoints.

## R11 — Frontend surface

**Decision**: one `(app)/requests` page + `features/requests/`:
`RequestsView` (status filter chips + newest-first list + status chips +
decision/fulfillment actions rendered only when `/api/auth/me` grants the
corresponding permission), `RequestForm` (purpose text area + line editor:
`ItemSearchCombobox` per line, quantity input, note, add/remove rows),
`FulfillDialog` (per-line placement picker fed by `warehouseApi.placements`
filtered by item). Nav gains a `nav.requests` entry (ClipboardList icon).
**Rationale**: mirrors the Phase-4 console pattern; the combobox and
responsive-table utilities are reused unchanged; permission-conditional
actions follow the identity payload already returned by `/auth/me`.

## R12 — Testing strategy

**Decision**: flat `backend/tests/test_item_requests_*.py`:
- `test_item_request_flow.py` — creation validation matrix, decision
  guards + version race (two sessions), status immutability, scope/ownership
  visibility, audit entries per transition.
- `test_item_request_fulfillment.py` — happy path (quantities drop exactly,
  one movement per line, status fulfilled), per-line overdraw atomicity,
  double-fulfillment refusal, pending-request refusal, cross-request stock
  contention (two requests, one placement — exactly one fulfills), requester
  deactivation does not block decisions.
SQLite runs cover validation units; PG-gated integration mirrors the Phase-4
harness. Smoke test gains a request E2E section; frontend lint/tsc/build.
**Rationale**: the Phase-4 harness proved out; the contention test makes
SC-003 executable.

## R13 — i18n and navigation

**Decision**: `requests.*` namespace in both catalogs (compose form, list,
status chips, dialogs, errors) + `nav.requests`; error codes reuse the shared
dictionary pattern under `requests.errors.*`.
**Rationale**: consistent with the Phase-4 namespace layout; the constitution
bilingual gate applies per surface.

## Open items carried to tasks

None — all NEEDS CLARIFICATION were resolved with the owner (spec
Clarifications) and every design choice above is binding for
`/speckit.tasks`.
