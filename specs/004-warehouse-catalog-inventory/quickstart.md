# Quickstart: Warehouse Module — bring-up & gate validation

**Gate**: item created → duplicate blocked → stock received → issued →
overdraw rejected → movement history consistent → low-stock alert raised and
resolved → scope filtering verified → both locales RTL-correct → all Phase
1–3 checks stay green → CI green.

## Prerequisites

Phase 3 bring-up complete (`backend/.env`, `frontend/.env.local` from their
`.example` files; DB `zces_dev` reachable). No new env vars in this phase.

## Bring-up

```powershell
.\scripts\dev-backend.ps1      # venv + deps + alembic (0004 applied) + uvicorn
.\scripts\dev-frontend.ps1     # next dev :3000
```

Seed (idempotent — safe to re-run; now also creates the warehouse
permissions and maps them to WarehouseKeeper/WarehouseApprover roles):

```powershell
cd backend; .\.venv\Scripts\Activate.ps1
python -m app.seeds.seed_dev
```

## Validate the phase gate

```powershell
.\scripts\smoke-test.ps1       # includes new warehouse checks
```

Automated suites:

```powershell
cd backend; .\.venv\Scripts\Activate.ps1
pytest                                   # unit + integration (PG) + concurrency
ruff check . ; ruff format --check . ; mypy app
cd ..\frontend
npm run lint ; npx tsc --noEmit ; npm run build
.\scripts\smoke-ui.ps1                   # hydration/login/theme guard stays green
```

## Manual checklist (browser)

1. Sign in as the seeded admin. Sidebar → **Warehouse** (انبار in Persian):
   the console opens with tabs Catalog / Warehouses / Stock / Low stock.
2. **Catalog → New item**: create "Test Bearing" with code `TB-1`, unit `ad`,
   minimum 10. While typing "bear" in the item search, results appear live
   (debounced — pause typing, results follow) and paginated.
3. Create a second item with the SAME name but different casing/spacing
   ("  test bearing  ") → duplicate error naming the field; the existing item
   is offered by live search. Same with the same code `tb-1` (case differs) →
   duplicate on code. A retired item's name can be reused.
4. **Warehouses**: create a warehouse anchored to "Coke Plant 1" and a shelf
   `A-01` under it. Attempt to retire the shelf → blocked once it holds stock
   (business-rule error).
5. **Stock → Receive**: receive 50 of Test Bearing onto A-01. The placement
   row shows 42.000-style decimals after an issue. **Issue** 15 → quantity
   drops, one movement line. **Issue** 999 → rejected with the
   insufficient-stock error; quantity unchanged; no phantom movement line.
6. **Adjust** (a user with only receive+issue gets a denial — verify with a
   scoped role): set the counted quantity to 30 → an `adjust` movement
   records the delta; history shows receive/issue/adjust with resulting
   quantities that always sum to the current quantity.
7. **Low stock**: with minimum 10, issue down to 8 → the alert appears in the
   Low-stock tab with item, shelf, warehouse, quantity, threshold. Issue
   again (still below 10) → no duplicate alert. Receive back to 12 → alert
   resolves. Drop below 10 again → a new alert appears.
8. **Concurrency spot check** (two browser windows): issue nearly all stock
   in both windows at the same moment → exactly one succeeds; the other gets
   the insufficient-stock error.
9. **Scope check**: create a user with only a workplace-level scope
   (Coke Plant 1) + warehouse read permissions; their warehouse list shows
   only CP1 warehouses and they cannot open a CP2 warehouse by URL.
10. Switch to **فارسی**: all warehouse surfaces Persian and RTL-correct,
    Jalali timestamps in movement history, Farsi digits native; responsive
    down to 375px (tables collapse to cards); skeletons during search.
