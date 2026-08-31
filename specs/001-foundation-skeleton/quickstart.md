# Quickstart: Foundation Skeleton — bring-up & gate validation

**Gate**: both apps boot · `GET /healthz` → 200 · tests green · CI green · smoke script passes.

## Prerequisites

- Windows dev machine with Python 3.12, Node LTS ≥ 20, npm ≥ 10, Git
- PostgreSQL 16+ running locally (dev machine has PG 18 as service `postgresql-x64-18`)
- No Redis/Celery needed in Phase 1

## 1. Configure environment

```powershell
Copy-Item backend\.env.example backend\.env      # then edit values
Copy-Item frontend\.env.example frontend\.env.local
```

Create the dev database (values match `backend\.env`):

```sql
CREATE DATABASE zces_dev;
CREATE USER zces_user WITH PASSWORD '<from .env>';
GRANT ALL PRIVILEGES ON DATABASE zces_dev TO zces_user;
```

Never commit `.env` / `.env.local`. Hosts/secrets exist only in these files.

## 2. Bring up the backend

```powershell
.\scripts\dev-backend.ps1     # venv → deps → alembic upgrade head → uvicorn :8000
```

Manual equivalent:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

## 3. Bring up the frontend

```powershell
.\scripts\dev-frontend.ps1    # npm install → next dev :3000
```

## 4. Validate the phase gate

```powershell
.\scripts\smoke-test.ps1      # exits 0 only when everything below passes
```

The script checks:

1. `GET http://<backend>/healthz` → 200 with `{status:"ok", app, env, version, components}`
2. Database component reports `"up"` (with PG running)
3. `GET http://<frontend>/api/health` → 200 (BFF proxy works)
4. `GET http://<frontend>/en` → 200 (LTR, Kalameh standard)
5. `GET http://<frontend>/fa` → 200 (RTL, Kalameh FaNum)
6. `GET http://<backend>/definitely-not-a-route` → 404 with the standard error envelope
   (`RESOURCE_NOT_FOUND` + `trace_id`)
7. Requests without `X-Request-ID` receive a generated one; supplied ids are echoed

Manual smoke checklist:

- [ ] Health JSON shows DB `up` while PG runs, `down` (still HTTP 200) when PG stops
- [ ] `/en/login` and `/fa/login` render the shell; language toggle flips `dir` and font
- [ ] No hardcoded strings: swap a message key and see it change in the UI
- [ ] Login shell usable at 375px and 1440px; buttons ≥ 44px touch targets
- [ ] `prefers-reduced-motion` (OS setting) suppresses page transitions
- [ ] Invalid login form input shows inline validation state (Zod, no network call)

## 5. Tests & quality gates

```powershell
# backend
cd backend; .\.venv\Scripts\Activate.ps1
ruff check app tests
mypy app
pytest

# frontend
cd frontend
npm run lint
npx tsc --noEmit
npm run build
```

## 6. CI

Push / open a PR → GitHub Actions runs both jobs (backend with a PostgreSQL service
container; frontend build). All green = CI gate met.
