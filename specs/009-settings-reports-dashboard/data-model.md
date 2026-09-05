# Data Model: Settings, Reports & Management Dashboard

**Feature branch**: `feature/009-settings-reports-dashboard` | **Date**: 2026-09-05
**Source**: spec.md, research.md decisions (R1, R2).

---

## Entities

### Setting (`settings`)

Global typed key/value row. Never physically deleted. One row per key from
the fixed code-defined key set (research R2).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID PK | | |
| key | VARCHAR(100) | NOT NULL, UNIQUE | e.g. `alerting.low_stock_enabled` |
| value | JSONB | NOT NULL | typed by `value_type` |
| value_type | VARCHAR(10) | NOT NULL, CHECK IN ('boolean','integer','string','json') | |
| description | TEXT | NOT NULL | English description |
| description_fa | TEXT | NOT NULL | Persian description |
| version | INTEGER | NOT NULL, DEFAULT 1 | optimistic lock (§25) |
| created_at / updated_at | TIMESTAMPTZ | | |

**Indexes / constraints**

- `uq_settings_key` UNIQUE `(key)` — one row per key (no soft-delete state:
  settings are never deleted, so a plain unique is correct).
- CHECK `ck_settings_value_type`.

**Semantics**

- Rows are created by seed (idempotent) with code defaults; only `value`
  and `version` change at runtime.
- Updates: service validates the typed value, checks the submitted
  `version` (mismatch → `STALE_VERSION`), bumps it, and writes the audit
  row (`action='SETTING_UPDATED'`, `entity_type='setting'`,
  `entity_id=key`, before/after snapshots) in the same transaction.
- Reads: contract `get_setting(session, key)` returns the typed value with
  the code default as fallback; unknown keys never reach storage.

**Seeded key set (v1 — research R2)**

| Key | value_type | Default | Consumer |
|---|---|---|---|
| alerting.low_stock_enabled | boolean | true | warehouse low-stock alert raise |
| alerting.low_stock_notify_broadcast | boolean | true | notification recipients mode |
| notifications.default_recipients | json | [] | fallback recipient ids |
| requests.approval_require_note | boolean | true | request approve/reject note requirement |
| dashboard.show_alerts_breakdown | boolean | true | dashboard card |
| dashboard.show_requests_breakdown | boolean | true | dashboard card |
| flags.loan_module_enabled | boolean | true | loans nav/UI |
| flags.asset_module_enabled | boolean | true | assets nav/UI |

### Migration `0009_settings`

Creates `settings` with the above columns, unique, and CHECK. Reversible
(drop table). No changes to existing tables.

---

## Report projections (no storage — read-only)

Views over existing data, produced via module contracts (research R3):

- **DashboardOut**: counters (active_employees, catalog_items,
  open_item_requests, active_loans, unresolved_low_stock_alerts,
  delivered_notifications) + breakdowns (item_requests_by_status,
  low_stock_alerts_by_warehouse, loans_by_status) — each element
  scope-filtered by the owning module's filter.
- **InventoryReportRow**: item (name/name_fa/code/unit), warehouse,
  shelf, quantity, threshold, below_min flag.
- **RequestReportRow**: id, status, requester display, purpose, line count,
  created/decided/fulfilled timestamps.
- **LoanReportRow**: workplace, year, request counts by status, active
  loan/guarantee commitments, policy caps.
- **AuditReportRow**: actor display, action, entity_type, entity_id, masked
  before/after snapshots, trace_id, created_at.

Excel exports (research R4) serialize the same row DTOs; no additional
schema.
