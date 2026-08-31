# Quickstart: Org & Employee Module — bring-up & gate validation

**Gate**: employee created in the browser → new user signs in → edit works →
deactivate kills the session → duplicates blocked → both locales RTL-correct →
all Phase 1–2 checks stay green → CI green.

## Prerequisites

Phase 2 bring-up complete (`backend/.env`, `frontend/.env.local` from their
`.example` files; DB `zces_dev` reachable). No new env vars in this phase.

## Bring-up

```powershell
.\scripts\dev-backend.ps1      # venv + deps + alembic (0003 applied) + uvicorn
.\scripts\dev-frontend.ps1     # next dev :3000
```

Seed (idempotent — safe to re-run; now also creates the org tree):

```powershell
cd backend; .\.venv\Scripts\Activate.ps1
python -m app.seeds.seed_dev
```

## Validate the phase gate

```powershell
.\scripts\smoke-test.ps1       # includes new org/employee checks
```

Automated suites:

```powershell
cd backend; .\.venv\Scripts\Activate.ps1
pytest                                   # unit + integration (PG)
ruff check . ; ruff format --check . ; mypy app
cd ..\frontend
npm run lint ; npx tsc --noEmit ; npm run build
```

## Manual checklist (browser)

1. Sign in as the seeded admin (`INITIAL_ADMIN_*`).
2. Sidebar → **Employees**: the list is empty on a fresh DB; the create form
   offers the four seeded workplaces (grouped by complex) — no others.
3. Create an employee (national ID 10 digits, personnel code, work email,
   initial password ≥ 8 chars). Success returns to a list showing them; the
   audit trail records `EMPLOYEE_CREATED` with `national_id` masked and no
   password material.
4. Sign out; sign in as the NEW employee with the issued credentials — works
   with no roles (empty permissions; admin surfaces 403).
5. Sign back in as admin. Try creating a second employee with the SAME
   national ID → duplicate error naming the field. Same with the same
   personnel code. Then deactivate the first employee and retry — creation
   now succeeds (identity reuse).
6. Edit the remaining employee: change phone (saves), attempt to clear the
   national ID (rejected — immutable). Open the same employee in a second
   tab, edit in both, save both → the second save gets a conflict error with
   a refresh-and-retry affordance.
7. Deactivate the employee while their browser session is open → their next
   click lands on the login screen (session dead); their sign-in is refused.
   Reactivate → sign-in works again.
8. **System → Roles**: create a role; assign it to a user; grant a
   complex-level scope ("Coking and Tar Refining Complex") for
   `user:employee:read`. A complex-scoped admin now sees only that complex's
   employees in the directory (verify with a second browser profile).
9. Switch to **فارسی**: all new surfaces Persian, RTL correct, Jalali dates
   for birth dates, Farsi digits native; forms responsive down to 375px
   (tables collapse to cards).
10. Admin "set password" on the employee → old password refused on next
    sign-in, new one accepted; audit shows `USER_PASSWORD_SET` with no
    credential material.
