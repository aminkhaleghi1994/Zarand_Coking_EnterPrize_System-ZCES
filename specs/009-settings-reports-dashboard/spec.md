# Feature Specification: Settings, Reports & Management Dashboard

**Feature Branch**: `feature/009-settings-reports-dashboard`

**Created**: 2026-09-05

**Status**: Draft

**Input**: Phase 9 of the implementation roadmap (`docs/reviews/en/01-implementation-roadmap.md`): "Settings + feature flags (audited); management dashboard; inventory/request/loan/audit reports; Excel export with permission-aware masking" — sourced from `docs/requirements-prompt.txt` §3.1 (reports & settings bullets), §24 (Settings/Reports endpoints), §21 (audit of setting changes + masking rules), §25 (optimistic locking on setting updates).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sensitive-operations report & Excel export (Priority: P1)

An Auditor opens the sensitive-operations report: a filterable, paginated
list of audit entries (actor, entity, action, before/after snapshots,
trace id, timestamp). Sensitive fields in the snapshots are masked unless
the Auditor holds the unmask-level permission. The Auditor exports the
current filtered view to Excel; the downloaded file respects exactly the
same masking rules (masked values are exported masked).

**Why this priority**: requirements §3.1 names "گزارش عملیات حساس"
(sensitive-operations report) and "خروجی Excel با رعایت سطح دسترسی و
Masking" as core deliverables; this is the compliance surface the whole
audit trail (Phases 2–8) exists to serve.

**Independent Test**: sign in as an Auditor, open the sensitive-operations
report, filter by action and date range, export to Excel, open the file —
masked fields stay masked; a user without the report permission gets 403.

**Acceptance Scenarios**:

1. **Given** audit rows exist from earlier phases, **When** the Auditor
   opens the sensitive-operations report, **Then** rows render paginated
   newest-first with actor, action, entity, masked snapshots, trace id,
   and Jalali (fa) / Gregorian (en) timestamps.
2. **Given** the Auditor holds only masked-level visibility, **When** a
   snapshot contains a national id, **Then** only the last few digits are
   displayed.
3. **Given** the Auditor applies filters (action, date range), **When** a
   page is exported to Excel, **Then** the file contains exactly the rows
   the Auditor is allowed to see, with the same masking applied.
4. **Given** a user without the sensitive-operations report permission,
   **When** they call the report endpoint, **Then** the request is denied.

---

### User Story 2 - Operational reports: inventory, item requests, loans (Priority: P1)

A Manager needs trustworthy overviews: the inventory report (placements
with quantities, thresholds, low-stock flags, per warehouse), the item
request report (status counts and per-status listing over a date range),
and the loan report (policy caps, request counts, active commitments per
workplace/year). All three are scope-filtered: a Manager only ever sees
rows their scopes cover, and each is exportable to Excel with the same
rules.

**Why this priority**: "نبود گزارش‌های قابل اعتماد" (no trustworthy
reports) is a stated pain point in §2.1; these three reports turn the
existing warehouse/loan data into decision material.

**Independent Test**: sign in as a Manager with a Workplace-level scope,
open each report, verify only in-scope rows appear, and export each to
Excel.

**Acceptance Scenarios**:

1. **Given** inventory across multiple warehouses, **When** the Manager
   opens the inventory report, **Then** only placements their scopes
   cover are listed (quantity, threshold, low-stock flag, warehouse) and
   totals are computed over that filtered set.
2. **Given** item requests in all four statuses, **When** the Manager
   opens the request report with a date range, **Then** status counts and
   rows respect the range and their scope.
3. **Given** loan requests and policies, **When** the Manager opens the
   loan report, **Then** per-workplace yearly figures (requests, active
   loan/guarantee commitments) respect their scope.
4. **Given** any of the three reports, **When** the Manager exports,
   **Then** the Excel file matches the on-screen filtered rows.

---

### User Story 3 - Management dashboard (Priority: P1)

A Manager signs in and sees a management dashboard: headline counters
(active employees, catalog items, open item requests, active loans,
unresolved low-stock alerts, notifications delivered), plus simple
breakdowns (item requests by status, loans by status, low-stock alerts by
warehouse). Every number is scope-filtered, so a Workplace-scoped Manager
sees their world, not the company's.

**Why this priority**: "داشبورد پایه مدیریتی" is the first reports &
dashboard bullet in §3.1; it is the daily landing surface for managers
and the natural home page upgrade.

**Independent Test**: seed data exists; sign in as a Global-scoped
Manager, verify counters match the seeded counts; sign in as a
Workplace-scoped user, verify smaller numbers.

**Acceptance Scenarios**:

1. **Given** seeded data, **When** a Global-scoped Manager opens the
   dashboard, **Then** counters equal the global totals.
2. **Given** the same data, **When** a Workplace-scoped Manager opens the
   dashboard, **Then** counters cover only that workplace's data.
3. **Given** a user without the dashboard permission, **When** they call
   the dashboard endpoint, **Then** the request is denied.

---

### User Story 4 - System settings with audit trail (Priority: P2)

An operator opens the settings page and adjusts global settings: the
low-stock alerting behavior, the notification recipient defaults, the
item-request approval policy, and dashboard defaults. Every change is
version-guarded (concurrent edits are rejected with a stale-version
error) and audited with before/after snapshots; the change log is visible
in the sensitive-operations report. Feature flags toggle module features
on/off without code changes.

**Why this priority**: "تنظیمات" (settings) bullets in §3.1 and §21
("تغییر تنظیمات" audited) make settings audited mutable state — required
for operators to tune alerting/approval behavior, but not blocking for
the read-only reports.

**Independent Test**: change the low-stock alert threshold behavior,
verify the before/after audit row appears, then submit the same change
with an old version and verify it is rejected.

**Acceptance Scenarios**:

1. **Given** the settings page, **When** a setting is updated, **Then**
   the new value applies immediately and an audit row records
   before/after with the actor and trace id.
2. **Given** two operators editing the same setting, **When** the second
   saves with the first's stale version, **Then** the save is rejected
   with a stale-version error.
3. **Given** a feature flag is off, **When** a user opens the affected
   surface, **Then** the feature is hidden/disabled without errors.
4. **Given** a user without settings permission, **When** they call the
   settings endpoints, **Then** the requests are denied.

### Edge Cases

- Empty report filters that match no rows → standard empty page (items
  [], total 0), not an error.
- Excel export of an empty filtered view → a valid workbook with headers
  only.
- A deactivated employee referenced in report rows → still listed
  (reports are historical), with name rendered and user state shown as
  inactive.
- Unknown setting key on update → validation error; the key set is fixed
  and seeded.
- Export while data changes underneath → the export snapshot is taken
  once at request time (rows consistent with what the filters produced
  at that moment).
- Masked fields in Excel: cells contain the masked string; no hidden
  columns or cell comments leak raw values.
- Very large exports → bounded by the same pagination limits as the
  screen (page-consistent export, not an unbounded dump).
- Settings seed on a fresh database → defaults exist before first use;
  re-running the seed is idempotent.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a paginated, filterable
  sensitive-operations (audit) report covering actor, action, entity
  type/id, masked snapshots, trace id, and timestamp, newest first.
- **FR-002**: The system MUST mask sensitive snapshot fields
  (national_id, personnel_code, loan amounts, asset assignment data,
  credentials/tokens/secrets) in the report surface; unmasked values
  MUST be available only to holders of the unmask-level permission.
- **FR-003**: The system MUST provide an inventory report: per-placement
  quantity, threshold, low-stock flag, and warehouse/shelf context,
  scope-filtered, with filtered-set totals.
- **FR-004**: The system MUST provide an item-request report: per-status
  counts and listings filterable by date range and status, scope-aware
  (requester-own rows for users without management scope).
- **FR-005**: The system MUST provide a loan report: per-workplace
  yearly request counts, active loan/guarantee commitments, and policy
  caps, scope-filtered.
- **FR-006**: The system MUST provide Excel exports of the audit,
  inventory, item-request, and loan reports that contain exactly the
  rows the requesting user's filters and permissions produce, with the
  same masking rules applied in the workbook.
- **FR-007**: The system MUST provide a management dashboard with
  scope-filtered headline counters (active employees, catalog items, open
  item requests, active loans, unresolved low-stock alerts, delivered
  notifications) and by-status/by-warehouse breakdowns.
- **FR-008**: The system MUST provide global settings storage with a
  fixed, seeded key set covering: low-stock alert behavior,
  notification recipient defaults, item-request approval policy, and
  dashboard defaults.
- **FR-009**: Settings updates MUST be version-guarded (stale versions
  rejected with the standard stale-version error) and audited with
  before/after snapshots, actor, and trace id in the same transaction.
- **FR-010**: The system MUST support feature flags stored as settings,
  toggleable without code changes or restarts.
- **FR-011**: All report/dashboard queries MUST apply the mandatory
  scope filter (permission AND scope); scope-less access to report data
  MUST be denied.
- **FR-012**: Every report/dashboard surface MUST be fully bilingual
  (English + Persian) with Jalali calendar rendering for `fa` and RTL
  layout.
- **FR-013**: Export responses MUST be streamed as spreadsheet files
  (correct content type and filename) and never embed unmasked sensitive
  values for users without the unmask permission.
- **FR-014**: New permissions MUST be seeded idempotently for settings
  read/update, dashboard view, and each report/export, mapped to the
  Manager and Auditor roles per the requirements role table.

### Key Entities *(include if feature involves data)*

- **Setting**: a global key/value record (fixed key set: low-stock alert
  behavior, notification recipient defaults, request approval policy,
  dashboard defaults, feature flags) with typed value, description, and
  optimistic version; never physically deleted; changes audited.
- **Report view** (read-only, no new storage): scope-filtered projections
  over existing audit, warehouse, request, and loan data.
- **Dashboard view** (read-only): scope-filtered aggregates over
  employees, catalog, requests, loans, alerts, and notifications.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A Manager can answer "what do I own, what is low, what is
  open, what is committed" for their scope entirely from the dashboard +
  reports in under 2 minutes without touching raw lists.
- **SC-002**: 100% of sensitive fields are masked in both screen and
  Excel surfaces for users without the unmask permission — verified by
  full-value absence checks on exports.
- **SC-003**: Report pages and the dashboard render for both locales
  (`en` LTR, `fa` RTL with Jalali dates and Farsi digits) and at 375px
  and 1440px widths without layout breakage.
- **SC-004**: Every settings change produces exactly one audit row with
  before/after snapshots; stale-version writes are 100% rejected.
- **SC-005**: Exported workbooks open cleanly in a standard spreadsheet
  application, contain the filtered rows, and respect masking; header
  rows are bilingual per the requesting locale.
- **SC-006**: A scope-restricted user never sees a row, total, or
  exported cell outside their scope (spot-checked per report).

## Assumptions

- Global-only settings in v1 (user decision 2026-09-05); per-workplace
  overrides are deferred.
- Reports are read-only projections over existing module data via
  published contracts — no new fact tables or ETL.
- The existing audit module's masking rules and permission model are
  reused and extended (unmask-level permission) rather than rebuilt.
- Exports are synchronous request-scoped files sized by the same
  pagination bounds as the screens; async/scheduled exports are out of
  scope for v1.
- Seeded default settings are sensible for a fresh install; no settings
  migration from external sources.
- Dashboard refresh cadence is user-driven (navigation/query) with
  standard cache staleness; no live-pushing of report numbers in v1
  (notifications SSE already covers event-driven awareness).
