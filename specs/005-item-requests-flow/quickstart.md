# Quickstart: Item Request Flow — bring-up & gate validation

**Gate**: request composed in the browser → approved → fulfilled with stock
verified to move → overdraw refused atomically → scope/ownership visibility
verified → both locales RTL-correct → all Phase 1–4 checks stay green → CI
green.

## Prerequisites

Phase 4 bring-up complete (`backend/.env`, `frontend/.env.local` from their
`.example` files; DB `zces_dev` reachable). No new env vars in this phase.

## Bring-up

```powershell
.\scripts\dev-backend.ps1      # venv + deps + alembic (0005 applied) + uvicorn
.\scripts\dev-frontend.ps1     # next dev :3000
```

Seed (idempotent — safe to re-run; now also creates the request permissions
and extends the approver/keeper role mappings):

```powershell
cd backend; .\.venv\Scripts\Activate.ps1
python -m app.seeds.seed_dev
```

## Validate the phase gate

```powershell
.\scripts\smoke-test.ps1       # includes the item-request E2E section
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

1. Sign in as the seeded admin → Sidebar → **Requests** (درخواست‌ها): the
   console opens with status filter chips and an empty-or-existing list.
2. **New request**: search two items via the live picker, set quantities
   (e.g. 4 and 1.5), add a purpose, submit → the request appears with status
   Pending and the requester is you.
3. Submit invalid variants: no lines (refused), blank purpose (refused),
   quantity 0 (refused per-line), duplicate item on two lines (refused).
4. Receive stock for the requested items onto a shelf of an in-scope
   warehouse (Phase-4 Stock tab).
5. **Approve** the request (admin holds decide) → status chip Approved;
   audit trail records the transition. Try **reject** afterwards → refused
   (not pending).
6. **Fulfill**: pick a placement per line (the dialog lists in-scope
   placements of each requested item) → status Fulfilled; the Stock tab
   shows the decremented quantities and each line has a `fulfillment`
   movement in its history.
7. **Overdraw**: approve a second request whose line exceeds available stock
   → fulfill is refused with the insufficient-stock error naming the line;
   quantities unchanged, no movements.
8. **Concurrency spot check** (two browser windows): decide the same pending
   request in both → exactly one approve/reject wins, the other gets the
   stale-version error.
9. **Visibility**: sign in as a workplace-scoped keeper of CP1 → their list
   shows CP1-anchored requests plus their own; requests anchored to SP never
   appear (list or direct URL).
10. Switch to **فارسی**: all request surfaces Persian and RTL-correct, Jalali
    timestamps, Farsi digits native; responsive down to 375px (tables
    collapse to cards).
