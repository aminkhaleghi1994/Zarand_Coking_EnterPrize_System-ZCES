# Research: Foundation Skeleton

**Date**: 2026-08-29 · Resolves all technical unknowns for [plan.md](./plan.md)

## R1 — Dependency set for Phase 1 (backend)

**Decision**: Runtime: `fastapi`, `uvicorn[standard]`, `sqlalchemy>=2.0`, `alembic`,
`psycopg[binary]`, `pydantic>=2`, `pydantic-settings`. Dev: `pytest`, `httpx`,
`ruff`, `mypy`. Pinned with `~=` to current majors at implementation time.

**Rationale**: Exactly the constitution stack. Auth (`python-jose`/`passlib`),
`redis`, `celery`, `structlog` are deferred to the phase that needs them
(constitution VIII). `httpx` is required by FastAPI's TestClient transport.

**Alternatives considered**: full requirements §31 install list now (rejected —
installs unused auth/queue code and invites configuration drift); async SQLAlchemy
(rejected — AGENTS.md mandates sync sessions).

## R2 — Configuration approach

**Decision**: Single `Settings` class in `app/core/config.py` (pydantic-settings,
`env_file=".env"`, `extra="ignore"`), exposing app/env/debug, database URL + parts,
CORS origins, log level, API prefix. `.env.example` carries the FULL requirements §30
set (JWT/cookie/seed-admin placeholders included) so later phases only add code.

**Rationale**: Fail-fast validation with typed config; `extra="ignore"` lets one
template serve all phases without breaking Phase 1 startup. Secrets never printed:
settings dumps are forbidden; errors name the variable, never the value.

**Alternatives considered**: read-each-phase settings (rejected — template churn);
python-decouple (rejected — pydantic-settings is the constitution stack).

## R3 — Trace correlation

**Decision**: `X-Request-ID` as the canonical header. ASGI middleware reads it (non-empty
→ adopt; else generate `uuid4`), stores it in a `contextvar`, echoes it on the response,
and a logging filter injects it into every record. Error envelope `trace_id` reads the
contextvar.

**Rationale**: One middleware + one filter covers header propagation, envelope, and logs
with no per-endpoint code. Requirements call the concept `trace_id`; the HTTP header
convention `X-Request-ID` is standard and documented in the contract.

**Alternatives considered**: OpenTelemetry now (rejected — constitution VIII defers
observability depth to Phase 10; contextvar design is OTel-compatible later).

## R4 — Error envelope mechanics

**Decision**: `AppError(code, message, details, status_code)` + exception handlers:
`AppError` → its status; FastAPI `RequestValidationError` → 422 `VALIDATION_ERROR`;
`StarletteHTTPException` → mapped standard code (404 → `RESOURCE_NOT_FOUND`, 405 →
`BUSINESS_RULE_VIOLATION`, others → `INTERNAL_ERROR` except auth codes reserved for
Phase 2); unhandled `Exception` → 500 `INTERNAL_ERROR` with log traceback, no internals
in the body. OpenAPI documents the envelope via a shared response model.

**Rationale**: Guarantees FR-006 for every failure path, including unknown routes and
framework-level validation, without per-router boilerplate.

**Alternatives considered**: middleware-only rewriting (rejected — double-handling and
lost exception context); per-endpoint try/except (rejected — unenforceable).

## R5 — Health endpoint semantics

**Decision**: `GET /healthz` (root level, also mounted under the API prefix for gateway
consistency). Always HTTP 200 when the app is alive; body `{status:"ok", app, env,
version, components:{database:{status:"up"|"down", latency_ms}}}`. Database probe =
`SELECT 1` with a short statement timeout, failure swallowed into component status.

**Rationale**: Liveness (app up) and readiness (dependencies) are distinguished per
spec FR-001/edge cases; the phase gate ("healthz 200") holds even with the DB stopped.

**Alternatives considered**: 503 on DB-down (rejected — breaks liveness gate semantics;
readiness distinction arrives with orchestrators in Phase 11).

## R6 — Alembic baseline

**Decision**: `alembic init` with `env.py` importing `app.core.database.Base.metadata`;
single initial revision `0001_baseline` with empty `upgrade()`/`downgrade()` (stamp
point). Verified reversible via `upgrade head` + `downgrade base` + re-upgrade.

**Rationale**: Autogenerate needs a clean baseline; mixins are code (Python), not DDL,
until the first real entity lands in Phase 3 — nothing to create yet keeps the DB
schema honest.

**Alternatives considered**: baseline that creates a dummy table (rejected — physical
schema should never lead the domain); separate DB per test (deferred to Phase 2 when
entity tables exist).

## R7 — Mixin set (shared entity conventions)

**Decision**: `app/common/mixins.py` with declarative mixins — `IDMixin` (UUID pk,
`default=uuid4`), `TimestampMixin` (`created_at`/`updated_at` server-side now()), 
`SoftDeleteMixin` (nullable `deleted_at`), `VersionMixin` (`version int default 1`),
`CreatedByMixin`/`UpdatedByMixin` (nullable UUID actor columns), `OrgScopeMixin`
(nullable `company_id`/`complex_id`/`workplace_id` + composite index hints).
A `ConcreteBaseExample` unit test asserts column presence/types on a scratch model
(kept in tests only, never migrated).

**Rationale**: Requirements §10.1/§10.2 exactly; type-checked, reusable, and unit-
testable without a database round-trip.

**Alternatives considered**: abstract `BaseEntity` god-class (rejected — composable
mixins let later modules opt into exactly what they need, e.g. settings rows may not
need soft delete).

## R8 — Frontend scaffold choices

**Decision**: `create-next-app@latest` (App Router, `src/`, TS, ESLint, Tailwind,
`@/*` alias), Next.js current stable with React 19. shadcn/ui initialized (Tailwind v4
CSS-variable theming). next-intl v4 plugin with `[locale]` segment + middleware
negotiation (`en` default, `fa` second; `localePrefix: "always"`). Kalameh via
`next/font/local` — `standard/` for `en`, `fa-num/` for `fa`, weights 100/400/700/900
(mapped: design 500/600 → 700), `display: "swap"`, `FontLicense.txt` untouched.

**Rationale**: Matches constitution stack and frontend/AGENTS.md conventions exactly;
next-intl handles `lang`/`dir` and negotiation; local fonts keep FaNum digits native
with zero runtime cost.

**Alternatives considered**: `app/[lang]` DIY i18n (rejected — reinvents
negotiation/RTL plumbing); i18next (rejected — next-intl is the project decision).

## R9 — Design tokens mapping (DESIGN.md → code)

**Decision**: `globals.css` defines CSS variables for the DESIGN.md palette
(`--color-canvas #ffffff`, `--color-primary #024ad8`, `--color-primary-deep #0e3191`,
`--color-ink #1a1a1a`, `--color-charcoal #3d3d3d`, `--color-graphite #636363`,
`--color-cloud #f7f7f7`, `--color-fog #e8e8e8`, `--color-steel #c2c2c2`,
`--color-bloom-deep #b3262b`, semantic success/warn reserved), radius two-tier
(`--radius-md 4px` buttons/inputs, `--radius-xl 16px` cards), Soft Lift shadow
`0 2px 8px rgba(26,26,26,.08)`, spacing per Tailwind default (8px base), and the
150–300ms ease-out transition duration tokens. shadcn variables (`--background`,
`--primary`, `--ring`, …) are aliased to these tokens so generated components inherit
the brand. Global reduced-motion guard included.

**Rationale**: DESIGN.md is the binding visual source of truth; aliasing into shadcn
vars means `npx shadcn add` output is brand-correct with zero hand-editing.

**Alternatives considered**: Tailwind config extension only (rejected on Tailwind v4 —
CSS-first variables are canonical); hardcoding hex in components (forbidden).

## R10 — BFF proxy pattern

**Decision**: `src/app/api/health/route.ts` performs a server-side `fetch` to
`${BACKEND_API_BASE_URL}/healthz`, re-validates the JSON against the envelope/status
shapes (Zod), and returns it; backend-unreachable/timeout maps to the standard error
envelope with code `INTERNAL_ERROR` and HTTP 502. `lib/api.ts` is the single fetch
helper browser code uses (never imports backend URLs directly).

**Rationale**: Establishes the "browser talks only to the BFF" invariant (AGENTS.md)
with the smallest possible surface before Phase 2 adds auth cookies to the same layer.

**Alternatives considered**: rewrite-nextjs-proxy config (rejected — route handlers
give typed validation points we will need for login); direct client→FastAPI
(forbidden).

## R11 — CI pipeline

**Decision**: Single workflow `.github/workflows/ci.yml`, two jobs on
`ubuntu-latest`, triggered on push/PR to `main` and feature branches. Backend:
Python 3.12 → pip install `requirements-dev.txt` → `ruff check app tests` →
`mypy app` → `pytest` with a `postgres:16` service container
(`DATABASE_URL` from env; DB integration test skips gracefully if unset locally).
Frontend: Node 22 → `npm ci` → `npm run lint` → `npx tsc --noEmit` → `npm run build`.

**Rationale**: Constitution VII (CI from Phase 1) with the exact quality gate from
the confirmed decisions; PG service container keeps constraint/index tests honest
from the first migration-bearing phase onward.

**Alternatives considered**: Windows runners (rejected — slower and unnecessary;
Python/Node artifacts are cross-platform); separate workflows per side (rejected —
one PR check is simpler to read at this scale).

## R12 — Bring-up scripts (Windows/PowerShell)

**Decision**: `scripts/dev-backend.ps1` (create venv if missing → activate →
`pip install -r requirements-dev.txt` → `alembic upgrade head` → `uvicorn
app.main:app --reload --port 8000`), `scripts/dev-frontend.ps1` (`npm install` if
`node_modules` missing → `npm run dev`), `scripts/smoke-test.ps1` (healthz direct +
via BFF + both locale pages → exit code). All read host/port from `.env` — no
hardcoded hosts in scripts either.

**Rationale**: One-command bring-up per side (SC-001) on the mandated dev platform,
plus a repeatable phase-gate smoke test for `/speckit.converge`.

**Alternatives considered**: Makefile (rejected — Windows-native PowerShell is the
operating environment for v1); bash scripts (same reason).
