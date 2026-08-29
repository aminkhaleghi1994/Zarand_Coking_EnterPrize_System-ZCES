# Quickstart: Auth, RBAC & Scope Platform — bring-up & gate validation

**Gate**: end-to-end login in the browser · scope resolver unit tests green · all
Phase 1 gates stay green · smoke test (with auth checks) passes · CI green.

## Prerequisites

Phase 1 bring-up complete (DB `zces_dev`, backend `.env`, frontend `.env.local`).
New env vars (already in `backend/.env.example` — copy into your `.env`):

```
JWT_SECRET_KEY=<random 32+ chars>
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
COOKIE_SECURE=false
COOKIE_HTTPONLY=true
COOKIE_SAMESITE=lax
INITIAL_ADMIN_EMAIL=admin@example.com
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=<your dev password, min 8 chars>
```

## Bring-up

```powershell
.\scripts\dev-backend.ps1      # venv → deps → alembic (0002 applied) → uvicorn
.\scripts\dev-frontend.ps1     # next dev :3000
```

Seed (idempotent — safe to re-run):

```powershell
cd backend; .\.venv\Scripts\Activate.ps1
python -m app.seeds.seed_dev
```

## Validate the phase gate

```powershell
.\scripts\smoke-test.ps1       # now includes auth checks
```

Manual checklist:

1. Open `http://localhost:3000/en` → redirected to `/en/login` (not authenticated).
2. Sign in with `INITIAL_ADMIN_EMAIL` / `INITIAL_ADMIN_PASSWORD` → authenticated
   shell shows your email + SuperAdmin role; Logout control visible.
3. Cookies: `zces_at`, `zces_rt` HttpOnly (invisible to `document.cookie`);
   `zces_csrf` readable.
4. Sign out → back to login; direct URL access redirects again.
5. Wrong password → single generic localized error (EN and FA), no hint which factor
   failed; backend log/audit shows `LOGIN_FAILED` with masked email.
6. Switch locale FA → all auth surfaces Persian, RTL correct.
7. Expired access token: set `ACCESS_TOKEN_EXPIRE_MINUTES=1`, restart backend, log
   in, wait, click around → transparent renewal (no visible error), still signed in.
8. Reuse detection (dev only): copy `zces_rt` value, log out, replay refresh via the
   BFF route → 401 + family revoked; the still-open other browser session of the same
   user is also forced out.
9. Authorization: create a roleless user via API (admin token), try admin endpoints
   with their token → 403 `AUTHORIZATION_DENIED`.
10. Audit: `GET /api/v1/audit-logs` (admin) lists the login/role events with
    `trace_id`, masked emails, no token material.

## Tests & quality gates

```powershell
# backend — resolver gate (SC-002) included
cd backend; .\.venv\Scripts\Activate.ps1
ruff check app tests; mypy app; pytest

# frontend
cd frontend; npm run lint; npx tsc --noEmit; npm run build
```

## CI

Push/PR → backend job (ruff, mypy, migrations, pytest incl. auth + resolver + seed
idempotency against PG16) and frontend job — both must be green.
