# Data Model: Organizational Structure & Employee/User Management

**Date**: 2026-08-31 · Companion to [plan.md](./plan.md) · 4 new tables, migration `0003_org_user_module`

All tables: UUID PK (`IDMixin`), timestamps (`TimestampMixin`), actor columns
(`CreatedByMixin`/`UpdatedByMixin`). Org + employee entities add
`SoftDeleteMixin` + `VersionMixin`. Uniqueness on active rows via partial
unique indexes (`WHERE deleted_at IS NULL`).

## Entity catalog

### companies
| Column | Type | Rules |
|---|---|---|
| code | text | NOT NULL; **unique** (natural seed key, e.g. `ZCS`) |
| name | text | NOT NULL (English display name) |
| name_fa | text | NOT NULL (Persian display name) |
| mixins | — | ID, Timestamp, SoftDelete, Version, CreatedBy, UpdatedBy |

Single row in v1 (seeded); uniqueness on `code` (not partial — codes are
immutable natural keys that must stay unique across soft-deleted rows too).

### complexes
| Column | Type | Rules |
|---|---|---|
| company_id | FK companies | NOT NULL |
| code | text | NOT NULL; **unique** (`CTR`, `SM`) |
| name / name_fa | text | NOT NULL |
| mixins | — | full set incl. SoftDelete + Version |

### workplaces
| Column | Type | Rules |
|---|---|---|
| complex_id | FK complexes | NOT NULL |
| code | text | NOT NULL; **unique** (`KCM`, `CP1`, `CP2`, `SP`) |
| name / name_fa | text | NOT NULL |
| mixins | — | full set incl. SoftDelete + Version |

### employees
| Column | Type | Rules |
|---|---|---|
| workplace_id | FK workplaces | NOT NULL; exactly one workplace |
| national_id | text(10) | NOT NULL; digits-only service validation; **partial unique** on active rows; immutable; masked in audit/exports |
| personnel_code | text | NOT NULL; non-empty; **partial unique** on active rows; immutable |
| first_name / last_name | text | NOT NULL |
| first_name_fa / last_name_fa | text | nullable (bilingual display) |
| birth_date | date | nullable |
| phone | text | nullable |
| is_active | bool | NOT NULL default true; mirrors user activation |
| mixins | — | ID, Timestamp, SoftDelete, Version, CreatedBy, UpdatedBy |

Indexes: partial unique (`national_id`, `personnel_code` on active rows),
`workplace_id`, `last_name` (search).

### users (changed)
| Column | Type | Rules |
|---|---|---|
| employee_id | FK employees, **unique** | nullable at the schema level (Phase-2 admin user has no employee); every employee's user has it — enforces 1:1 |
| — | — | existing columns unchanged |

The unique FK is the 1:1 constraint. Backfill not required (seed admin has no
employee record by design — it is a bootstrap identity, not a person).

### scope_assignments (changed)
`complex_id` / `workplace_id` become real FK columns to `complexes` /
`workplaces` (Phase 2 left them plain UUIDs). Resolver behavior unchanged;
deactivated units still match (historical scopes remain resolvable) but no new
assignments may reference a deactivated unit (service check).

## Relationships

- companies 1—N complexes 1—N workplaces 1—N employees
- employees 1—1 users (unique FK on users.employee_id)
- user_roles / role_permissions / scope_assignments / refresh_tokens unchanged
- audit_logs unchanged (logical reference only)

## State transitions

- employee: active ⇄ deactivated (soft delete + `is_active`); deactivation ⇒
  linked user `is_active=false` + all refresh families revoked (same txn);
  reactivation reverses employee+user activation only.
- employee identity anchors (`national_id`, `personnel_code`) never change;
  edits touch names/contact/workplace with `version` guard.
- org records: created by seed; deactivation supported (disappears from
  pickers, historically referenceable); no physical delete.

## Audit actions (new)

`ORG_SEEDED` (dev/prod seed run, after-snapshot of tree) ·
`EMPLOYEE_CREATED` · `EMPLOYEE_UPDATED` · `EMPLOYEE_MOVED` ·
`EMPLOYEE_DEACTIVATED` · `EMPLOYEE_REACTIVATED` · `USER_PASSWORD_SET` ·
(existing `ROLE_*`, `SCOPE_*` actions from Phase 2)

Masking: `national_id` via `mask_identifier` (shows last 4); password material
never enters snapshots.

## Migration notes (`0003_org_user_module`)

1. Create `companies`, `complexes`, `workplaces`, `employees` (+ indexes).
2. Add `users.employee_id` (unique FK, `ON DELETE` never — soft delete only).
3. Convert `scope_assignments.complex_id/workplace_id` to real FKs.
4. Downgrade drops in reverse order (reversible; verified upgrade → downgrade
   → upgrade on local PG before commit).
