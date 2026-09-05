# Research: Warehouse, Item Catalog & Inventory

**Date**: 2026-08-31 · Companion to [plan.md](./plan.md) · Resolves every
design question surfaced by the spec and the Phase-3 codebase inventory.

## R1 — Quantity representation

**Decision**: `Numeric(14, 3)` (PostgreSQL `NUMERIC`) for placement quantity,
movement `quantity_delta` and `resulting_quantity`, and item
`min_quantity`; `CHECK (quantity >= 0)` on `inventory_placements`; service
rounds inputs to 3 decimal places.
**Rationale**: clarified unit model is "one unit per item" with units like kg
or meters, so fractional quantities are real (e.g. 12.500 kg). NUMERIC is
exact — no float drift in a ledger. 3 decimals cover industrial use.
**Alternatives**: integer units (rejected — breaks kg/L items); float
(rejected — ledger must be exact); NUMERIC(12,6) (rejected — false precision).

## R2 — Duplicate-name/code enforcement with normalization

**Decision**: `item_catalog` stores the display `name`/`name_fa` plus service-
maintained `name_norm = lower(btrim(name))` and nullable `code_norm`; partial
unique indexes on `name_norm` and `code_norm` `WHERE deleted_at IS NULL`; the
service normalizes before insert/update and maps unique violations to
`DUPLICATE_RESOURCE` naming the field.
**Rationale**: the requirement's uniqueness is semantic ("treats case/
whitespace variants as duplicates"); a maintained normalized column makes the
DB itself the enforcer (race-proof), matching the Phase-3 partial-index
pattern. Retired rows are excluded, so names/codes become reusable (FR-002).
**Alternatives**: validating only in the service (rejected — TOCTOU race);
DB `citext`/expression indexes (viable but a maintained column is simpler to
index, search, and reason about); `citext` extension (rejected — new
extension for no benefit at this scale).

## R3 — Live search implementation

**Decision**: server-side `ILIKE '%term%'` over `name_norm`, `name_fa`, and
`code_norm`, paginated (`Page[ItemOut]`, bounded `page_size ≤ 100`);
client debounces 300 ms and cancels in-flight requests via the query
lifecycle. No full-text/trigram machinery.
**Rationale**: clarified scale is ~500 items — ILIKE is comfortably inside the
P95 < 200ms goal, needs zero extensions (constitution VIII), and the spec
explicitly defers heavy search machinery (assumptions). Debounce+cancel gives
the "pauses, not keystrokes" behavior (FR-003).
**Alternatives**: pg_trgm GIN index (rejected — extension + ops cost for no
measured need); client-side filtering of a full item list (rejected — spec
mandates server-side, paginated search).

## R4 — Concurrency control for stock

**Decision**: issues and adjustments lock the placement row with
`SELECT … FOR UPDATE` (`with_for_update()`) inside the transaction, then
re-read the authoritative quantity, apply the delta, write the movement, and
commit; receives take the same lock (uniform path). Placements carry **no
`version` column** — serialization replaces optimistic locking there
(versioned optimistic locking stays on catalog/warehouse/shelf edits, which
are ordinary document edits per FR-004/FR-009).
**Rationale**: two simultaneous issues must produce exactly one winner
(spec US3 scenario 4); row locking is the constitution-mandated mechanism
(III) and the requirements' own risk mitigation (§36 Risk 2). The DB
`CHECK (quantity >= 0)` is the last line of defense.
**Alternatives**: optimistic `version` on placements (rejected — every
receive would fight every issue with user-visible conflicts for no business
meaning); advisory locks (rejected — heavier and less idiomatic than row
locks); no lock + CHECK-only (rejected — cryptic 500s instead of the
insufficient-stock error).

## R5 — Scope anchoring and the company-wide catalog

**Decision**: `warehouses.workplace_id` is the scope anchor (NOT NULL; the
warehouse's `company_id`/`complex_id` org columns are filled from the
workplace's parents at creation). All warehouse/shelf/placement/movement/alert
queries filter through a join to `warehouses.workplace_id` using the existing
`allowed_units` pattern (`_employee_scope_filter` as the template). The
**catalog is company-wide reference data**: `warehouse:item:read` needs the
permission only (pickers must work for every keeper); catalog **writes** need
the permission **and** at least one active scope assignment in the warehouse
domain (any level).
**Rationale**: the spec calls the catalog "the company catalog" (US1) while
FR-019 scopes the *physical* domain; a keeper of any workplace must pick any
item, but mutating the shared catalog is gated beyond bare authentication.
Documented in the endpoint contract so `/speckit.analyze` can check it.
**Alternatives**: per-workplace catalogs (rejected — duplicates the same bolt
across plants, contradicts "company catalog"); company-wide write for anyone
authenticated (rejected — weakens audit posture).

## R6 — Ledger and placement shape

**Decision**: `inventory_placements(shelf_id, item_id)` unique, `quantity`
with CHECK, timestamps + actor columns, **no soft delete** (placements live
forever; a zero-quantity placement is simply empty, and history must stay
joinable). `stock_movements` is an append-only ledger: `placement_id`,
denormalized `item_id` (per-item history later), `movement_type` (text enum:
`receive` / `issue` / `adjust`, extensible for Phase-5 `fulfillment`),
`quantity_delta` (signed), `resulting_quantity`, `reason` (nullable), actor +
timestamp; no update/delete paths exist in code.
**Rationale**: the spec's "movement history stays queryable after retirement"
edge case and "every change paired with exactly one movement" (SC-003) are
naturally satisfied by an immutable ledger keyed to a permanent placement.
Denormalizing `item_id` avoids a two-join for the future item-centric views
without violating normalization meaningfully (item of a placement is
invariant).
**Alternatives**: soft-deleting emptied placements (rejected — orphans
ledger rows); storing only deltas without resulting quantity (rejected —
history must be auditable at a glance and reconciliation-friendly).

## R7 — Alert episode lifecycle

**Decision**: `stock_alerts(placement_id, item_id, quantity_at_alert,
threshold_at_alert, raised_at, resolved_at, resolve_reason)` with a partial
unique index `UNIQUE (placement_id) WHERE resolved_at IS NULL` — the DB makes
"one active alert per episode" (FR-017) structural. Evaluation runs inside the
same transaction as the movement: resulting quantity < `min_quantity` → raise
if none active; ≥ threshold → resolve the active alert (`resolve_reason =
'recovered'`). Retirement of a shelf or item resolves its active alerts
(`resolve_reason = 'placement_retired'` / `'item_retired'`). No manual
resolve endpoint in v1.
**Rationale**: episode semantics with a unique partial index cannot produce
duplicate alerts even under races; same-transaction evaluation keeps
alert state consistent with the ledger (audit `critical=True` per
constitution III). Retirement resolution closes the "alert on a dead
placement" hole surfaced during clarification.
**Alternatives**: recompute-on-read (rejected — SC-005 requires stored,
auditable episodes); async evaluation via queue (rejected — no Celery yet,
constitution VIII, and delivery belongs to Phase 8 anyway).

## R8 — Adjustment semantics

**Decision**: `adjust` takes the **corrected absolute quantity** (a physical
recount result), not a delta; the service computes `delta = target − current`,
rejects `target < 0` (`VALIDATION_ERROR`), rejects `delta == 0`
(`VALIDATION_ERROR` — nothing to correct), and records the movement with the
signed delta and resulting quantity.
**Rationale**: corrections in warehouses come from stocktakes ("shelf says
7, system says 9") — absolute is the natural input, and the signed ledger
still captures the true change. The movement type records that this was an
adjustment, preserving the audit story.
**Alternatives**: signed delta input (rejected — error-prone for recounts,
allows "adjust by −999" with no counted value in view).

## R9 — Retirement blocking

**Decision**: retiring a shelf is blocked (`BUSINESS_RULE_VIOLATION`, details
naming the blocking placements) while any of its active placements holds
quantity ≠ 0; retiring a warehouse is blocked while any placement under its
active shelves holds quantity ≠ 0. The check runs inside the retiring
transaction after locking the relevant rows.
**Rationale**: FR-008/US2 require stock never be orphaned; the placement
table makes the check a single indexed query. Retirement remains possible at
zero stock (spec edge case — history stays queryable).
**Alternatives**: cascade-move stock on retire (rejected — silent stock
movement violates the explicit-movement principle); allow retire with stock
and hide placements (rejected — orphaned inventory).

## R10 — Permissions and role mapping

**Decision**: 16 permission codes appended to `BASE_PERMISSIONS`
(`module:resource:operation` convention):

```
warehouse:item:create        warehouse:item:read
warehouse:item:update        warehouse:item:retire
warehouse:warehouse:create   warehouse:warehouse:read
warehouse:warehouse:update   warehouse:warehouse:retire
warehouse:shelf:create       warehouse:shelf:read
warehouse:shelf:update       warehouse:shelf:retire
warehouse:stock:receive      warehouse:stock:issue
warehouse:stock:adjust       warehouse:stock:read
warehouse:alert:read
```

Role mapping (idempotent seed helpers exist): `WarehouseKeeper` ← item
create/read/update/retire, warehouse/shelf read, shelf create/update/retire,
stock receive/issue/read, alert read. `WarehouseApprover` ← item/warehouse/
shelf/stock/alert read only (approve/reject powers arrive with Phase 5).
`SuperAdmin` keeps the existing ensure-all behavior.
**Rationale**: clarification Q1 (separate receive/issue/adjust authorities)
plus least-privilege daily work; the codes match `test_scope_resolver.py`'s
existing sample strings (`warehouse:item:create/read`), so no churn there.
**Alternatives**: one `warehouse:stock:change` (rejected — clarification);
auto-granting manage rights to approvers (rejected — Phase 5 concern).

## R11 — Error mapping

**Decision**: `INSUFFICIENT_STOCK` → HTTP 409 (conflict with current stock),
`BUSINESS_RULE_VIOLATION` (retirement blocked, zero-delta adjust) → 422,
`DUPLICATE_RESOURCE` → 409, `STALE_VERSION` → 409, `VALIDATION_ERROR` → 422
— via the existing `AppError` factories. `AppError` takes an explicit
`status_code`, so no core changes are needed.
**Rationale**: matches the Phase-3 conventions (stale version = 409) and
keeps the frontend error handling uniform (`ApiError.message` shown inline).

## R12 — Movement type column

**Decision**: `Enum(MovementType, native_enum=False, create_constraint=True,
length=20)` — same style as the user module's enums; values `receive`, `issue`,
`adjust`; adding `fulfillment` in Phase 5 is a migration append.
**Rationale**: native PG enums make appends painful; the codebase already
standardized on check-constrained text enums.

## R13 — Frontend surface: one page, tabs, one combobox

**Decision**: single `(app)/warehouse/page.tsx` rendering `WarehouseConsole`
with tabs **Catalog / Warehouses / Stock / Low stock** (the AdminViews tab
pattern), one debounced `ItemSearchCombobox` (300 ms, TanStack Query, cancel
on unmount) used by the item picker and later by request lines; nav label
`nav.warehouse` in both locales.
**Rationale**: four surfaces share one scope context and one item picker;
tabs avoid four near-empty pages and mirror the established admin console
pattern. The combobox is the reusable piece Phase 5 needs (requirements §6:
"جستجوی زنده کالا هنگام ثبت").
**Alternatives**: four separate routes (rejected — more chrome, no benefit);
a generic reusable combobox component in `components/` now (deferred —
promote it when a second consumer appears, per simplicity).

## R14 — Testing strategy

**Decision**: flat `backend/tests/test_warehouse_*.py` (repo convention):
- `test_warehouse_catalog.py` — normalization duplicates (case/whitespace,
  code), reuse after retire, version conflict, seed idempotency.
- `test_warehouse_stock.py` — receive/issue/adjust ledger math, insufficient
  stock, retirement blocking, scope filters (workplace/complex/global),
  alert raise/resolve/re-raise, alert resolution on retirement.
- `test_warehouse_concurrency.py` — **PG-only** (`requires_db`): N threads ×
  separate sessions racing issues that together overdraw — assert exactly the
  expected number of successes, no negative quantity, ledger consistency
  (`sum(deltas) == final quantity`).
SQLite runs cover validation/unit paths (concurrency + partial-index tests
skip without PG, like Phase 3). Frontend: eslint/tsc/build; smoke-test.ps1
gains a warehouse section (item create → duplicate rejected → receive →
issue → overdraw rejected → alert listed) via the BFF cookie flow.
**Rationale**: mirrors the proven Phase-3 harness (pg fixture, seed run,
`_admin_token` helpers); the concurrency test is the spec's SC-004 made
executable.

## R15 — i18n and navigation

**Decision**: one `warehouse.*` namespace in `en.json`/`fa.json`
(`tabs`, `catalog.*`, `warehouses.*`, `stock.*`, `alerts.*`, `errors.*`);
navigation gets a single `nav.warehouse` entry. Zod form schemas carry i18n
message keys as error messages (established convention).
**Rationale**: matches the existing message organization and the
constitution's bilingual gate; one namespace keeps the dictionary flat.

## Open items carried to tasks

None — all NEEDS CLARIFICATION resolved; remaining choices are recorded
above with rationale and are binding for `/speckit.tasks`.
