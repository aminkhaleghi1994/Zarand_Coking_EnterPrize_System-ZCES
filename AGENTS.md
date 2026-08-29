# ZCES — Zarand Coking Enterprise System

Agent instructions for this repository. Read this file first, then the scoped
`AGENTS.md` in `backend/` or `frontend/` before working in those areas.

## What this project is

A bilingual (English / Persian) enterprise web system for Zarand Coking &
Steel: employees, warehouse & inventory, item requests, asset tracking,
loans & guarantees, notifications, reports, settings, and full audit logging.

- Architecture: **Modular Monolith** (one deployable, independent internal modules)
- Backend: FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2 (Python 3.12, venv)
- Frontend: Next.js (App Router) + TypeScript strict + Tailwind CSS + shadcn/ui
- Data: PostgreSQL (primary), Redis (cache / Celery broker / SSE)
- AuthN: JWT access + rotating refresh tokens in HttpOnly cookies, BFF pattern
- AuthZ: RBAC (roles -> permissions) + hierarchical scopes (Global > Complex >
  Workplace); access requires BOTH permission and scope

## Repository layout

```
backend/     FastAPI modular monolith (Phase 1+)
frontend/    Next.js app — see frontend/AGENTS.md and frontend/DESIGN.md
infra/       VM deploy configs: nginx, systemd (Phase 11)
docs/        Requirements + bilingual implementation reviews
scripts/     Dev/deploy helper scripts
.github/     CI workflows
.specify/    Spec Kit workspace (constitution, templates, specs, plans, tasks)
.opencode/   OpenCode commands (speckit.*) and agent skills
```

## Source-of-truth documents

- `docs/requirements-prompt.txt` — full requirements (Persian). If code and
  this document disagree, stop and ask.
- `frontend/DESIGN.md` — the design system spec for all frontend work.
- `docs/reviews/en|fa/` — roadmap, 13-layer decisions, improvements.
- `.specify/memory/constitution.md` — governing principles (binding).

## Golden rules (never violate)

1. **Every query is scoped.** No repository query runs without the mandatory
   scope filter. Permission alone is never enough; scope alone is never enough.
2. **No physical deletes.** Soft delete (`deleted_at`) + partial unique
   indexes on active rows (`WHERE deleted_at IS NULL`).
3. **Sensitive operations are always audited** — before/after snapshots,
   `actor_user_id`, `trace_id`, masking of sensitive fields.
4. **UUIDs** for all primary keys and main foreign keys.
5. **Environment-driven config only.** Never hardcode `localhost` /
   `127.0.0.1` or any host/secret in code — only `.env` / `.env.example`.
6. **Standard error envelope** `{code, message, details, trace_id}`; list
   responses use `{items, page, page_size, total}`.
7. **Employee + User are created in one transaction**; failure of one rolls
   back the other. Deactivating an employee deactivates its user.
8. **Stock never changes without a StockMovement**, in the same transaction,
   with `SELECT ... FOR UPDATE` on decrements. Inventory may never go negative.
9. **Notification failures never break the main transaction** unless the
   notification is explicitly Critical (Outbox pattern).
10. **Modules talk through contracts only** — never touch another module's
    repository or models directly.
11. **Bilingual UI is mandatory.** All user-facing strings via i18n (`en` +
    `fa`); `fa` renders RTL with the Kalameh FaNum font and Farsi digits;
    Jalali calendar for `fa` dates.
12. **Optimistic locking** (`version`) on editable entities — return
    `STALE_VERSION` / `CONFLICT_CONCURRENT_UPDATE` on stale writes.

## Development workflow — Spec Kit (spec-driven)

This repo uses GitHub Spec Kit (`.opencode/commands/speckit.*.md`). Work
happens in strictly sequential phases; each phase is one full spec-kit cycle
and must pass its gate before the next:

```
/speckit.specify -> /speckit.clarify -> /speckit.plan -> /speckit.analyze
-> /speckit.tasks -> /speckit.implement -> /speckit.converge
```

Phase gates: app boots, all tests green, new capability manually
smoke-tested. Never start a new phase's `specify` before the previous phase
converged. The phase roadmap lives in
`docs/reviews/en/01-implementation-roadmap.md`.

## Commands

Backend (PowerShell, from `backend/`):

```
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
alembic upgrade head
pytest
```

Frontend (from `frontend/`):

```
npm run dev      # http://localhost:3000
npm run lint
npm run build
```

## Conventions

- Git: Conventional Commits (`feat(user): ...`), branches `feature/*`,
  `fix/*`, `hotfix/*`, `release/*`; Semantic Versioning; `main` = deployable.
- Backend: layered `router -> service -> repository`, type hints everywhere,
  Pydantic schemas for all I/O, sync SQLAlchemy sessions.
- Frontend: server components by default, feature code under
  `features/<module>/`, browser talks only to the Next.js BFF.
- Never commit secrets or `.env` files. `.env.example` only.
