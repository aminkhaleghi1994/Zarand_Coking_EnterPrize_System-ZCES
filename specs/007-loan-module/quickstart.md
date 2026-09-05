# Quickstart & Validation: Loan & Guarantee Management

**Feature branch**: `feature/007-loan-module` | **Date**: 2026-09-01

## Prerequisites

Phases 1–6 converged (platform, auth/RBAC/scope, org & employees, warehouse,
requests, assets); `.env` files present; DB `zces_dev` reachable; no new env
vars in this phase.

## Bring-up

```powershell
# backend (from backend/)
.\.venv\Scripts\Activate.ps1
alembic upgrade head          # applies 0007_loan_module
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# frontend (from frontend/)
npm run dev                   # http://localhost:3000
```

Seeding is unchanged; the seed adds the 9 loan permission codes and the
LoanOfficer mapping idempotently.

## Validate the phase gate

1. **Backend gate**: `.\.venv\Scripts\python.exe -m pytest` all green —
   including the new loan tests (validation cascade order, settled/soft-deleted
   semantics, race one-winner, Nowruz boundary, scope purity, masking,
   seed idempotency).
2. **API cascade probe** (as admin via BFF or API): with a policy of
   3/year, 5 lifetime, 100M loan cap, 50M guarantee cap —
   - 4th request of the year → refused naming `yearly_count` with
     `{used: 3, limit: 3}`;
   - settle nothing, submit with `lifetime` exhausted → refused naming
     `lifetime_count`;
   - active loan sum 90M + request 20M → refused naming `loan_cap` with
     current/limit/requested;
   - same for guarantees → `guarantee_cap`;
   - passing request → 201 pending.
3. **Lifecycle probe**: activate → active amounts bind the cap; settle →
   `settled_at` stamped and the cap frees; cancel → cap frees, counts keep
   counting.
4. **Race probe**: two concurrent submissions for the last count slot →
   exactly one 201, one 422 (integration test covers this; smoke repeat
   optional).
5. **Browser gate** (manual checklist below): policies + requests consoles
   work in both locales; transitions work; Jalali year displays correctly.

## Manual checklist (browser)

1. Sign in as admin → Sidebar → **Loans (وام‌ها)**: console opens with the
   Policies / Requests tabs.
2. Policies tab: create a policy for workplace CP1, year 1405 with the four
   limits → appears in the list; duplicate (same workplace+year) → refused;
   edit with a stale version → stale-write error.
3. Requests tab (as an employee, e.g. a fake user): submit a loan → pending;
   trip each validation rule in order and see the named rule + numbers.
4. As LoanOfficer/admin: activate the pending request → active; settle it →
   settled with timestamp; the amount no longer binds the cap.
5. Sign in as a workplace-scoped keeper/officer → only their workplace's
   policies and requests appear; a cross-workplace direct URL is denied
   without leak.
6. Switch to **فارسی**: all loan surfaces Persian and RTL-correct, Jalali
   year labels, Farsi digits native; responsive down to 375px (tables
   collapse to cards).
