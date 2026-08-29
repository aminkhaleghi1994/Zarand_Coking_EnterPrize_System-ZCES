# Implementation Plan: Foundation Skeleton

**Branch**: `feature/001-foundation-skeleton` | **Date**: 2026-08-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-foundation-skeleton/spec.md`

## Summary

Deliver the Phase 1 platform skeleton: a bootable FastAPI backend with environment-driven
config, structured logging with trace-id correlation, the standard error envelope, a health
endpoint with database component status, Alembic baseline + shared entity mixins; a Next.js
App Router frontend with TypeScript strict, Tailwind + shadcn/ui styled from DESIGN.md tokens,
next-intl bilingual (EN/FA, RTL, Kalameh standard/FaNum variants), a login visual shell, page
transitions with reduced-motion support, and a BFF health proxy; plus `.env.example` templates,
PowerShell bring-up scripts, and GitHub Actions CI. Gate: both apps boot, `GET /healthz` → 200,
CI green.

## Technical Context

**Language/Version**: Python 3.12.0 (backend, venv) · Node 24.11 / npm 11.5 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Alembic, Pydantic v2 +
pydantic-settings, uvicorn, psycopg; Next.js (App Router), TypeScript (strict), Tailwind CSS,
shadcn/ui, next-intl, React Hook Form + Zod, TanStack Query

**Storage**: PostgreSQL 18 (Windows service `postgresql-x64-18`, running on :5432)

**Testing**: pytest + FastAPI TestClient (backend); eslint + `tsc --noEmit` + `next build`
(frontend)

**Target Platform**: Local Windows dev (Phase 1) → single Ubuntu VM later; GitHub Actions CI on
ubuntu-latest

**Project Type**: Modular-monolith web system (backend API + frontend BFF/UI)

**Performance Goals**: Health endpoint responds < 2s (SC-002); p95 < 200ms applies to later API
phases

**Constraints**: No hardcoded hosts/secrets in code (env templates only); no Redis/Celery/Docker
in this phase (constitution VIII); browser never calls the backend directly — only via BFF
routes; no physical deletes, UUID PKs, soft-delete/optimistic-lock conventions delivered as
mixins

**Scale/Scope**: 0 business entities; 1 health endpoint + 1 BFF proxy route; 2 locale
dictionaries; 1 baseline migration; ~40 fine-grained tasks

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence / Plan |
|---|---|---|
| I. Spec-driven sequential delivery | ✅ Pass | This phase is one full cycle; gate = boot + tests + smoke |
| II. Scoped access on every query | ✅ N/A (safeguarded) | No repositories exist yet; `OrgScopeMixin` delivered so later entities carry scope columns from birth; layering rules documented in AGENTS.md |
| III. Auditability & data integrity | ✅ Pass | Mixins: UUID PK, timestamps, `deleted_at` soft-delete marker, `version`, `created_by`/`updated_by`; no physical-delete APIs exist |
| IV. Security & secrets discipline | ✅ Pass | All config via pydantic-settings from `.env`; `.env.example` only; fail-fast without printing secrets; logs exclude secrets |
| V. Bilingual RTL responsive UX | ✅ Pass | US3/FR-011–017: EN+FA dictionaries, locale-prefixed routes, `dir` switching, Kalameh standard (EN) / FaNum (FA), 4 breakpoints, ≥44px targets, 150–300ms transitions, `prefers-reduced-motion` |
| VI. Modular monolith boundaries | ✅ Pass | `core/` vs `common/` split; module layout reserved per backend/AGENTS.md; no cross-module code exists |
| VII. Standard API contracts | ✅ Pass | Error envelope `{code, message, details, trace_id}` enforced by exception handlers for ALL errors; `common/pagination.py` provides the `{items, page, page_size, total}` schema for later phases; trace id in header + logs |
| VIII. Simplicity over speculation | ✅ Pass | No Redis/Celery/Docker/Sentry/OTel in Phase 1 — they arrive with the phase that needs them |

**Post-design re-check**: ✅ Still passes — design adds no entities, no auth, no queues;
complexity tracking table remains empty (no violations).

## Project Structure

### Documentation (this feature)

```text
specs/001-foundation-skeleton/
├── plan.md              # This file
├── research.md          # Technology decisions (Decision/Rationale/Alternatives)
├── data-model.md        # Shared entity conventions + migration baseline
├── contracts/           # healthz, error envelope, BFF proxy contracts
├── quickstart.md        # Bring-up + validation guide (gate script)
└── tasks.md             # Task list (created by /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── main.py                    # FastAPI app factory, middleware, exception handlers
│   ├── core/
│   │   ├── config.py              # pydantic-settings Settings (env-driven)
│   │   ├── database.py            # engine, SessionLocal, Base (DeclarativeBase)
│   │   ├── errors.py              # AppError + envelope + exception handlers
│   │   ├── logging.py             # structured logging + trace_id filter
│   │   └── tracing.py             # trace-id contextvar + middleware support
│   ├── common/
│   │   ├── mixins.py              # ID/Timestamp/SoftDelete/Version/CreatedBy/UpdatedBy/OrgScope
│   │   ├── pagination.py          # Page[T] = {items, page, page_size, total}
│   │   └── schemas.py             # HealthStatus, ErrorEnvelope models
│   └── modules/                   # (empty; populated from Phase 2 onward)
├── alembic/                       # env.py wired to Base.metadata; versions/
├── tests/                         # pytest: healthz, errors, tracing, config, db
├── pyproject.toml                 # ruff / mypy / pytest config
├── requirements.txt               # pinned runtime deps
├── requirements-dev.txt           # + ruff, mypy, pytest, httpx
└── .env.example                   # full §30 variable set (no secrets)

frontend/
├── src/
│   ├── app/
│   │   ├── [locale]/
│   │   │   ├── layout.tsx         # html lang/dir, fonts, providers, app chrome
│   │   │   ├── page.tsx           # landing/shell placeholder
│   │   │   └── login/page.tsx     # login visual shell (RHF + Zod, no auth)
│   │   ├── api/health/route.ts    # BFF proxy → backend /healthz
│   │   └── globals.css            # DESIGN.md tokens as CSS variables
│   ├── components/ui/             # shadcn primitives (button, input, card, …)
│   ├── components/layout/         # AppChrome (brand mark, nav placeholder, footer)
│   ├── components/common/         # Skeleton, LocaleSwitcher, TransitionWrapper
│   ├── i18n/                      # routing.ts, request.ts
│   ├── messages/                  # en.json, fa.json
│   ├── lib/                       # api.ts (BFF fetch helper), error-codes.ts, utils.ts
│   ├── middleware.ts              # locale negotiation + redirect
│   └── fonts/kalameh/             # staged fonts + FontLicense.txt (already present)
├── messages → src/messages        # next-intl source
├── .env.example
├── components.json                # shadcn config
└── package.json / tsconfig.json / eslint config / next.config.ts

scripts/
├── dev-backend.ps1                # venv + deps + migrate + uvicorn
├── dev-frontend.ps1               # npm install/ci + dev server
└── smoke-test.ps1                 # gate checks: healthz direct + via BFF, locales

.github/workflows/ci.yml          # backend (ruff, mypy, pytest w/ PG service) + frontend
```

**Structure Decision**: Two-project web layout (`backend/` + `frontend/`) matching the
requirements §29 structure and the AGENTS.md module layout exactly; Alembic at `backend/alembic/`
with app metadata import; frontend uses the App Router `src/` directory with a `[locale]` segment
and `app/api/**` BFF handlers.

## Complexity Tracking

> Empty — no constitution violations to justify.
