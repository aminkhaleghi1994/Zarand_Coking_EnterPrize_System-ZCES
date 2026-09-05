# ZCES — Zarand Coking Enterprise System

A bilingual (English / Persian) enterprise web system for Zarand Coking &
Steel: employee management, warehouse & inventory, item requests, asset
tracking, loans & guarantees, notifications, management reports, system
settings, and complete audit logging.

| | |
|---|---|
| Architecture | Modular Monolith |
| Backend | FastAPI · SQLAlchemy 2.0 · Alembic · Pydantic v2 · Celery + Redis |
| Frontend | Next.js (App Router) · TypeScript · Tailwind CSS · shadcn/ui · TanStack Query |
| Database | PostgreSQL (UUID keys, soft delete, partial unique indexes) |
| Auth | JWT + rotating refresh tokens (HttpOnly cookies) via Next.js BFF; RBAC + hierarchical scopes |
| Locales | `en` (LTR) · `fa` (RTL, Kalameh FaNum, Jalali calendar) |

## Status

**Phase 9 complete (Settings, Reports & Management Dashboard)** — on top
of the Phase 1–8 foundation (platform, auth/RBAC/scopes, org &
employees, warehouse, item requests, assets, loans, notifications):
audited global settings with feature flags, a scope-filtered management
dashboard, four operational reports, and permission-aware masked Excel
exports. Phases 10–11 run sequentially; next:
`hardening-observability`.

## Settings, reports & dashboard (Phase 9)

**Module map**: `backend/app/modules/settings/` (models, defaults,
schemas, repository, service, router, contracts) ·
`backend/app/modules/reports/` (schemas, service, excel, router — owns
no storage; consumes module contracts) · `frontend/src/features/
{settings,reports,dashboard}/` + `app/api/{settings,reports}/**` (BFF
incl. binary export passthrough) · migration `0009_settings`.

**Settings**: a global typed key/value store with a fixed code-defined
key set (low-stock alerting, notification recipients, request approval
policy, dashboard defaults, feature flags). Updates validate the typed
value, guard the version (`STALE_VERSION` on stale writes), and write a
`SETTING_UPDATED` audit row with before/after snapshots in the same
transaction. Contract reads fall back to code defaults — a missing row
never breaks a consumer.

**Dashboard & reports**: every number and row is scope-filtered by the
owning module's filter via published contracts (constitution II + VI) —
a Workplace-scoped manager sees workplace-bounded data. The dashboard
composes counters + by-status breakdowns; the reports cover inventory,
item requests (with status counts over the filtered set), loans
(per-workplace Jalali-year aggregates), and the sensitive-operations
audit report (snapshots visible only with `audit:log:read_full`).

**Excel export**: `GET /reports/export/excel` (permission
`reports:export:excel` + the target report's read permission) exports
the current filtered page via openpyxl — the same scope + masking rules
as the JSON endpoints (masked values written masked, never raw), bilingual
headers per locale, `fa` workbooks RTL with Jalali dates, and RFC 5987
Persian filenames. The BFF streams the workbook through a binary
passthrough forwarding the session cookie.

**Feature flags**: `flags.loan_module_enabled` /
`flags.asset_module_enabled` (plain settings) toggle module nav
visibility without restarts; the dashboard breakdown cards honor
`dashboard.show_*`.

## Notifications (Phase 8)

**Module map**: `backend/app/modules/notification/` (models, schemas,
repository, service, relay, router, contracts) ·
`backend/app/common/bus.py` (thread→asyncio event bus) ·
`frontend/src/features/notifications/` + `app/api/notifications/**` (BFF,
incl. the streaming SSE passthrough) · migration
`0008_notifications_outbox_sse`.

**Outbox model**: every mapped business action appends an `EventOutbox`
row in its own transaction — a rolled-back action leaves no row. The
lifespan-managed relay claims pending events (`FOR UPDATE SKIP LOCKED`,
≤ 50 per 2s poll), resolves scope-driven recipients (explicit users plus
permission-covered holders, implicit deny; deactivated users skipped),
and inserts notifications exactly-once via the partial unique
`(outbox_event_id, user_id)`. Failures retry with backoff (≤ 5 attempts)
then terminally `failed`/`skipped` — never physical deletes, and never
raising into the business transaction.

**Criticality**: `InventoryLowStock` (v1 of the data-driven map) is
Critical — its notification rows are written by `deliver_critical` inside
the alert's commit, so they exist the moment the alert does; everything
else is relay-delivered.

**Live stream + inbox**: `GET /notifications/stream` pushes
`event: notification` frames per user over SSE (Bearer-auth, 15s
keep-alives, no proxy buffering); the inbox endpoints (`GET
/notifications` newest-first, `unread-count`, idempotent mark-read,
read-all) are owner-scoped — a user's inbox is personal data. The BFF
forwards the session cookie (browsers cannot set EventSource headers) and
propagates client disconnects upstream. The header bell's badge and the
open panel refresh within relay latency via the stream.

## Loan module (Phase 7)

**Module map**: `backend/app/modules/loan/` (first dedicated business
module: models, schemas, repository, service, router) ·
`app/common/jalali.py` (dependency-free Gregorian→Jalali) ·
`frontend/src/features/loans/` + `app/api/loan/**` (BFF) · migration
`0007_loan_module`.

**Validation cascade (exact §19 order, first failure wins with the rule
named in `details`)**: ① lifetime request count → ② yearly request count →
③ active loan cap → ④ active guarantee cap. Settled, cancelled, and
soft-deleted requests never free the count limits; only active requests of
the validated Jalali year bind the amount caps; settlement/cancellation
frees the commitment. Submissions lock the policy row, so concurrent
submissions at a boundary resolve to exactly one winner.

**Permissions** (seeded idempotently; `LoanOfficer` has all nine):
`loan:policy:create` `read` `update` `retire` · `loan:request:create` `read`
`activate` `settle` `cancel`. Self-service submission needs authentication
only (own request, ownership-scoped visibility like item requests).

## Asset tracking (Phase 6)

**Module map**: `backend/app/modules/warehouse/asset_repository.py` +
`asset_service.py` (assets are warehouse-domain data) ·
`frontend/src/features/assets/` + `app/api/warehouse/assets/**` (BFF) ·
migration `0006_asset_tracking`.

**Holder model**: an asset is `available` → `assigned` (to an active
employee in scope, or a free-text location) → optionally `returned` →
eventually `retired` (soft delete; blocked while assigned). Retirement frees
the serial for reuse. Every transition appends an `AssetHistory` row
(append-only, from/to holder captured) and an audit record
(`ASSET_CREATED/UPDATED/ASSIGNED/RETURNED/RETIRED`).

**Integrity**: serials are normalized and unique among active assets
(case/whitespace-proof partial unique index — reuse only after retirement);
holder-state consistency is enforced by a DB CHECK plus the service state
machine; concurrent assign/return races resolve to exactly one winner via
optimistic locking (`STALE_VERSION` on stale writes).

**Permissions** (seeded idempotently; `WarehouseKeeper` has all six,
`WarehouseApprover` has `read`): `warehouse:asset:create` `read` `update`
`retire` `assign` `return`.

## Item request flow (Phase 5)

**Module map**: `backend/app/modules/warehouse/request_repository.py` +
`request_service.py` (requests are warehouse-domain data per requirements
§9.2) · `frontend/src/features/requests/` + `app/api/warehouse/requests/**`
· migration `0005_item_requests_flow`.

**Flow**: `pending` → (WarehouseApprover) `approved` / `rejected` →
(keeper) `fulfilled`. Decisions are version-guarded (concurrent decisions
resolve to exactly one winner); fulfillment decrements every line through
`apply_fulfillment_issue` in one all-or-nothing transaction — insufficient
stock refuses atomically with the offending line named. Every transition is
audited (`REQUEST_CREATED/APPROVED/REJECTED/FULFILLED` — the §20 domain
events; notification delivery arrives in Phase 8).

**Permissions**: self-service compose/own-view (any active user,
ownership-scoped) · `warehouse:request:read` (scope-wide visibility) ·
`warehouse:request:decide` (WarehouseApprover) ·
`warehouse:request:fulfill` (WarehouseKeeper).

## Warehouse module (Phase 4)

**Module map**: `backend/app/modules/warehouse/` (models, schemas, repository,
service, router, contracts) · `frontend/src/features/warehouse/` +
`app/api/warehouse/**` (BFF) · migration `0004_warehouse_catalog_inventory`.

**Stock-integrity rules** (constitution III):

- Stock exists only as `InventoryPlacement` (shelf × item) and changes
  exclusively through `StockMovement` rows written atomically in the same
  transaction (`quantity >= 0` CHECK + row-locked decrements — negative
  inventory is structurally impossible).
- Movement types: `receive`, `issue`, `adjust` (+ `fulfillment` reserved for
  Phase 5 via the module contract `apply_fulfillment_issue`, which runs in the
  caller's transaction).
- Low-stock alerts: one active episode per placement (partial unique index),
  raised/resolved transactionally and audited; user-facing delivery arrives
  with the notifications phase.

**Permissions** (`module:resource:operation`, seeded idempotently):

| Resource | Operations |
|---|---|
| `warehouse:item` | `create` `read` `update` `retire` |
| `warehouse:warehouse` | `create` `read` `update` `retire` |
| `warehouse:shelf` | `create` `read` `update` `retire` |
| `warehouse:stock` | `receive` `issue` `adjust` `read` |
| `warehouse:alert` | `read` |

**Roles**: `WarehouseKeeper` — daily catalog + shelf management,
receive/issue (no adjust); `WarehouseApprover` — read-only until the Phase-5
approval flow; `SuperAdmin` — all. Scope anchoring: every warehouse belongs to
one workplace, so warehouse visibility follows Global > Complex > Workplace
exactly like employees.

## Quick start (Windows PowerShell)

1. Configure environment:

   ```powershell
   Copy-Item backend\.env.example backend\.env       # then edit values
   Copy-Item frontend\.env.example frontend\.env.local
   ```

2. Create the dev database (match `backend\.env`):

   ```sql
   CREATE DATABASE zces_dev;
   CREATE USER zces_user WITH PASSWORD '<from .env>';
   GRANT ALL PRIVILEGES ON DATABASE zces_dev TO zces_user;
   ALTER DATABASE zces_dev OWNER TO zces_user;
   ```

3. Bring up both apps:

   ```powershell
   .\scripts\dev-backend.ps1     # venv → deps → alembic → uvicorn :8000
   .\scripts\dev-frontend.ps1    # npm install → next dev :3000
   ```

4. Seed the initial admin + base roles (idempotent, credentials from `backend\.env`):

   ```powershell
   cd backend; .\.venv\Scripts\python.exe -m app.seeds.seed_dev
   ```

5. Verify the phase gates:

   ```powershell
   .\scripts\smoke-test.ps1      # healthz, DB, BFF, EN/FA, error envelope, trace ids, auth
   ```

## Repository layout

```
backend/     FastAPI modular monolith (Phase 1+)
frontend/    Next.js app (DESIGN.md + AGENTS.md inside)
infra/       VM deploy configs (Phase 11)
docs/        Requirements + bilingual implementation reviews
scripts/     Dev/deploy helper scripts
.github/     CI workflows (Phase 1+)
.specify/    Spec Kit workspace (constitution, templates, specs, plans, tasks)
.opencode/   OpenCode commands (speckit.*) + agent skills
```

## Documentation

- `docs/requirements-prompt.txt` — full requirements (Persian, binding)
- `frontend/DESIGN.md` — frontend design system
- `docs/reviews/en/` and `docs/reviews/fa/` — implementation roadmap,
  13-layer engineering review, skills & tooling, improvements (EN + FA)
- `.specify/memory/constitution.md` — governing principles
- `AGENTS.md`, `backend/AGENTS.md`, `frontend/AGENTS.md` — agent guides

## Development

Spec-driven with GitHub Spec Kit — each phase runs:
`/speckit.specify → clarify → plan → analyze → tasks → implement → converge`

Phase gates: app boots · all tests green · manual smoke test passed.

Quality gates (from `backend/` and `frontend/` respectively):

```powershell
# backend
ruff check app tests; mypy app; pytest

# frontend
npm run lint; npx tsc --noEmit; npm run build
```

CI (`.github/workflows/ci.yml`) runs the same gates on every push/PR —
backend with a PostgreSQL 16 service container.

Backend (PowerShell, from `backend/`):

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
alembic upgrade head
pytest
```

Frontend (from `frontend/`):

```powershell
npm run dev      # http://localhost:3000
npm run lint
npm run build
```

## Prerequisites

Python 3.12+ · Node.js LTS · PostgreSQL 16+ (18 in use) · Redis (WSL2 on
Windows dev machines) · Git · uv (for the `specify` CLI).

## License & attribution

Kalameh font family by FontIran (`frontend/src/fonts/kalameh/FontLicense.txt`)
— keep the license file beside the fonts at all times.
