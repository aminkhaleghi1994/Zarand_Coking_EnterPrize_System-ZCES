# API Contracts: Notifications, Event Outbox & Live SSE

**Feature branch**: `feature/008-notifications-outbox-sse` | **Date**: 2026-09-01
Base path `/api/v1` (BFF mirrors under `/api/notifications/**`). All
endpoints are owner-scoped: authentication only (`load_context`), no RBAC —
a user's inbox is personal data. Standard error envelope applies.

---

## Notification store

### `GET /notifications`

Query: `page`, `page_size` (bounded ≤ 100), `unread_only` (default false).

Response item (`NotificationOut`):

```json
{
  "id": "uuid",
  "event_type": "InventoryLowStock",
  "payload": {
    "entity_id": "uuid",
    "title": "low_stock",
    "body": "Item X below threshold at Warehouse CP1",
    "workplace_id": "uuid"
  },
  "read_at": null,
  "created_at": "2026-09-01T10:00:00Z"
}
```

Ordering: newest first (`created_at DESC`, id tiebreak).

### `GET /notifications/unread-count`

```json
{"unread": 3}
```

### `POST /notifications/{id}/read` → 200

Idempotent; stamps `read_at` if unset. Foreign ids → `RESOURCE_NOT_FOUND`
(no leak).

### `POST /notifications/read-all` → 200

```json
{"marked": 2}
```

## Live stream

### `GET /notifications/stream` (SSE)

- Response: `200`, `Content-Type: text/event-stream`, no buffering.
- Auth: Bearer (via BFF cookie proxying — browsers cannot set headers on
  `EventSource`); unauthenticated → standard 401 envelope before the stream
  starts.
- Frames:

```
event: notification
data: {"id":"uuid","event_type":"LoanRequestActivated","payload":{...}}

: keep-alive
```

- A comment line (`: keep-alive`) every 15s; connection ends server-side
  after client disconnect; reconnects recover missed items via
  `GET /notifications?unread_only=true`.

## Capture contract (module-internal, for other modules)

```python
record_event(session, event_type, payload, actor_user_id, critical=False)
# appends an EventOutbox row in the caller's transaction

deliver_critical(session, event_type, payload, recipient_ids, actor_user_id)
# writes Notification rows in the caller's transaction (Critical events)
```

`CRITICAL_EVENTS` mapping lives in the notification module (data-driven);
v1: `InventoryLowStock`.

## Relay semantics (module-internal)

- Claim: `UPDATE event_outbox SET status='processing' WHERE id IN
  (SELECT id FROM event_outbox WHERE status='pending' ORDER BY created_at
  FOR UPDATE SKIP LOCKED LIMIT 50)`.
- Deliver: resolve recipients (research R3) → insert notifications
  (idempotent via partial unique) → mark `delivered`.
- Retry: increment `attempts` ≤ 5 with 2s backoff; beyond → `failed` with
  `last_error`. Unknown event types → immediate `failed`.

## Frontend BFF routes

`/api/notifications` (list), `/api/notifications/unread-count`,
`/api/notifications/[id]/read`, `/api/notifications/read-all`,
`/api/notifications/stream` (streaming passthrough forwarding the session
cookie).
