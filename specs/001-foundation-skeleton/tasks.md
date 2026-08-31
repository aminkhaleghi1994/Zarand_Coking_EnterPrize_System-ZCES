# Tasks: Foundation Skeleton

**Input**: Design documents from `/specs/001-foundation-skeleton/`

**Prerequisites**: plan.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: REQUIRED per constitution (tests are part of each task, written before the
implementation they verify — TDD where practical).

**Organization**: Tasks grouped by user story; Foundational tasks block all stories.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependency on the previous task)
- **[Story]**: owning user story (US1–US4); FND = foundational, POL = polish
- FR/SC references in parentheses map to spec.md requirements

---

## Phase 1: Setup

- [ ] T001 [FND] Create backend layout `backend/app/{core,common}`, `backend/tests`,
      `backend/app/modules/` (empty pkg), `backend/requirements.txt` (fastapi,
      uvicorn[standard], sqlalchemy>=2, alembic, psycopg[binary], pydantic,
      pydantic-settings), `backend/requirements-dev.txt` (+pytest, httpx, ruff, mypy),
      `backend/pyproject.toml` (ruff+mypy+pytest config) (FR-002, FR-011-analog)
- [ ] T002 [FND] Write `backend/.env.example` with the full requirements §30 variable set
      (app/env/debug, API prefix, DATABASE_* parts + composed URL, REDIS_* placeholder,
      JWT_*/COOKIE_* placeholders for Phase 2, CORS origins, LOG_LEVEL, APP_VERSION=0.1.0)
      — comments mark Phase-2+ variables as unused-but-reserved (FR-002, FR-010, FR-003)
- [ ] T003 [FND] Scaffold frontend with create-next-app (TypeScript strict, App Router,
      src dir, Tailwind, ESLint, `@/*` alias) into `frontend/` preserving existing
      `src/fonts/`, `DESIGN.md`, `AGENTS.md`; commit `frontend/.env.example`
      (NEXT_PUBLIC_APP_NAME/VERSION, NEXT_PUBLIC_FRONTEND_URL, BACKEND_API_BASE_URL,
      NEXT_PUBLIC_DEFAULT_LOCALE=en) (FR-011, FR-003)
- [ ] T004 [P] [FND] Verify root `.gitignore` ignores `.env`/`.env.local`/`.venv`/
      `node_modules`/`.next`; add patterns if missing (FR-003)

---

## Phase 2: Foundational (blocking)

**⚠️ No user-story work until this phase is complete.**

- [ ] T005 [FND] `app/core/config.py`: pydantic-settings `Settings` (env_file=.env,
      extra=ignore) exposing app/env/debug/api_prefix/database url+parts/cors/log_level/
      version; missing-or-invalid required config raises a specific error naming the
      variable and NEVER the value; write `tests/test_config.py` FIRST (missing var →
      error message contains var name, not secret; env override works; composed
      DATABASE_URL from parts) (FR-002, FR-010)
- [ ] T006 [P] [FND] `app/core/tracing.py`: `trace_id` contextvar + `get_trace_id()` +
      `new_trace_id()` (uuid4); `tests/test_tracing.py` (generation, isolation between
      requests) (FR-004)
- [ ] T007 [P] [FND] `app/core/logging.py`: JSON formatter (timestamp, level, logger,
      message, trace_id, extras), trace-id filter, `setup_logging(level)` reading
      settings; `tests/test_logging.py` (record contains trace_id when set; level from
      config; no message interpolation of secrets) (FR-005)
- [ ] T008 [FND] `app/core/database.py`: sync engine from settings (pool_pre_ping,
      connect timeout), `SessionLocal`, `Base(DeclarativeBase)`; `get_db()` dependency;
      unit test builds engine from test URL (no live DB required) (FR-010)
- [ ] T009 [P] [FND] `app/common/schemas.py` (`ErrorEnvelope`, `HealthStatus`,
      `ComponentStatus` Pydantic models) + `app/common/pagination.py` (`Page[T]` =
      items/page/page_size/total); unit tests assert exact field sets (FR-006, VII)
- [ ] T010 [P] [FND] `app/common/mixins.py`: IDMixin/TimestampMixin/SoftDeleteMixin/
      VersionMixin/CreatedByMixin/UpdatedByMixin/OrgScopeMixin per data-model.md §1;
      `tests/test_mixins.py` with a scratch declarative model asserting column presence,
      types (UUID pk, timestamptz, nullable deleted_at, version default 1, scope UUIDs)
      — scratch model lives in tests only (FR-009, III)
- [ ] T011 [FND] Alembic: `backend/alembic/` with env.py importing `Base.metadata`, URL
      from settings; revision `0001_baseline` (empty upgrade/downgrade); verify locally:
      `upgrade head` → `downgrade base` → `upgrade head` all succeed (FR-008)

**Checkpoint**: core/common/alembic importable; `pytest` green on unit tests.

---

## Phase 3: US1 — Boot & health (P1) 🎯 MVP

**Goal**: Both apps start; healthz 200 with component status.

**Independent Test**: `scripts/smoke-test.ps1` items 1–3.

- [ ] T012 [US1] Database probe: `app/core/database.py::check_database_health()` →
      `SELECT 1` with a 2-second timeout, returns `ComponentStatus(up, latency_ms)` or
      `down`; unit-test both branches with monkeypatched engine (FR-001)
- [ ] T013 [US1] `app/main.py`: `create_app()` — FastAPI(title=settings.app_name,
      version=settings.app_version), CORS middleware from settings origins,
      `GET /healthz` + `GET {API_V1_PREFIX}/healthz` returning HealthStatus with live
      DB probe; `tests/test_healthz.py`: 200 + exact shape; DB down (monkeypatched) →
      still 200 with `database.status="down"` (SC-002, FR-001)
- [ ] T014 [US1] `scripts/dev-backend.ps1` (venv→deps→`alembic upgrade head`→uvicorn,
      host/port from `.env`), `scripts/dev-frontend.ps1` (npm install→dev), no hardcoded
      hosts in either (FR-018)
- [ ] T015 [US1] Live bring-up per quickstart.md §2–3: backend boots against local PG,
      `alembic upgrade head` stamps baseline, frontend dev server boots — record
      results in converge notes (SC-001)

**Checkpoint**: `GET /healthz` → 200 (MVP demonstrable).

---

## Phase 4: US2 — Trace correlation + error envelope (P2)

**Goal**: Every request carries a trace id; every error uses `{code, message, details,
trace_id}`.

**Independent Test**: `scripts/smoke-test.ps1` items 6–7.

- [ ] T016 [US2] ASGI middleware in `app/main.py`: adopt non-empty `X-Request-ID`,
      else generate; set contextvar; echo response header; `tests/test_tracing_middleware.py`
      (echo supplied id, generate when absent, empty value → new id, header+contextvar
      equality) (FR-004)
- [ ] T017 [US2] `app/core/errors.py`: `AppError` + handlers — AppError→own status,
      RequestValidationError→422 VALIDATION_ERROR (field details),
      StarletteHTTPException→mapped code (404→RESOURCE_NOT_FOUND, 405→
      BUSINESS_RULE_VIOLATION), Exception→500 INTERNAL_ERROR (traceback logged, body
      clean); register in create_app; error envelope carries trace_id from contextvar
      (FR-006, contracts/error-envelope.md)
- [ ] T018 [US2] `tests/test_error_envelope.py`: 422/404/500 envelopes exact-shape
      (code/message/details/trace_id), 500 body contains no traceback, trace_id matches
      `X-Request-ID` response header and appears in captured log records (SC-003)

**Checkpoint**: smoke items 6–7 pass (manual curl acceptable here;
`scripts/smoke-test.ps1` from T030 may be created early and formalized then) —
SC-003 testable.

---

## Phase 5: US3 — Bilingual RTL shell (P3)

**Goal**: EN/FA shell + login visual shell, DESIGN.md tokens, BFF health proxy.

**Independent Test**: manual checklist in quickstart.md §4 + lint/tsc/build.

- [ ] T019 [US3] Tailwind v4 theme in `frontend/src/app/globals.css`: DESIGN.md tokens
      as CSS vars (canvas/primary/primary-deep/primary-bright/ink/charcoal/graphite/
      cloud/fog/steel/bloom-deep, radius two-tier 4px/16px, Soft Lift shadow, durations
      150–300ms ease-out) + shadcn variable aliasing + global `prefers-reduced-motion`
      guard (FR-014, FR-016, V)
- [ ] T020 [US3] shadcn init + add `button`, `input`, `label`, `card`, `skeleton`;
      verify generated components consume the token vars (no hand-editing of generated
      files) (FR-014)
- [ ] T021 [US3] next-intl v4: `src/i18n/routing.ts` (locales en/fa, default en,
      localePrefix always), `src/i18n/request.ts`, `src/middleware.ts` (negotiation +
      redirect `/`→`/en`), `src/app/[locale]/layout.tsx` setting `<html lang>`/`dir`;
      `src/messages/en.json` + `fa.json` with full key set for Phase 1 pages
      (FR-012)
- [ ] T022 [P] [US3] Kalameh via `next/font/local` in a `src/fonts/kalameh/index.ts`:
      standard variant (en) + fa-num variant (fa), weights 100/400/700/900 (design
      500/600 → 700), display swap; expose CSS vars `--font-kalameh` (locale-switched
      in layout); assert FontLicense.txt untouched beside files (FR-013)
- [ ] T023 [US3] App chrome: `src/components/layout/AppChrome.tsx` (brand-mark area,
      nav placeholder, dark-ink footer), `src/components/common/LocaleSwitcher.tsx`,
      `src/components/common/Skeleton.tsx`, page-transition wrapper (150–300ms CSS);
      landing page `src/app/[locale]/page.tsx` using chrome (FR-017, FR-016)
- [ ] T024 [US3] Login visual shell `src/app/[locale]/login/page.tsx` (+ client form
      component): React Hook Form + Zod (email/password), inline field errors, error
      message slot, primary button 44px, disabled-while-validating state, NO network
      call and NO auth logic; all strings via messages (FR-015, V)
- [ ] T025 [US3] BFF: `src/app/api/health/route.ts` (server fetch to
      `BACKEND_API_BASE_URL/healthz`, Zod validation of health shape, ≤5s timeout,
      failure → 502 standard envelope with fresh trace id) + `src/lib/api.ts` (shared
      fetch helper) + `src/lib/error-codes.ts` (code→localized message dictionary
      EN/FA mirroring the standard set) (FR-007, contracts/bff-proxy.md)
- [ ] T026 [US3] Frontend gates: `npm run lint`, `npx tsc --noEmit`, `npm run build`
      all clean; manual RTL/responsive/reduced-motion walkthrough of /en /fa /en/login
      /fa/login at 375/768/1024/1440 recorded in converge notes (SC-004, SC-005)

**Checkpoint**: US3 acceptance scenarios 1–4 verifiable.

---

## Phase 6: US4 — CI (P3)

**Goal**: Automated quality gates on push/PR.

**Independent Test**: pipeline green on the phase's final commit.

- [ ] T027 [US4] `.github/workflows/ci.yml` backend job: ubuntu-latest, Python 3.12,
      pip install requirements-dev.txt, `ruff check app tests`, `mypy app`, `pytest`
      with postgres:16 service container (DATABASE_URL env; DB tests skip gracefully
      if unset) (FR-019)
- [ ] T028 [P] [US4] CI frontend job: Node 22, `npm ci`, `npm run lint`,
      `npx tsc --noEmit`, `npm run build` (FR-019)
- [ ] T029 [US4] Push branch → both jobs green; fix any pipeline-only failures; add
      CI badge to README (SC-006)

---

## Phase 7: Polish & Convergence

- [ ] T030 [P] [POL] `scripts/smoke-test.ps1`: healthz direct (200 + shape), DB
      component up, BFF `/api/health` 200, /en + /fa 200, unknown backend route →
      404 envelope, X-Request-ID echo/generate — non-zero exit on any failure
      (SC-001..SC-003)
- [ ] T031 [POL] README quickstart (mirrors quickstart.md), CHANGELOG 0.1.0 entry for
      foundation skeleton, VERSION stays 0.1.0 (FR-020)
- [ ] T032 [POL] Run full quickstart.md §4–5 gate end-to-end on a clean venv/node_modules;
      fix findings; re-run until exit 0

---

## Dependencies & Execution Order

- T001–T004 (setup) → T005–T011 (foundational; [P] pairs parallel) →
  US1 (T012–T015) → US2 (T016–T018) → US3 (T019–T026; T019→T020→T023 chain,
  T021/T022 parallel with T019) → US4 (T027–T029) → Polish (T030–T032).
- US2 depends only on foundational; US3 frontend work can start after T003/T004 but
  its BFF task (T025) needs the backend running (post-T015).
- Tests precede implementation within each task (constitution: tests are part of the task).

## Notes

- No business entities, no auth, no Redis/Celery/Docker in this phase (constitution VIII).
- Commit after each phase checkpoint (Conventional Commits on `feature/001-foundation-skeleton`).
- Verify every task's file paths against plan.md Project Structure before closing it.
