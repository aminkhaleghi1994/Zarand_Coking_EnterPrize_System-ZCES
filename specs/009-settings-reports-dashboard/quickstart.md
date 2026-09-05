# Quickstart & Validation: Settings, Reports & Management Dashboard

**Feature branch**: `feature/009-settings-reports-dashboard` | **Date**: 2026-09-05

## Prerequisites

Phases 1–8 converged; `.env` files present; DB `zces_dev` reachable; no
new env vars in this phase. One new backend dependency: `openpyxl`
(`pip install -r requirements-dev.txt` after pulling).

## Bring-up

```powershell
# backend (from backend/)
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt   # installs openpyxl
alembic upgrade head                  # applies 0009_settings
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# frontend (from frontend/)
npm run dev                           # http://localhost:3000
```

## Validate the phase gate

1. **Backend gate**: full pytest green — settings validation/version/audit
   tests, each report's scope-filter + masking tests, export bytes
   (workbook opens, rows match filtered page, masking identical), seed
   idempotency, dashboard aggregation math.
2. **Settings probe**: PATCH a setting → value applies, version bumps,
   `SETTING_UPDATED` audit row exists with before/after; PATCH again with
   the old version → `STALE_VERSION`.
3. **Scope probe**: Workplace-scoped Manager sees smaller dashboard
   counters and only in-scope report rows vs. the Global admin.
4. **Export probe (the phase gate)**: open each report as Manager →
   "Export" downloads an .xlsx that opens cleanly with the same rows;
   as a masked user, sensitive fields are masked **in the workbook**.
5. **Localization probe**: `fa` reports show Persian headers, Jalali
   dates, RTL sheet view; `en` shows Gregorian/LTR.

## Manual checklist (browser)

1. Sign in as Manager → dashboard shows scope-filtered counters and
   breakdown cards; toggle `dashboard.show_alerts_breakdown` off in
   settings → the card disappears after refetch.
2. Reports → four tabs (inventory/requests/loans/audit), filters narrow
   rows, pagination works, tables collapse to cards at 375px.
3. Audit tab as Auditor → snapshots visible; as Manager (masked) →
   snapshot values hidden; Excel follows the same rule.
4. Settings → grouped typed controls; a stale save surfaces the conflict
   message and the form refetches.
5. Feature flag `flags.loan_module_enabled` off → Loans leaves the nav;
   on → returns (no restart).
6. Switch to **فارسی** → every surface RTL-correct with Farsi digits and
   Jalali dates, including the exported workbook headers.
