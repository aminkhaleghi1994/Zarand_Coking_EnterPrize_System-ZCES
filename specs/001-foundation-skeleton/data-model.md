# Data Model: Foundation Skeleton

**Date**: 2026-08-29 · Companion to [plan.md](./plan.md)

Phase 1 introduces **no business entities and no business tables**. This document fixes the
shared conventions every later entity inherits, delivered as code (mixins) and verified by a
reversible Alembic baseline.

## 1. Shared column conventions (delivered by mixins)

Every future primary entity composes from these declarative mixins
(`backend/app/common/mixins.py`). Column names are snake_case; tables are plural
snake_case (e.g. `employees`, `warehouses`).

| Mixin | Columns | Rules |
|---|---|---|
| `IDMixin` | `id` UUID PK | server-safe `uuid4` default; all FKs reference UUIDs |
| `TimestampMixin` | `created_at` timestamptz, `updated_at` timestamptz | NOT NULL, DB server defaults (`now()`), `updated_at` onupdate |
| `SoftDeleteMixin` | `deleted_at` timestamptz NULL | physical deletes forbidden; active rows = `deleted_at IS NULL`; uniqueness on active rows uses partial unique indexes (`WHERE deleted_at IS NULL`) |
| `VersionMixin` | `version` integer NOT NULL default 1 | optimistic locking; stale writes → `STALE_VERSION` |
| `CreatedByMixin` | `created_by` UUID NULL | actor attribution (set by services, never client input) |
| `UpdatedByMixin` | `updated_by` UUID NULL | actor attribution |
| `OrgScopeMixin` | `company_id`, `complex_id`, `workplace_id` UUIDs NULL | hierarchical scope columns for every scoped entity (Company > Complex > Workplace); repositories MUST filter by them |

Composition rules for later phases:

- Master-data entities (employees, items, warehouses, policies, settings rows):
  `ID + Timestamp + SoftDelete + Version + CreatedBy + UpdatedBy` (+ `OrgScope` when scoped).
- Append-only ledger entities (stock movements, audit logs, outbox):
  `ID + Timestamp` (+ actor/trace columns as specified by their phase); no soft delete, no
  version — they are never updated.
- Entity conventions are code-level now; their DDL lands with the first real entity
  (Phase 3) and each migration is reviewed for partial indexes and UUID types
  (backend/AGENTS.md).

## 2. Database baseline

- `alembic/` initialized at `backend/alembic/`; `env.py` imports
  `app.core.database.Base.metadata` (offline + online modes).
- Revision `0001_baseline`: empty `upgrade()`/`downgrade()` — a stamp point so future
  autogenerate diffs are clean and the deployment story (`alembic upgrade head`) exists
  from day one.
- Connection config entirely from environment (`DATABASE_URL` or composed
  `DATABASE_*` parts) — `postgresql+psycopg` driver.

## 3. Non-entity runtime shapes (contracts, not tables)

- **Health status**: `{status, app, env, version, components: {database: {status,
  latency_ms?}}}` — see [contracts/health.md](./contracts/health.md).
- **Error envelope**: `{code, message, details?, trace_id}` — see
  [contracts/error-envelope.md](./contracts/error-envelope.md).
- **Page envelope** (ready for Phase 2+): `{items: T[], page, page_size, total}` via
  `common/pagination.py`.

## 4. State / lifecycle

None in this phase (no stateful domain objects). The lifecycle that matters is
operational: app boots → health probed → migrations applied (`alembic_version` stamped).
