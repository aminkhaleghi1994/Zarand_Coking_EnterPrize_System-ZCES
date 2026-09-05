# Data Model: Item Request Flow

**Date**: 2026-08-31 · Companion to [plan.md](./plan.md) · 2 new tables,
migration `0005_item_requests_flow`

Requests are immutable flow history: UUID PKs, timestamps, actor columns and
`version` (optimistic locking for decisions/fulfillment), but **no soft
delete and no edit paths** — a request's lines never change after creation
(research R7).

## Entity catalog

### item_requests
| Column | Type | Rules |
|---|---|---|
| requested_by | FK users | NOT NULL; immutable requester (FR-013) |
| purpose_description | text | NOT NULL; non-blank (service-validated) |
| status | text enum | NOT NULL default `pending`; CHECK in (`pending`,`approved`,`rejected`,`fulfilled`) |
| decision_note | text | nullable (approve/reject note) |
| decided_by | uuid | nullable (deciding user) |
| decided_at | timestamptz | nullable |
| fulfilled_at | timestamptz | nullable |
| company_id / complex_id / workplace_id | uuid, nullable | requester's workplace anchor snapshot at creation (research R6); nullable for users without an employee record |
| version | integer | NOT NULL default 1; optimistic-lock guard for decisions/fulfillment |
| mixins | — | ID, Timestamp, CreatedBy, UpdatedBy |

Indexes: `ix_item_requests_requested_by`, `ix_item_requests_workplace_id`,
`ix_item_requests_complex_id`, `ix_item_requests_status`.

### item_request_lines
| Column | Type | Rules |
|---|---|---|
| request_id | FK item_requests | NOT NULL; lines belong to exactly one request |
| item_id | FK item_catalog | NOT NULL; must reference an active item at creation |
| quantity | numeric(14,3) | NOT NULL; **CHECK (quantity > 0)**; ≤3 decimals (service) |
| note | text | nullable (per-line note, ≤500 chars) |
| mixins | — | ID, Timestamp, CreatedBy only |

Constraints: **unique `(request_id, item_id)`** — one line per item per
request (duplicates are a composition error). Immutable: no update/delete
paths exist in code.

## Relationships

- users 1—N item_requests (requested_by)
- item_requests 1—N item_request_lines 1—1 item_catalog (per line)
- item_requests → item_catalog only indirectly through lines
- fulfillment writes Phase-4 `stock_movements` rows (type `fulfillment`)
  against `inventory_placements` — no schema change to those tables
- No changes to any existing table.

## State transitions

```
pending ──approve──▶ approved ──fulfill──▶ fulfilled
   │
   └──reject───▶ rejected
```

- approve/reject: only from `pending`; records `decided_by`/`decided_at` +
  optional note; `version += 1` (guard: `STALE_VERSION` on stale writes).
- fulfill: only from `approved`; sets `fulfilled_at`; `version += 1`; the
  per-line stock decrements and their movements commit or roll back together
  with the status change (one transaction).
- rejected/fulfilled are terminal; no transition or deletion path exists.

## Audit actions (new)

`REQUEST_CREATED` (after-snapshot incl. lines) ·
`REQUEST_APPROVED` · `REQUEST_REJECTED` (before/after status + note + actor) ·
`REQUEST_FULFILLED` (before/after status + per-line movement references and
before/after quantities) — the four §20 domain events
(`ItemRequestCreated/Approved/Rejected/Fulfilled`) expressed as audit actions
until the Phase-8 outbox publishes them.

Masking: request snapshots contain no sensitive fields (purpose text stored
verbatim).

## Migration notes (`0005_item_requests_flow`)

1. Create `item_requests` and `item_request_lines` (+ status/quantity CHECK
   constraints, unique `(request_id, item_id)`, list indexes) — hand-written
   in the established style, `down_revision =
   "0004_warehouse_catalog_inventory"`.
2. Downgrade drops `item_request_lines` then `item_requests`; reversible,
   verified upgrade → downgrade → upgrade on local PG before commit.
3. Seeds add the 3 request permissions and extend the approver/keeper role
   mappings (idempotent re-run).
