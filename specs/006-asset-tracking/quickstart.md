# Quickstart: Asset Tracking — bring-up & gate validation

**Gate**: asset registered in the browser → assigned to an employee →
history complete → returned → duplicate serial refused → retirement blocked
while assigned → scope/ownership visibility verified → both locales
RTL-correct → all Phase 1–5 checks stay green → CI green.

## Prerequisites

Phase 5 bring-up complete (`backend/.env`, `frontend/.env.local` from their
`.example` files; DB `zces_dev` reachable). No new env vars in this phase.

## Bring-up

```powershell
.\scripts\dev-backend.ps1      # venv + deps + alembic (0006 applied) + uvicorn
.\scripts\dev-frontend.ps1     # next dev :3000
```

Seed (idempotent — safe to re-run; now also creates the asset permissions
and extends the keeper/approver role mappings):

```powershell
cd backend; .\.venv\Scripts\Activate.ps1
python -m app.seeds.seed_dev
```

## Validate the phase gate

```powershell
.\scripts\smoke-test.ps1       # includes the asset E2E section
```

Automated suites:

```powershell
cd backend; .\.venv\Scripts\Activate.ps1
pytest                                   # unit + integration (PG)
ruff check . ; ruff format --check . ; mypy app
cd ..\frontend
npm run lint ; npx tsc --noEmit ; npm run build
.\scripts\smoke-ui.ps1                   # hydration/login/theme guard stays green
```

## Manual checklist (browser)

1. Sign in as the seeded admin → Sidebar → **Assets** (دارایی‌ها): the
   console opens with status filter chips and the register form.
2. Register "Torque wrench" with serial `TW-001` → appears as Available.
3. Register `tw-001` again (case variant) → duplicate error naming the
   serial. Register with trailing spaces → same refusal.
4. **Assign** it to an employee picked from the directory (in scope) with a
   note → status Assigned; the card shows the holder's name.
5. Open **History**: entries `Created` then `Assigned` newest-first with the
   from/to holder and your note.
6. **Return** it with a note → Available again; history gains `Returned`.
7. Assign once more, then attempt **retire** → blocked (business-rule
   error); return, then retire → the asset disappears from the default list
   (visible via the Retired filter) and its history stays queryable.
8. **Serial reuse**: register a new asset with serial `TW-001` after the
   retirement → succeeds.
9. **Visibility**: sign in as a workplace-scoped keeper of CP1 → their list
   shows only CP1-anchored assets; an SP asset's direct URL is denied
   without leak.
10. Switch to **فارسی**: all asset surfaces Persian and RTL-correct, Jalali
    timestamps, Farsi digits native; responsive down to 375px (tables
    collapse to cards).
