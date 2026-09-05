# Research: Settings, Reports & Management Dashboard

**Feature branch**: `feature/009-settings-reports-dashboard` | **Date**: 2026-09-05
**Inputs**: spec.md, requirements §3.1 (reports/settings), §21 (audit+masking),
§24 (endpoints), §25 (optimistic locking on setting updates), §28 (performance),
platform patterns Phases 2–8.

---

## R1 — Settings storage model (typed global KV)

**Decision**: a single `settings` table — one row per key from a fixed,
code-defined key set (`defaults.py`), each with `key` (unique), `value`
(JSONB), `value_type` ('boolean'|'integer'|'string'|'json'), `description`,
bilingual `description_fa`, and `version`. No physical deletes; updates bump
`version` (optimistic lock, requirements §25) and write an audit row with
before/after snapshots in the same transaction. Seeding inserts defaults
idempotently.

**Rationale**: global-only scope decided by the user (2026-09-05); a typed
schema per setting (one wide table with many columns) would require a
migration for every new setting — a KV with typed values keeps the key set
in code (validated, documented) while the storage stays one table.
JSONB matches the existing JSONB usage (outbox payloads). The fixed key set
is enforced by the service layer (unknown key → VALIDATION_ERROR), keeping
"the key set is seeded" true without a DB enum.

**Alternatives considered**: per-setting columns (migration per change —
rejected); env-file settings (not runtime-editable, not auditable — rejected);
per-workplace rows (deferred by decision).

## R2 — Settings key set (v1)

**Decision**: the seeded key set covers exactly the §3.1 bullets:

- `alerting.low_stock_enabled` (bool, default true) and
  `alerting.low_stock_notify_broadcast` (bool, default true) — whether low-stock
  alerts raise notifications and whether the recipient set is the
  scope-covered broadcast (true) or only the configured list (false).
- `notifications.default_recipients` (json, default []) — fallback user id
  list when broadcast is off.
- `requests.approval_require_note` (bool, default true) — whether
  approve/reject must carry a decision note.
- `dashboard.show_alerts_breakdown` / `dashboard.show_requests_breakdown`
  (bool, default true) — dashboard card visibility (feature-flag style).
- `flags.loan_module_enabled`, `flags.asset_module_enabled` (bool, default
  true) — feature flags toggling module UI visibility without restarts.

**Rationale**: each key maps to a §3.1 settings bullet; feature flags are
plain settings (FR-010) so no separate flag machinery is built
(constitution VIII). Consumers read via the settings contract with a typed
default fallback, so a missing row never breaks a module.

**Alternatives considered**: a separate flags table (two mechanisms for one
behavior — rejected).

## R3 — Cross-module data access for reports

**Decision**: the `reports` module owns **no models and no repositories**.
It consumes each source module's published contract: `audit.contracts` (NEW
filtered page of audit rows), `warehouse.contracts` gains filtered list
functions (placements, alerts, requests summaries), `loan.contracts` (NEW:
per-workplace aggregates), `user.contracts` (NEW: employee counts), and the
notification repository total. Each contract function takes the
`ScopeContext` + the module's own scope filter — the scope filter logic
stays in the module that owns the data (constitution II and VI both
satisfied).

**Rationale**: reports are projections (spec assumption); duplicating scope
filters in a reports repository would drift from the source modules'
filters. Contract dataclasses keep the reports layer decoupled from ORM
models.

**Alternatives considered**: SQL views in the DB (bypasses scope logic —
rejected); reports importing other modules' repositories directly
(constitution VI violation — rejected).

## R4 — Excel export strategy

**Decision**: openpyxl (added to `requirements-dev.txt` and
`requirements.txt` if split; write_only mode for low memory). Export is
synchronous, bounded by the same page_size limits as the screen (≤ 200 rows
per request — the page the user sees), built from exactly the same
scope+masking-filtered page the endpoint would return. Response streamed
with `Content-Type
application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` and
`Content-Disposition: attachment; filename=...`. Headers are bilingual per
locale (`en`/`fa` column titles; `fa` workbook is RTL sheet view).

**Rationale**: single-VM simplicity (no Celery export jobs — constitution
VIII); page-bounded exports keep memory and latency flat; openpyxl is the
standard pure-python xlsx writer (no system deps) and the smallest surface
that satisfies "خروجی Excel". Masking: export reuses the same
mask_snapshot path; users without `audit:log:read_full` get masked values
*in the workbook* (never raw) — no hidden columns/comments.

**Alternatives considered**: pandas+xlsxwriter (heavier deps — rejected);
CSV (not "Excel" — rejected); async export jobs (out of v1 scope).

## R5 — Dashboard aggregation approach

**Decision**: count()/group_by queries executed in the source modules'
repositories behind contracts (e.g. `warehouse.contracts.count_open_alerts(scope_context)`),
composed by the reports service into one `DashboardOut` DTO. No
materialized aggregates, no cache (v1 scale: seeded data; p95 < 500ms per
requirements §28 is achievable with direct counts).

**Rationale**: keeps scope filters in owner modules (R3) and avoids cache
invalidation machinery (constitution VIII). Breakdowns are small
(fixed status enums, workplace count ≤ dozens).

## R6 — Permissions and role mapping

**Decision**: new permissions, seeded idempotently:

- `settings:setting:read` / `settings:setting:update`
- `reports:dashboard:read`
- `reports:inventory:read`, `reports:request:read`, `reports:loan:read`,
  `reports:audit:read` (audit report reuses `audit:log:read` semantics but
  a distinct code is unnecessary — **decision: reuse `audit:log:read` +
  `audit:log:read_full`** for the sensitive-operations report to avoid two
  permission gates over the same data)
- `reports:export:excel` (one export permission across reports; masking
  still governed by `audit:log:read_full`)

Role maps: Manager gets `reports:dashboard:read`, all three operational
report reads, `reports:export:excel`, `settings:setting:read`; Auditor gets
the audit-report reads (already has `audit:log:read*`) + `reports:export:excel`;
SuperAdmin everything; HRAdmin/WarehouseKeeper/etc. unchanged. Scope-wise
these are new module:resource:operation targets, so scope assignments
follow the existing pattern (admin UI already generic).

**Rationale**: minimal new permission surface; reusing audit permissions for
the audit report prevents divergence of "who sees audit data". Export is a
distinct operation (§3.1 calls it out) but one code across report types
keeps the matrix small.

## R7 — Audit of settings changes

**Decision**: `settings.service.update_setting` runs in one transaction:
SELECT the row (plain read), validate the typed value (Pydantic per key),
bump `version`, write the audit row via the existing audit contract with
`action='SETTING_UPDATED'`, `entity_type='setting'`, entity_id = key,
before/after snapshots of `{key, value, value_type}` — snapshots masked with
the standard masker (values are not secrets by key-set design, but the path
is uniform). Stale version → `STALE_VERSION` error before any write.

**Rationale**: §21 lists "تغییر تنظیمات" among audited operations; the
platform's write_audit is the established mechanism. A `SETTING_UPDATED`
event is NOT added to the outbox (not in the §20 13-event set — adding a
14th event type would violate the fixed event CHECK without a requirements
basis; settings visibility is immediate on next read).

## R8 — BFF passthrough for binary exports

**Decision**: the BFF export route forwards the access cookie as Bearer
(same as proxyToBackend) but returns the upstream bytes verbatim with
upstream Content-Type/Content-Disposition instead of parsing JSON. ~10 lines
alongside bff-proxy (a `proxyFileToBackend` helper). The browser triggers
download via a normal link (`<a href>`/window.location) — no fetch needed,
so no CSRF concern (GET, no side effects).

**Rationale**: the existing JSON proxy buffers+re-parses bodies; exports are
the one binary path in v1. A dedicated helper keeps both paths explicit.
GET-only export (side-effect free, snapshot per request) avoids CSRF
complexity.

## R9 — Frontend surface plan

**Decision**: three areas:

1. **Dashboard** (`features/dashboard/`): the existing home page becomes
   the management dashboard for users holding `reports:dashboard:read`
   (fallback to the current module-overview for others — no permission
   regression). Counter cards (Soft Lift) + two breakdown cards
   (requests-by-status, alerts-by-warehouse) with visibility flags read
   from settings.
2. **Reports** (`features/reports/ReportsConsole.tsx`): tabs for
   inventory/requests/loans/audit; per-tab filter forms, paginated tables
   (card collapse on mobile), export button → `/api/reports/export?...`
   download; Jalali dates in `fa`.
3. **Settings** (`features/settings/SettingsConsole.tsx`): grouped
   setting forms rendered by value_type (bool → switch, integer → number
   input, json → textarea with validation), stale-version surfacing
   (refetch + error message), feature flags grouped under "Feature flags".

**Rationale**: reuses the LoansConsole tab pattern and the established
table→card, skeleton, and i18n conventions; dashboard fallback keeps the
home page meaningful for non-managers.

**Alternatives considered**: separate dashboard micro-app (overkill);
settings modal (settings deserve a page for audit gravity).
