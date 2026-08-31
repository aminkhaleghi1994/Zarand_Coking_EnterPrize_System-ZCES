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

**Phase 2 complete (Auth, RBAC & Scope Platform)** — on top of the Phase 1
foundation: login/logout/me with JWT access tokens and rotating refresh
tokens (DB-backed families, reuse detection revokes the whole family),
HttpOnly cookies owned by the BFF, double-submit CSRF, RBAC + hierarchical
scope resolver (permission AND scope, union, implicit deny, Global >
Complex > Workplace), append-only audit base with masking, idempotent
seeds (initial admin + 7 base roles). Phases 3–11 run sequentially; next:
`org-user-module`.

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
