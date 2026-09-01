# Implementation Plan: Notifications, Event Outbox & Live SSE

**Branch**: `feature/008-notifications-outbox-sse` | **Date**: 2026-09-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-notifications-outbox-sse/spec.md`

## Summary

Deliver the notification platform as the `modules/notification` module per
requirements §20: every one of the 13 mapped domain events is captured into
an append-only `event_outbox` inside the same transaction as its business
action (via a contract other modules call — constitution VI); an in-process
relay worker claims pending events with row locking, resolves recipients
through the user module's scope model, and writes idempotent `notifications`
rows (partial unique on outbox-event + recipient makes replay exactly-once);
an authenticated SSE stream pushes each user's new notifications live, with
the browser recovering any gap from the unread list on reconnect. The
criticality rule mirrors the audit pattern: Critical-mapped events write
their in-app rows inside the business transaction itself; everything else
tolerates delivery failures with bounded retries and terminal-failure
statuses (no physical deletes). The console gains a header bell with a live
unread badge and a bilingual RTL notification panel. Gate: a live
notification reaches the open browser stream within seconds; the full
Phase 1–7 gate suite stays green.

## Technical Context

**Language/Version**: Python 3.12 (backend venv) · Node 24 / npm 11 (frontend)

**Primary Dependencies**: existing stack only — SQLAlchemy 2.0, Alembic,
Pydantic v2, FastAPI (native `StreamingResponse` for SSE); frontend
TanStack Query + EventSource; **no new runtime dependencies**

**Storage**: PostgreSQL — 2 new tables (`event_outbox`, `notifications` +
status CHECKs, event-type CHECK, exactly-once partial unique, unread/list
indexes); migration `0008_notifications_outbox_sse` (reversible,
`down_revision = 0007_loan_module`)

**Testing**: pytest (unit: criticality mapping, recipient resolution,
payload summaries; integration on PG: atomic capture incl. rollback case,
relay idempotency across restart, retry/backoff, SSE auth + stream shape,
mark-read flows, seed idempotency) · eslint/tsc/build · extended smoke test

**Target Platform**: Local Windows dev → single Ubuntu VM; GitHub Actions CI

**Performance Goals**: relay latency ≤ 10s from business commit to
in-app row (SC-003); SSE push ≤ 2s after delivery; relay claims batches of
≤ 50 events per poll (2s interval); indexed claim/read queries

**Constraints**: browser never touches FastAPI directly — the SSE stream is
proxied by the BFF with cookie-auth (EventSource cannot set headers);
notification delivery failures never break business transactions except for
Critical-mapped events' in-transaction rows (constitution golden rule 9 +
§20); no physical deletes; no new deps (constitution VIII)

**Scale/Scope**: 1 new module (`modules/notification`) · 2 new tables ·
1 event-capture contract called from user/warehouse/loan modules · 6
notification endpoints + SSE · ~20 wiring touch-points in existing modules ·
bell + panel UI · ~22 tasks

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence / Plan |
|---|---|---|
| I. Spec-driven sequential delivery | ✅ Pass | This cycle; gate = live SSE notification in browser + atomic-capture/rollback proof + idempotent relay |
| II. Scoped access on every query | ✅ Enabled | Notifications are strictly owner-scoped (a user reads only their rows); SSE streams only the signed-in user's events; recipient resolution reuses the platform scope model (no new visibility surface) |
| III. Auditability & data integrity | ✅ Pass | Outbox + notifications are append-only with status transitions; exactly-once partial unique; critical in-transaction writes; no physical deletes |
| IV. Security & secrets discipline | ✅ Pass | SSE auth via the BFF cookie flow (no token in browser); payloads carry ids/summaries, not secrets; no new env secrets |
| V. Bilingual RTL responsive UX | ✅ Pass | `notifications.*` namespace EN/FA; bell + panel; Jalali timestamps + Farsi digits in `fa`; skeletons; reduced motion |
| VI. Modular monolith boundaries | ✅ Pass | Capture happens through `notification.contracts.record_event` called from other modules' services; recipients resolved through `user.contracts`; no cross-module model imports |
| VII. Standard API contracts | ✅ Pass | Envelope for REST endpoints; SSE uses the text/event-stream protocol with JSON data lines; lists `{items, page, page_size, total}` |
| VIII. Simplicity over speculation | ✅ Pass | In-process relay thread (no Celery/Redis broker this phase); email deferred; no preferences system (Phase 9); no new deps |

**Post-design re-check**: ✅ Passes — see Complexity Tracking (empty).

## Project Structure

### Documentation (this feature)

```text
specs/008-notifications-outbox-sse/
├── plan.md / research.md / data-model.md / quickstart.md / tasks.md
└── contracts/ (notification-endpoints.md)
```

### Source Code (repository root)

```text
backend/app/
├── common/bus.py            # NEW: in-process event bus (thread→asyncio bridge)
├── modules/notification/
│   ├── models.py            # EventOutbox + Notification (migration 0008)
│   ├── schemas.py           # NotificationOut, stream payload, transitions
│   ├── repository.py        # claim/append-only writes, owner-scoped reads
│   ├── service.py           # relay delivery, recipients, criticality table
│   ├── relay.py             # background poller thread (lifespan-managed)
│   ├── router.py            # list/count/read/stream endpoints
│   └── contracts.py         # record_event (capture API for other modules)
├── modules/user/contracts.py# + get_recipient_user_ids (scope-based resolution)
├── modules/user|warehouse|loan/service.py  # + record_event calls (13 events)
├── seeds/seed_dev.py        # (no new permissions — notifications are owner-scoped)
└── alembic/versions/0008_notifications_outbox_sse.py

frontend/src/
├── app/api/notifications/** # BFF passthrough + streaming SSE proxy
├ ├── components/layout/      # bell + unread badge (header)
├── features/notifications/  # NotificationPanel (list, mark read)
├ ├── lib/client-api.ts       # notificationApi + types
└ └ messages/{en,fa}.json    # + notifications.* namespace
```

**Structure Decision**: notifications become the `modules/notification`
module per the platform layout; the outbox is owned by that module and
exposed to emitters purely through its contract. The relay is a lifespan-
managed daemon thread (single-VM MVP, research R3); SSE uses FastAPI's
native streaming with an in-process bus bridge (research R5).

## Complexity Tracking

> Empty — no constitution violations to justify.
