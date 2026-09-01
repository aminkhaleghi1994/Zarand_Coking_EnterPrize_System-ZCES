# Research: Notifications, Event Outbox & Live SSE

**Feature branch**: `feature/008-notifications-outbox-sse` | **Date**: 2026-09-01
**Inputs**: spec.md, requirements §20 §21, platform patterns Phases 2–7.

---

## R1 — Module ownership and the capture contract

**Decision**: `backend/app/modules/notification/` owns `EventOutbox` and
`Notification`. Emitters (user/warehouse/loan services) capture events only
through the published contract
`notification.contracts.record_event(session, event_type, payload, actor_user_id)`
— called inside their existing transaction, so the outbox row commits or
rolls back with the business change.

**Rationale**: The outbox pattern requires atomicity with the business
write; contract-only access keeps constitution VI (no cross-module model
imports). All 13 §20 events map to existing service methods, so the capture
calls are one-liners at each commit point.

**Alternatives considered**: DB triggers writing the outbox (hidden logic,
hard to audit); a separate events service with its own transaction (loses
atomicity — rejected).

## R2 — Relay design (in-process, lifespan-managed)

**Decision**: A daemon thread started by the FastAPI lifespan polls every
2s: claims up to 50 pending events with
`UPDATE … WHERE id IN (SELECT … FOR UPDATE SKIP LOCKED LIMIT 50)`, resolves
recipients, writes notification rows, marks events delivered. Failures
increment `attempts` with a fixed backoff (attempt count bounded at 5);
beyond the bound the event is marked `failed` with the last error (terminal
status, no deletion). On startup the relay re-claims anything left in
`processing` (at-least-once claim; the exactly-once partial unique makes the
effect idempotent).

**Rationale**: Single-VM MVP simplicity (constitution VIII) — no Celery
broker; row-locked claims are the platform's established concurrency
discipline; SKIP LOCKED makes multi-worker deployment safe later.

**Alternatives considered**: Celery beat + worker (new infra this phase —
deferred); asyncio task polling in the event loop (blocks the loop on sync
DB calls — rejected); per-request inline delivery (loses the outbox's
tolerance — rejected).

## R3 — Recipient resolution through the scope model

**Decision**: New user-module contract
`get_recipient_user_ids(session, permission_code, workplace_id)` returning
active users whose scope assignments cover that workplace for that
permission (scope_assignments ∩ roles ∩ permissions ∩ active users,
implicit deny). Per-event mapping (documented, testable):

| Event | Recipients |
|---|---|
| `ItemRequestCreated` | requester + `warehouse:request:decide` holders scoped to the request's workplace |
| `ItemRequestApproved/Rejected/Fulfilled` | requester (+ fulfillers for Approved: `warehouse:request:fulfill` holders) |
| `InventoryLowStock` | `warehouse:stock:read` holders scoped to the alert's workplace |
| `AssetAssigned/Returned` | the holder employee's linked user (+ the acting keeper) |
| `LoanRequestCreated/Activated/Settled` | requester + `loan:request:read` holders scoped to the workplace |
| `UserCreated` | `user:employee:read` holders scoped to the employee's workplace |
| `ItemCatalogCreated` | `warehouse:item:read` holders scoped to the creator's workplace |

**Rationale**: Reuses existing scopes — no new subscription surface; the
implicit-deny rule means out-of-scope staff never receive another unit's
events (spec edge case). Deactivated users are filtered at resolution time
and per-delivery (spec edge case 2).

**Alternatives considered**: a notification-subscription table (Phase 9
settings territory); broadcasting to everyone (leaks out-of-scope data —
constitution II violation).

## R4 — Criticality table and the §20 rule

**Decision**: A module-level mapping `CRITICAL_EVENTS: frozenset[str]`
(data-driven, v1 = `InventoryLowStock`). `record_event` accepts
`critical: bool`; for critical events the caller-side service ALSO writes
the in-app notification rows in the same transaction (via
`notification.contracts.deliver_critical`), so a failure fails the business
transaction — exactly the §20 allowance and the audit-critical pattern.
Non-critical events rely on the relay; their failures never surface.

**Rationale**: Mirrors `write_audit(critical=True)` semantics the platform
already uses; keeps the rule observable and testable (SC-004).

**Alternatives considered**: marking delivery-failure as transaction-
breaking post-commit (impossible — the tx already committed); making all
events critical (over-constrains; §20 says explicitly-critical only).

## R5 — SSE live stream

**Decision**: Backend endpoint `GET /api/v1/notifications/stream` (async
generator via `StreamingResponse`, `text/event-stream`). A process-wide
in-process bus (`app/common/bus.py`) bridges the relay thread to the
asyncio loop: after a successful delivery the relay pushes
`{user_id, notification}` through the bus; each open stream filters for its
owner and yields `event: notification\ndata: {json}\n\n`. A per-connection
keep-alive comment every 15s prevents proxy idle timeouts. The BFF proxies
the stream with a new streaming passthrough that forwards the session
cookie as the Bearer header (browser `EventSource` cannot set headers) and
pipes bytes through unchanged.

**Rationale**: Live push within ~2s of delivery (SC-003) without polling
churn; the bus is ~40 lines; the BFF keeps the browser token-free
(constitution IV/VII). Reconnect recovery needs no Last-Event-ID machinery:
on (re)connect the client fetches the unread list, which contains anything
missed (spec edge case 5).

**Alternatives considered**: WebSocket (bidirectional overhead, no §20
mandate); client polling (latency + churn — the phase exists to avoid it);
Redis pub/sub (no multi-instance need yet — deferred per R2).

## R6 — Payload summaries and masking

**Decision**: Outbox payloads are JSON with stable keys
(`entity_id`, `actor_user_id`, `title`, `body`, optional `workplace_id`,
`amount` for loan events). `title`/`body` are i18n-neutral short English
keys — the UI renders human-readable bilingual text from the `event_type`
via the `notifications.*` message namespace, so no server-side translation
exists. Loan amounts stay in payloads (recipients are the loan's own
parties — §21 masking governs audit/logs, not the recipient's own data).
The UI panel shows type + workplace + entity context, never raw payload
JSON.

**Rationale**: Keeps the API locale-agnostic (bilingual rendering is a
frontend duty per constitution V); recipients only ever see events
addressed to them (R3), so payload contents are within their legitimate
visibility.

**Alternatives considered**: server-rendered localized messages (duplicates
i18n server-side); masking amounts in notifications (recipients are the
owners — unnecessary).

## R7 — Read semantics and retention

**Decision**: `notifications.read_at` nullable timestamp; unread = rows
with `read_at IS NULL`. Endpoints: list (paginated newest-first, optional
`unread_only`), `unread-count`, `POST {id}/read` (idempotent), `POST
/read-all`. Retention: rows are kept indefinitely (volume is small per
user); no pruning in this phase (settings phase may add retention policy).

**Rationale**: Simplest correct model; the badge derives live from the
count endpoint so no counter drift is possible.

**Alternatives considered**: a denormalized unread counter (drift risk);
auto-read on open (users lose track of what they saw — rejected).

## R8 — Migration and constraint notes

**Decision**: `event_outbox` — status CHECK
(pending/processing/delivered/failed/skipped), event-type CHECK (the 13
§20 events), partial index `(status, created_at) WHERE status IN
('pending','processing')` for the claim query, plus `actor_user_id` and
`trace_id` columns. `notifications` — FK owner user RESTRICT, FK outbox
event RESTRICT, partial unique `(outbox_event_id, user_id)` for
exactly-once, partial index `(user_id) WHERE read_at IS NULL` for the
badge, `(user_id, created_at DESC)` for the list. Enum-like columns are
plain `String(20)` + named CHECKs (the Phase-6 parity rule).

**Rationale**: Matches the established model/migration parity discipline;
claim and read paths are index-served.

## R9 — Emitting touch-points (wiring inventory)

**Decision**: one `record_event` call per §20 event at the corresponding
service commit point: user creation (employee service), catalog create,
alert raise, request create/approve/reject/fulfill (warehouse), asset
assign/return, loan create/activate/settle. Each call carries the entity id
and the actor already in scope; critical flag comes from the mapping table
(R4). `UserCreated` fires only when a user account is actually created
(bootstrap seed admin is exempt — no notification storm on seed).

**Rationale**: Exhaustive mapping keeps SC-001's 13/13 guarantee verifiable;
the seed exemption prevents seed-time noise.

## R10 — API shapes

**Decision** (full I/O in `contracts/notification-endpoints.md`):
`GET /notifications` (+`unread_only`), `GET /notifications/unread-count`,
`POST /notifications/{id}/read`, `POST /notifications/read-all`,
`GET /notifications/stream` (SSE). All owner-scoped (load_context, no
permission needed — a user's inbox is personal data). BFF mirrors under
`/api/notifications/**`.

**Rationale**: Personal data needs authentication, not RBAC (matches the
loan self-service precedent); permission gates would block ordinary
employees from their own inbox.

## R11 — Frontend pattern

**Decision**: Header bell (badge = live unread count via SSE + query
invalidation), panel popover/list under `features/notifications/`, mark-read
buttons, bilingual descriptions resolved from `event_type` via the
`notifications.events.*` message namespace, Jalali timestamps in `fa`,
skeletons + reduced motion. `EventSource` opens on app mount for
authenticated users; on message → invalidate the list/count queries and
append.

**Rationale**: Reuses the established console idioms; no new component
primitives.
