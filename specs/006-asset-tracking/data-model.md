# Data Model: Asset Tracking

**Date**: 2026-08-31 · Companion to [plan.md](./plan.md) · 2 new tables,
migration `0006_asset_tracking`

Assets are master data (soft delete + version) with a typed current-holder;
history is append-only (no update/delete paths).

## Entity catalog

### asset_instances
| Column | Type | Rules |
|---|---|---|
| name / name_fa | text(200) | NOT NULL |
| serial | text(100) | NOT NULL; immutable after creation |
| serial_norm | text(100) | NOT NULL; maintained = `lower(btrim(serial))`; **partial unique** on active rows |
| description | text | nullable |
| holder_type | text enum | nullable; CHECK in (`employee`, `location`); NULL = available |
| holder_employee_id | FK employees | nullable |
| holder_location | text(200) | nullable |
| company_id / complex_id / workplace_id | uuid nullable | creator's workplace anchor snapshot (research R6) |
| version | integer | NOT NULL default 1; optimistic-lock guard |
| mixins | — | ID, Timestamp, SoftDelete, Version, CreatedBy, UpdatedBy |

Constraints:
- **CHECK holder-state consistency** — exactly one of:
  - available: `holder_type IS NULL AND holder_employee_id IS NULL AND holder_location IS NULL`
  - employee-held: `holder_type='employee' AND holder_employee_id IS NOT NULL AND holder_location IS NULL`
  - location-held: `holder_type='location' AND holder_employee_id IS NULL AND holder_location IS NOT NULL`
- **partial unique** `(serial_norm)` on active rows
- indexes: `workplace_id`, `complex_id`, `serial_norm` (search), `holder_employee_id`

### asset_histories
| Column | Type | Rules |
|---|---|---|
| asset_id | FK asset_instances | NOT NULL |
| action | text enum | NOT NULL; CHECK in (`created`, `updated`, `assigned`, `returned`, `retired`) |
| from_type / to_type | text enum | nullable (`employee` / `location`) |
| from_employee_id / to_employee_id | FK employees | nullable |
| from_location / to_location | text(200) | nullable |
| note | text(500) | nullable |
| mixins | — | ID, Timestamp, CreatedBy (actor) — append-only |

Indexes: `(asset_id, created_at DESC)` for the timeline, `to_employee_id`.

## Relationships

- workplaces 1—N asset_instances (via creator anchor; nullable for
  anchorless creators)
- asset_instances 1—N asset_histories
- employees referenced by `holder_employee_id` / history from-to columns
  (RESTRICT — employees are soft-deleted, never physically removed)
- No changes to existing tables.

## State transitions

- **asset**: available ⇄ assigned (assign/return with version guard);
  available → retired (blocked while assigned); assigned/retired rows are
  immutable history — no physical delete.
- **history entry**: written once in the same transaction as the action it
  records; never mutated.

## Audit actions (new)

`ASSET_CREATED` · `ASSET_UPDATED` · `ASSET_ASSIGNED` · `ASSET_RETURNED` ·
`ASSET_RETIRED` — the §18 events `AssetAssigned`/`AssetReturned` plus the
lifecycle complement. Snapshots include before/after holder state.

## Migration notes (`0006_asset_tracking`)

1. Create `asset_instances` (+ holder-state CHECK, serial partial unique,
   org indexes) and `asset_histories` (+ action CHECK, timeline index) —
   hand-written, `down_revision = "0005_item_requests_flow"`.
2. Downgrade drops histories then instances; reversible, verified
   upgrade → downgrade → upgrade on local PG before commit.
3. Seeds add the 6 asset permissions and extend the keeper/approver role
   mappings (idempotent re-run).
