# Quickstart & Validation: Notifications, Event Outbox & Live SSE

**Feature branch**: `feature/008-notifications-outbox-sse` | **Date**: 2026-09-01

## Prerequisites

Phases 1–7 converged; `.env` files present; DB `zces_dev` reachable; no new
env vars in this phase.

## Bring-up

```powershell
# backend (from backend/)
.\.venv\Scripts\Activate.ps1
alembic upgrade head          # applies 0008_notifications_outbox_sse
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# frontend (from frontend/)
npm run dev                   # http://localhost:3000
```

The relay starts with the backend (lifespan-managed); no extra process.

## Validate the phase gate

1. **Backend gate**: full pytest green — including atomic capture (commit +
   rollback cases), relay idempotency across a simulated restart, retry
   boundedness, SSE auth + stream shape, owner-scoped reads, mark-read
   flows, seed idempotency.
2. **Capture probe**: trigger a low-stock alert (receive then issue below
   threshold) → an `InventoryLowStock` outbox row exists; because it is
   Critical, its notification rows also exist in the same commit for
   scoped warehouse users.
3. **Relay probe**: submit an item request → within ≤ 10s the requester's
   unread count grows by one and the outbox event is `delivered`.
4. **Live probe (the phase gate)**: open the browser as the requester with
   the console open → trigger an action addressed to them (e.g. approve
   their request) → the bell badge increments live and the SSE event
   arrives within seconds.
5. **Failure tolerance**: stop delivery (simulate) → business actions keep
   succeeding; events accumulate pending and deliver on relay recovery.

## Manual checklist (browser)

1. Sign in → the header shows the bell with the live unread badge.
2. Trigger an action addressed to you → the badge increments without a
   page reload (SSE live).
3. Open the panel → newest-first list, human-readable bilingual
   descriptions, Jalali timestamps in `fa`.
4. Mark one read → badge decrements; "mark all read" → badge clears.
5. Switch to **فارسی** → the panel is RTL-correct with Farsi digits.
6. Open the same account in two tabs → both receive the live event.
