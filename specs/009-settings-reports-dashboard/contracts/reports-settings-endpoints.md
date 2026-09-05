# API Contracts: Settings, Reports & Dashboard

**Feature branch**: `feature/009-settings-reports-dashboard` | **Date**: 2026-09-05
Base path `/api/v1` (BFF mirrors under `/api/settings/**` and
`/api/reports/**`). Standard error envelope and list envelope apply.

---

## Settings

### `GET /settings`

Permission `settings:setting:read` (scope: any — global resource).

Response: `{items: [SettingOut], page, page_size, total}` (usually one
page; the fixed key set is ≤ ~12 rows).

`SettingOut`:

```json
{
  "key": "alerting.low_stock_enabled",
  "value": true,
  "value_type": "boolean",
  "description": "Raise notifications when stock drops below threshold",
  "description_fa": "...",
  "version": 3,
  "updated_at": "2026-09-05T10:00:00Z"
}
```

### `PATCH /settings/{key}`

Permission `settings:setting:update`. Body:

```json
{ "value": true, "version": 3 }
```

- Typed validation per key (bool/integer/string/json) — invalid type or
  unknown key → `VALIDATION_ERROR`.
- Stale version → `STALE_VERSION` (`CONFLICT_CONCURRENT_UPDATE` semantics).
- Success → `SettingOut` with bumped `version`; audit row written
  (`SETTING_UPDATED`, before/after snapshots) in the same transaction.

## Dashboard

### `GET /reports/dashboard`

Permission `reports:dashboard:read`. Scope-filtered aggregates.

```json
{
  "counters": {
    "active_employees": 12,
    "catalog_items": 48,
    "open_item_requests": 3,
    "active_loans": 2,
    "unresolved_low_stock_alerts": 1,
    "delivered_notifications": 210
  },
  "item_requests_by_status": { "pending": 1, "approved": 1, "rejected": 0, "fulfilled": 7 },
  "loans_by_status": { "pending": 1, "active": 2, "settled": 4, "cancelled": 0 },
  "low_stock_alerts_by_warehouse": [ { "warehouse": "WH1", "count": 1 } ]
}
```

## Operational reports

All: paginated `{items, page, page_size, total}`, scope-filtered
(constitution II), newest-first or natural order.

### `GET /reports/inventory`

Permission `reports:inventory:read`. Query: `page`, `page_size`,
`warehouse_id?`, `below_min_only?`.

Item: `{item_name, item_name_fa, item_code, unit, warehouse, shelf,
quantity, threshold, below_min}`.

### `GET /reports/requests`

Permission `reports:request:read`. Query: `page`, `page_size`,
`status?` (pending/approved/rejected/fulfilled), `date_from?`, `date_to?`
(ISO; inclusive on dates).

Item: `{id, status, requested_by, purpose_description, line_count,
created_at, decided_at, fulfilled_at}`. Also returns status counts over
the filtered set (first page only): `{status_counts: {...}}` — delivered
as a header object `X`-less: counts are embedded in
`{items, ..., total, status_counts}` (additive field, list envelope
preserved).

### `GET /reports/loans`

Permission `reports:loan:read`. Query: `year?`, `workplace_id?`.

Per workplace+year rows: `{workplace, workplace_name_fa, year,
requests_total, requests_pending, requests_active, requests_settled,
requests_cancelled, active_loan_commitment, active_guarantee_commitment,
policy_max_loan, policy_max_guarantee}` (amounts masked for users without
`audit:log:read_full`? — **No**: loan *caps* are policy data; per-request
amounts are masked per §21. Commitment sums are aggregate figures → kept;
individual request amounts in the audit report are masked.)

### `GET /reports/audit`

Permissions `audit:log:read` (+ `audit:log:read_full` to see snapshot
values). Query: `page`, `page_size`, `action?`, `entity_type?`,
`actor_user_id?`, `date_from?`, `date_to?`.

Item: `{id, actor, action, entity_type, entity_id, before_snapshot,
after_snapshot, trace_id, created_at}` — snapshots masked by the standard
masker; without `read_full`, snapshot *contents* are null (matching the
existing audit endpoint semantics).

## Excel export

### `GET /reports/export/excel`

Permission `reports:export:excel` (masking per audit permissions as
above). Query: `report` (inventory|requests|loans|audit) + the same
filters as the corresponding report endpoint; `locale` (en|fa) for header
language.

Response: binary workbook (≤ page_size rows of the filtered page — same
bound as the screen), headers:

```
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename="inventory-report-2026-09-05.xlsx"
```

- Rows identical to the report endpoint's filtered page; masking applied
  identically (no raw sensitive values for users without
  `audit:log:read_full`).
- `fa` workbooks use RTL sheet view + Persian headers + Jalali dates.
- Empty filter result → valid workbook with headers only.

## Frontend BFF routes

- `/api/settings` (GET list), `/api/settings/[key]` (PATCH)
- `/api/reports/dashboard`, `/api/reports/inventory`,
  `/api/reports/requests`, `/api/reports/loans`, `/api/reports/audit`
- `/api/reports/export` — binary passthrough (cookie → Bearer, upstream
  Content-Type/Content-Disposition forwarded verbatim)
