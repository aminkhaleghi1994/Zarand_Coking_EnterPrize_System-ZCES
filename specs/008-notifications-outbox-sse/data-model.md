# Data Model: Notifications, Event Outbox & Live SSE

**Feature branch**: `feature/008-notifications-outbox-sse` | **Date**: 2026-09-01
**Source**: spec.md, research.md decisions.

---

## Entities

### EventOutbox (`event_outbox`)

Append-only, in-transaction event record. Never physically deleted.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID PK | | |
| event_type | VARCHAR(30) | NOT NULL, CHECK IN (13 §20 events) | |
| payload | JSONB | NOT NULL | entity ids + summary keys (research R6) |
| actor_user_id | UUID | NULLABLE | triggering user |
| trace_id | VARCHAR(64) | NULLABLE | trace correlation |
| status | VARCHAR(20) | NOT NULL, CHECK IN ('pending','processing','delivered','failed','skipped'), DEFAULT 'pending' | |
| attempts | INTEGER | NOT NULL, DEFAULT 0 | relay retry counter |
| last_error | TEXT | NULLABLE | terminal/diagnostic reason |
| created_at / updated_at | TIMESTAMPTZ | | |

**Indexes / constraints**

- `ix_event_outbox_claim` `(status, created_at)` WHERE
  `status IN ('pending','processing')` — relay claim path.
- `ix_event_outbox_type` `(event_type)` — diagnostics.
- CHECK `ck_event_outbox_status`, `ck_event_outbox_event_type`.

**Semantics**

- Rows are created by `record_event` inside the emitting transaction.
- `delivered` is terminal success; `failed` is terminal (bounded retries
  exhausted or unknown event type); `skipped` marks recipient-less events.
- `processing` rows at startup are re-claimed (at-least-once; the
  notification partial unique keeps the effect exactly-once).

### Notification (`notifications`)

Per-recipient in-app message. Append-only except `read_at`.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID PK | | |
| user_id | UUID FK → users.id | NOT NULL, RESTRICT | owner; strictly owner-scoped reads |
| outbox_event_id | UUID FK → event_outbox.id | NOT NULL, RESTRICT | provenance |
| event_type | VARCHAR(30) | NOT NULL, CHECK IN (13 events) | denormalized for list rendering |
| payload | JSONB | NOT NULL | recipient-facing summary |
| read_at | TIMESTAMPTZ | NULLABLE | set by mark-read |
| created_at | TIMESTAMPTZ | | delivery time |

**Indexes / constraints**

- `uq_notifications_event_recipient` UNIQUE `(outbox_event_id, user_id)` —
  the exactly-once guarantee across relay replays.
- `ix_notifications_unread` `(user_id)` WHERE `read_at IS NULL` — badge.
- `ix_notifications_owner_created` `(user_id, created_at DESC)` — list.
- CHECKs: `ck_notifications_event_type`.

**Semantics**

- Critical events' rows are written by the emitting service in-transaction
  (R4); everything else by the relay.
- `read_at` is the only mutable column (mark-read flows).

## Relationships

- `EventOutbox 1 — N Notification` (one event → one row per recipient)
- `Notification.user_id → User` (owner, RESTRICT)

## Migration notes (`0008_notifications_outbox_sse`)

- Two tables with the constraint set above; partial unique + partial
  indexes; JSONB payloads (postgres JSONB via `sa.dialects.postgresql.JSONB`).
- Reversible (`down_revision = 0007_loan_module`); drop tables on downgrade.
- No data migrations; tables start empty.
